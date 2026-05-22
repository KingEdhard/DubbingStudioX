import os
import re
import json
import subprocess
import time
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

def _ejecutar_ffmpeg_progreso(comando, duracion, progress_callback=None):
    print("\n⏳ Multiplexando...")
    proceso = subprocess.Popen(
        comando,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        encoding='utf-8',
        errors='replace',
        bufsize=1
    )
    usar_tqdm = (progress_callback is None)
    if usar_tqdm:
        pbar = tqdm(total=100, desc="Progreso", unit="%", ncols=80)
    else:
        pbar = None
    patron_tiempo = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")
    tiempo_previo = 0.0
    ultimo_porcentaje_cb = -1
    ultimo_tiempo_cb = 0.0
    frecuencia_cb = 0.2
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
                    if pbar:
                        incr = max(0.0, progreso - tiempo_previo)
                        if incr > 0:
                            pbar.update(incr)
                            tiempo_previo = progreso
                    if progress_callback:
                        ahora = time.time()
                        if abs(progreso - ultimo_porcentaje_cb) >= 1.0 or (ahora - ultimo_tiempo_cb) >= frecuencia_cb:
                            progress_callback(progreso)
                            ultimo_porcentaje_cb = progreso
                            ultimo_tiempo_cb = ahora
    except:
        pass
    ret = proceso.wait()
    if pbar:
        pbar.close()
    if progress_callback:
        progress_callback(100.0)
    return ret == 0, stderr_total

def _construir_comando_mux(archivo_video, srt_ingles, srt_espanol, formato_salida, ruta_salida, audio_doblaje=None):
    cmd = [FFMPEG_PATH, '-y']
    cmd.extend(['-i', archivo_video.replace('\\', '/')])
    num_inputs = 1

    # Audio doblado (opcional)
    idx_doblaje = None
    if audio_doblaje and os.path.exists(audio_doblaje):
        cmd.extend(['-i', audio_doblaje.replace('\\', '/')])
        idx_doblaje = num_inputs
        num_inputs += 1

    # Subtítulo inglés (opcional)
    idx_eng = None
    if srt_ingles and os.path.exists(srt_ingles):
        cmd.extend(['-i', srt_ingles.replace('\\', '/')])
        idx_eng = num_inputs
        num_inputs += 1

    # Subtítulo español (opcional)
    idx_esp = None
    tiene_esp = False
    if srt_espanol and os.path.exists(srt_espanol):
        cmd.extend(['-i', srt_espanol.replace('\\', '/')])
        idx_esp = num_inputs
        num_inputs += 1
        tiene_esp = True

    # Mapeos
    cmd.extend(['-map', '0:v'])  # video siempre
    if idx_doblaje is not None:
        cmd.extend(['-map', f'{idx_doblaje}:a'])
    cmd.extend(['-map', '0:a?'])  # pistas de audio originales
    cmd.extend(['-map', '0:s?'])  # CONSERVAR subtítulos originales (si los hay)

    if idx_eng is not None:
        cmd.extend(['-map', f'{idx_eng}:s'])
    if idx_esp is not None:
        cmd.extend(['-map', f'{idx_esp}:s'])

    # Códecs de video
    cmd.extend(['-c:v', 'copy'])

    # Códecs de audio: copiar todos, pero codificar el primer audio (doblaje) a AAC si existe
    if idx_doblaje is not None:
        cmd.extend(['-c:a', 'copy', '-c:a:0', 'aac', '-b:a:0', '192k'])
    else:
        cmd.extend(['-c:a', 'copy'])

    # Códecs de subtítulos solo si hay subtítulos nuevos (los originales se copian)
    if idx_eng is not None or idx_esp is not None:
        if formato_salida == 'mp4':
            cmd.extend(['-c:s', 'mov_text'])
        else:
            cmd.extend(['-c:s', 'srt'])

    cmd.extend(['-map_metadata', '0', '-map_chapters', '0'])
    cmd.append(ruta_salida.replace('\\', '/'))
    return cmd, tiene_esp

def incrustar_subtitulos(archivo_video, srt_ingles, srt_espanol, formato_salida=None, progress_callback=None, audio_doblaje=None):
    if not os.path.exists(archivo_video):
        print("✖ No se encontró el video original.")
        return None

    # Validar SRTs solo si se proporcionaron (None se acepta para modo solo doblaje)
    if srt_ingles is not None and not os.path.exists(srt_ingles):
        print("✖ No se proporcionó un subtítulo en inglés válido.")
        return None
    if srt_espanol is not None and not os.path.exists(srt_espanol):
        print("⚠ Subtítulo en español no disponible. Se incrustará solo el inglés.")
        srt_espanol = None

    # Seleccionar formato
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

    # Verificar compatibilidad de audio en MP4; si no compatible, cambiar a MKV automáticamente
    if extension == 'mp4':
        pistas = _obtener_pistas_audio(archivo_video)
        problematicas = _detectar_audio_incompatible_mp4(pistas)
        if problematicas:
            print("⚠ El archivo contiene codecs de audio no soportados en MP4. Se cambiará automáticamente a MKV para evitar errores.")
            extension = 'mkv'
            formato_salida = 'mkv'

    # Acortar nombre base si es muy largo
    dir_video = os.path.dirname(archivo_video)
    nombre_base = os.path.splitext(os.path.basename(archivo_video))[0]
    if len(nombre_base) > 100:
        nombre_base = nombre_base[:97] + "..."
        print(f"⚠ Nombre de archivo muy largo, se acortó a: {nombre_base}")
    carpeta_salida = os.path.join(dir_video, nombre_base + "_subtitulos_generados")
    os.makedirs(carpeta_salida, exist_ok=True)
    ruta_salida = os.path.join(carpeta_salida, nombre_base + "_doblado." + extension)
    duracion = _obtener_duracion(archivo_video)
    cmd, tiene_esp = _construir_comando_mux(archivo_video, srt_ingles, srt_espanol, extension, ruta_salida, audio_doblaje)
    if DEBUG:
        print("[DEBUG] Comando multiplexación:", ' '.join(cmd))
    exito, stderr = _ejecutar_ffmpeg_progreso(cmd, duracion, progress_callback=progress_callback)
    if not exito:
        if DEBUG:
            print("[DEBUG] stderr del intento principal:")
            print(stderr[-2000:])
        print("✖ Error en la multiplexación. Se conserva el original.")
        return None
    print(f"\n✔ Nuevo archivo creado: {ruta_salida}")
    if formato_salida is None:
        eliminar = input_validado("🗑 ¿Eliminar el video original? (s/n) [n]: ", ['s','n','si','no',''], defecto='n', map_alias={'si':'s','no':'n'})
        if eliminar == 's':
            try:
                os.remove(archivo_video)
                print("✔ Video original eliminado.")
            except Exception as e:
                print(f"⚠ No se pudo eliminar: {e}")
    return ruta_salida