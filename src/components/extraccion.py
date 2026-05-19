import subprocess
import json
import os
import re
import time
import glob
from src.utils import FFMPEG_PATH, FFPROBE_PATH, DEBUG, input_validado

def obtener_pistas_audio(archivo):
    """Devuelve una lista de pistas de audio con (index, idioma, codec, canales)."""
    cmd = [
        FFPROBE_PATH, '-v', 'error',
        '-select_streams', 'a',
        '-show_entries', 'stream=index,codec_name,channels,channel_layout:stream_tags=language',
        '-of', 'json', archivo.replace('\\', '/')
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        if res.returncode != 0 or not res.stdout.strip():
            return []
        datos = json.loads(res.stdout)
        streams = datos.get('streams', [])
        pistas = []
        for s in streams:
            idx = s.get('index')
            codec = s.get('codec_name', '???')
            canales = s.get('channels', 0)
            tags = s.get('tags', {})
            idioma = tags.get('language', 'und').lower()
            pistas.append({
                'index': idx,
                'idioma': idioma,
                'codec': codec,
                'canales': canales,
                'layout': s.get('channel_layout', '')
            })
        return pistas
    except Exception as e:
        if DEBUG:
            print(f"[DEBUG] Error obteniendo pistas: {e}")
        return []

def elegir_pista_ingles(pistas):
    """Selecciona la primera pista en inglés; si no hay, pregunta al usuario."""
    pistas_eng = [p for p in pistas if p['idioma'] in ('eng', 'en', 'english', 'en-us', 'en-gb')]
    if pistas_eng:
        elegida = pistas_eng[0]
        print(f"🔊 Pista de audio en inglés detectada: índice {elegida['index']} ({elegida['codec']}, {elegida['canales']}ch)")
        return elegida['index']
    else:
        print("\n⚠ No se detectó pista en inglés. Pistas disponibles:")
        for p in pistas:
            print(f"   [{p['index']}] Idioma: {p['idioma']}, {p['codec']}, {p['canales']}ch")
        opciones = [str(p['index']) for p in pistas]
        indice = input_validado(
            "👉 Elige el índice de la pista a usar: ",
            opciones_validas=opciones,
            defecto=opciones[0] if opciones else None
        )
        return int(indice)

def _obtener_duracion_video(archivo):
    """Devuelve la duración del video en segundos usando ffprobe."""
    cmd = [
        FFPROBE_PATH, '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'json', archivo.replace('\\', '/')
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        if res.returncode == 0 and res.stdout.strip():
            datos = json.loads(res.stdout)
            return float(datos.get('format', {}).get('duration', 0))
    except:
        pass
    return 0.0

def _limpiar_carpeta_salida(carpeta):
    """Elimina archivos .wav y .srt existentes en la carpeta de salida."""
    if not os.path.isdir(carpeta):
        return
    patrones = ['*.wav', '*.srt']
    for patron in patrones:
        for archivo in glob.glob(os.path.join(carpeta, patron)):
            try:
                os.remove(archivo)
                if DEBUG:
                    print(f"[DEBUG] Eliminado archivo previo: {archivo}")
            except Exception as e:
                print(f"⚠ No se pudo eliminar {archivo}: {e}")

def extraer_audio_mejorado(archivo_video, progress_callback=None):
    """
    Extrae la pista de audio en inglés, aplica realce de diálogos y devuelve
    la ruta del WAV temporal listo para Whisper.
    Los archivos se guardan en una subcarpeta <nombre_video>_subtitulos_generados/
    Se eliminan automáticamente .wav y .srt de ejecuciones anteriores.
    """
    if not os.path.exists(archivo_video):
        print(f"✖ Archivo no encontrado: {archivo_video}")
        return None

    print(f"\n🎬 Analizando audio de: {os.path.basename(archivo_video)}")
    pistas = obtener_pistas_audio(archivo_video)
    if not pistas:
        print("✖ No se encontraron pistas de audio. Proceso cancelado.")
        return None

    idx_audio = elegir_pista_ingles(pistas)

    # Crear carpeta de salida y limpiar restos
    dir_video = os.path.dirname(archivo_video)
    nombre_base = os.path.splitext(os.path.basename(archivo_video))[0]
    carpeta_salida = os.path.join(dir_video, nombre_base + "_subtitulos_generados")
    os.makedirs(carpeta_salida, exist_ok=True)
    _limpiar_carpeta_salida(carpeta_salida)   # <-- ¡limpieza!

    # WAV dentro de la carpeta
    wav_temp = os.path.join(carpeta_salida, nombre_base + "_dialogos_mejorados.wav")
    if os.path.exists(wav_temp):
        os.remove(wav_temp)

    # Filtro de ganancia en diálogos
    filtro = "dynaudnorm=f=150:g=31:p=0.95,firequalizer=gain=if(gte(f\\,400)\\,if(lte(f\\,4000)\\,2\\,0)\\,0)"
    
    cmd = [
        FFMPEG_PATH, '-y',
        '-i', archivo_video.replace('\\', '/'),
        '-map', f'0:{idx_audio}',
        '-af', filtro,
        '-ac', '1',
        '-ar', '16000',
        '-c:a', 'pcm_s16le',
        wav_temp.replace('\\', '/')
    ]
    
    print("\n🔥 Aplicando filtro de ganancia de diálogos...")
    if DEBUG:
        print(f"[DEBUG] Comando: {' '.join(cmd)}")

    duracion = _obtener_duracion_video(archivo_video)
    if duracion > 0:
        print(f"⏱ Duración detectada: {duracion:.1f} segundos")
    else:
        print("⚠ No se pudo determinar la duración del video. La barra de progreso no estará disponible.")

    try:
        proceso = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            encoding='utf-8',
            errors='replace'
        )

        patron_tiempo = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")
        ultimo_porcentaje = -1
        ultimo_tiempo_cb = 0.0
        frecuencia_cb = 0.2

        for linea in proceso.stdout:
            if progress_callback and duracion > 0:
                m = patron_tiempo.search(linea)
                if m:
                    h, m_, s = map(float, m.groups())
                    t_actual = h * 3600 + m_ * 60 + s
                    porcentaje = (t_actual / duracion) * 100.0
                    ahora = time.time()
                    if abs(porcentaje - ultimo_porcentaje) >= 1.0 or (ahora - ultimo_tiempo_cb) >= frecuencia_cb:
                        progress_callback(porcentaje)
                        ultimo_porcentaje = porcentaje
                        ultimo_tiempo_cb = ahora

        retorno = proceso.wait()
        if retorno == 0:
            if progress_callback:
                progress_callback(100.0)
            print(f"✔ Audio extraído y mejorado: {wav_temp}")
            return wav_temp
        else:
            print(f"✖ Error al extraer audio. Código: {retorno}")
            if DEBUG:
                print("[DEBUG] No se pudo capturar salida de error porque ya fue leída línea a línea.")
            return None

    except Exception as e:
        print(f"✖ Excepción ejecutando ffmpeg: {e}")
        return None
