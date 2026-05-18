# 🎙️ VocesClaras-STT – Transcripción y subtitulado automático con realce de diálogos

**VocesClaras‑STT** toma uno o varios vídeos, extrae la pista de audio en inglés, **realza las voces** (eliminando ruido y amplificando frecuencias vocales), y luego genera **subtítulos precisos en inglés** con inteligencia artificial.  
Posteriormente, **traduce los subtítulos al español latino** y, opcionalmente, **incrusta ambos subtítulos** en un nuevo archivo de video, conservando todas las pistas originales.

Todo el proceso se ejecuta **100 % en local, sin necesidad de GPU ni conexión a internet** (salvo la primera descarga de modelos).  
Está diseñado para funcionar de forma eficiente en **procesadores Intel básicos** (Intel Inside, Celeron, Pentium) usando precisión `float32`.

---

## ⚙️ Instalación automática (recomendada)

Después de clonar o descargar el proyecto, ejecuta un solo comando según tu sistema:

- **Windows (PowerShell):** `.\setup.ps1`
- **Windows (Git Bash), Linux o macOS:** `chmod +x setup.sh && ./setup.sh`

Estos scripts crearán el entorno virtual, instalarán las dependencias y descargarán automáticamente `ffmpeg.exe` y `ffprobe.exe` en la carpeta `bin/`.

🔽 Para obtener el proyecto haz clic en el botón verde **Code** en GitHub y selecciona **Download ZIP** o copia la URL para clonarlo con `git clone`.

---

## 🔧 Instalación manual

1. Crea un entorno virtual: `python -m venv venv`
2. Actívalo:
   - Windows (PowerShell): `venv\Scripts\Activate.ps1`
   - Windows (Git Bash): `source venv/Scripts/activate`
   - Linux/macOS: `source venv/bin/activate`
3. Instala las dependencias: `pip install -r requirements.txt`
4. Descarga `ffmpeg.exe` y `ffprobe.exe` de [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) (versión *release essentials*) y colócalos en la carpeta `bin/`.

---

## 🔄 Flujo de trabajo

1. **Selección de archivos** – Diálogo gráfico que permite elegir múltiples vídeos.
2. **Extracción y mejora de audio** – Detecta la pista en inglés, aplica el filtro de realce vocal y la convierte a WAV mono 16 kHz.
3. **Transcripción en inglés** – `faster‑whisper` (modelo `medium` o `large‑v3`) genera un archivo `.srt` con marcas de tiempo.
4. **Traducción al español** – `Helsinki‑NLP/opus‑mt‑en‑es` traduce cada segmento, conservando las marcas de tiempo.
5. **Incrustación** – `FFmpeg` multiplexa los subtítulos en un nuevo vídeo (MKV o MP4 elegible desde la interfaz gráfica).
6. **Limpieza** – Se eliminan los archivos temporales (WAV) y se pregunta si se desea borrar el vídeo original.

---

## 🔊 Mejoras en el audio

- Normalización dinámica (`dynaudnorm=f=150:g=31:p=0.95`)
- Realce de voces (+2 dB entre 400‑4000 Hz con `firequalizer`)
- Conversión a mono 16 kHz para máxima compatibilidad con Whisper

---

## 📦 Conservación de datos originales

- Vídeo copiado sin recodificar (`-c:v copy`)
- Pistas de audio y subtítulos originales conservados con su códec original
- Subtítulos originales copiados (MKV) u omitidos si son incompatibles (MP4)
- Metadatos globales y capítulos heredados del archivo fuente

---

## 🛡️ Manejo de errores

- Si el formato elegido falla (códecs incompatibles con MP4), se reintenta automáticamente en MKV.
- Subtítulos gráficos (PGS/DVD) detectados y omitidos si causan conflictos.
- Fallo en la multiplexación → se reintenta automáticamente omitiendo subtítulos originales y cambiando a MKV si era MP4.
- En procesamiento por lotes, un error en un vídeo no detiene el resto de la cola.

---

## 🎛️ Personalización

- **Ganancia de diálogos:** Editar el valor `gain=2` en `extraccion.py` (línea del filtro `firequalizer`). Subir a `3` o `4` para voces más marcadas.
- **Modelo de transcripción:** Cambiar la variable `modelo` en `transcripcion.py` a `"large-v3"` para máxima precisión (el doble de tiempo).
- **Post‑edición de la traducción:** Añadir un diccionario de localización en `traduccion.py` para adaptar modismos ibéricos a latinos (ligero y sin impacto en rendimiento).
- **Precisión numérica:** Para CPUs Intel básicas sin AVX-512 VNNI se usa `float32` por defecto, evitando la sobrecarga del modo `int8`.

---

## 🔧 Requisitos

- **FFmpeg y FFprobe** (se descargan automáticamente con el script de instalación)
- **Python 3.8+** con `faster-whisper`, `transformers`, `sentencepiece`, `torch`, `tqdm`, `numpy`
- **Windows** (Linux/macOS adaptable)

---

## ▶️ Cómo ejecutar

```bash
source venv/Scripts/activate   # activar entorno virtual
python src/components/interfaz.py   # lanzar la interfaz gráfica
```

También puedes usar el modo texto con `python main.py`.

---

Repositorio creado por **[KingEdhard](https://github.com/KingEdhard)**  
*"Voces claras, subtítulos perfectos"*
