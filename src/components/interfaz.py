import os
import sys
import time
import threading
import tkinter as tk
from tkinter import messagebox, filedialog, scrolledtext, simpledialog

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
        self.formato_salida = 'mkv'  # valor por defecto
        self._crear_widgets()

    def _crear_widgets(self):
        frame_top = tk.Frame(self.root, padx=10, pady=10)
        frame_top.pack(fill=tk.X)
        btn_sel = tk.Button(frame_top, text="📂 Seleccionar vídeos", command=self.seleccionar_videos, height=2)
        btn_sel.pack(side=tk.LEFT, padx=5)
        self.lbl_count = tk.Label(frame_top, text="0 archivos seleccionados")
        self.lbl_count.pack(side=tk.LEFT, padx=20)

        # Selector de formato de salida
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
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)
        self.root.update_idletasks()

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
        self.formato_salida = self.formato_var.get()  # leer formato antes de empezar
        t = threading.Thread(target=self.procesar_videos, daemon=True)
        t.start()

    def detener_procesamiento(self):
        self.procesando = False
        self.log_message("Detenido por el usuario.")

    def procesar_videos(self):
        total = len(self.archivos)
        self.log_message(f"Iniciando procesamiento de {total} vídeos...")
        for i, video in enumerate(self.archivos, 1):
            if not self.procesando:
                break
            self.log_message(f"\n🎬 Vídeo {i}/{total}: {os.path.basename(video)}")
            self.actualizar_barra_global((i-1)/total*100)

            self._start_tarea = time.time()
            self.actualizar_barra_tarea(0, "Extrayendo audio...")
            try:
                wav = extraer_audio_mejorado(video)
                if not wav:
                    self.log_message("⚠ Fallo en extracción de audio.")
                    continue
            except Exception as e:
                self.log_message(f"❌ Error en extracción: {e}")
                continue
            self.actualizar_barra_tarea(25, "Audio extraído")

            self._start_tarea = time.time()
            self.actualizar_barra_tarea(0, "Transcribiendo...")
            try:
                srt_ing = transcribir_audio(wav)
                if not srt_ing:
                    self.log_message("⚠ Fallo en transcripción.")
                    if os.path.exists(wav): os.remove(wav)
                    continue
            except Exception as e:
                self.log_message(f"❌ Error en transcripción: {e}")
                if os.path.exists(wav): os.remove(wav)
                continue
            self.actualizar_barra_tarea(50, "Transcripción completada")

            self._start_tarea = time.time()
            self.actualizar_barra_tarea(0, "Traduciendo...")
            try:
                srt_esp = traducir_srt(srt_ing)
                if not srt_esp:
                    self.log_message("⚠ Fallo en traducción. Se incrustará solo inglés.")
            except Exception as e:
                self.log_message(f"❌ Error en traducción: {e}")
                srt_esp = None
            self.actualizar_barra_tarea(75, "Traducción completada" if srt_esp else "Sin traducción")

            self._start_tarea = time.time()
            self.actualizar_barra_tarea(0, "Multiplexando...")
            try:
                ruta_final = incrustar_subtitulos(video, srt_ing, srt_esp, formato_salida=self.formato_salida)
                if ruta_final:
                    self.log_message(f"✔ Completado: {ruta_final}")
                    # Preguntar si eliminar original (ventana emergente)
                    if messagebox.askyesno("Eliminar original", "¿Deseas eliminar el video original?"):
                        try:
                            os.remove(video)
                            self.log_message("✔ Video original eliminado.")
                        except Exception as e:
                            self.log_message(f"⚠ No se pudo eliminar: {e}")
                else:
                    self.log_message("⚠ No se pudo empaquetar. Conserva los subtítulos sueltos.")
            except Exception as e:
                self.log_message(f"❌ Error en multiplexación: {e}")
            self.actualizar_barra_tarea(100, "Finalizado")

            if os.path.exists(wav):
                os.remove(wav)
                self.log_message("🧹 Temporal eliminado.")

        self.actualizar_barra_global(100)
        self.lbl_eta_global.config(text="Completado")
        self.log_message("\n✅ Procesamiento completado.")
        self.btn_iniciar.config(state=tk.NORMAL)
        self.btn_detener.config(state=tk.DISABLED)
        self.procesando = False

def ejecutar_interfaz():
    root = tk.Tk()
    app = VocesClarasApp(root)
    root.mainloop()

if __name__ == "__main__":
    ejecutar_interfaz()
