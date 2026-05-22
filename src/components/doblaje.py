import json
import os
import torch
from TTS.api import TTS
from pydub import AudioSegment
from tqdm import tqdm

def generar_doblaje(json_segmentos_es, audio_original, salida_wav, device="cuda"):
    """
    Genera una pista de audio doblada a partir de segmentos traducidos y clona la voz.
    Ajusta la duración de cada segmento para que encaje en el slot original.
    """
    with open(json_segmentos_es, 'r', encoding='utf-8') as f:
        segments = json.load(f)

    # Inicializar TTS (XTTS-v2 multilingüe) en el dispositivo elegido
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)

    # Extraer muestra de voz del audio original (primeros 12-15 segundos)
    ref_audio = AudioSegment.from_file(audio_original)
    ref_audio = ref_audio.set_channels(1).set_frame_rate(22050)
    speaker_wav = "temp_speaker.wav"
    ref_audio[:12000].export(speaker_wav, format="wav")

    combinado = AudioSegment.empty()
    print(f"\n🎙️ Generando doblaje por segmentos ({len(segments)} frases)...")
    for i, seg in enumerate(tqdm(segments, desc="Sintetizando voz")):
        texto = seg["text"]
        inicio = seg["start"]
        fin = seg["end"]
        duracion_original_ms = (fin - inicio) * 1000

        temp_wav = f"temp_seg_{i}.wav"
        tts.tts_to_file(
            text=texto,
            speaker_wav=speaker_wav,
            language="es",
            file_path=temp_wav
        )
        snippet = AudioSegment.from_file(temp_wav)

        # Ajuste de duración para sincronización visual
        if len(snippet) > duracion_original_ms:
            factor = len(snippet) / duracion_original_ms
            if factor <= 1.2:
                snippet = snippet.speedup(playback_speed=factor)
            else:
                # Si la diferencia es muy grande, recortamos (no aceleramos demasiado)
                snippet = snippet[:duracion_original_ms]
        elif len(snippet) < duracion_original_ms:
            silencio = AudioSegment.silent(duration=duracion_original_ms - len(snippet))
            snippet += silencio

        combinado += snippet
        os.remove(temp_wav)

    os.remove(speaker_wav)
    combinado.export(salida_wav, format="wav")
    print(f"✔ Audio doblado guardado en: {salida_wav}")
    return salida_wav
