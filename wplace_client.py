import tkinter as tk
from tkinter import messagebox, ttk, simpledialog, filedialog
from PIL import Image, ImageTk, ImageOps, ImageDraw
from PIL.PngImagePlugin import PngInfo
import requests
from io import BytesIO
import threading
import re
import os
import json
from datetime import datetime

# ================= CONFIGURACIÓN =================
TILE_SIZE = 1000
BASE_URL = "https://backend.wplace.live/files/s0/tiles"
OUTPUT_FOLDER = "wplace_capturas_local"
CONFIG_FILE = "client_config.json"

class WPlaceClient:
    def __init__(self, root):
        self.root = root
        self.root.title("WPlace Commander v12.1")
        
        if os.path.exists("wplace_icon.ico"):
            try: self.root.iconbitmap("wplace_icon.ico")
            except: pass
            
        self.root.geometry("760x920")
        self.root.resizable(True, True)
        
        self.config = self.cargar_config()

        # Variables
        self.server_ip = tk.StringVar(value=self.config.get("server_ip", "http://192.168.1.107:5000"))
        self.tg_token = tk.StringVar(value=self.config.get("tg_token", ""))
        self.tg_chat = tk.StringVar(value=self.config.get("tg_chat", ""))
        self.mode_timelapse = tk.BooleanVar(value=self.config.get("mode_timelapse", True))
        self.mode_sentry = tk.BooleanVar(value=self.config.get("mode_sentry", False))
        
        self.cycle_interval = tk.StringVar(value=self.config.get("last_interval", "30"))
        self.duration_val = tk.StringVar(value=self.config.get("last_duration", "24"))
        self.duration_unit = tk.StringVar(value="Horas")
        self.limit_mb = tk.StringVar(value=self.config.get("last_limit", "1000"))
        self.alert_threshold = tk.DoubleVar(value=self.config.get("alert_threshold", 5.0))

        self.current_image = None
        self.last_parsed_coords = None 
        self.last_raw_text = ""

        self.setup_ui()
        self.actualizar_estado_remoto()

    def setup_ui(self):
        main_scroll = tk.Frame(self.root)
        main_scroll.pack(fill="both", expand=True, padx=8, pady=5)

        # === 1. MONITOR ===
        status_frame = tk.LabelFrame(main_scroll, text=" Estado del Servidor ", padx=5, pady=2)
        status_frame.pack(fill="x", pady=(0, 5))
        
        frm_mon = tk.Frame(status_frame)
        frm_mon.pack(fill="x")
        self.led_canvas = tk.Canvas(frm_mon, width=25, height=25, highlightthickness=0)
        self.led_canvas.pack(side="left")
        self.led_circle = self.led_canvas.create_oval(5, 5, 20, 20, fill="gray")
        self.status_label = tk.Label(frm_mon, text="Conectando...", font=("Arial", 9, "bold"), fg="#555")
        self.status_label.pack(side="left", padx=5)
        self.captures_label = tk.Label(frm_mon, text="Fotos: 0", font=("Arial", 8))
        self.captures_label.pack(side="right", padx=5)
        self.progress_bar = ttk.Progressbar(status_frame, orient="horizontal", mode="determinate")
        self.progress_bar.pack(fill="x", padx=5, pady=(2, 5))

        # === 2. OBJETIVO ===
        frm_glob = tk.LabelFrame(main_scroll, text=" Configuración de Objetivo ", padx=5, pady=5)
        frm_glob.pack(fill="x", pady=5)
        
        f_url = tk.Frame(frm_glob)
        f_url.pack(fill="x", pady=2)
        tk.Label(f_url, text="URL RPi:").pack(side="left")
        tk.Entry(f_url, textvariable=self.server_ip, bg="#FAFAFA").pack(side="left", fill="x", expand=True, padx=5)
        tk.Button(f_url, text="💾", command=self.guardar_config, width=3).pack(side="left")

        f_fav = tk.Frame(frm_glob)
        f_fav.pack(fill="x", pady=2)
        tk.Label(f_fav, text="Favoritos:").pack(side="left")
        self.combo_favs = ttk.Combobox(f_fav, state="readonly")
        self.combo_favs.pack(side="left", padx=5, fill="x", expand=True)
        self.combo_favs.bind("<<ComboboxSelected>>", self.cargar_favorito)
        self.actualizar_combo_favs()
        tk.Button(f_fav, text="+", command=self.guardar_favorito_dialog, width=3).pack(side="left", padx=1)
        tk.Button(f_fav, text="-", command=self.borrar_favorito, width=3).pack(side="left", padx=1)

        tk.Label(frm_glob, text="A (Inicio):", font=("Arial", 8, "bold")).pack(anchor="w", padx=2)
        self.entry_p1 = tk.Entry(frm_glob, bg="#F0F8FF"); self.entry_p1.pack(fill="x", padx=2, pady=1)
        self.entry_p1.bind("<Double-Button-1>", self.pegar_portapapeles)

        tk.Label(frm_glob, text="B (Fin):", font=("Arial", 8, "bold")).pack(anchor="w", padx=2)
        self.entry_p2 = tk.Entry(frm_glob, bg="#F0F8FF"); self.entry_p2.pack(fill="x", padx=2, pady=1)
        self.entry_p2.bind("<Double-Button-1>", self.pegar_portapapeles)

        # === 3. VISTA PREVIA (DINÁMICA) ===
        tk.Button(main_scroll, text="🔍 Generar Vista Previa", command=self.iniciar_preview, bg="#E0E0E0").pack(pady=5, fill="x")
        
        self.preview_container = tk.Frame(main_scroll, bg="#DCDCDC", relief="sunken", bd=1)
        self.preview_container.pack(pady=2)
        
        self.lbl_preview = tk.Label(self.preview_container, text="Esperando Coordenadas...", bg="#DCDCDC", padx=5, pady=5)
        self.lbl_preview.pack()

        # === 4. PESTAÑAS ===
        self.notebook = ttk.Notebook(main_scroll)
        self.notebook.pack(fill="both", expand=True, pady=5)

        tab_task = tk.Frame(self.notebook)
        self.notebook.add(tab_task, text="🎮 Tareas")

        frm_modes = tk.LabelFrame(tab_task, text=" Modos ", padx=10, pady=5)
        frm_modes.pack(fill="x", padx=10, pady=5)
        f_m1 = tk.Frame(frm_modes); f_m1.pack(fill="x")
        tk.Checkbutton(f_m1, variable=self.mode_timelapse).pack(side="left")
        tk.Label(f_m1, text="📷 TIMELAPSE", font=("Arial", 9, "bold")).pack(side="left")
        f_m2 = tk.Frame(frm_modes); f_m2.pack(fill="x")
        tk.Checkbutton(f_m2, variable=self.mode_sentry).pack(side="left")
        tk.Label(f_m2, text="🛡️ CENTINELA", font=("Arial", 9, "bold")).pack(side="left")

        frm_cyc = tk.LabelFrame(tab_task, text=" Configuración ", padx=10, pady=5)
        frm_cyc.pack(fill="x", padx=10, pady=5)
        
        f_int = tk.Frame(frm_cyc); f_int.pack(fill="x", pady=2)
        tk.Label(f_int, text="Ciclo:").pack(side="left")
        tk.Spinbox(f_int, from_=1, to=1440, width=5, textvariable=self.cycle_interval).pack(side="left", padx=5)
        tk.Label(f_int, text="min").pack(side="left")

        f_dur = tk.Frame(frm_cyc); f_dur.pack(fill="x", pady=2)
        tk.Label(f_dur, text="Duración:").pack(side="left")
        tk.Spinbox(f_dur, from_=1, to=1000, width=5, textvariable=self.duration_val).pack(side="left", padx=5)
        ttk.Combobox(f_dur, values=["Horas", "Minutos"], width=8, state="readonly", textvariable=self.duration_unit).pack(side="left")

        f_sen = tk.Frame(frm_cyc); f_sen.pack(fill="x", pady=2)
        tk.Label(f_sen, text="Sensibilidad:").pack(side="left")
        tk.Scale(f_sen, from_=0.1, to=50.0, orient="horizontal", variable=self.alert_threshold).pack(side="left", fill="x", expand=True, padx=5)

        frm_btn = tk.Frame(tab_task, pady=5); frm_btn.pack()
        tk.Button(frm_btn, text="▶ EJECUTAR", command=self.enviar_orden_rpi, bg="#4CAF50", fg="white", font=("bold"), width=15).pack(pady=5)
        tk.Button(frm_btn, text="⏹ DETENER", command=self.detener_rpi, bg="#F44336", fg="white", font=("bold"), width=15).pack(pady=5)

        tab_tg = tk.Frame(self.notebook)
        self.notebook.add(tab_tg, text="🔔 Telegram")
        frm_tg = tk.LabelFrame(tab_tg, text=" Credenciales ", padx=10, pady=10)
        frm_tg.pack(fill="x", padx=10, pady=20)
        tk.Label(frm_tg, text="Bot Token:").pack(anchor="w")
        tk.Entry(frm_tg, textvariable=self.tg_token).pack(fill="x", pady=(0,10))
        tk.Label(frm_tg, text="Chat ID:").pack(anchor="w")
        tk.Entry(frm_tg, textvariable=self.tg_chat).pack(fill="x")

        tab_man = tk.Frame(self.notebook)
        self.notebook.add(tab_man, text="📂 Gestión")
        frm_rem = tk.LabelFrame(tab_man, text=" Remoto ", padx=10, pady=10)
        frm_rem.pack(fill="x", padx=10, pady=5)
        tk.Button(frm_rem, text="📥 Bajar ZIP", command=self.descargar_zip, bg="#2196F3", fg="white").pack(fill="x", pady=2)
        tk.Button(frm_rem, text="🗑 Borrar RPi", command=self.vaciar_server, bg="#FF9800", fg="white").pack(fill="x", pady=2)
        frm_loc = tk.LabelFrame(tab_man, text=" Local ", padx=10, pady=10)
        frm_loc.pack(fill="x", padx=10, pady=5)
        tk.Button(frm_loc, text="💾 Guardar PNG", command=self.guardar_local).pack(fill="x", pady=2)
        tk.Button(frm_loc, text="🕵️ Inspeccionar", command=self.inspeccionar_png).pack(fill="x", pady=2)

    def crear_fondo_ajedrez(self, w, h, celda=15):
        bg = Image.new("RGBA", (w, h), (220, 220, 220, 255))
        d = ImageDraw.Draw(bg)
        for y in range(0, h, celda):
            for x in range(0, w, celda):
                if (x//celda + y//celda) % 2 == 0:
                    d.rectangle([x,y,x+celda,y+celda], fill=(255,255,255,255))
        return bg

    def iniciar_preview(self):
        self.lbl_preview.config(text="Procesando...", image="")
        threading.Thread(target=self._worker_imagen, daemon=True).start()

    def _worker_imagen(self):
        try:
            t1, t2 = self.entry_p1.get(), self.entry_p2.get()
            def parse(t):
                m = re.search(r"Tl X:\s*(\d+).*Tl Y:\s*(\d+).*Px X:\s*(\d+).*Px Y:\s*(\d+)", t)
                return [int(x) for x in m.groups()] if m else None
            c1, c2 = parse(t1), parse(t2)
            if not c1 or not c2:
                self.root.after(0, lambda: messagebox.showerror("Error", "Coordenadas inválidas"))
                return
            gx1, gy1 = (c1[0]*1000)+c1[2], (c1[1]*1000)+c1[3]
            gx2, gy2 = (c2[0]*1000)+c2[2], (c2[1]*1000)+c2[3]
            xs, xe, ys, ye = min(gx1,gx2), max(gx1,gx2), min(gy1,gy2), max(gy1,gy2)
            self.last_parsed_coords = {"x_start": xs, "x_end": xe, "y_start": ys, "y_end": ye, "raw_text": t1}
            self.last_raw_text = t1 
            w, h = xe-xs, ye-ys
            lienzo = Image.new("RGBA", (w, h), (0,0,0,0))
            tx_s, tx_e = xs//1000, (xe-1)//1000
            ty_s, ty_e = ys//1000, (ye-1)//1000
            for tx in range(tx_s, tx_e+1):
                for ty in range(ty_s, ty_e+1):
                    try:
                        r = requests.get(f"{BASE_URL}/{tx}/{ty}.png", timeout=5)
                        if r.status_code==200:
                            tile = Image.open(BytesIO(r.content)).convert("RGBA")
                            lienzo.paste(tile, ((tx*1000)-xs, (ty*1000)-ys), tile)
                    except: pass
            self.current_image = lienzo
            MAX_SCREEN_W, MAX_SCREEN_H = 680, 350
            if w > MAX_SCREEN_W or h > MAX_SCREEN_H:
                ratio = min(MAX_SCREEN_W/w, MAX_SCREEN_H/h)
                new_w, new_h = int(w*ratio), int(h*ratio)
                thumb = lienzo.resize((new_w, new_h), Image.Resampling.LANCZOS)
            else:
                new_w, new_h = w, h
                thumb = lienzo.copy()
            fondo = self.crear_fondo_ajedrez(new_w, new_h)
            final = Image.alpha_composite(fondo, thumb)
            self.root.after(0, lambda: self._mostrar_imagen(final))
        except Exception as e:
             self.root.after(0, lambda: messagebox.showerror("Error Preview", str(e)))

    def _mostrar_imagen(self, img):
        self.tk_img = ImageTk.PhotoImage(img)
        self.lbl_preview.config(image=self.tk_img, text="")

    def enviar_orden_rpi(self):
        if not self.last_parsed_coords:
            messagebox.showwarning("!", "Genera vista previa primero.")
            return
        self.guardar_config()
        # --- FIX SINTAXIS LÍNEA 256 ---
        val = float(self.duration_val.get())
        horas = val / 60.0 if self.duration_unit.get() == "Minutos" else val

        payload = {
            "coords": self.last_parsed_coords, "interval": int(self.cycle_interval.get()),
            "limit_mb": int(self.limit_mb.get()), "duration_hours": horas,
            "tg_token": self.tg_token.get(), "tg_chat": self.tg_chat.get(),
            "sentry": self.mode_sentry.get(), "alert_pct": self.alert_threshold.get(),
            "save_timelapse": self.mode_timelapse.get()
        }
        try:
            r = requests.post(f"{self.server_ip.get().rstrip('/')}/start_task", json=payload, timeout=3)
            messagebox.showinfo("RPi", r.json().get("status", "OK"))
        except Exception as e: messagebox.showerror("Error", str(e))

    def inspeccionar_png(self):
        f = filedialog.askopenfilename(filetypes=[("PNG", "*.png")])
        if f:
            try:
                img = Image.open(f)
                meta = img.text
                key = "WPlace_Source"
                msg = "METADATOS:\n"
                if key in meta:
                    self.root.clipboard_clear()
                    self.root.clipboard_append(meta[key])
                    self.root.update()
                    msg += f"✅ COPIADO:\n{meta[key]}\n\n"
                msg += "-"*20 + "\n" + "\n".join([f"{k}: {v}" for k,v in meta.items()])
                messagebox.showinfo("Inspector", msg)
            except Exception as e: messagebox.showerror("Error", str(e))

    def guardar_local(self):
        if self.current_image:
            if not os.path.exists(OUTPUT_FOLDER): os.makedirs(OUTPUT_FOLDER)
            p = f"{OUTPUT_FOLDER}/local_{datetime.now().strftime('%H%M%S')}.png"
            info = PngInfo()
            if self.last_raw_text: info.add_text("WPlace_Source", self.last_raw_text)
            self.current_image.save(p, pnginfo=info)
            messagebox.showinfo("Guardado", f"Imagen guardada:\n{p}")

    def cargar_config(self):
        defaults = {"favorites": {}}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f: defaults.update(json.load(f))
            except: pass
        return defaults

    def guardar_config(self):
        self.config.update({
            "server_ip": self.server_ip.get(), "last_interval": self.cycle_interval.get(),
            "last_limit": self.limit_mb.get(), "last_duration": self.duration_val.get(),
            "tg_token": self.tg_token.get(), "tg_chat": self.tg_chat.get(),
            "mode_timelapse": self.mode_timelapse.get(), "mode_sentry": self.mode_sentry.get(),
            "alert_threshold": self.alert_threshold.get(), "favorites": self.config.get("favorites", {})
        })
        try:
            with open(CONFIG_FILE, "w") as f: json.dump(self.config, f, indent=4)
        except: pass

    def actualizar_estado_remoto(self):
        def check():
            try:
                r = requests.get(f"{self.server_ip.get().rstrip('/')}/status", timeout=2)
                if r.status_code == 200:
                    d = r.json()
                    col = "#4CAF50" if d["running"] else "#FF9800"
                    txt = "EJECUTANDO" if d["running"] else "EN ESPERA"
                    prog = 0
                    if d["running"] and d.get("start_time"):
                        start = datetime.fromisoformat(d["start_time"])
                        dur = float(d.get("duration_hours", 24))
                        curr = (datetime.now() - start).total_seconds()
                        if (dur*3600) > 0: prog = min(100, max(0, (curr/(dur*3600))*100))
                    self.root.after(0, lambda: self.ui_update(col, txt, d.get("captures", 0), prog))
                else: self.root.after(0, lambda: self.ui_update("red", "ERROR", 0, 0))
            except: self.root.after(0, lambda: self.ui_update("red", "OFFLINE", 0, 0))
            self.root.after(3000, self.actualizar_estado_remoto)
        threading.Thread(target=check, daemon=True).start()

    def ui_update(self, col, txt, caps, prog):
        self.led_canvas.itemconfig(self.led_circle, fill=col)
        self.status_label.config(text=txt, fg=col if col != "gray" else "#555")
        self.captures_label.config(text=f"Fotos: {caps}")
        self.progress_bar["value"] = prog

    def guardar_favorito_dialog(self):
        n = simpledialog.askstring("Guardar", "Nombre:")
        if n:
            self.config["favorites"][n] = {"p1": self.entry_p1.get(), "p2": self.entry_p2.get()}
            self.guardar_config(); self.actualizar_combo_favs()

    def borrar_favorito(self):
        n = self.combo_favs.get()
        if n in self.config["favorites"]:
            del self.config["favorites"][n]
            self.guardar_config(); self.actualizar_combo_favs()

    def actualizar_combo_favs(self):
        self.combo_favs['values'] = list(self.config["favorites"].keys())

    def cargar_favorito(self, e):
        d = self.config["favorites"].get(self.combo_favs.get())
        if d:
            self.entry_p1.delete(0,tk.END); self.entry_p1.insert(0, d['p1'])
            self.entry_p2.delete(0,tk.END); self.entry_p2.insert(0, d['p2'])

    def pegar_portapapeles(self, event):
        try: event.widget.delete(0, tk.END); event.widget.insert(0, self.root.clipboard_get())
        except: pass

    def detener_rpi(self):
        try: requests.post(f"{self.server_ip.get().rstrip('/')}/stop_task")
        except: pass
    def descargar_zip(self):
        try:
            r = requests.get(f"{self.server_ip.get().rstrip('/')}/download_zip", stream=True)
            if r.status_code == 200:
                if not os.path.exists(OUTPUT_FOLDER): os.makedirs(OUTPUT_FOLDER)
                p = f"{OUTPUT_FOLDER}/pack_{datetime.now().strftime('%H%M%S')}.zip"
                with open(p, 'wb') as f:
                    for chunk in r.iter_content(8192): f.write(chunk)
                messagebox.showinfo("OK", f"Guardado: {p}")
        except: pass
    def vaciar_server(self):
        if messagebox.askyesno("Confirma", "¿Borrar fotos RPi?"): requests.post(f"{self.server_ip.get().rstrip('/')}/clear_data")

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = WPlaceClient(root)
        root.mainloop()
    except Exception as e: messagebox.showerror("Error", str(e))