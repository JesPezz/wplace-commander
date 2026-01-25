import tkinter as tk
from tkinter import messagebox, ttk, simpledialog, Menu
from PIL import Image, ImageTk, ImageDraw
import requests
from io import BytesIO
import threading
import time
import json
import os
import subprocess
import platform
import re
from datetime import datetime

# ================= CONFIGURACIÓN =================
CONFIG_FILE = "client_config.json"
OUTPUT_FOLDER = "wplace_downloads"
TILE_SERVER = "https://backend.wplace.live/files/s0/tiles"

class WPlaceClient:
    def __init__(self, root):
        self.root = root
        self.root.title("WPlace Commander v16.0 (Ultimate)")
        self.root.geometry("1200x800")
        
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Treeview", rowheight=25, font=('Segoe UI', 9))
        style.configure("Treeview.Heading", font=('Segoe UI', 10, 'bold'))
        style.configure("TButton", font=('Segoe UI', 9))
        style.configure("Accent.TButton", font=('Segoe UI', 10, 'bold'), background="#2196F3", foreground="white")
        style.configure("Danger.TButton", font=('Segoe UI', 9, 'bold'), background="#F44336", foreground="white")
        style.configure("Warning.TButton", font=('Segoe UI', 9, 'bold'), background="#FF9800", foreground="white")
        
        self.config = self.cargar_config()
        self.server_ip = tk.StringVar(value=self.config.get("server_ip", "http://192.168.1.107:5000"))
        
        # Estado Visual
        self.click_count = 0
        self.preview_image_raw = None # Imagen PIL original
        self.tk_image_ref = None
        self.zoom_level = 1.0
        
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.tab_new = ttk.Frame(self.notebook)
        self.tab_manager = ttk.Frame(self.notebook)
        self.tab_system = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_new, text="🔭 Misión")
        self.notebook.add(self.tab_manager, text="📋 Radar")
        self.notebook.add(self.tab_system, text="⚙️ Sistema")
        
        self.setup_tab_new()
        self.setup_tab_manager()
        self.setup_tab_system()
        
        self.running = True
        threading.Thread(target=self.monitor_loop, daemon=True).start()

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
        if match:
            tl_x, tl_y, px_x, px_y = map(int, match.groups())
            return (tl_x * 1000) + px_x, (tl_y * 1000) + px_y
        try:
            parts = text.replace('(', '').replace(')', '').split(',')
            return int(parts[0]), int(parts[1])
        except: raise ValueError("Coord Error")

    # ================= PESTAÑA 1: NUEVA TAREA =================
    def setup_tab_new(self):
        paned = tk.PanedWindow(self.tab_new, orient=tk.HORIZONTAL, sashwidth=6, sashrelief=tk.RAISED, bg="#d0d0d0")
        paned.pack(fill='both', expand=True)

        # --- CONTROLES ---
        left = ttk.Frame(paned, width=400)
        paned.add(left, minsize=380)
        
        # 1. Info General
        l1 = ttk.LabelFrame(left, text="1. Datos Básicos")
        l1.pack(fill='x', padx=5, pady=5)
        tk.Label(l1, text="IP:").grid(row=0, column=0, sticky='e'); tk.Entry(l1, textvariable=self.server_ip, width=20).grid(row=0, column=1)
        tk.Label(l1, text="Nombre:").grid(row=1, column=0, sticky='e'); 
        self.task_name = tk.Entry(l1, width=20); self.task_name.grid(row=1, column=1); self.task_name.insert(0, "Objetivo Alpha")

        # 2. Coordenadas
        l2 = ttk.LabelFrame(left, text="2. Coordenadas")
        l2.pack(fill='x', padx=5, pady=5)
        tk.Label(l2, text="P1:").grid(row=0, column=0); self.entry_p1 = tk.Entry(l2, width=32); self.entry_p1.grid(row=0, column=1, pady=2)
        tk.Label(l2, text="P2:").grid(row=1, column=0); self.entry_p2 = tk.Entry(l2, width=32); self.entry_p2.grid(row=1, column=1, pady=2)
        
        # Favoritos
        f_fav = ttk.Frame(l2)
        f_fav.grid(row=2, column=0, columnspan=2, pady=5)
        self.combo_favs = ttk.Combobox(f_fav, width=18, state="readonly", values=list(self.config["favorites"].keys()))
        self.combo_favs.pack(side='left'); self.combo_favs.bind("<<ComboboxSelected>>", self.cargar_fav)
        ttk.Button(f_fav, text="💾", width=3, command=self.guardar_fav).pack(side='left', padx=2)
        ttk.Button(f_fav, text="🗑", width=3, command=self.del_fav).pack(side='left', padx=2)

        # 3. Modos y Parametros
        l3 = ttk.LabelFrame(left, text="3. Configuración Avanzada")
        l3.pack(fill='x', padx=5, pady=5)
        
        self.chk_time = tk.BooleanVar(value=True)
        self.chk_sent = tk.BooleanVar(value=False)
        ttk.Checkbutton(l3, text="Timelapse", variable=self.chk_time).grid(row=0, column=0, sticky='w')
        ttk.Checkbutton(l3, text="Centinela", variable=self.chk_sent).grid(row=0, column=1, sticky='w')

        # Grid de parametros
        tk.Label(l3, text="Intervalo (min):").grid(row=1, column=0, sticky='e')
        self.sp_int = ttk.Spinbox(l3, from_=1, to=120, width=6); self.sp_int.set(1); self.sp_int.grid(row=1, column=1, sticky='w')
        
        tk.Label(l3, text="Duración (h):").grid(row=2, column=0, sticky='e')
        self.sp_dur = ttk.Spinbox(l3, from_=0, to=48, width=6); self.sp_dur.set(0); self.sp_dur.grid(row=2, column=1, sticky='w')
        
        tk.Label(l3, text="Límite MB:").grid(row=3, column=0, sticky='e')
        self.sp_mb = ttk.Spinbox(l3, from_=100, to=5000, width=6); self.sp_mb.set(1000); self.sp_mb.grid(row=3, column=1, sticky='w')

        tk.Label(l3, text="Sensibilidad %:").grid(row=4, column=0, sticky='e')
        self.sp_sens = ttk.Spinbox(l3, from_=0.1, to=50, width=6, increment=0.1); self.sp_sens.set(5.0); self.sp_sens.grid(row=4, column=1, sticky='w')

        # 4. Telegram
        l4 = ttk.LabelFrame(left, text="4. Telegram (Opc)")
        l4.pack(fill='x', padx=5, pady=5)
        self.et_tok = tk.Entry(l4, width=35); self.et_tok.pack(pady=2); self.et_tok.insert(0, self.config.get("tg_token", ""))
        self.et_chat = tk.Entry(l4, width=35); self.et_chat.pack(pady=2); self.et_chat.insert(0, self.config.get("tg_chat", ""))

        ttk.Button(left, text="🚀 INICIAR TAREA", style="Accent.TButton", command=self.lanzar).pack(fill='x', padx=10, pady=15, ipady=5)

        # --- VISUALIZACION ---
        right = ttk.LabelFrame(paned, text="Visor Táctico")
        paned.add(right, minsize=400, stretch="always")
        
        # Toolbar
        tool = ttk.Frame(right)
        tool.pack(fill='x', pady=2)
        ttk.Button(tool, text="📷 Cargar Vista", command=self.preview).pack(side='left', padx=2)
        ttk.Button(tool, text="💾 Guardar PNG", command=self.snap_local).pack(side='left', padx=2)
        ttk.Button(tool, text="➕ Zoom In", command=lambda: self.zoom(1.2)).pack(side='right', padx=2)
        ttk.Button(tool, text="➖ Zoom Out", command=lambda: self.zoom(0.8)).pack(side='right', padx=2)

        # Canvas con fondo ajedrez (simulado con color oscuro)
        self.canvas = tk.Canvas(right, bg="#303030", cursor="cross") # Grid oscuro para resaltar PNGs
        sx = ttk.Scrollbar(right, orient="horizontal", command=self.canvas.xview)
        sy = ttk.Scrollbar(right, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=sx.set, yscrollcommand=sy.set)
        sx.pack(side="bottom", fill="x"); sy.pack(side="right", fill="y"); self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self.map_click)
        
        # Generar patrón de ajedrez (checkerboard)
        self.create_checkerboard()

    def create_checkerboard(self):
        # Creamos una imagen pequeña de 20x20 con patrón gris/oscuro
        check = Image.new("RGB", (20, 20), "#404040")
        d = ImageDraw.Draw(check)
        d.rectangle([0,0,10,10], fill="#303030")
        d.rectangle([10,10,20,20], fill="#303030")
        self.bg_pattern = ImageTk.PhotoImage(check)
        # Se usará para "tilar" el fondo si es necesario, pero un BG fijo suele bastar

    # --- FUNCIONES VISUALES ---
    def map_click(self, e):
        # Ajustar coords según zoom y scroll
        cx = self.canvas.canvasx(e.x)
        cy = self.canvas.canvasy(e.y)
        
        real_x = int(cx / self.zoom_level)
        real_y = int(cy / self.zoom_level)
        
        txt = self.coords_to_str(real_x, real_y)
        if self.click_count % 2 == 0: self.entry_p1.delete(0, tk.END); self.entry_p1.insert(0, txt)
        else: self.entry_p2.delete(0, tk.END); self.entry_p2.insert(0, txt)
        self.click_count += 1
        
        # Dibujar marcador ajustado al zoom
        r = 5 * self.zoom_level
        self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r, outline="#00FF00", width=2, tags="marker")

    def preview(self):
        try:
            p1 = self.str_to_coords(self.entry_p1.get() or "0,0")
            p2 = self.str_to_coords(self.entry_p2.get() or "1000,1000")
            c = {"x_start": min(p1[0], p2[0]), "y_start": min(p1[1], p2[1]), "x_end": max(p1[0], p2[0]), "y_end": max(p1[1], p2[1])}
            
            w, h = c['x_end']-c['x_start'], c['y_end']-c['y_start']
            if w*h > 25000000 and not messagebox.askyesno("Alerta", "Área gigante. ¿Seguir?"): return

            img = Image.new("RGBA", (w, h))
            tx_s, tx_e = c['x_start']//1000, (c['x_end']-1)//1000
            ty_s, ty_e = c['y_start']//1000, (c['y_end']-1)//1000
            
            self.root.title("Descargando..."); self.root.update()
            for tx in range(tx_s, tx_e + 1):
                for ty in range(ty_s, ty_e + 1):
                    try:
                        r = requests.get(f"{TILE_SERVER}/{tx}/{ty}.png", timeout=2)
                        if r.status_code == 200:
                            tile = Image.open(BytesIO(r.content)).convert("RGBA")
                            img.paste(tile, ((tx*1000)-c['x_start'], (ty*1000)-c['y_start']), tile)
                    except: pass
            
            self.root.title("WPlace Commander v16.0")
            self.preview_image_raw = img
            self.zoom_level = 1.0
            self.render_image()
            
        except Exception as e: messagebox.showerror("Error", str(e))

    def zoom(self, factor):
        if not self.preview_image_raw: return
        self.zoom_level *= factor
        self.render_image()

    def render_image(self):
        if not self.preview_image_raw: return
        w, h = self.preview_image_raw.size
        nw, nh = int(w*self.zoom_level), int(h*self.zoom_level)
        
        # Resizing de alta calidad
        img_resized = self.preview_image_raw.resize((nw, nh), Image.Resampling.NEAREST)
        self.tk_image_ref = ImageTk.PhotoImage(img_resized)
        
        self.canvas.delete("all")
        # Centrar imagen si es pequeña
        self.canvas.config(scrollregion=(0, 0, nw, nh))
        self.canvas.create_image(0, 0, image=self.tk_image_ref, anchor="nw")

    def snap_local(self):
        if self.preview_image_raw:
            if not os.path.exists(OUTPUT_FOLDER): os.makedirs(OUTPUT_FOLDER)
            path = f"{OUTPUT_FOLDER}/snap_{datetime.now().strftime('%H%M%S')}.png"
            self.preview_image_raw.save(path)
            messagebox.showinfo("OK", path); self.abrir_carpeta(OUTPUT_FOLDER)

    # --- FAVORITOS ---
    def guardar_fav(self):
        n = simpledialog.askstring("Nombre", "Nombre zona:")
        if n: 
            self.config["favorites"][n] = {"p1": self.entry_p1.get(), "p2": self.entry_p2.get()}
            self.guardar_config(); self.combo_favs['values'] = list(self.config["favorites"].keys())
            self.combo_favs.set(n)
    def del_fav(self):
        n = self.combo_favs.get()
        if n in self.config["favorites"]: 
            del self.config["favorites"][n]; self.guardar_config()
            self.combo_favs['values'] = list(self.config["favorites"].keys()); self.combo_favs.set('')
    def cargar_fav(self, e):
        d = self.config["favorites"].get(self.combo_favs.get())
        if d: self.entry_p1.delete(0, tk.END); self.entry_p1.insert(0, d['p1']); self.entry_p2.delete(0, tk.END); self.entry_p2.insert(0, d['p2'])

    # --- LANZAR ---
    def lanzar(self):
        try:
            p1 = self.str_to_coords(self.entry_p1.get()); p2 = self.str_to_coords(self.entry_p2.get())
            c = {"x_start": min(p1[0], p2[0]), "y_start": min(p1[1], p2[1]), "x_end": max(p1[0], p2[0]), "y_end": max(p1[1], p2[1])}
            
            data = {
                "name": self.task_name.get(), "coords": c,
                "save_timelapse": self.chk_time.get(), "sentry": self.chk_sent.get(),
                "interval": int(self.sp_int.get()), "duration_hours": float(self.sp_dur.get()),
                "limit_mb": int(self.sp_mb.get()), "alert_pct": float(self.sp_sens.get()),
                "tg_token": self.et_tok.get(), "tg_chat": self.et_chat.get()
            }
            r = requests.post(f"{self.server_ip.get().rstrip('/')}/tasks/create", json=data, timeout=3)
            if r.status_code==200:
                tid = r.json()['task_id']
                requests.post(f"{self.server_ip.get().rstrip('/')}/tasks/{tid}/start")
                self.notebook.select(1); self.guardar_config()
            else: messagebox.showerror("Err", r.text)
        except Exception as e: messagebox.showerror("Err", str(e))

    # ================= PESTAÑA 2: RADAR =================
    def setup_tab_manager(self):
        f = ttk.LabelFrame(self.tab_manager, text="Estado Global")
        f.pack(fill='x', padx=10, pady=5)
        self.lbl_cpu = tk.Label(f, text="CPU: --%", fg="blue", font=("Arial", 10, "bold"))
        self.lbl_cpu.pack(side='left', padx=20)
        self.lbl_ram = tk.Label(f, text="RAM: --%", fg="green", font=("Arial", 10, "bold"))
        self.lbl_ram.pack(side='left', padx=20)
        
        # MENU CONTEXTUAL
        self.context_menu = Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="📥 Descargar datos de esta tarea", command=self.descargar_tarea_individual)
        self.context_menu.add_command(label="🗑 Eliminar tarea", command=lambda: self.control_task("delete"))

        cols = ("ID", "Nombre", "Modo", "Estado", "Fotos", "Restante")
        self.tree = ttk.Treeview(self.tab_manager, columns=cols, show='headings', selectmode='browse')
        for c in cols: self.tree.heading(c, text=c); self.tree.column(c, anchor="center")
        self.tree.column("Nombre", width=200, anchor="w")
        self.tree.pack(fill='both', expand=True, padx=10, pady=5)
        self.tree.bind("<Button-3>", self.show_context_menu) # Click derecho

        bf = ttk.Frame(self.tab_manager)
        bf.pack(fill='x', padx=10, pady=10)
        ttk.Button(bf, text="▶ START", command=lambda: self.control_task("start")).pack(side='left')
        ttk.Button(bf, text="⏸ STOP", command=lambda: self.control_task("stop")).pack(side='left', padx=5)
        ttk.Button(bf, text="🗑 BORRAR", command=lambda: self.control_task("delete")).pack(side='right')

    def show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

    def descargar_tarea_individual(self):
        sel = self.tree.selection()
        if not sel: return
        tid = self.tree.item(sel[0])['values'][0]
        self.descargar_zip(tid)

    def control_task(self, act):
        sel = self.tree.selection()
        if sel:
            tid = self.tree.item(sel[0])['values'][0]
            try: requests.post(f"{self.server_ip.get().rstrip('/')}/tasks/{tid}/{act}"); self.refresh()
            except: pass

    def monitor_loop(self):
        while self.running:
            try: self.refresh()
            except: pass
            time.sleep(2)

    def refresh(self):
        try:
            r = requests.get(f"{self.server_ip.get().rstrip('/')}/status", timeout=1)
            if r.status_code==200: self.root.after(0, lambda: self.upd_ui(r.json()))
        except: pass

    def upd_ui(self, d):
        self.lbl_cpu.config(text=f"CPU: {d['system']['cpu']}%")
        self.lbl_ram.config(text=f"RAM: {d['system']['ram']}%")
        
        for r in self.tree.get_children(): self.tree.delete(r)
        for t in d['tasks']:
            tag = 'run' if t['status']=='running' else 'stop'
            if t['status']=='error': tag='err'
            self.tree.insert("", "end", values=(t['id'], t['name'], t['mode'], t['status'].upper(), t['captures'], t['restante']), tags=(tag,))
        self.tree.tag_configure('run', foreground='green'); self.tree.tag_configure('err', foreground='red')

    # ================= PESTAÑA 3: SISTEMA =================
    def setup_tab_system(self):
        f = ttk.LabelFrame(self.tab_system, text="Gestión de Datos")
        f.pack(fill='both', padx=20, pady=20)
        
        ttk.Button(f, text="📥 DESCARGAR ZIP COMPLETO (Todas las tareas)", style="Accent.TButton", command=lambda: self.descargar_zip(None)).pack(pady=10, fill='x')
        ttk.Button(f, text="⚠️ VACIAR SERVIDOR (Borrar Todo)", style="Warning.TButton", command=self.vaciar_server).pack(pady=10, fill='x')
        
        f2 = ttk.LabelFrame(self.tab_system, text="Control Crítico")
        f2.pack(fill='x', padx=20, pady=20)
        ttk.Button(f2, text="🛑 APAGADO DE EMERGENCIA", style="Danger.TButton", command=self.stop_all).pack(pady=10)

    def descargar_zip(self, tid=None):
        try:
            url = f"{self.server_ip.get().rstrip('/')}/download_zip"
            if tid: url += f"?task_id={tid}"
            
            r = requests.get(url, stream=True)
            if r.status_code==200:
                if not os.path.exists(OUTPUT_FOLDER): os.makedirs(OUTPUT_FOLDER)
                name = f"task_{tid}" if tid else "full_backup"
                path = f"{OUTPUT_FOLDER}/{name}_{datetime.now().strftime('%H%M%S')}.zip"
                with open(path, 'wb') as f: 
                    for chunk in r.iter_content(8192): f.write(chunk)
                messagebox.showinfo("OK", path); self.abrir_carpeta(OUTPUT_FOLDER)
        except Exception as e: messagebox.showerror("Err", str(e))

    def stop_all(self):
        if messagebox.askyesno("Confirmar", "Detener todo?"): requests.post(f"{self.server_ip.get().rstrip('/')}/stop_all")
    def vaciar_server(self):
        if messagebox.askyesno("PELIGRO", "¿Borrar TODAS las fotos y tareas de la Raspberry?"): 
            requests.post(f"{self.server_ip.get().rstrip('/')}/clear_all")
            messagebox.showinfo("Hecho", "Servidor formateado.")

if __name__ == "__main__":
    root = tk.Tk()
    app = WPlaceClient(root)
    root.mainloop()