import os
import re
import json
import subprocess
from tqdm import tqdm
from src.utils import FFMPEG_PATH, FFPROBE_PATH, DEBUG, input_validado

CODECS_AUDIO_MP4 = {'aac', 'mp3', 'ac3', 'eac3', 'alac'}

def _detectar_subs_incompatibles(archivo):
    cmd = [FFPROBE_PATH, '-v', 'error', '-select_streams', 's', '-show_entries', 'stream=index,codec_name', '-of', 'json', archivo.replace('\\', '/')]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        datos = json.loads(res.stdout) if res.stdout else {}
    except:
        return []
    incompatibles = []
    for s in datos.get('streams', []):
        idx = s.get('index')
        codec = (s.get('codec_name') or '').lower()
        if codec in ('hdmv_pgs_subtitle', 'pgs', 'dvd_subtitle', 'dvdsub', 'hdmv_pgs'):
            incompatibles.append((idx, codec))
    return incompatibles

def _detectar_audio_incompatible_mp4(pistas):
    problematicas = []
    for p in pistas:
        codec = p.get('codec', '').lower()
        if codec not in CODECS_AUDIO_MP4:
            problematicas.append(f"[{p['index']}] {p.get('idioma','und')} ({codec})")
    return problematicas

def _obtener_pistas_audio(archivo):
    cmd = [FFPROBE_PATH, '-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=index,codec_name:stream_tags=language', '-of', 'json', archivo.replace('\\', '/')]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        if res.returncode != 0 or not res.stdout.strip():
            return []
        datos = json.loads(res.stdout)
        streams = datos.get('streams', [])
        pistas = []
        for s in streams:
            pistas.append({
                'index': s.get('index'),
                'codec': s.get('codec_name', '???'),
                'idioma': (s.get('tags', {}) or {}).get('language', 'und')
            })
        return pistas
    except:
        return []

def _obtener_duracion(archivo):
    cmd = [FFPROBE_PATH, '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', archivo.replace('\\', '/')]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        if res.returncode != 0: return 0
        return float(json.loads(res.stdout).get('format', {}).get('duration', 0))
    except:
        return 0

def _ejecutar_ffmpeg_progreso(comando, duracion):
    print("\n⏳ Multiplexando...")
    proceso = subprocess.Popen(comando, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, encoding='utf-8', errors='replace')
    pbar = tqdm(total=100, desc="Progreso", unit="%", ncols=80)
    patron_tiempo = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")
    tiempo_previo = 0.0
    stderr_total = ""
    try:
        for linea in proceso.stdout:
            stderr_total += linea
            m = patron_tiempo.search(linea)
            if m:
                h, m_, s = map(float, m.groups())
                t_actual = h * 3600 + m_ * 60 + s
                if duracion > 0:
                    progreso = (t_actual / duracion) * 100.0
                    incr = max(0.0, progreso - tiempo_previo)
                    if incr > 0:
                        pbar.update(incr)
                        tiempo_previo = progreso
    except:
        pass
    ret = proceso.wait()
    pbar.close()
    return ret == 0, stderr_total

def _construir_comando_mux(archivo_video, srt_ingles, srt_espanol, formato_salida, omitir_subs=False):
    cmd = [FFMPEG_PATH, '-y']
    cmd.extend(['-i', archivo_video.replace('\\', '/')])
    cmd.extend(['-i', srt_ingles.replace('\\', '/')])
    tiene_espanol = srt_espanol is not None
    if tiene_espanol:
        cmd.extend(['-i', srt_espanol.replace('\\', '/')])

    # Mapear pistas originales
    cmd.extend(['-map', '0:v', '-map', '0:a?'])
    if not omitir_subs:
        cmd.extend(['-map', '0:s?'])
    cmd.extend(['-map', '0:t?', '-map', '0:d?'])

    # Copiar codecs
    cmd.extend(['-c:v', 'copy', '-c:a', 'copy', '-c:t', 'copy', '-c:d', 'copy'])
    if not omitir_subs:
        cmd.extend(['-c:s', 'copy'])

    # Subtítulos externos
    cmd.extend(['-map', '1'])
    if formato_salida == 'mp4':
        cmd.extend(['-c:s:0', 'mov_text'])
    else:
        cmd.extend(['-c:s:0', 'srt'])
    cmd.extend(['-metadata:s:s:0', 'language=eng', '-metadata:s:s:0', 'title=English'])
    cmd.extend(['-disposition:s:s:0', 'default'])

    if tiene_espanol:
        cmd.extend(['-map', '2'])
        if formato_salida == 'mp4':
            cmd.extend(['-c:s:1', 'mov_text'])
        else:
            cmd.extend(['-c:s:1', 'srt'])
        cmd.extend(['-metadata:s:s:1', 'language=spa', '-metadata:s:s:1', 'title=Español Latino'])
        cmd.extend(['-disposition:s:s:1', '0'])

    cmd.extend(['-map_metadata', '0', '-map_chapters', '0'])
    return cmd

def incrustar_subtitulos(archivo_video, srt_ingles, srt_espanol, formato_salida=None):
    """
    Si formato_salida se especifica ('mkv' o 'mp4'), lo usa directamente.
    Si es None, pregunta por consola (útil para main.py).
    """
    if not os.path.exists(archivo_video):
        print("✖ No se encontró el video original.")
        return None

    # Elegir formato
    if formato_salida is None:
        formato = input_validado(
            "¿Formato de salida? (1=MKV, 2=MP4) [MKV]: ",
            opciones_validas=['1','2','mkv','mp4',''],
            defecto='mkv',
            map_alias={'1':'mkv','2':'mp4'}
        )
        extension = formato if formato in ('mkv','mp4') else 'mkv'
    else:
        extension = formato_salida

    base = os.path.splitext(archivo_video)[0]
    ruta_salida = f"{base}_subtitulado.{extension}"
    duracion = _obtener_duracion(archivo_video)

    # Primer intento
    omitir_subs = False
    cmd = _construir_comando_mux(archivo_video, srt_ingles, srt_espanol, extension, omitir_subs)
    exito, stderr = _ejecutar_ffmpeg_progreso(cmd, duracion)

    if not exito:
        if DEBUG:
            print("[DEBUG] stderr de primer intento:")
            print(stderr[-2000:])
        # Fallback automático (solo si hay subtítulos originales que puedan causar conflicto)
        if any(tag in (stderr or "").lower() for tag in ('mov_text', 'subtitle', 'could not write header', 'error writing trailer')):
            print("\n⚠ Error de empaquetado. Reintentando sin subtítulos originales...")
            omitir_subs = True
            if extension == 'mp4':
                extension = 'mkv'
                ruta_salida = f"{base}_subtitulado.{extension}"
            cmd2 = _construir_comando_mux(archivo_video, srt_ingles, srt_espanol, extension, omitir_subs)
            cmd2.append(ruta_salida)
            exito2, stderr2 = _ejecutar_ffmpeg_progreso(cmd2, duracion)
            if not exito2:
                print("✖ El reintento también falló. Los subtítulos no se incrustaron.")
                if DEBUG:
                    print("[DEBUG] stderr del reintento:")
                    print(stderr2[-2000:])
                return None
            else:
                print("✔ Multiplexación completada en el reintento.")
        else:
            print("✖ Error en la multiplexación. Se conserva el original.")
            return None

    print(f"\n✔ Nuevo archivo creado: {ruta_salida}")
    # Preguntar si eliminar original (solo si se ejecuta por consola)
    if formato_salida is None:
        eliminar = input_validado("🗑 ¿Eliminar el video original? (s/n) [n]: ", ['s','n','si','no',''], defecto='n', map_alias={'si':'s','no':'n'})
        if eliminar == 's':
            try:
                os.remove(archivo_video)
                print("✔ Video original eliminado.")
            except Exception as e:
                print(f"⚠ No se pudo eliminar: {e}")
    return ruta_salida
