import os, time, json, requests, threading
from datetime import datetime
from PIL import Image, PngImagePlugin
from io import BytesIO

class TaskWorker:
    def __init__(self, task_id, config, data_dir, sentry_dir):
        self.id = task_id
        self.config = config
        self.data_dir = data_dir
        self.sentry_dir = sentry_dir
        
        self.running = False
        self.paused = False
        self.status = "stopped"
        self.start_time_ts = None
        self.captures_count = 0
        self.last_img = None
        self.last_saved_img = None
        self.last_saved_path = None
        self.current_diff = 0.0
        
        self.load_persistence()

    def log(self, msg):
        modos = "T" if self.config.get('save_timelapse') else ""
        modos += "S" if self.config.get('sentry') else ""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [T{self.id}|{modos}] {msg}", flush=True)

    def get_persistence_file(self):
        return f"task_{self.id}_state.json"

    def save_persistence(self):
        try:
            state = {
                "captures_count": self.captures_count,
                "start_timestamp": self.start_time_ts,
                "last_saved_path": self.last_saved_path
            }
            with open(self.get_persistence_file(), "w") as f: 
                json.dump(state, f)
        except Exception as e: 
            self.log(f"Error Persistencia: {e}")

    def load_persistence(self):
        f = self.get_persistence_file()
        if os.path.exists(f):
            try:
                with open(f, "r") as file:
                    state = json.load(file)
                    self.captures_count = state.get("captures_count", 0)
                    self.start_time_ts = state.get("start_timestamp")
                    path = state.get("last_saved_path")
                    if path and os.path.exists(path):
                        self.last_saved_img = Image.open(path).convert("RGBA")
                        self.last_saved_path = path
                        self.log(f"Memoria visual cargada: {path}")
            except: 
                pass

    def save_image_with_metadata(self, img, path):
        c = self.config['coords']
        meta_data = {
            "Tl": {"X": c['x_start'] // 1000, "Y": c['y_start'] // 1000},
            "Px": {"X": c['x_start'] % 1000, "Y": c['y_start'] % 1000}
        }
        meta = PngImagePlugin.PngInfo()
        meta.add_text("Description", json.dumps(meta_data, indent=2))
        img.save(path, "PNG", pnginfo=meta)

    def send_telegram(self, title, details, img_path=None):
        token = self.config.get("tg_token")
        chat_id = self.config.get("tg_chat")
        if not token or not chat_id: 
            return
        
        start_str = datetime.fromtimestamp(self.start_time_ts).strftime('%H:%M') if self.start_time_ts else "--:--"
        dur = float(self.config.get('duration_hours', 0))
        restante_str = "♾️ Infinito"
        if dur > 0 and self.start_time_ts:
            elapsed = (time.time() - self.start_time_ts) / 3600
            rest = max(0, dur - elapsed)
            restante_str = f"{rest:.2f}h"

        modos = []
        if self.config.get('save_timelapse'): modos.append("📷 Timelapse")
        if self.config.get('sentry'): modos.append("🛡️ Centinela")
        
        src = self.config.get('source', 'WPlace')

        caption = (
            f"🤖 *Tarea {self.id} ({src}): {self.config.get('name')}*\n"
            f"{title}\n\n"
            f"⚙️ *Modos:* {' + '.join(modos)}\n"
            f"🕒 *Inicio:* {start_str}\n"
            f"⏳ *Restante:* {restante_str}\n"
            f"📦 *Capturas:* {self.captures_count}\n"
            f"{details}"
        )
        try:
            url = f"https://api.telegram.org/bot{token}/{'sendDocument' if img_path else 'sendMessage'}"
            data = {'chat_id': chat_id, 'caption' if img_path else 'text': caption, 'parse_mode': 'Markdown'}
            files = {'document': open(img_path, 'rb')} if img_path else None
            requests.post(url, data=data, files=files, timeout=10)
        except Exception as e: 
            self.log(f"Error TG: {e}")

    def calculate_diff(self, img1, img2):
        if img1.size != img2.size: 
            return 100.0
        i1, i2 = img1.convert("RGB"), img2.convert("RGB")
        pairs = zip(i1.getdata(), i2.getdata())
        dif = sum(abs(c1-c2) for p1,p2 in pairs for c1,c2 in zip(p1,p2))
        return (dif / 255.0 * 100) / (i1.size[0] * i1.size[1] * 3)

    def download_area(self):
        c = self.config['coords']
        source_target = self.config.get('source', 'WPlace')
        if source_target == 'BPlace':
            base_url = "https://bplace.org/files/s0/tiles"
        else:
            base_url = "https://backend.wplace.live/files/s0/tiles"

        w, h = c['x_end']-c['x_start'], c['y_end']-c['y_start']
        full_img = Image.new("RGBA", (w, h))
        tx_s, tx_e = c['x_start']//1000, (c['x_end']-1)//1000
        ty_s, ty_e = c['y_start']//1000, (c['y_end']-1)//1000
        for tx in range(tx_s, tx_e + 1):
            for ty in range(ty_s, ty_e + 1):
                url = f"{base_url}/{tx}/{ty}.png"
                try:
                    headers = {'User-Agent': 'Mozilla/5.0'}
                    r = requests.get(url, headers=headers, timeout=10)
                    if r.status_code == 200:
                        tile = Image.open(BytesIO(r.content)).convert("RGBA")
                        full_img.paste(tile, ((tx*1000)-c['x_start'], (ty*1000)-c['y_start']), tile)
                except: 
                    pass
        return full_img

    def run_loop(self):
        self.running = True
        self.status = "running"
        if not self.start_time_ts: 
            self.start_time_ts = time.time()
            self.save_persistence()
        
        self.log("INICIANDO LOOP")
        self.send_telegram("🚀 *Iniciada*", "El sistema está monitoreando el objetivo.")

        while self.running:
            if self.paused: 
                self.status = "paused"
                time.sleep(1)
                continue
                
            dur = float(self.config.get('duration_hours', 0))
            if dur > 0 and (time.time() - self.start_time_ts)/3600 >= dur:
                self.stop()
                self.send_telegram("🏁 *Finalizada*", "Tiempo cumplido.")
                break

            try:
                self.save_persistence()
                limit_mb = float(self.config.get('limit_mb', 1000))
                current_mb = sum(os.path.getsize(os.path.join(self.data_dir, f)) for f in os.listdir(self.data_dir)) / (1024*1024)
                if current_mb > limit_mb: 
                    self.stop()
                    self.send_telegram("🛑 *Detenida*", "Límite de MB excedido.")
                    break

                self.log("Descargando...")
                current = self.download_area()

                if self.config.get('sentry'):
                    sens = float(self.config.get('alert_pct', 5.0))
                    if self.last_img is None: 
                        self.last_img = current.copy()
                    else:
                        diff = self.calculate_diff(self.last_img, current)
                        self.current_diff = diff
                        if diff >= sens:
                            path = os.path.join(self.sentry_dir, f"alert_{self.id}.png")
                            self.save_image_with_metadata(current, path)
                            
                            # --- DIAGNÓSTICO MATEMÁTICO DE DAÑO ---
                            c = self.config['coords']
                            ancho = c['x_end'] - c['x_start']
                            alto = c['y_end'] - c['y_start']
                            px_danados = int((ancho * alto) * (diff / 100.0))
                            
                            diag_txt = f"📉 *Variación:* `{diff:.2f}%` (~`{px_danados} px` alterados)\n"
                            
                            if os.path.exists("plan_state.json"):
                                try:
                                    with open("plan_state.json", "r") as f:
                                        p_data = json.load(f)
                                    restante_sec = max(0, p_data['alert_time'] - time.time())
                                    px_obj = p_data['px_objetivo']
                                    px_disp = max(0, px_obj - int(restante_sec / 30))
                                    
                                    diag_txt += f"🔋 *Reserva disponible estimada:* `{px_disp} px`\n"
                                    if px_disp >= px_danados:
                                        diag_txt += "⚡ *Diagnóstico:* ¡Reserva suficiente! Puedes reparar el 100% del daño inmediatamente."
                                    else:
                                        faltan = px_danados - px_disp
                                        hrs_req = round((faltan * 30) / 3600.0, 2)
                                        diag_txt += f"⚠️ *Diagnóstico:* Te faltan `{faltan} px`. Tiempo para recuperar la reserva necesaria: `{hrs_req} hrs`."
                                except Exception:
                                    pass

                            self.send_telegram("⚠️ *¡ATAQUE DETECTADO!*", diag_txt, path)
                            self.last_img = current.copy()
                            self.log(f"ALERTA. Dif: {diff}%")

                if self.config.get('save_timelapse'):
                    should_save = False
                    if self.last_saved_img is None: 
                        should_save = True
                    else:
                        d_t = self.calculate_diff(self.last_saved_img, current)
                        if d_t > 0.0001: 
                            should_save = True
                        else: 
                            self.log("Sin cambios visuales.")

                    if should_save:
                        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                        path = os.path.join(self.data_dir, f"cap_{self.id}_{ts}.png")
                        self.save_image_with_metadata(current, path)
                        self.last_saved_img = current.copy()
                        self.last_saved_path = path
                        self.captures_count += 1
                        self.save_persistence()
                        self.log(f"Guardado: {path}")

            except Exception as e: 
                self.log(f"Error: {e}")
                self.status = "error"
                
            time.sleep(self.config.get('interval', 1) * 60)

    def start(self): 
        threading.Thread(target=self.run_loop, daemon=True).start()
        
    def stop(self): 
        self.running = False
        self.status = "stopped"
        self.save_persistence()
    
    def get_info(self):
        dur = float(self.config.get('duration_hours', 0))
        rest = "Inf"
        if dur > 0 and self.start_time_ts: 
            rest = f"{max(0, dur - (time.time()-self.start_time_ts)/3600):.2f}h"
        m = []
        if self.config.get('save_timelapse'): m.append("T")
        if self.config.get('sentry'): m.append("S")
        return {
            "id": self.id, 
            "name": self.config.get("name"), 
            "source": self.config.get('source', 'WPlace'),
            "mode": "+".join(m),
            "status": self.status, 
            "captures": self.captures_count,
            "restante": rest, 
            "diff_actual": f"{self.current_diff:.4f}%"
        }