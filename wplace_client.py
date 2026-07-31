import tkinter as tk
from tkinter import messagebox, ttk, simpledialog, Menu, filedialog
from PIL import Image, ImageTk, ImageDraw, PngImagePlugin
import requests
from io import BytesIO
import threading
import time
import json
import os
import subprocess
import platform
import re
from datetime import datetime, timedelta
import pyperclip

CONFIG_FILE = "client_config.json"
OUTPUT_FOLDER = "wplace_downloads"

# 🧠 DICCIONARIO DE OBJETIVOS
SOURCES = {
    "WPlace": "https://backend.wplace.live/files/s0/tiles",
    "BPlace": "https://bplace.org/files/s0/tiles"
}

class SabuesoTab(ttk.Frame):
    def __init__(self, parent, server_url_getter):
        super().__init__(parent)
        self.get_server_url = server_url_getter
        
        # Estado local del visor
        self.grid_size = 50 # Matrix 50x50 para representar el Chunk
        self.cell_pixels = {} # Guardar IDs de rectángulos del Canvas
        self.is_monitoring = False
        self.config_loaded = False # 👈 Bandera para sincronizar la primera vez
        self.seen_findings = set()
        self._build_ui()
        
        # Iniciar monitoreo automático desde el arranque de la app
        self.is_monitoring = True
        self.poll_status()

    def _build_ui(self):
        # --- PANEL IZQUIERDO: CONFIGURACIÓN Y CONTROLES ---
        left_panel = ttk.LabelFrame(self, text=" 🐺 Configuración de la Jauría ", padding=10)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        ttk.Label(left_panel, text="IDs Objetivo (separados por coma/espacio):").pack(anchor=tk.W, pady=2)
        self.txt_targets = ttk.Entry(left_panel, width=30)
        self.txt_targets.pack(fill=tk.X, pady=2)

        coords_frame = ttk.Frame(left_panel)
        coords_frame.pack(fill=tk.X, pady=5)

        ttk.Label(coords_frame, text="Tile X:").grid(row=0, column=0, sticky=tk.W)
        self.ent_tile_x = ttk.Entry(coords_frame, width=8)
        self.ent_tile_x.grid(row=0, column=1, padx=2)

        ttk.Label(coords_frame, text="Tile Y:").grid(row=0, column=2, sticky=tk.W)
        self.ent_tile_y = ttk.Entry(coords_frame, width=8)
        self.ent_tile_y.grid(row=0, column=3, padx=2)

        ttk.Label(left_panel, text="Cantidad de Sabuesos (Jauría):").pack(anchor=tk.W, pady=(10, 2))
        self.spn_hounds = ttk.Spinbox(left_panel, from_=1, to=16, width=5)
        self.spn_hounds.pack(anchor=tk.W, pady=2)

        # Botones de Acción
        btn_frame = ttk.Frame(left_panel)
        btn_frame.pack(fill=tk.X, pady=15)

        self.btn_start = ttk.Button(btn_frame, text="🐺 SOLTAR JAURÍA", command=self.start_jauria)
        self.btn_start.pack(fill=tk.X, pady=2)

        self.btn_stop = ttk.Button(btn_frame, text="🛑 DETENER JAURÍA", command=self.stop_jauria, state=tk.DISABLED)
        self.btn_stop.pack(fill=tk.X, pady=2)

        # 🆕 BOTÓN DE RESETEO
        self.btn_reset = ttk.Button(btn_frame, text="🔄 REINICIAR PROGRESO (DESDE 0%)", command=self.reset_jauria)
        self.btn_reset.pack(fill=tk.X, pady=(10, 2))

        # --- PANEL CENTRAL: VISOR GRAFICO RADAR (CANVAS) ---
        center_panel = ttk.LabelFrame(self, text=" 🗺️ Radar del Chunk (1000x1000) ", padding=10)
        center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.canvas = tk.Canvas(center_panel, width=400, height=400, bg="#1e1e1e", highlightthickness=0)
        self.canvas.pack(anchor=tk.CENTER, expand=True, pady=5)
        self._init_radar_grid()

        prog_frame = ttk.Frame(center_panel)
        prog_frame.pack(fill=tk.X, pady=5)

        self.lbl_progress = ttk.Label(prog_frame, text="Progreso: 0% (0 / 1,000,000 px)")
        self.lbl_progress.pack(anchor=tk.W)

        self.progress_bar = ttk.Progressbar(prog_frame, mode="determinate", maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=2)

        # --- PANEL DERECHO: HALLAZGOS Y LINKS ---
        right_panel = ttk.LabelFrame(self, text=" 🎯 Hallazgos en Vivo ", padding=10)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ("time", "user", "coords", "hound")
        self.tree = ttk.Treeview(right_panel, columns=columns, show="headings", height=12)
        self.tree.heading("time", text="Hora")
        self.tree.heading("user", text="Usuario")
        self.tree.heading("coords", text="Coordenada")
        self.tree.heading("hound", text="Sabueso")

        self.tree.column("time", width=60)
        self.tree.column("user", width=100)
        self.tree.column("coords", width=90)
        self.tree.column("hound", width=60)
        self.tree.pack(fill=tk.BOTH, expand=True, pady=5)

        self.item_links = {}

        btn_copy = ttk.Button(right_panel, text="📋 Copiar Link Seleccionado", command=self.copy_selected_link)
        btn_copy.pack(fill=tk.X, pady=2)

        # --- TERMINAL DE LOGS EN VIVO ---
        log_frame = ttk.LabelFrame(self, text=" 🖥️ Terminal de Sabuesos (Live) ", padding=5)
        log_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        
        self.txt_logs = tk.Text(log_frame, height=7, bg="#0c0c0c", fg="#00ff00", font=("Consolas", 9))
        self.txt_logs.pack(fill=tk.BOTH, expand=True, pady=2)

    def _init_radar_grid(self):
        self.canvas.delete("all")
        self.cell_pixels.clear()
        
        self.grid_size = 100 # 👈 10,000 celdas
        self.painted_cells = set() # 👈 Historial de celdas pintadas para no sobrecargar el canvas
        
        cell_w = 400 / self.grid_size
        cell_h = 400 / self.grid_size

        for gx in range(self.grid_size):
            for gy in range(self.grid_size):
                x1 = gx * cell_w
                y1 = gy * cell_h
                x2 = x1 + cell_w
                y2 = y1 + cell_h
                rect = self.canvas.create_rectangle(x1, y1, x2, y2, fill="#2b2b2b", outline="")
                self.cell_pixels[(gx, gy)] = rect

    def start_jauria(self):
        try:
            raw_text = self.txt_targets.get().replace("\n", ",").replace(" ", ",")
            targets = [int(i.strip()) for i in raw_text.split(",") if i.strip().isdigit()]
            
            if not targets:
                messagebox.showerror("Error", "Debes ingresar al menos un ID numérico válido.")
                return

            tile_x = int(self.ent_tile_x.get())
            tile_y = int(self.ent_tile_y.get())
            hounds = int(self.spn_hounds.get())
        except ValueError:
            messagebox.showerror("Error", "Revisa los campos numéricos de Tile X, Tile Y o Sabuesos.")
            return

        url = f"{self.get_server_url()}/sabueso/start"
        payload = {
            "target_ids": targets,
            "tile_x": tile_x,
            "tile_y": tile_y,
            "xmin": 0, "xmax": 999,
            "ymin": 0, "ymax": 999,
            "num_hounds": hounds
        }

        try:
            r = requests.post(url, json=payload, timeout=5)
            if r.status_code == 200:
                self.btn_start.config(state=tk.DISABLED)
                self.btn_stop.config(state=tk.NORMAL)
                self.is_monitoring = True
            else:
                messagebox.showerror("Error", f"Error al iniciar Jauría: {r.text}")
        except Exception as e:
            messagebox.showerror("Error de conexión", str(e))

    def stop_jauria(self):
        url = f"{self.get_server_url()}/sabueso/stop"
        try:
            requests.post(url, timeout=5)
        except:
            pass
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)

    def reset_jauria(self):
        if not messagebox.askyesno("Confirmar Reseteo", "¿Estás seguro de borrar el avance de este Tile?\nSe iniciará el rastreo desde 0% (1,000,000 px)."):
            return

        url = f"{self.get_server_url()}/sabueso/reset"
        try:
            r = requests.post(url, timeout=5)
            if r.status_code == 200:
                self._init_radar_grid()  # Limpiar radar
                self.painted_cells.clear()
                self.progress_bar["value"] = 0
                self.lbl_progress.config(text="Progreso: 0% (0 / 1,000,000 px)")
                # Limpiar tabla de hallazgos
                for item in self.tree.get_children():
                    self.tree.delete(item)
                self.item_links.clear()
                self.seen_findings.clear()
                messagebox.showinfo("Éxito", "Avance reseteado. Puedes presionar 'SOLTAR JAURÍA' para iniciar de nuevo.")
            else:
                messagebox.showerror("Error", f"No se pudo resetear: {r.text}")
        except Exception as e:
            messagebox.showerror("Error de conexión", str(e))

    def poll_status(self):
        try:
            # 1. Pedir estado
            url_status = f"{self.get_server_url()}/sabueso/status"
            r_status = requests.get(url_status, timeout=2)
            if r_status.status_code == 200:
                self.update_ui(r_status.json())

            # 2. Pedir logs vivos
            url_logs = f"{self.get_server_url()}/sabueso/logs"
            r_logs = requests.get(url_logs, timeout=2)
            if r_logs.status_code == 200:
                logs = r_logs.json().get("logs", [])
                if logs:
                    self.txt_logs.delete(1.0, tk.END)
                    for line in logs:
                        self.txt_logs.insert(tk.END, line)
                    self.txt_logs.see(tk.END) # Auto-scroll
        except Exception as ex:
            pass

        self.after(1500, self.poll_status)

    def update_ui(self, data):
        try:
            # 0. Sincronización inicial la primera vez que se reciben datos
            if not self.config_loaded and isinstance(data, dict):
                target_ids = data.get("target_ids") or []
                tile_x = data.get("tile_x", 460)
                tile_y = data.get("tile_y", 874)
                num_hounds = data.get("num_hounds", 8)

                # Rellenar cajas de texto
                ids_str = ", ".join(str(i) for i in target_ids)
                self.txt_targets.delete(0, tk.END)
                self.txt_targets.insert(0, ids_str)

                self.ent_tile_x.delete(0, tk.END)
                self.ent_tile_x.insert(0, str(tile_x))

                self.ent_tile_y.delete(0, tk.END)
                self.ent_tile_y.insert(0, str(tile_y))

                self.spn_hounds.set(num_hounds)
                self.config_loaded = True

            # Actualizar estado de los botones (Soltar / Detener)
            is_running = data.get("running", False)
            if is_running:
                self.btn_start.config(state=tk.DISABLED)
                self.btn_stop.config(state=tk.NORMAL)
            else:
                self.btn_start.config(state=tk.NORMAL)
                self.btn_stop.config(state=tk.DISABLED)

            # 1. Actualizar barra de progreso (Ahora mide Lotes)
            percentage = data.get("progress_percentage", 0)
            scanned = data.get("scanned_count", 0)
            total = data.get("total_count", 10000)

            self.progress_bar["value"] = percentage
            self.lbl_progress.config(text=f"Progreso: {percentage}% ({scanned:,} / {total:,} Lotes Completados)")

            # 2. Pintar Celdas Verdes (Lotes Completados)
            completed_batches = data.get("completed_batches", [])
            for gx, gy in completed_batches:
                if (gx, gy) not in self.painted_cells:
                    rect_id = self.cell_pixels.get((gx, gy))
                    if rect_id:
                        self.canvas.itemconfig(rect_id, fill="#00e676")
                    self.painted_cells.add((gx, gy))

            # 3. Pintar Celdas Rojas (Hallazgos - Sobrescribe al verde)
            findings = data.get("findings", [])
            for f in findings:
                # Calcular a qué lote pertenece el píxel exacto
                gx = int(f["x"] / 10)
                gy = int(f["y"] / 10)
                
                rect_id = self.cell_pixels.get((gx, gy))
                if rect_id:
                    self.canvas.itemconfig(rect_id, fill="#ff1744")

                link = f["link"]
                item_id = f"{f['timestamp']}_{f['x']}_{f['y']}"
                
                if item_id not in self.seen_findings:
                    row_id = self.tree.insert("", "end", values=(f["timestamp"], f["user_name"], f"({f['x']},{f['y']})", f"#{f['hound_id']}"))
                    self.item_links[row_id] = link
                    self.seen_findings.add(item_id)

        except Exception as err:
            print(f"Error procesando update_ui: {err}")

    def copy_selected_link(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Atención", "Selecciona un hallazgo de la lista.")
            return
        
        row_id = selected[0]
        link = self.item_links.get(row_id)
        if link:
            pyperclip.copy(link)
            messagebox.showinfo("Copiado", f"Link copiado al portapapeles:\n{link}")


class WPlaceClient:
    def __init__(self, root):
        self.root = root
        self.root.title("WPlace Commander v19.0 (Hybrid Ops)")
        self.root.geometry("1280x850")
        
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Treeview", rowheight=30, font=('Segoe UI', 9))
        style.configure("Treeview.Heading", font=('Segoe UI', 10, 'bold'), background="#d9d9d9")
        
        style.configure("Green.TButton", font=('Segoe UI', 9), background="#E8F5E9", foreground="#2E7D32")
        style.configure("Red.TButton", font=('Segoe UI', 9), background="#FFEBEE", foreground="#C62828")
        style.configure("Blue.TButton", font=('Segoe UI', 9), background="#E3F2FD", foreground="#1565C0")
        style.configure("Orange.TButton", font=('Segoe UI', 9), background="#FFF3E0", foreground="#EF6C00")
        style.configure("Accent.TButton", font=('Segoe UI', 10, 'bold'), background="#2196F3", foreground="white")
        style.configure("Danger.TButton", font=('Segoe UI', 9, 'bold'), background="#F44336", foreground="white")
        style.configure("Warning.TButton", font=('Segoe UI', 9, 'bold'), background="#FF9800", foreground="white")
        
        self.config = self.cargar_config()
        self.server_ip = tk.StringVar(value=self.config.get("server_ip", "http://192.168.1.107:5000"))
        
        self.click_count = 0
        self.preview_image_raw = None
        self.tk_image_ref = None
        self.zoom_level = 1.0
        self.checker_tile = None 
        
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.tab_new = ttk.Frame(self.notebook)
        self.tab_manager = ttk.Frame(self.notebook)
        self.tab_system = ttk.Frame(self.notebook)
        self.tab_planner = ttk.Frame(self.notebook)
        self.tab_telegram = ttk.Frame(self.notebook) 
        self.tab_sabueso = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_new, text="🔭 Misión")
        self.notebook.add(self.tab_manager, text="📡 Radar de Tareas")
        self.notebook.add(self.tab_planner, text="📅 Planificador")
        self.notebook.add(self.tab_sabueso, text="🐶 Sabueso")
        self.notebook.add(self.tab_telegram, text="📱 Telegram") 
        self.notebook.add(self.tab_system, text="⚙️ Sistema")
        
        self.setup_tab_new()
        self.setup_tab_manager()
        self.setup_tab_planner()
        self.setup_tab_telegram()
        self.setup_tab_system()
        
        # --- MONTAJE DE LA PESTAÑA MODERNA DEL SABUESO ---
        self.sabueso_tab = SabuesoTab(self.tab_sabueso, lambda: self.server_ip.get().rstrip('/'))
        self.sabueso_tab.pack(fill='both', expand=True)
        
        self.running = True
        threading.Thread(target=self.monitor_loop, daemon=True).start()

    # ================= PESTAÑA TELEGRAM =================
    def setup_tab_telegram(self):
        f = ttk.LabelFrame(self.tab_telegram, text="Credenciales Globales de Telegram")
        f.pack(fill='both', expand=True, padx=20, pady=20)
        
        ttk.Label(f, text="Bot Token:").grid(row=0, column=0, padx=10, pady=10, sticky='e')
        self.et_tok = tk.Entry(f, width=45)
        self.et_tok.insert(0, self.config.get("tg_token", ""))
        self.et_tok.grid(row=0, column=1, padx=10, pady=10)
        
        ttk.Label(f, text="Chat ID:").grid(row=1, column=0, padx=10, pady=10, sticky='e')
        self.et_chat = tk.Entry(f, width=45)
        self.et_chat.insert(0, self.config.get("tg_chat", ""))
        self.et_chat.grid(row=1, column=1, padx=10, pady=10)
        
        ttk.Button(f, text="💾 GUARDAR CONFIGURACIÓN", style="Accent.TButton", command=self.guardar_tg).grid(row=2, column=0, columnspan=2, pady=20)
        
    def guardar_tg(self):
        self.config["tg_token"] = self.et_tok.get()
        self.config["tg_chat"] = self.et_chat.get()
        self.guardar_config()
        messagebox.showinfo("Guardado", "Credenciales de Telegram guardadas globalmente.\nAhora aplicarán para Misiones y Planificador.")

    # ================= PESTAÑA PLANIFICADOR =================
    def setup_tab_planner(self):
        main_f = ttk.Frame(self.tab_planner)
        main_f.pack(fill='both', expand=True, padx=15, pady=10)

        f = ttk.LabelFrame(main_f, text="Calculadora Estratégica Híbrida")
        f.pack(fill='x', padx=5, pady=5)
        
        f_in = ttk.Frame(f)
        f_in.pack(fill='x', padx=10, pady=5)

        ttk.Label(f_in, text="Píxeles Actuales:").grid(row=0, column=0, padx=10, pady=5, sticky='e')
        self.pl_actuales = ttk.Entry(f_in, width=15)
        self.pl_actuales.grid(row=0, column=1, padx=10, pady=5, sticky='w')
        
        ttk.Label(f_in, text="Capacidad Máxima:").grid(row=1, column=0, padx=10, pady=5, sticky='e')
        self.pl_max = ttk.Entry(f_in, width=15)
        self.pl_max.insert(0, "7404")
        self.pl_max.grid(row=1, column=1, padx=10, pady=5, sticky='w')
        
        ttk.Label(f_in, text="Objetivo de Disparo (%):").grid(row=2, column=0, padx=10, pady=5, sticky='e')
        self.pl_obj = ttk.Entry(f_in, width=15)
        self.pl_obj.insert(0, "85")
        self.pl_obj.grid(row=2, column=1, padx=10, pady=5, sticky='w')
        
        ttk.Label(f_in, text="Reserva de Defensa (%):").grid(row=3, column=0, padx=10, pady=5, sticky='e')
        self.pl_res = ttk.Entry(f_in, width=15)
        self.pl_res.insert(0, "25")
        self.pl_res.grid(row=3, column=1, padx=10, pady=5, sticky='w')
        
        ttk.Button(f, text="CALCULAR Y ACTIVAR ALERTA", style="Accent.TButton", command=self.calcular_plan).pack(pady=10)
        
        f_diag = ttk.LabelFrame(main_f, text="🛡️ Evaluador de Daños por Ataque")
        f_diag.pack(fill='x', padx=5, pady=5)
        
        f_diag_in = ttk.Frame(f_diag)
        f_diag_in.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(f_diag_in, text="Píxeles Dañados o % de Ataque:").grid(row=0, column=0, padx=5, pady=5, sticky='e')
        self.entry_damage = ttk.Entry(f_diag_in, width=15)
        self.entry_damage.insert(0, "2000")
        self.entry_damage.grid(row=0, column=1, padx=5, pady=5, sticky='w')
        
        ttk.Button(f_diag_in, text="🔍 ANALIZAR CAPACIDAD DE REPARACIÓN", style="Blue.TButton", command=self.analizar_dano).grid(row=0, column=2, padx=15, pady=5)

        res_f = ttk.LabelFrame(main_f, text="Resultados y Cronograma")
        res_f.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.lbl_plan_res = ttk.Label(res_f, text="Ingresa tus datos para generar el plan...", justify="left", font=('Segoe UI', 10))
        self.lbl_plan_res.pack(padx=15, pady=15, anchor="w")

    def analizar_dano(self):
        try:
            px_danados = int(self.entry_damage.get())
            actuales = int(self.pl_actuales.get() or "0")
            
            if actuales >= px_danados:
                sobrantes = actuales - px_danados
                messagebox.showinfo(
                    "✅ REPARACIÓN VIABLE",
                    f"¡Tienes suficientes píxeles para reparar el daño de inmediato!\n\n"
                    f"• Píxeles necesarios: {px_danados} px\n"
                    f"• Reserva actual: {actuales} px\n"
                    f"• Te quedarán: {sobrantes} px en reserva después de reparar."
                )
            else:
                faltantes = px_danados - actuales
                minutos_espera = (faltantes * 30) // 60
                horas_espera = round(minutos_espera / 60.0, 2)
                
                messagebox.showwarning(
                    "⚠️ RESERVA INSUFICIENTE",
                    f"No tienes suficientes píxeles para reparar el daño completo en este momento.\n\n"
                    f"• Píxeles necesarios: {px_danados} px\n"
                    f"• Reserva actual: {actuales} px\n"
                    f"• Píxeles faltantes: {faltantes} px\n\n"
                    f"⏳ Tiempo estimado de recarga requerido: {horas_espera} hrs ({minutos_espera} min)."
                )
        except ValueError:
            messagebox.showerror("Error", "Ingresa una cantidad numérica válida de píxeles dañados.")

    def calcular_plan(self):
        try:
            actuales = int(self.pl_actuales.get())
            maximos = int(self.pl_max.get())
            obj_pct = float(self.pl_obj.get())
            res_pct = float(self.pl_res.get())
            
            px_objetivo = int(maximos * (obj_pct / 100))
            px_reserva = int(maximos * (res_pct / 100))
            px_gastar = px_objetivo - px_reserva
            
            px_faltantes = max(0, px_objetivo - actuales)
            segundos_espera = px_faltantes * 30
            fecha_alerta = datetime.now() + timedelta(seconds=segundos_espera)
            horas_margen = ((maximos - px_objetivo) * 30) / 3600.0
            
            txt = (
                f"🎯 Objetivo a alcanzar: {px_objetivo} px ({obj_pct}%)\n"
                f"🛡️ Reserva a dejar: {px_reserva} px ({res_pct}%)\n"
                f"🖌️ Píxeles a pintar por sesión: {px_gastar} px\n\n"
                f"⏱️ Tiempo de recarga estimado: {round(segundos_espera / 3600.0, 2)} horas\n"
                f"⏰ Hora de notificación: {fecha_alerta.strftime('%d/%m/%Y a las %H:%M:%S')}\n"
                f"🔋 Margen de inactividad antes de perder píxeles: {round(horas_margen, 2)} horas"
            )
            self.lbl_plan_res.config(text=txt)
            
            token = self.et_tok.get()
            chat_id = self.et_chat.get()
            
            if not token or not chat_id:
                messagebox.showwarning("Aviso", "Ve a la pestaña 'Telegram' y configura tus credenciales para recibir la alerta.")
                return

            if px_faltantes > 0:
                payload = {
                    "segundos_espera": segundos_espera,
                    "px_objetivo": px_objetivo,
                    "token": token,
                    "chat_id": chat_id,
                    "config_txt": txt 
                }
                r = requests.post(f"{self.server_ip.get().rstrip('/')}/plan/set", json=payload, timeout=3)
                if r.status_code == 200:
                    messagebox.showinfo("Alerta Activada", "¡Plan calculado! El servidor te avisará por Telegram en el momento exacto.")
                else:
                    messagebox.showerror("Error", f"El servidor devolvió el código {r.status_code}.")
            else:
                messagebox.showinfo("Listo", "¡Ya tienes los píxeles necesarios para pintar!")
                
        except ValueError:
            messagebox.showerror("Error de Datos", "Asegúrate de ingresar solo números válidos en las casillas.")
        except Exception as e:
            messagebox.showerror("Error Crítico", f"El programa se detuvo por este error de código:\n{str(e)}")

    def cargar_config(self):
        if os.path.exists(CONFIG_FILE):
            try: return json.load(open(CONFIG_FILE))
            except: pass
        return {"favorites": {}}

    def guardar_config(self):
        self.config["server_ip"] = self.server_ip.get()
        with open(CONFIG_FILE, "w") as f: json.dump(self.config, f, indent=4)

    def abrir_carpeta(self, path):
        path = os.path.abspath(path)
        if platform.system() == "Windows": os.startfile(path)
        elif platform.system() == "Darwin": subprocess.Popen(["open", path])
        else: subprocess.Popen(["xdg-open", path])

    def coords_to_str(self, x, y):
        return f"(Tl X: {x//1000}, Tl Y: {y//1000}, Px X: {x%1000}, Px Y: {y%1000})"

    def str_to_coords(self, text):
        match = re.search(r"Tl X:\s*(\d+).*?Tl Y:\s*(\d+).*?Px X:\s*(\d+).*?Px Y:\s*(\d+)", text)
        if match: return (int(match.group(1)) * 1000) + int(match.group(3)), (int(match.group(2)) * 1000) + int(match.group(4))
        try: parts = text.replace('(', '').replace(')', '').split(','); return int(parts[0]), int(parts[1])
        except: raise ValueError("Formato incorrecto")

    # ================= PESTAÑA 1 =================
    def setup_tab_new(self):
        paned = tk.PanedWindow(self.tab_new, orient=tk.HORIZONTAL, sashwidth=6, sashrelief=tk.RAISED, bg="#d0d0d0")
        paned.pack(fill='both', expand=True)

        left = ttk.Frame(paned, width=400); paned.add(left, minsize=380)
        
        l1 = ttk.LabelFrame(left, text="1. Datos de Misión"); l1.pack(fill='x', padx=5, pady=5)
        tk.Label(l1, text="IP:").grid(row=0, column=0, sticky='e'); tk.Entry(l1, textvariable=self.server_ip, width=22).grid(row=0, column=1)
        tk.Label(l1, text="Nombre:").grid(row=1, column=0, sticky='e'); self.task_name = tk.Entry(l1, width=22); self.task_name.grid(row=1, column=1)
        
        tk.Label(l1, text="Objetivo:").grid(row=2, column=0, sticky='e')
        self.combo_source = ttk.Combobox(l1, values=["BPlace", "WPlace"], state="readonly", width=20)
        self.combo_source.current(0)
        self.combo_source.grid(row=2, column=1, pady=5)

        l2 = ttk.LabelFrame(left, text="2. Coordenadas"); l2.pack(fill='x', padx=5, pady=5)
        tk.Label(l2, text="P1:").grid(row=0, column=0); self.entry_p1 = tk.Entry(l2, width=35); self.entry_p1.grid(row=0, column=1, pady=2)
        tk.Label(l2, text="P2:").grid(row=1, column=0); self.entry_p2 = tk.Entry(l2, width=35); self.entry_p2.grid(row=1, column=1, pady=2)
        
        f_fav = ttk.Frame(l2); f_fav.grid(row=2, column=0, columnspan=2, pady=5)
        self.combo_favs = ttk.Combobox(f_fav, width=20, state="readonly", values=list(self.config["favorites"].keys()))
        self.combo_favs.pack(side='left'); self.combo_favs.bind("<<ComboboxSelected>>", self.cargar_fav)
        ttk.Button(f_fav, text="💾", width=3, command=self.guardar_fav).pack(side='left', padx=2)
        ttk.Button(f_fav, text="🗑", width=3, command=self.del_fav).pack(side='left', padx=2)

        l3 = ttk.LabelFrame(left, text="3. Configuración"); l3.pack(fill='x', padx=5, pady=5)
        self.chk_time = tk.BooleanVar(value=True); self.chk_sent = tk.BooleanVar(value=False)
        ttk.Checkbutton(l3, text="Timelapse", variable=self.chk_time).grid(row=0, column=0, sticky='w')
        ttk.Checkbutton(l3, text="Centinela", variable=self.chk_sent).grid(row=0, column=1, sticky='w')
        tk.Label(l3, text="Min:").grid(row=1, column=0, sticky='e'); self.sp_int = ttk.Spinbox(l3, from_=1, to=120, width=5); self.sp_int.set(1); self.sp_int.grid(row=1, column=1)
        tk.Label(l3, text="Hrs:").grid(row=1, column=2, sticky='e'); self.sp_dur = ttk.Spinbox(l3, from_=0, to=48, width=5); self.sp_dur.set(0); self.sp_dur.grid(row=1, column=3)
        tk.Label(l3, text="MB:").grid(row=2, column=0, sticky='e'); self.sp_mb = ttk.Spinbox(l3, from_=100, to=5000, width=5); self.sp_mb.set(1000); self.sp_mb.grid(row=2, column=1)
        tk.Label(l3, text="Alert:").grid(row=2, column=2, sticky='e'); self.sp_sens = ttk.Spinbox(l3, from_=0.1, to=50, width=5, increment=0.1); self.sp_sens.set(5.0); self.sp_sens.grid(row=2, column=3)
       
        ttk.Button(left, text="🚀 LANZAR TAREA", style="Accent.TButton", command=self.lanzar).pack(fill='x', padx=10, pady=15, ipady=5)

        right = ttk.LabelFrame(paned, text="Visor Táctico"); paned.add(right, minsize=400, stretch="always")
        tool = ttk.Frame(right); tool.pack(fill='x', pady=2)
        ttk.Button(tool, text="📷 Cargar Vista", command=self.preview).pack(side='left', padx=2)
        ttk.Button(tool, text="💾 PNG", command=self.snap_local).pack(side='left', padx=2)
        ttk.Button(tool, text="➕", width=3, command=lambda: self.zoom(1.2)).pack(side='right', padx=2)
        ttk.Button(tool, text="➖", width=3, command=lambda: self.zoom(0.8)).pack(side='right', padx=2)

        self.canvas = tk.Canvas(right, bg="#202020", cursor="cross")
        sx = ttk.Scrollbar(right, orient="horizontal", command=self.canvas.xview); sy = ttk.Scrollbar(right, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=sx.set, yscrollcommand=sy.set)
        sx.pack(side="bottom", fill="x"); sy.pack(side="right", fill="y"); self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self.map_click)
        self.prepare_checkerboard()

    def prepare_checkerboard(self):
        check = Image.new("RGB", (20, 20), "#CCCCCC")
        d = ImageDraw.Draw(check); d.rectangle([10,0,20,10], fill="#999999"); d.rectangle([0,10,10,20], fill="#999999")
        self.checker_tile = check

    def map_click(self, e):
        cx, cy = self.canvas.canvasx(e.x), self.canvas.canvasy(e.y)
        rx, ry = int(cx / self.zoom_level), int(cy / self.zoom_level)
        txt = self.coords_to_str(rx, ry)
        if self.click_count % 2 == 0: self.entry_p1.delete(0, tk.END); self.entry_p1.insert(0, txt)
        else: self.entry_p2.delete(0, tk.END); self.entry_p2.insert(0, txt)
        self.click_count += 1
        r = 5 * self.zoom_level; self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r, outline="#00FF00", width=2, tags="marker")

    def preview(self):
        try:
            target_source = self.combo_source.get()
            base_url = SOURCES[target_source]

            p1 = self.str_to_coords(self.entry_p1.get() or "0,0"); p2 = self.str_to_coords(self.entry_p2.get() or "1000,1000")
            c = {"x_start": min(p1[0], p2[0]), "y_start": min(p1[1], p2[1]), "x_end": max(p1[0], p2[0]), "y_end": max(p1[1], p2[1])}
            w, h = c['x_end']-c['x_start'], c['y_end']-c['y_start']
            if w*h > 25000000 and not messagebox.askyesno("Alerta", "Área gigante. ¿Seguir?"): return
            img = Image.new("RGBA", (w, h)); tx_s, tx_e = c['x_start']//1000, (c['x_end']-1)//1000; ty_s, ty_e = c['y_start']//1000, (c['y_end']-1)//1000
            
            self.root.title(f"Descargando de {target_source}..."); self.root.update()
            
            headers = {'User-Agent': 'Mozilla/5.0'}
            for tx in range(tx_s, tx_e + 1):
                for ty in range(ty_s, ty_e + 1):
                    try: 
                        r = requests.get(f"{base_url}/{tx}/{ty}.png", headers=headers, timeout=2)
                        if r.status_code==200: img.paste(Image.open(BytesIO(r.content)).convert("RGBA"), ((tx*1000)-c['x_start'], (ty*1000)-c['y_start']))
                    except: pass
            self.root.title("WPlace Commander v19.0"); self.preview_image_raw = img; self.zoom_level = 1.0; self.render_image()
        except Exception as e: messagebox.showerror("Error", str(e))

    def zoom(self, f):
        if not self.preview_image_raw: return
        self.zoom_level *= f; self.render_image()
    
    def render_image(self):
        if not self.preview_image_raw: return
        w, h = self.preview_image_raw.size; nw, nh = int(w*self.zoom_level), int(h*self.zoom_level)
        bg = Image.new("RGB", (nw, nh))
        pat = Image.new("RGB", (100, 100))
        for i in range(0, 100, 20):
            for j in range(0, 100, 20): pat.paste(self.checker_tile, (i, j))
        for i in range(0, nw, 100):
            for j in range(0, nh, 100): bg.paste(pat, (i, j))
        resized = self.preview_image_raw.resize((nw, nh), Image.Resampling.NEAREST)
        bg.paste(resized, (0, 0), resized)
        self.tk_image_ref = ImageTk.PhotoImage(bg)
        self.canvas.delete("all"); self.canvas.config(scrollregion=(0, 0, nw, nh)); self.canvas.create_image(0, 0, image=self.tk_image_ref, anchor="nw")

    def snap_local(self):
        if self.preview_image_raw:
            try:
                if not os.path.exists(OUTPUT_FOLDER): os.makedirs(OUTPUT_FOLDER)
                path = f"{OUTPUT_FOLDER}/snap_{datetime.now().strftime('%H%M%S')}.png"
                p1_str = self.entry_p1.get()
                try:
                    p1_x, p1_y = self.str_to_coords(p1_str)
                    meta_data = {
                        "Tl": {"X": p1_x // 1000, "Y": p1_y // 1000},
                        "Px": {"X": p1_x % 1000, "Y": p1_y % 1000}
                    }
                    meta = PngImagePlugin.PngInfo()
                    meta.add_text("Description", json.dumps(meta_data, indent=2))
                    self.preview_image_raw.save(path, "PNG", pnginfo=meta)
                except: self.preview_image_raw.save(path)
                messagebox.showinfo("OK", f"Guardado:\n{path}"); self.abrir_carpeta(OUTPUT_FOLDER)
            except Exception as e: messagebox.showerror("Error", str(e))
        else: messagebox.showwarning("Ops", "Sin preview.")

    def guardar_fav(self):
        n = simpledialog.askstring("Nombre", "Nombre zona:")
        if n: self.config["favorites"][n] = {"p1": self.entry_p1.get(), "p2": self.entry_p2.get()}; self.guardar_config(); self.combo_favs['values'] = list(self.config["favorites"].keys()); self.combo_favs.set(n)
    def del_fav(self):
        n = self.combo_favs.get()
        if n in self.config["favorites"]: del self.config["favorites"][n]; self.guardar_config(); self.combo_favs['values'] = list(self.config["favorites"].keys()); self.combo_favs.set('')
    def cargar_fav(self, e):
        name = self.combo_favs.get(); d = self.config["favorites"].get(name)
        if d: self.entry_p1.delete(0, tk.END); self.entry_p1.insert(0, d['p1']); self.entry_p2.delete(0, tk.END); self.entry_p2.insert(0, d['p2']); self.task_name.delete(0, tk.END); self.task_name.insert(0, name)

    def lanzar(self):
        try:
            p1 = self.str_to_coords(self.entry_p1.get()); p2 = self.str_to_coords(self.entry_p2.get())
            c = {"x_start": min(p1[0], p2[0]), "y_start": min(p1[1], p2[1]), "x_end": max(p1[0], p2[0]), "y_end": max(p1[1], p2[1])}
            data = {
                "name": self.task_name.get(), "coords": c, 
                "source": self.combo_source.get(),
                "save_timelapse": self.chk_time.get(), "sentry": self.chk_sent.get(), 
                "interval": int(self.sp_int.get()), "duration_hours": float(self.sp_dur.get()), 
                "limit_mb": int(self.sp_mb.get()), "alert_pct": float(self.sp_sens.get()), 
                "tg_token": self.et_tok.get(), "tg_chat": self.et_chat.get()
            }
            r = requests.post(f"{self.server_ip.get().rstrip('/')}/tasks/create", json=data, timeout=3)
            if r.status_code==200: tid = r.json()['task_id']; requests.post(f"{self.server_ip.get().rstrip('/')}/tasks/{tid}/start"); messagebox.showinfo("OK", f"Tarea iniciada (ID {tid})"); self.notebook.select(1); self.guardar_config()
            else: messagebox.showerror("Err", r.text)
        except Exception as e: messagebox.showerror("Err", str(e))

    def setup_tab_manager(self):
        f = ttk.LabelFrame(self.tab_manager, text="Estado Global"); f.pack(fill='x', padx=10, pady=5)
        self.lbl_cpu = tk.Label(f, text="CPU: --%", fg="blue", font=("Arial", 10, "bold")); self.lbl_cpu.pack(side='left', padx=20)
        self.lbl_ram = tk.Label(f, text="RAM: --%", fg="green", font=("Arial", 10, "bold")); self.lbl_ram.pack(side='left', padx=20)
        
        self.ctx_menu = Menu(self.root, tearoff=0)
        self.ctx_menu.add_command(label="▶ Reanudar", command=lambda: self.do_act("start"))
        self.ctx_menu.add_command(label="⏸ Pausar/Detener", command=lambda: self.do_act("stop"))
        self.ctx_menu.add_command(label="✏️ Editar Tarea", command=self.open_edit_task_dialog) 
        self.ctx_menu.add_command(label="📥 Descargar Datos", command=self.do_down)
        self.ctx_menu.add_separator()
        self.ctx_menu.add_command(label="🗑 ELIMINAR TAREA", command=lambda: self.do_act("delete"))

        cols = ("ID", "Nombre", "Fuente", "Modos", "Inicio", "Estado", "Fotos", "Restante", "Dif %")
        self.tree = ttk.Treeview(self.tab_manager, columns=cols, show='headings', selectmode='browse')
        for c, w in zip(cols, [40, 180, 80, 120, 100, 80, 60, 80, 80]): self.tree.heading(c, text=c); self.tree.column(c, width=w, anchor="center")
        self.tree.pack(fill='both', expand=True, padx=10, pady=5); self.tree.bind("<Button-3>", lambda e: (self.tree.selection_set(self.tree.identify_row(e.y)), self.ctx_menu.post(e.x_root, e.y_root)) if self.tree.identify_row(e.y) else None)

        bf = ttk.Frame(self.tab_manager); bf.pack(fill='x', padx=10, pady=10)
        ttk.Button(bf, text="▶ START", style="Green.TButton", command=lambda: self.do_act("start")).pack(side='left', padx=2)
        ttk.Button(bf, text="⏸ STOP", style="Blue.TButton", command=lambda: self.do_act("stop")).pack(side='left', padx=2)
        ttk.Button(bf, text="✏️ EDITAR", style="Blue.TButton", command=self.open_edit_task_dialog).pack(side='left', padx=5) 
        ttk.Button(bf, text="📥 ZIP", style="Orange.TButton", command=self.do_down).pack(side='left', padx=2)
        ttk.Button(bf, text="🗑 BORRAR", style="Red.TButton", command=lambda: self.do_act("delete")).pack(side='right', padx=2)

    def open_edit_task_dialog(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Atención", "Selecciona una tarea de la lista para editar.")
            return
            
        item = self.tree.item(selected[0])
        raw_values = item['values']
        if not raw_values:
            messagebox.showwarning("Atención", "No se pudieron obtener los datos de la fila seleccionada.")
            return

        task_id = raw_values[0]
        
        try:
            url = f"{self.server_ip.get().rstrip('/')}/status"
            r = requests.get(url, timeout=5)
            if r.status_code != 200:
                messagebox.showerror("Error", f"Servidor devolvió código {r.status_code}")
                return
                
            tasks_data = r.json().get('tasks', [])
            current_task = None
            for t in tasks_data:
                tid = t.get('id') if t.get('id') is not None else t.get('task_id')
                if str(tid).strip() == str(task_id).strip():
                    current_task = t
                    break

            if not current_task:
                messagebox.showerror("Error", f"No se encontraron los datos de la Tarea #{task_id} en el servidor.")
                return

        except Exception as e:
            messagebox.showerror("Error", f"Error de conexión al consultar tarea: {e}")
            return

        cfg = current_task.get('config', {})

        edit_win = tk.Toplevel(self.root)
        edit_win.title(f"Editar Tarea #{task_id}")
        edit_win.geometry("380x350")
        edit_win.transient(self.root)
        edit_win.grab_set()

        f = ttk.Frame(edit_win, padding=15)
        f.pack(fill='both', expand=True)

        ttk.Label(f, text="Nombre:").grid(row=0, column=0, sticky='w', pady=5)
        entry_name = ttk.Entry(f, width=25)
        entry_name.insert(0, cfg.get('name', current_task.get('name', '')))
        entry_name.grid(row=0, column=1, pady=5)

        ttk.Label(f, text="Intervalo (Min):").grid(row=1, column=0, sticky='w', pady=5)
        entry_interval = ttk.Entry(f, width=25)
        entry_interval.insert(0, str(cfg.get('interval', 1)))
        entry_interval.grid(row=1, column=1, pady=5)

        ttk.Label(f, text="Sensibilidad Alerta (%):").grid(row=2, column=0, sticky='w', pady=5)
        entry_alert = ttk.Entry(f, width=25)
        entry_alert.insert(0, str(cfg.get('alert_pct', 5.0)))
        entry_alert.grid(row=2, column=1, pady=5)

        ttk.Label(f, text="Límite MB:").grid(row=3, column=0, sticky='w', pady=5)
        entry_mb = ttk.Entry(f, width=25)
        entry_mb.insert(0, str(cfg.get('limit_mb', 1000)))
        entry_mb.grid(row=3, column=1, pady=5)

        ttk.Label(f, text="Duración (Horas, 0=Inf):").grid(row=4, column=0, sticky='w', pady=5)
        entry_dur = ttk.Entry(f, width=25)
        entry_dur.insert(0, str(cfg.get('duration_hours', 0)))
        entry_dur.grid(row=4, column=1, pady=5)

        var_timelapse = tk.BooleanVar(value=cfg.get('save_timelapse', True))
        var_sentry = tk.BooleanVar(value=cfg.get('sentry', True))

        chk_time = ttk.Checkbutton(f, text="📷 Activar Timelapse", variable=var_timelapse)
        chk_time.grid(row=5, column=0, columnspan=2, sticky='w', pady=5)

        chk_sent = ttk.Checkbutton(f, text="🛡️ Activar Centinela", variable=var_sentry)
        chk_sent.grid(row=6, column=0, columnspan=2, sticky='w', pady=5)

        def guardar_cambios():
            try:
                payload = {
                    "id": int(task_id),
                    "config": {
                        "name": entry_name.get(),
                        "interval": float(entry_interval.get()),
                        "alert_pct": float(entry_alert.get()),
                        "limit_mb": float(entry_mb.get()),
                        "duration_hours": float(entry_dur.get()),
                        "save_timelapse": var_timelapse.get(),
                        "sentry": var_sentry.get()
                    }
                }
                res = requests.post(f"{self.server_ip.get().rstrip('/')}/tasks/update", json=payload, timeout=5)
                if res.status_code == 200 and res.json().get('status') == 'ok':
                    messagebox.showinfo("Éxito", "¡Tarea actualizada correctamente!")
                    edit_win.destroy()
                    self.refresh()
                else:
                    messagebox.showerror("Error", f"No se pudo guardar: {res.text}")
            except Exception as ex:
                messagebox.showerror("Error", f"Fallo al guardar cambios: {ex}")

        ttk.Button(f, text="💾 GUARDAR CAMBIOS", style="Accent.TButton", command=guardar_cambios).grid(row=7, column=0, columnspan=2, pady=15)

    def do_act(self, act):
        sel = self.tree.selection()
        if sel: 
            try: requests.post(f"{self.server_ip.get().rstrip('/')}/tasks/{self.tree.item(sel[0])['values'][0]}/{act}", timeout=2); self.refresh()
            except: pass
            
    def do_down(self):
        sel = self.tree.selection(); 
        if sel: self.descargar_zip(self.tree.item(sel[0])['values'][0])

    def monitor_loop(self):
        while self.running: 
            try: self.refresh() 
            except: pass
            time.sleep(2)

    def refresh(self):
        try:
            r = requests.get(f"{self.server_ip.get().rstrip('/')}/status", timeout=2)
            r_plan = requests.get(f"{self.server_ip.get().rstrip('/')}/plan/status", timeout=2)
            
            if r.status_code == 200:
                d = r.json()
                p = r_plan.json() if r_plan.status_code == 200 else {"active": False}
                self.root.after(0, lambda: self.upd_ui(d, p))
        except: 
            pass

    def upd_ui(self, d, p):
        sid = None; sel = self.tree.selection()
        if sel: sid = self.tree.item(sel[0])['values'][0]
        self.lbl_cpu.config(text=f"CPU: {d['system']['cpu']}%"); self.lbl_ram.config(text=f"RAM: {d['system']['ram']}%")
        for r in self.tree.get_children(): self.tree.delete(r)
        for t in d['tasks']:
            m = []
            if "T" in t['mode']: m.append("Timelapse")
            if "S" in t['mode']: m.append("Centinela")
            tag = 'run' if t['status']=='running' else 'stop'; 
            if t['status']=='error': tag='err'
            
            source_show = t.get('source', 'WPlace') 
            
            item = self.tree.insert("", "end", values=(t['id'], t['name'], source_show, " + ".join(m) or "Inactivo", t.get('start_str'), t['status'].upper(), t['captures'], t['restante'], t['diff_actual']), tags=(tag,))
            if str(t['id']) == str(sid): self.tree.selection_set(item)
        self.tree.tag_configure('run', foreground='green'); self.tree.tag_configure('err', foreground='red')

        if hasattr(self, 'lbl_plan_res'):
            if p.get("active"):
                config_txt = p.get('config_txt', '')
                if p.get("expired"):
                    estado_completado = f"✅ ¡TIEMPO CUMPLIDO - LISTO PARA PINTAR!\n\n{config_txt}"
                    self.lbl_plan_res.config(text=estado_completado, foreground="#2E7D32")
                else:
                    rest = p['restante']
                    hrs = int(rest // 3600)
                    mins = int((rest % 3600) // 60)
                    estado_vivo = f"⏳ ALERTA ACTIVA EN SERVIDOR: Faltan {hrs}h {mins}m\n\n{config_txt}"
                    self.lbl_plan_res.config(text=estado_vivo, foreground="#1565C0")
            else:
                if "ALERTA ACTIVA" in self.lbl_plan_res.cget("text") or "TIEMPO CUMPLIDO" in self.lbl_plan_res.cget("text"):
                    self.lbl_plan_res.config(text="Ingresa tus datos para generar el plan...", foreground="black")

    def setup_tab_system(self):
        f = ttk.LabelFrame(self.tab_system, text="Gestión Global"); f.pack(fill='both', padx=20, pady=20)
        ttk.Button(f, text="🔍 INSPECCIONAR CAPTURA", style="Accent.TButton", command=self.inspect_file).pack(pady=10, fill='x')
        ttk.Button(f, text="📥 DESCARGAR BACKUP COMPLETO", style="Orange.TButton", command=lambda: self.descargar_zip(None)).pack(pady=10, fill='x')
        ttk.Button(f, text="📂 ABRIR CARPETA LOCAL", style="Blue.TButton", command=lambda: self.abrir_carpeta(OUTPUT_FOLDER)).pack(pady=10, fill='x')
        f2 = ttk.LabelFrame(self.tab_system, text="Zona de Peligro"); f2.pack(fill='x', padx=20, pady=20)
        ttk.Button(f2, text="🧹 ELIMINAR TODAS LAS TAREAS", style="Warning.TButton", command=self.del_all_tasks).pack(side='left', expand=True, padx=5, pady=10)
        ttk.Button(f2, text="🔥 ELIMINAR TODAS LAS FOTOS", style="Red.TButton", command=self.del_all_photos).pack(side='right', expand=True, padx=5, pady=10)

    def inspect_file(self):
        f = filedialog.askopenfilename(title="Seleccionar PNG", filetypes=[("PNG", "*.png")])
        if f:
            try:
                img = Image.open(f); img.load()
                raw_data = img.info.get("Description") or img.text.get("Description")
                if raw_data:
                    json_data = json.loads(raw_data); formatted_json = json.dumps(json_data, indent=2)
                    pyperclip.copy(formatted_json)
                    messagebox.showinfo("Inspección", f"📁 {os.path.basename(f)}\n\n📍 JSON:\n{formatted_json}\n\n✅ Copiado al portapapeles!")
                else: messagebox.showwarning("Aviso", "Sin metadatos JSON.")
            except Exception as e: messagebox.showerror("Error", str(e))

    def descargar_zip(self, tid=None):
        try:
            url = f"{self.server_ip.get().rstrip('/')}/download_zip" + (f"?task_id={tid}" if tid else "")
            r = requests.get(url, stream=True)
            if r.status_code==200:
                if not os.path.exists(OUTPUT_FOLDER): os.makedirs(OUTPUT_FOLDER)
                p = f"{OUTPUT_FOLDER}/{f'task_{tid}' if tid else 'full'}_{datetime.now().strftime('%H%M%S')}.zip"
                with open(p, 'wb') as f: 
                    for chunk in r.iter_content(8192): f.write(chunk)
                messagebox.showinfo("OK", p); self.abrir_carpeta(OUTPUT_FOLDER)
        except Exception as e: messagebox.showerror("Error", str(e))

    def del_all_tasks(self): 
        if messagebox.askyesno("CONFIRMAR", "¿Borrar tareas?"): requests.post(f"{self.server_ip.get().rstrip('/')}/delete_tasks")
    def del_all_photos(self): 
        if messagebox.askyesno("PELIGRO", "¿Borrar fotos?"): requests.post(f"{self.server_ip.get().rstrip('/')}/delete_photos")
    def stop_all(self): requests.post(f"{self.server_ip.get().rstrip('/')}/stop_all")

if __name__ == "__main__":
    root = tk.Tk()
    app = WPlaceClient(root)
    root.mainloop()