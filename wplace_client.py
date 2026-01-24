import tkinter as tk
from tkinter import messagebox, ttk, simpledialog, filedialog
from PIL import Image, ImageTk, ImageOps
from PIL.PngImagePlugin import PngInfo
import requests
from io import BytesIO
import threading
import re
import os
import json  # <--- NUEVO: Para guardar configuración
from datetime import datetime, timedelta

# ================= CONFIGURACIÓN =================
TILE_SIZE = 1000
BASE_URL = "https://backend.wplace.live/files/s0/tiles"
HEADERS = {"User-Agent": "Mozilla/5.0"}
OUTPUT_FOLDER = "wplace_capturas_local"
CONFIG_FILE = "client_config.json" # Archivo de memoria

class WPlaceClient:
    def __init__(self, root):
        self.root = root
        self.root.title("WPlace Commander v4.0")
        if os.path.exists("wplace_icon.ico"):
            self.root.iconbitmap("wplace_icon.ico")
        self.root.geometry("700x900")
        self.root.resizable(True, True)
        
        # 1. CARGAR CONFIGURACIÓN AL INICIO
        self.config = self.cargar_config()

        # Variables de control
        self.server_ip = tk.StringVar(value=self.config.get("server_ip", "http://192.168.1.107:5000"))
        
        self.setup_ui()

        # Iniciar el monitoreo en segundo plano
        self.actualizar_estado_remoto()

        # --- ESTILOS ---
        style = ttk.Style()
        style.configure("TButton", font=("Arial", 10), padding=5)

        # --- SECCIÓN 1: COORDENADAS Y MEMORIA ---
        frame_coords = tk.LabelFrame(root, text=" 1. Coordenadas y Favoritos ", padx=10, pady=5)
        frame_coords.pack(fill="x", padx=10, pady=5)

        # >> SUB-SECCIÓN DE FAVORITOS (NUEVO)
        frm_fav = tk.Frame(frame_coords, bg="#f0f0f0", pady=5)
        frm_fav.pack(fill="x", pady=5)
        
        tk.Label(frm_fav, text="📁 Cargar Ubicación:", bg="#f0f0f0").pack(side=tk.LEFT, padx=5)
        
        # Lista desplegable
        self.combo_favs = ttk.Combobox(frm_fav, state="readonly", width=30)
        self.combo_favs.pack(side=tk.LEFT, padx=5)
        self.combo_favs.bind("<<ComboboxSelected>>", self.cargar_favorito)
        
        # Botón Guardar Favorito
        btn_save_fav = tk.Button(frm_fav, text="💾 Guardar Actual", command=self.guardar_favorito_dialog, bg="#FFC107", font=("Arial", 8))
        btn_save_fav.pack(side=tk.LEFT, padx=5)

        # Botón Borrar Favorito
        btn_del_fav = tk.Button(frm_fav, text="🗑", command=self.borrar_favorito, bg="#FF5722", fg="white", font=("Arial", 8))
        btn_del_fav.pack(side=tk.LEFT, padx=5)

        # >> INPUTS DE COORDENADAS
        tk.Label(frame_coords, text="Punto A (Inicio):").pack(anchor="w")
        self.entry_p1 = tk.Entry(frame_coords, width=70, bg="#e8f0fe")
        self.entry_p1.pack(pady=2)
        self.entry_p1.bind("<Double-Button-1>", self.pegar_portapapeles) 

        tk.Label(frame_coords, text="Punto B (Fin):").pack(anchor="w")
        self.entry_p2 = tk.Entry(frame_coords, width=70, bg="#e8f0fe")
        self.entry_p2.pack(pady=2)
        self.entry_p2.bind("<Double-Button-1>", self.pegar_portapapeles)

        # --- SECCIÓN 2: PREVISUALIZACIÓN ---
        self.btn_preview = tk.Button(root, text="🔍 Generar Previa (Local)", command=self.iniciar_preview, bg="#dddddd")
        self.btn_preview.pack(pady=5)
        
        self.lbl_preview = tk.Label(root, text="[Vista Previa]", bg="#f0f0f0")
        self.lbl_preview.pack(fill="x", padx=10)

        # --- SECCIÓN 3: PESTAÑAS ---
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(expand=True, fill="both", padx=10, pady=5)

        # TAB 1: LOCAL
        tab_local = tk.Frame(self.notebook)
        self.notebook.add(tab_local, text="💾 Guardar en PC")
        
        tk.Button(tab_local, text="Guardar Un PNG Ahora", command=self.guardar_local, bg="#4CAF50", fg="white", height=2).pack(pady=20, fill="x", padx=50)
        self.lbl_status_local = tk.Label(tab_local, text="Listo.", fg="gray")
        self.lbl_status_local.pack()

        # TAB 2: RASPBERRY PI
        tab_remote = tk.Frame(self.notebook)
        self.notebook.add(tab_remote, text="🍓 Raspberry Pi")

        # Configuración RPi
        frm_rpi = tk.Frame(tab_remote)
        frm_rpi.pack(pady=5)
        
        tk.Label(frm_rpi, text="IP:").grid(row=0, column=0, sticky="e")
        self.entry_ip = tk.Entry(frm_rpi, width=15)
        self.entry_ip.insert(0, self.config.get("last_ip", "192.168.1.107")) # Cargar memoria
        self.entry_ip.grid(row=0, column=1, padx=5)

        tk.Label(frm_rpi, text="Puerto:").grid(row=0, column=2, sticky="e")
        self.entry_port = tk.Entry(frm_rpi, width=6)
        self.entry_port.insert(0, self.config.get("last_port", "5000")) # Cargar memoria
        self.entry_port.grid(row=0, column=3, padx=5)

        # Configuración Timelapse
        frm_time = tk.LabelFrame(tab_remote, text="Configuración Timelapse", padx=10, pady=5)
        frm_time.pack(fill="x", padx=10)

        tk.Label(frm_time, text="Minutos:").grid(row=0, column=0)
        self.spin_interval = tk.Spinbox(frm_time, from_=1, to=1440, width=5)
        self.spin_interval.delete(0,"end"); self.spin_interval.insert(0, self.config.get("last_interval", "30"))
        self.spin_interval.grid(row=0, column=1, padx=5)

        tk.Label(frm_time, text="Límite MB:").grid(row=0, column=2)
        self.spin_limit = tk.Spinbox(frm_time, from_=100, to=10000, width=6)
        self.spin_limit.delete(0,"end"); self.spin_limit.insert(0, self.config.get("last_limit", "1000"))
        self.spin_limit.grid(row=0, column=3, padx=5)

        tk.Label(frm_time, text="Horas:").grid(row=1, column=0, pady=5)
        self.spin_duration = tk.Spinbox(frm_time, from_=1, to=720, width=5)
        self.spin_duration.delete(0,"end"); self.spin_duration.insert(0, self.config.get("last_duration", "24"))
        self.spin_duration.grid(row=1, column=1, pady=5)

        # Botones Control
        frm_ctrl = tk.Frame(tab_remote)
        frm_ctrl.pack(pady=10)
        self.btn_send_rpi = tk.Button(frm_ctrl, text="▶ INICIAR", command=self.enviar_orden_rpi, bg="#4CAF50", fg="white", font=("bold"))
        self.btn_send_rpi.pack(side=tk.LEFT, padx=5)
        self.btn_stop_rpi = tk.Button(frm_ctrl, text="⏹ DETENER", command=self.detener_rpi, bg="#F44336", fg="white", font=("bold"))
        self.btn_stop_rpi.pack(side=tk.LEFT, padx=5)

        # Botones Gestión
        frm_manage = tk.Frame(tab_remote)
        frm_manage.pack(pady=5, fill="x", padx=15)
        self.btn_download = tk.Button(frm_manage, text="📥 DESCARGAR ZIP", command=self.descargar_zip, bg="#2196F3", fg="white")
        self.btn_download.pack(side=tk.LEFT, expand=True, fill="x", padx=5)

        self.btn_inspect = tk.Button(frm_manage, text="🕵️ INSPECCIONAR", command=self.inspeccionar_png, bg="#9C27B0", fg="white")
        self.btn_inspect.pack(side=tk.LEFT, expand=True, fill="x", padx=2)

        self.btn_clear = tk.Button(frm_manage, text="🗑 VACIAR DATOS", command=self.vaciar_server, bg="#FF9800", fg="white")
        self.btn_clear.pack(side=tk.LEFT, expand=True, fill="x", padx=5)

        self.lbl_status_rpi = tk.Label(tab_remote, text="Estado: Listo", fg="gray")
        self.lbl_status_rpi.pack(pady=5)

        # Inicializar UI de favoritos
        self.actualizar_combo_favs()
        
        # Variables internas
        self.current_image = None
        self.last_parsed_coords = None 
        self.raw_coords_text = "" 

    def setup_ui(self):
        # --- SECCIÓN: ESTADO DEL SERVIDOR (NUEVA) ---
        status_frame = ttk.LabelFrame(self.root, text=" Monitor de Raspberry Pi ")
        status_frame.pack(fill="x", padx=10, pady=5)

        # Contenedor para el LED y el texto
        info_conn_frame = ttk.Frame(status_frame)
        info_conn_frame.pack(fill="x", padx=5, pady=5)

        self.led_canvas = tk.Canvas(info_conn_frame, width=20, height=20, highlightthickness=0)
        self.led_canvas.pack(side="left", padx=5)
        self.led_circle = self.led_canvas.create_oval(5, 5, 15, 15, fill="gray")

        self.status_label = ttk.Label(info_conn_frame, text="Buscando servidor...", font=("Arial", 9, "bold"))
        self.status_label.pack(side="left", padx=5)

        self.captures_label = ttk.Label(info_conn_frame, text="Capturas: 0")
        self.captures_label.pack(side="right", padx=10)

        # Barra de Progreso de la Tarea
        self.progress_label = ttk.Label(status_frame, text="Progreso de la tarea: 0%")
        self.progress_label.pack(fill="x", padx=10)
        
        self.progress_bar = ttk.Progressbar(status_frame, orient="horizontal", mode="determinate")
        self.progress_bar.pack(fill="x", padx=10, pady=5)

        # --- SECCIÓN: IP DEL SERVIDOR ---
        ip_frame = ttk.Frame(self.root)
        ip_frame.pack(fill="x", padx=10)
        ttk.Label(ip_frame, text="URL Servidor:").pack(side="left")
        ttk.Entry(ip_frame, textvariable=self.server_ip).pack(side="left", fill="x", expand=True, padx=5)
        ttk.Button(ip_frame, text="Guardar IP", command=self.guardar_config).pack(side="left")

        # ... (Aquí iría el resto de tu UI original: Coordenadas, Botones, etc.) ...
        # Asegúrate de mantener tus botones de START y STOP originales.

    def actualizar_estado_remoto(self):
        """Hilo cíclico para pedir status al servidor Flask cada 3 segundos"""
        def check():
            try:
                r = requests.get(f"{self.server_ip.get()}/status", timeout=2)
                if r.status_code == 200:
                    data = r.json()
                    
                    # 1. Determinar color del LED
                    color = "green" if data["running"] else "orange"
                    status_text = "CONECTADO - Ejecutando" if data["running"] else "CONECTADO - En espera"
                    
                    # 2. Calcular Progreso (Basado en el tiempo)
                    progreso = 0
                    if data["running"] and "start_time" in data:
                        start_dt = datetime.fromisoformat(data["start_time"])
                        duracion_h = data.get("duration_hours", 24)
                        end_dt = start_dt + timedelta(hours=duracion_h)
                        
                        ahora = datetime.now()
                        total_segundos = (end_dt - start_dt).total_seconds()
                        transcurrido = (ahora - start_dt).total_seconds()
                        
                        if total_segundos > 0:
                            progreso = max(0, min(100, (transcurrido / total_segundos) * 100))

                    # Actualizar UI
                    self.root.after(0, lambda: self.actualizar_ui_status(color, status_text, data.get("captures", 0), progreso))
                else:
                    self.root.after(0, lambda: self.actualizar_ui_status("red", "Error de Servidor", 0, 0))
            except:
                self.root.after(0, lambda: self.actualizar_ui_status("red", "Servidor Offline", 0, 0))
            
            # Repetir cada 3 segundos
            self.root.after(3000, self.actualizar_estado_remoto)

        threading.Thread(target=check, daemon=True).start()

    def actualizar_ui_status(self, color, texto, captures, progreso):
        """Actualiza los widgets de la interfaz"""
        self.led_canvas.itemconfig(self.led_circle, fill=color)
        self.status_label.config(text=texto)
        self.captures_label.config(text=f"Capturas en RPi: {captures}")
        self.progress_bar["value"] = progreso
        self.progress_label.config(text=f"Progreso de la tarea: {progreso:.1f}%")

    def cargar_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f: return json.load(f)
        return {}

    def guardar_config(self):
        config = {"server_ip": self.server_ip.get()}
        with open(CONFIG_FILE, "w") as f: json.dump(config, f)
        messagebox.showinfo("OK", "Configuración guardada")    

    # ================= GESTIÓN DE MEMORIA (JSON) =================
    
    def cargar_config(self):
        """Carga el JSON si existe, si no devuelve defaults"""
        defaults = {
            "last_ip": "192.168.1.107",
            "last_port": "5000",
            "last_interval": "30",
            "last_limit": "1000",
            "last_duration": "24",
            "favorites": {}  # Diccionario {nombre: {p1: text, p2: text}}
        }
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    defaults.update(data) # Mezclar con lo guardado
            except: pass
        return defaults

    def guardar_config(self):
        """Guarda el estado actual de los campos en el JSON"""
        # Actualizamos el diccionario con lo que hay en pantalla
        self.config["last_ip"] = self.entry_ip.get()
        self.config["last_port"] = self.entry_port.get()
        self.config["last_interval"] = self.spin_interval.get()
        self.config["last_limit"] = self.spin_limit.get()
        self.config["last_duration"] = self.spin_duration.get()
        
        # Escribimos a disco
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error guardando config: {e}")

    # ================= GESTIÓN DE FAVORITOS =================

    def guardar_favorito_dialog(self):
        p1 = self.entry_p1.get()
        p2 = self.entry_p2.get()
        
        if not p1 or not p2:
            messagebox.showwarning("Error", "Los campos de coordenadas están vacíos.")
            return

        nombre = simpledialog.askstring("Guardar Ubicación", "Nombre para esta ubicación:")
        if nombre:
            # Guardar en memoria
            self.config["favorites"][nombre] = {"p1": p1, "p2": p2}
            self.guardar_config() # Persistir
            self.actualizar_combo_favs()
            messagebox.showinfo("Guardado", f"Ubicación '{nombre}' guardada.")

    def borrar_favorito(self):
        nombre = self.combo_favs.get()
        if not nombre: return
        
        if messagebox.askyesno("Borrar", f"¿Eliminar '{nombre}' de favoritos?"):
            del self.config["favorites"][nombre]
            self.guardar_config()
            self.combo_favs.set("") # Limpiar selección
            self.actualizar_combo_favs()

    def actualizar_combo_favs(self):
        # Actualiza la lista del combobox con las keys del diccionario
        nombres = list(self.config["favorites"].keys())
        self.combo_favs['values'] = nombres

    def cargar_favorito(self, event):
        nombre = self.combo_favs.get()
        if nombre in self.config["favorites"]:
            data = self.config["favorites"][nombre]
            # Llenar campos
            self.entry_p1.delete(0, tk.END); self.entry_p1.insert(0, data["p1"])
            self.entry_p2.delete(0, tk.END); self.entry_p2.insert(0, data["p2"])
            # Efecto visual
            self.entry_p1.config(bg="#fff3cd"); self.root.after(300, lambda: self.entry_p1.config(bg="#e8f0fe"))
            self.entry_p2.config(bg="#fff3cd"); self.root.after(300, lambda: self.entry_p2.config(bg="#e8f0fe"))

    # ================= FUNCIONES PRINCIPALES =================

    def pegar_portapapeles(self, event):
        widget = event.widget
        try:
            texto = self.root.clipboard_get()
            widget.delete(0, tk.END)
            widget.insert(0, texto)
            widget.config(bg="#d4edda")
            self.root.after(300, lambda: widget.config(bg="#e8f0fe"))
        except: pass

    def parsear_coordenadas(self, texto):
        patron = r"Tl X:\s*(\d+).*Tl Y:\s*(\d+).*Px X:\s*(\d+).*Px Y:\s*(\d+)"
        match = re.search(patron, texto)
        if match: return [int(n) for n in match.groups()]
        return None

    def get_global_coords(self, tl_x, tl_y, px_x, px_y):
        return (tl_x * TILE_SIZE) + px_x, (tl_y * TILE_SIZE) + px_y

    def iniciar_preview(self):
        # Guardamos config al iniciar una acción
        self.guardar_config()
        hilo = threading.Thread(target=self.generar_imagen)
        hilo.start()

    def generar_imagen(self):
        txt1 = self.entry_p1.get()
        txt2 = self.entry_p2.get()
        self.raw_coords_text = txt1

        c1 = self.parsear_coordenadas(txt1)
        c2 = self.parsear_coordenadas(txt2)

        if not c1 or not c2:
            messagebox.showerror("Error", "Coordenadas inválidas")
            return

        self.lbl_preview.config(text="Descargando...", image="")
        
        gx1, gy1 = self.get_global_coords(*c1)
        gx2, gy2 = self.get_global_coords(*c2)
        
        x_start, x_end = min(gx1, gx2), max(gx1, gx2)
        y_start, y_end = min(gy1, gy2), max(gy1, gy2)
        width, height = x_end - x_start, y_end - y_start

        if width == 0 or height == 0: return

        self.last_parsed_coords = {
            "x_start": x_start, "x_end": x_end,
            "y_start": y_start, "y_end": y_end,
            "raw_text": txt1
        }

        lienzo = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        t_start_x, t_end_x = x_start // TILE_SIZE, (x_end - 1) // TILE_SIZE
        t_start_y, t_end_y = y_start // TILE_SIZE, (y_end - 1) // TILE_SIZE

        for tx in range(t_start_x, t_end_x + 1):
            for ty in range(t_start_y, t_end_y + 1):
                url = f"{BASE_URL}/{tx}/{ty}.png"
                try:
                    resp = requests.get(url, headers=HEADERS, timeout=5)
                    if resp.status_code == 200:
                        tile = Image.open(BytesIO(resp.content)).convert("RGBA")
                        lienzo.paste(tile, ((tx * TILE_SIZE) - x_start, (ty * TILE_SIZE) - y_start), tile)
                except: pass

        self.current_image = lienzo
        
        preview_img = lienzo.copy()
        fondo = Image.new("RGBA", preview_img.size, (255, 255, 255, 255))
        fondo.paste(preview_img, (0, 0), preview_img)
        preview_img = fondo.convert("RGB")
        preview_img = ImageOps.contain(preview_img, (600, 350), Image.Resampling.NEAREST)
        
        self.tk_img = ImageTk.PhotoImage(preview_img)
        self.lbl_preview.config(image=self.tk_img, width=0, height=0)

    def guardar_local(self):
        if not self.current_image: return
        if not os.path.exists(OUTPUT_FOLDER): os.makedirs(OUTPUT_FOLDER)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"local_{timestamp}.png"
        path = os.path.join(OUTPUT_FOLDER, filename)
        
        meta = PngInfo()
        meta.add_text("WPlace_Coords_P1", self.raw_coords_text)
        
        self.current_image.save(path, pnginfo=meta)
        messagebox.showinfo("Guardado", f"Imagen guardada en:\n{path}")

    def detener_rpi(self):
        url = f"http://{self.entry_ip.get()}:{self.entry_port.get()}/stop_task"
        try:
            requests.post(url, timeout=3)
            self.lbl_status_rpi.config(text="🛑 Orden de STOP enviada", fg="red")
            messagebox.showinfo("Info", "Se envió la señal de DETENER a la Raspberry.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def vaciar_server(self):
        if messagebox.askyesno("PELIGRO", "¿Estás seguro de borrar TODAS las fotos en la Raspberry?"):
            url = f"http://{self.entry_ip.get()}:{self.entry_port.get()}/clear_data"
            try:
                r = requests.post(url, timeout=3)
                self.lbl_status_rpi.config(text="🗑 Datos Eliminados", fg="orange")
                messagebox.showinfo("Info", r.json().get("message"))
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def enviar_orden_rpi(self):
        # Guardamos config antes de enviar
        self.guardar_config()

        if not self.last_parsed_coords:
            messagebox.showwarning("Atención", "Primero genera una 'Previa' para calcular el área.")
            return

        ip = self.entry_ip.get()
        port = self.entry_port.get()
        
        payload = {
            "coords": self.last_parsed_coords,
            "interval_min": int(self.spin_interval.get()),
            "limit_mb": int(self.spin_limit.get()),
            "duration_hours": float(self.spin_duration.get())
        }

        url = f"http://{ip}:{port}/start_task"
        
        def send():
            try:
                self.lbl_status_rpi.config(text="Enviando...", fg="blue")
                r = requests.post(url, json=payload, timeout=3)
                if r.status_code == 200:
                    self.lbl_status_rpi.config(text=f"✅ RPi: {r.json()['message']}", fg="green")
                else:
                    self.lbl_status_rpi.config(text=f"❌ Error RPi: {r.text}", fg="red")
            except Exception as e:
                self.lbl_status_rpi.config(text=f"❌ Conexión fallida: {e}", fg="red")

        threading.Thread(target=send).start()

    def descargar_zip(self):
        ip = self.entry_ip.get()
        port = self.entry_port.get()
        url = f"http://{ip}:{port}/download_zip"
        
        if messagebox.askyesno("Confirmar", "¿Quieres descargar y comprimir todas las fotos de la Raspberry?"):
            try:
                self.lbl_status_rpi.config(text="⏳ Descargando ZIP (puede tardar)...", fg="blue")
                self.root.update() 
                
                resp = requests.get(url, stream=True)
                
                if resp.status_code == 200:
                    if not os.path.exists(OUTPUT_FOLDER): os.makedirs(OUTPUT_FOLDER)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"pack_rpi_{timestamp}.zip"
                    path = os.path.join(OUTPUT_FOLDER, filename)
                    
                    with open(path, 'wb') as f:
                        for chunk in resp.iter_content(chunk_size=8192):
                            f.write(chunk)
                            
                    self.lbl_status_rpi.config(text="✅ ZIP Descargado", fg="green")
                    messagebox.showinfo("Éxito", f"Archivo guardado en:\n{path}")
                    os.startfile(OUTPUT_FOLDER)
                else:
                    self.lbl_status_rpi.config(text="❌ Error en descarga", fg="red")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo conectar: {e}")
    def inspeccionar_png(self):
        # 1. Pedir al usuario que seleccione un archivo
        archivo = filedialog.askopenfilename(
            title="Selecciona una captura para analizar",
            initialdir=OUTPUT_FOLDER,
            filetypes=[("Imágenes PNG", "*.png")]
        )
        
        if not archivo: return

        try:
            # 2. Leer metadatos con Pillow
            img = Image.open(archivo)
            img.load() # Cargar info
            
            metadata = img.text # Esto es un diccionario con los textos
            
            if not metadata:
                messagebox.showinfo("Inspector", "Esta imagen no tiene metadatos de WPlace.")
                return

            # 3. Formatear mensaje
            info_str = "📋 METADATOS ENCONTRADOS:\n\n"
            
            # Buscar coordenadas específicas
            if "WPlace_Coords_P1" in metadata:
                info_str += f"📍 COORDENADAS ORIGINALES:\n{metadata['WPlace_Coords_P1']}\n\n"
            
            if "WPlace_Source" in metadata: # El nombre que usa la Raspberry
                info_str += f"🍓 ORIGEN RASPBERRY:\n{metadata['WPlace_Source']}\n\n"

            info_str += "-"*30 + "\nOTRAS CLAVES:\n"
            for k, v in metadata.items():
                if k not in ["WPlace_Coords_P1", "WPlace_Source"]:
                    info_str += f"{k}: {v}\n"

            # 4. Copiar al portapapeles automáticamente por comodidad
            if "WPlace_Coords_P1" in metadata:
                self.root.clipboard_clear()
                self.root.clipboard_append(metadata["WPlace_Coords_P1"])
                info_str += "\n(✅ Coordenadas copiadas al portapapeles)"
            elif "WPlace_Source" in metadata:
                self.root.clipboard_clear()
                self.root.clipboard_append(metadata["WPlace_Source"])
                info_str += "\n(✅ Coordenadas copiadas al portapapeles)"

            messagebox.showinfo(f"Inspector: {os.path.basename(archivo)}", info_str)

        except Exception as e:
            messagebox.showerror("Error", f"No se pudo leer la imagen: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = WPlaceClient(root)
    root.mainloop()