import os
import sys
import time
import threading
import shutil
import tkinter as tk
from tkinter import messagebox, filedialog, scrolledtext

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT_DIR)

from src.components.extraccion import extraer_audio_mejorado
from src.components.transcripcion import transcribir_audio
from src.components.traduccion import traducir_srt
from src.components.muxer import incrustar_subtitulos

class VocesClarasApp:
    def __init__(self, root):
        self.root = root
        self.root.title("VocesClaras-STT")
        self.root.geometry("700x600")
        self.root.resizable(True, True)
        self.archivos = []
        self.procesando = False
        self._start_global = None
        self._start_tarea = None
        self.formato_salida = 'mkv'
        self._crear_widgets()

    def _crear_widgets(self):
        frame_top = tk.Frame(self.root, padx=10, pady=10)
        frame_top.pack(fill=tk.X)
        btn_sel = tk.Button(frame_top, text="📂 Seleccionar vídeos", command=self.seleccionar_videos, height=2)
        btn_sel.pack(side=tk.LEFT, padx=5)
        self.lbl_count = tk.Label(frame_top, text="0 archivos seleccionados")
        self.lbl_count.pack(side=tk.LEFT, padx=20)

        formato_frame = tk.Frame(self.root, padx=10, pady=5)
        formato_frame.pack(fill=tk.X)
        tk.Label(formato_frame, text="Formato de salida:").pack(side=tk.LEFT)
        self.formato_var = tk.StringVar(value='mkv')
        tk.Radiobutton(formato_frame, text="MKV", variable=self.formato_var, value='mkv').pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(formato_frame, text="MP4", variable=self.formato_var, value='mp4').pack(side=tk.LEFT, padx=5)

        frame_lista = tk.Frame(self.root, padx=10)
        frame_lista.pack(fill=tk.BOTH, expand=True)
        self.lista_archivos = tk.Listbox(frame_lista, height=6)
        self.lista_archivos.pack(fill=tk.BOTH, expand=True)

        frame_prog_global = tk.Frame(self.root, padx=10, pady=5)
        frame_prog_global.pack(fill=tk.X)
        tk.Label(frame_prog_global, text="Progreso global:").pack(anchor=tk.W)
        self.barra_global = tk.Canvas(frame_prog_global, height=20, bg='white')
        self.barra_global.pack(fill=tk.X)
        self.rect_global = self.barra_global.create_rectangle(0, 0, 0, 20, fill='#4CAF50')
        self.lbl_eta_global = tk.Label(frame_prog_global, text="", fg="gray")
        self.lbl_eta_global.pack(anchor=tk.E)

        frame_prog_tarea = tk.Frame(self.root, padx=10, pady=5)
        frame_prog_tarea.pack(fill=tk.X)
        self.lbl_tarea = tk.Label(frame_prog_tarea, text="Tarea actual: ...")
        self.lbl_tarea.pack(anchor=tk.W)
        self.barra_tarea = tk.Canvas(frame_prog_tarea, height=20, bg='white')
        self.barra_tarea.pack(fill=tk.X)
        self.rect_tarea = self.barra_tarea.create_rectangle(0, 0, 0, 20, fill='#2196F3')
        self.lbl_eta_tarea = tk.Label(frame_prog_tarea, text="", fg="gray")
        self.lbl_eta_tarea.pack(anchor=tk.E)

        frame_botones = tk.Frame(self.root, padx=10, pady=10)
        frame_botones.pack(fill=tk.X)
        self.btn_iniciar = tk.Button(frame_botones, text="▶ Iniciar procesamiento", command=self.iniciar_procesamiento, height=2, bg='#4CAF50', fg='white')
        self.btn_iniciar.pack(side=tk.LEFT, padx=5)
        self.btn_detener = tk.Button(frame_botones, text="⏹ Detener", command=self.detener_procesamiento, state=tk.DISABLED, height=2, bg='#f44336', fg='white')
        self.btn_detener.pack(side=tk.LEFT, padx=5)

        frame_log = tk.Frame(self.root, padx=10, pady=5)
        frame_log.pack(fill=tk.BOTH, expand=True)
        tk.Label(frame_log, text="Registro de actividad:").pack(anchor=tk.W)
        self.log = scrolledtext.ScrolledText(frame_log, height=8, state=tk.DISABLED)
        self.log.pack(fill=tk.BOTH, expand=True)

    def log_message(self, msg):
        print(msg)
        self.root.after(0, self._insert_log, msg)

    def _insert_log(self, msg):
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def seleccionar_videos(self):
        filetypes = [
            ("Archivos de video", "*.mkv *.mp4 *.avi *.mov *.wmv *.flv *.webm *.ts *.m2ts *.mts *.m4v *.mpg *.mpeg *.vob"),
            ("Todos los archivos", "*.*")
        ]
        archivos = filedialog.askopenfilenames(title="Selecciona uno o varios vídeos", filetypes=filetypes)
        if archivos:
            self.archivos = list(archivos)
            self.lista_archivos.delete(0, tk.END)
            for a in self.archivos:
                self.lista_archivos.insert(tk.END, os.path.basename(a))
            self.lbl_count.config(text=f"{len(self.archivos)} archivos seleccionados")
            self.log_message(f"Seleccionados {len(self.archivos)} vídeos.")

    def _formato_tiempo(self, segundos):
        if segundos < 0:
            return "calculando..."
        m, s = divmod(int(segundos), 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}h {m}m"
        return f"{m}m {s}s"

    def actualizar_barra_global(self, porcentaje):
        ancho = self.barra_global.winfo_width()
        self.barra_global.coords(self.rect_global, 0, 0, ancho * porcentaje / 100, 20)
        if self._start_global and porcentaje > 0:
            elapsed = time.time() - self._start_global
            restante = (elapsed / porcentaje) * (100 - porcentaje)
            self.lbl_eta_global.config(text=f"Tiempo restante: {self._formato_tiempo(restante)}")
        self.root.update_idletasks()

    def actualizar_barra_tarea(self, porcentaje, tarea=""):
        ancho = self.barra_tarea.winfo_width()
        self.barra_tarea.coords(self.rect_tarea, 0, 0, ancho * porcentaje / 100, 20)
        if tarea:
            self.lbl_tarea.config(text=f"Tarea actual: {tarea}")
        if self._start_tarea and porcentaje > 0:
            elapsed = time.time() - self._start_tarea
            restante = (elapsed / porcentaje) * (100 - porcentaje)
            self.lbl_eta_tarea.config(text=f"Tiempo restante: {self._formato_tiempo(restante)}")
        else:
            self.lbl_eta_tarea.config(text="")
        self.root.update_idletasks()

    def iniciar_procesamiento(self):
        if not self.archivos:
            messagebox.showwarning("Aviso", "Selecciona al menos un vídeo.")
            return
        if self.procesando:
            return
        self.procesando = True
        self.btn_iniciar.config(state=tk.DISABLED)
        self.btn_detener.config(state=tk.NORMAL)
        self._start_global = time.time()
        self.formato_salida = self.formato_var.get()
        self.log_message(f"Formato de salida seleccionado: {self.formato_salida.upper()}")
        t = threading.Thread(target=self.procesar_videos, daemon=True)
        t.start()

    def detener_procesamiento(self):
        self.procesando = False
        self.log_message("Detenido por el usuario.")

    def extraccion_progress(self, porcentaje):
        self.root.after(0, self.actualizar_barra_tarea, porcentaje, "Extrayendo audio...")

    def transcripcion_progress(self, current, total):
        if total:
            porcentaje = (current / total) * 100
            msg = f"Transcribiendo... ({current}/{total} segmentos)"
            if current == total:
                self.log_message(f"📝 Total de segmentos transcritos: {total}")
        else:
            fake = min(current * 0.5, 95)
            msg = f"Transcribiendo... ({current} segmentos, total por determinar)"
            porcentaje = fake
        self.root.after(0, self.actualizar_barra_tarea, porcentaje, msg)

    def traduccion_progress(self, current, total):
        porcentaje = (current / total) * 100
        self.root.after(0, self.actualizar_barra_tarea, porcentaje, f"Traduciendo... ({current}/{total})")

    def muxer_progress(self, porcentaje):
        self.root.after(0, self.actualizar_barra_tarea, porcentaje, "Multiplexando...")

    def procesar_videos(self):
        total_videos = len(self.archivos)
        self.root.after(0, self.log_message, f"Iniciando procesamiento de {total_videos} vídeos...")

        etapas_por_video = 4
        peso_por_etapa = 100.0 / (total_videos * etapas_por_video)

        for i, video in enumerate(self.archivos, 1):
            if not self.procesando:
                break

            # Protección anti-anidamiento
            nombre_base_video = os.path.splitext(os.path.basename(video))[0]
            if nombre_base_video.endswith("_subtitulado"):
                self.root.after(0, self.log_message, f"⏭ Omitido (ya es un archivo de salida): {os.path.basename(video)}")
                continue

            nombre = os.path.basename(video)
            self.root.after(0, self.log_message, f"\n🎬 Vídeo {i}/{total_videos}: {nombre}")

            # Crear carpeta de salida desde el principio (junto al video original)
            dir_salida_def = os.path.join(os.path.dirname(video),
                                          nombre_base_video + "_subtitulos_generados")
            os.makedirs(dir_salida_def, exist_ok=True)

            progreso_base = (i - 1) * etapas_por_video * peso_por_etapa
            self.root.after(0, self.actualizar_barra_global, progreso_base)

            # 1. Extracción
            self._start_tarea = time.time()
            self.root.after(0, self.actualizar_barra_tarea, 0, "Extrayendo audio...")
            try:
                wav = extraer_audio_mejorado(video, progress_callback=self.extraccion_progress)
                if not wav:
                    self.root.after(0, self.log_message, "⚠ Fallo en extracción de audio.")
                    continue
            except Exception as e:
                self.root.after(0, self.log_message, f"❌ Error en extracción: {e}")
                continue
            self.root.after(0, self.actualizar_barra_global, progreso_base + peso_por_etapa)

            # 2. Transcripción
            self._start_tarea = time.time()
            self.root.after(0, self.actualizar_barra_tarea, 0, "Transcribiendo...")
            try:
                srt_ing = transcribir_audio(wav, progress_callback=self.transcripcion_progress)
                if not srt_ing:
                    self.root.after(0, self.log_message, "⚠ Fallo en transcripción.")
                    if os.path.exists(wav): os.remove(wav)
                    continue
                # Copiar SRT inglés a la carpeta definitiva inmediatamente
                srt_ing_final = os.path.join(dir_salida_def, os.path.basename(srt_ing))
                shutil.copy2(srt_ing, srt_ing_final)
                self.root.after(0, self.log_message, f"📄 Subtítulo inglés copiado: {srt_ing_final}")
            except Exception as e:
                self.root.after(0, self.log_message, f"❌ Error en transcripción: {e}")
                if os.path.exists(wav): os.remove(wav)
                continue
            self.root.after(0, self.actualizar_barra_global, progreso_base + 2 * peso_por_etapa)

            # 3. Traducción
            self._start_tarea = time.time()
            self.root.after(0, self.actualizar_barra_tarea, 0, "Traduciendo...")
            srt_esp_final = None
            try:
                srt_esp = traducir_srt(srt_ing, progress_callback=self.traduccion_progress)
                if srt_esp:
                    srt_esp_final = os.path.join(dir_salida_def, os.path.basename(srt_esp))
                    shutil.copy2(srt_esp, srt_esp_final)
                    self.root.after(0, self.log_message, f"📄 Subtítulo español copiado: {srt_esp_final}")
                else:
                    self.root.after(0, self.log_message, "⚠ Fallo en traducción. Se incrustará solo inglés.")
            except Exception as e:
                self.root.after(0, self.log_message, f"❌ Error en traducción: {e}")
                srt_esp = None
            self.root.after(0, self.actualizar_barra_global, progreso_base + 3 * peso_por_etapa)

            # 4. Multiplexado (usa las copias que ya están en dir_salida_def)
            self._start_tarea = time.time()
            self.root.after(0, self.actualizar_barra_tarea, 0, "Multiplexando...")
            try:
                ruta_final = incrustar_subtitulos(video, srt_ing_final, srt_esp_final,
                                                  formato_salida=self.formato_salida,
                                                  progress_callback=self.muxer_progress)
                if ruta_final:
                    self.root.after(0, self.log_message, f"✔ Completado: {ruta_final}")
                    self.root.after(0, self._preguntar_eliminar_original, video)
                else:
                    self.root.after(0, self.log_message, "⚠ No se pudo empaquetar. Conserva los subtítulos sueltos.")
            except Exception as e:
                self.root.after(0, self.log_message, f"❌ Error en multiplexación: {e}")
            self.root.after(0, self.actualizar_barra_global, progreso_base + 4 * peso_por_etapa)

            if os.path.exists(wav):
                os.remove(wav)
                self.root.after(0, self.log_message, "🧹 Temporal eliminado.")

        self.root.after(0, self.actualizar_barra_global, 100)
        self.root.after(0, self.lbl_eta_global.config, {"text": "Completado"})
        self.root.after(0, self.log_message, "\n✅ Procesamiento completado.")
        self.root.after(0, self.btn_iniciar.config, {"state": tk.NORMAL})
        self.root.after(0, self.btn_detener.config, {"state": tk.DISABLED})
        self.procesando = False

    def _preguntar_eliminar_original(self, video):
        """Diálogo desde el hilo principal."""
        if messagebox.askyesno("Eliminar original", "¿Deseas eliminar el video original?"):
            try:
                os.remove(video)
                self.log_message("✔ Video original eliminado.")
            except Exception as e:
                self.log_message(f"⚠ No se pudo eliminar: {e}")

def ejecutar_interfaz():
    root = tk.Tk()
    app = VocesClarasApp(root)
    root.mainloop()

if __name__ == "__main__":
    ejecutar_interfaz()
