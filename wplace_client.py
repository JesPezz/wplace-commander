import tkinter as tk
from tkinter import messagebox, ttk, simpledialog, Menu, filedialog
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

CONFIG_FILE = "client_config.json"
OUTPUT_FOLDER = "wplace_downloads"
TILE_SERVER = "https://backend.wplace.live/files/s0/tiles"

class WPlaceClient:
    def __init__(self, root):
        self.root = root
        self.root.title("WPlace Commander v18.0 (Final Gold)")
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
        
        self.notebook.add(self.tab_new, text="🔭 Misión")
        self.notebook.add(self.tab_manager, text="📡 Radar de Tareas")
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
        if match: return (int(match.group(1)) * 1000) + int(match.group(3)), (int(match.group(2)) * 1000) + int(match.group(4))
        try: parts = text.replace('(', '').replace(')', '').split(','); return int(parts[0]), int(parts[1])
        except: raise ValueError("Formato incorrecto")

    # ================= PESTAÑA 1 =================
    def setup_tab_new(self):
        paned = tk.PanedWindow(self.tab_new, orient=tk.HORIZONTAL, sashwidth=6, sashrelief=tk.RAISED, bg="#d0d0d0")
        paned.pack(fill='both', expand=True)

        left = ttk.Frame(paned, width=400); paned.add(left, minsize=380)
        
        l1 = ttk.LabelFrame(left, text="1. Datos"); l1.pack(fill='x', padx=5, pady=5)
        tk.Label(l1, text="IP:").grid(row=0, column=0, sticky='e'); tk.Entry(l1, textvariable=self.server_ip, width=22).grid(row=0, column=1)
        tk.Label(l1, text="Nombre:").grid(row=1, column=0, sticky='e'); self.task_name = tk.Entry(l1, width=22); self.task_name.grid(row=1, column=1)

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

        l4 = ttk.LabelFrame(left, text="4. Telegram"); l4.pack(fill='x', padx=5, pady=5)
        self.et_tok = tk.Entry(l4, width=35); self.et_tok.pack(pady=2); self.et_tok.insert(0, self.config.get("tg_token", ""))
        self.et_chat = tk.Entry(l4, width=35); self.et_chat.pack(pady=2); self.et_chat.insert(0, self.config.get("tg_chat", ""))

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
        # Crear un tile pequeño para el fondo
        check = Image.new("RGB", (20, 20), "#CCCCCC")
        d = ImageDraw.Draw(check)
        d.rectangle([10,0,20,10], fill="#999999")
        d.rectangle([0,10,10,20], fill="#999999")
        self.checker_tile = check # Lo guardamos para generarlo al tamaño necesario

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
            p1 = self.str_to_coords(self.entry_p1.get() or "0,0"); p2 = self.str_to_coords(self.entry_p2.get() or "1000,1000")
            c = {"x_start": min(p1[0], p2[0]), "y_start": min(p1[1], p2[1]), "x_end": max(p1[0], p2[0]), "y_end": max(p1[1], p2[1])}
            w, h = c['x_end']-c['x_start'], c['y_end']-c['y_start']
            if w*h > 25000000 and not messagebox.askyesno("Alerta", "Área gigante. ¿Seguir?"): return
            img = Image.new("RGBA", (w, h)); tx_s, tx_e = c['x_start']//1000, (c['x_end']-1)//1000; ty_s, ty_e = c['y_start']//1000, (c['y_end']-1)//1000
            self.root.title("Descargando..."); self.root.update()
            for tx in range(tx_s, tx_e + 1):
                for ty in range(ty_s, ty_e + 1):
                    try: 
                        r = requests.get(f"{TILE_SERVER}/{tx}/{ty}.png", timeout=2)
                        if r.status_code==200: img.paste(Image.open(BytesIO(r.content)).convert("RGBA"), ((tx*1000)-c['x_start'], (ty*1000)-c['y_start']))
                    except: pass
            self.root.title("WPlace Commander v18.0"); self.preview_image_raw = img; self.zoom_level = 1.0; self.render_image()
        except Exception as e: messagebox.showerror("Error", str(e))

    def zoom(self, f):
        if not self.preview_image_raw: return
        self.zoom_level *= f; self.render_image()
    
    def render_image(self):
        if not self.preview_image_raw: return
        w, h = self.preview_image_raw.size; nw, nh = int(w*self.zoom_level), int(h*self.zoom_level)
        
        # 1. Generar Fondo Ajedrez al tamaño requerido
        bg = Image.new("RGB", (nw, nh))
        # Rellenar con tiles (método rápido: resize de un patrón grande o loop)
        # Para ser eficiente, creamos patrón de 100x100 y lo copiamos
        pat = Image.new("RGB", (100, 100))
        for i in range(0, 100, 20):
            for j in range(0, 100, 20):
                pat.paste(self.checker_tile, (i, j))
        
        # Tilear el patrón grande
        for i in range(0, nw, 100):
            for j in range(0, nh, 100):
                bg.paste(pat, (i, j))
        
        # 2. Pegar imagen transparente encima
        resized = self.preview_image_raw.resize((nw, nh), Image.Resampling.NEAREST)
        bg.paste(resized, (0, 0), resized)
        
        self.tk_image_ref = ImageTk.PhotoImage(bg)
        self.canvas.delete("all"); self.canvas.config(scrollregion=(0, 0, nw, nh)); self.canvas.create_image(0, 0, image=self.tk_image_ref, anchor="nw")

    def snap_local(self):
        if self.preview_image_raw:
            if not os.path.exists(OUTPUT_FOLDER): os.makedirs(OUTPUT_FOLDER)
            path = f"{OUTPUT_FOLDER}/snap_{datetime.now().strftime('%H%M%S')}.png"
            self.preview_image_raw.save(path); messagebox.showinfo("OK", path); self.abrir_carpeta(OUTPUT_FOLDER)

    # --- FAVORITOS ---
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
            data = {"name": self.task_name.get(), "coords": c, "save_timelapse": self.chk_time.get(), "sentry": self.chk_sent.get(), "interval": int(self.sp_int.get()), "duration_hours": float(self.sp_dur.get()), "limit_mb": int(self.sp_mb.get()), "alert_pct": float(self.sp_sens.get()), "tg_token": self.et_tok.get(), "tg_chat": self.et_chat.get()}
            r = requests.post(f"{self.server_ip.get().rstrip('/')}/tasks/create", json=data, timeout=3)
            if r.status_code==200: tid = r.json()['task_id']; requests.post(f"{self.server_ip.get().rstrip('/')}/tasks/{tid}/start"); messagebox.showinfo("OK", f"Tarea iniciada (ID {tid})"); self.notebook.select(1); self.guardar_config()
            else: messagebox.showerror("Err", r.text)
        except Exception as e: messagebox.showerror("Err", str(e))

    # ================= PESTAÑA 2 =================
    def setup_tab_manager(self):
        f = ttk.LabelFrame(self.tab_manager, text="Estado Global"); f.pack(fill='x', padx=10, pady=5)
        self.lbl_cpu = tk.Label(f, text="CPU: --%", fg="blue", font=("Arial", 10, "bold")); self.lbl_cpu.pack(side='left', padx=20)
        self.lbl_ram = tk.Label(f, text="RAM: --%", fg="green", font=("Arial", 10, "bold")); self.lbl_ram.pack(side='left', padx=20)
        
        self.ctx_menu = Menu(self.root, tearoff=0)
        self.ctx_menu.add_command(label="▶ Reanudar", command=lambda: self.do_act("start"))
        self.ctx_menu.add_command(label="⏸ Pausar/Detener", command=lambda: self.do_act("stop"))
        self.ctx_menu.add_command(label="📥 Descargar Datos", command=self.do_down)
        self.ctx_menu.add_separator()
        self.ctx_menu.add_command(label="🗑 ELIMINAR TAREA", command=lambda: self.do_act("delete"))

        cols = ("ID", "Nombre", "Modos", "Inicio", "Estado", "Fotos", "Restante", "Dif %")
        self.tree = ttk.Treeview(self.tab_manager, columns=cols, show='headings', selectmode='browse')
        for c, w in zip(cols, [40, 200, 150, 100, 80, 60, 80, 80]): self.tree.heading(c, text=c); self.tree.column(c, width=w, anchor="center")
        self.tree.pack(fill='both', expand=True, padx=10, pady=5); self.tree.bind("<Button-3>", lambda e: (self.tree.selection_set(self.tree.identify_row(e.y)), self.ctx_menu.post(e.x_root, e.y_root)) if self.tree.identify_row(e.y) else None)

        bf = ttk.Frame(self.tab_manager); bf.pack(fill='x', padx=10, pady=10)
        ttk.Button(bf, text="▶ START", style="Green.TButton", command=lambda: self.do_act("start")).pack(side='left', padx=2)
        ttk.Button(bf, text="⏸ STOP", style="Blue.TButton", command=lambda: self.do_act("stop")).pack(side='left', padx=2)
        ttk.Button(bf, text="📥 ZIP", style="Orange.TButton", command=self.do_down).pack(side='left', padx=2)
        ttk.Button(bf, text="🗑 BORRAR", style="Red.TButton", command=lambda: self.do_act("delete")).pack(side='right', padx=2)

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
        r = requests.get(f"{self.server_ip.get().rstrip('/')}/status", timeout=2)
        if r.status_code == 200: self.root.after(0, lambda: self.upd_ui(r.json()))

    def upd_ui(self, d):
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
            item = self.tree.insert("", "end", values=(t['id'], t['name'], " + ".join(m) or "Inactivo", t.get('start_str'), t['status'].upper(), t['captures'], t['restante'], t['diff_actual']), tags=(tag,))
            if str(t['id']) == str(sid): self.tree.selection_set(item)
        self.tree.tag_configure('run', foreground='green'); self.tree.tag_configure('err', foreground='red')

    # ================= PESTAÑA 3: SISTEMA =================
    def setup_tab_system(self):
        f = ttk.LabelFrame(self.tab_system, text="Gestión Global"); f.pack(fill='both', padx=20, pady=20)
        ttk.Button(f, text="🔍 INSPECCIONAR CAPTURA (Ver Coordenadas)", style="Accent.TButton", command=self.inspect_file).pack(pady=10, fill='x')
        ttk.Button(f, text="📥 DESCARGAR BACKUP COMPLETO", style="Orange.TButton", command=lambda: self.descargar_zip(None)).pack(pady=10, fill='x')
        ttk.Button(f, text="📂 ABRIR CARPETA LOCAL", style="Blue.TButton", command=lambda: self.abrir_carpeta(OUTPUT_FOLDER)).pack(pady=10, fill='x')
        
        f2 = ttk.LabelFrame(self.tab_system, text="Zona de Peligro"); f2.pack(fill='x', padx=20, pady=20)
        ttk.Button(f2, text="🧹 ELIMINAR TODAS LAS TAREAS (Config)", style="Warning.TButton", command=self.del_all_tasks).pack(side='left', expand=True, padx=5, pady=10)
        ttk.Button(f2, text="🔥 ELIMINAR TODAS LAS FOTOS (Archivos)", style="Red.TButton", command=self.del_all_photos).pack(side='right', expand=True, padx=5, pady=10)

    def inspect_file(self):
        f = filedialog.askopenfilename(title="Seleccionar PNG de WPlace", filetypes=[("PNG", "*.png")])
        if f:
            try:
                img = Image.open(f)
                meta = img.text # Diccionario de metadatos
                
                # Intentamos leer la etiqueta standard o la custom
                coords = meta.get("Description") or meta.get("Coordinates") or "Sin datos de coordenadas"
                
                # Si hay más datos, los mostramos, si no, solo coords
                msg = f"📁 Archivo: {os.path.basename(f)}\n\n📍 {coords}"
                
                # Extra: si hubiera datos viejos
                if "WPlace_TaskName" in meta:
                    msg += f"\n🏷️ Tarea: {meta['WPlace_TaskName']}"

                messagebox.showinfo("Inspección Forense", msg)
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
        if messagebox.askyesno("CONFIRMAR", "¿Borrar TODAS las tareas de la lista? (Las fotos quedan guardadas)"): requests.post(f"{self.server_ip.get().rstrip('/')}/delete_tasks")
    def del_all_photos(self): 
        if messagebox.askyesno("PELIGRO", "¿Borrar TODAS las fotos del disco? (Esto es irreversible)"): requests.post(f"{self.server_ip.get().rstrip('/')}/delete_photos")
    def stop_all(self): requests.post(f"{self.server_ip.get().rstrip('/')}/stop_all")

if __name__ == "__main__":
    root = tk.Tk()
    app = WPlaceClient(root)
    root.mainloop()