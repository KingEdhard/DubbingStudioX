# 🎬 DubbingStudioX — Doblaje automático con IA en la nube

Evolución de **SubtitleStudioX**. Ahora, además de subtitular con precisión milimétrica, clona la voz original y genera un doblaje completo a español latino, todo ejecutado en Google Colab con GPU gratuita.

## 🔄 Flujo completo
- 🎵 Extracción y mejora de voz (VocesClaras-STT)
- 🧠 Transcripción con WhisperX Large-v3 + alineación fonética Wav2Vec2
- 🌎 Traducción a español latino (Helsinki-NLP/opus-mt-en-es)
- 🎙️ Síntesis de voz clonada con XTTS-v2 (GPU)
- ⏱️ Ajuste automático de duración para sincronía visual
- 🎬 Multiplexado final con FFmpeg (vídeo original + audio doblado + pistas originales + subtítulos)

## 🚀 Uso en Google Colab
1. Abre el notebook `DubbingStudioX_Colab.ipynb` desde GitHub en Colab.
2. Ejecuta la Celda 1 (instalación).
3. Ejecuta la Celda 2, elige el modo de trabajo y sube tus vídeos.

El cuaderno permite elegir entre **procesar desde cero** o **solo doblaje** si ya tienes los segmentos traducidos.

## 🛠️ Requisitos locales (opcional)
El código base puede ejecutarse en local (CPU), pero la síntesis de voz con clonación es mucho más rápida en GPU (Colab). Ver `requirements.txt` para las dependencias.

## 📝 Licencia
MIT – Libre uso, modificación y distribución.

---

Creado por [**KingEdhard**](https://github.com/KingEdhard) sobre la base de SubtitleStudio y SubtitleStudioX.
