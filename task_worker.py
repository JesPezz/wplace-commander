import os, time, json, requests, threading
from datetime import datetime
from PIL import Image
from io import BytesIO

class TaskWorker:
    def __init__(self, task_id, config, data_dir, sentry_dir):
        self.id = task_id
        self.config = config
        self.data_dir = data_dir
        self.sentry_dir = sentry_dir
        
        # Estado
        self.running = False
        self.paused = False
        self.status = "stopped"  # stopped, running, paused, error
        self.start_time_ts = None
        self.captures_count = 0
        self.last_img = None  # Centinela RAM
        self.last_saved_img = None # Timelapse RAM
        self.last_saved_path = None # Persistencia
        self.current_diff = 0.0

        # Cargar persistencia específica de esta tarea
        self.load_persistence()

    def log(self, msg):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [Task {self.id}] {msg}", flush=True)

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
            self.log(f"Error guardando estado: {e}")

    def load_persistence(self):
        f = self.get_persistence_file()
        if os.path.exists(f):
            try:
                with open(f, "r") as file:
                    state = json.load(file)
                    self.captures_count = state.get("captures_count", 0)
                    self.start_time_ts = state.get("start_timestamp")
                    
                    # Recuperar Memoria Visual
                    path = state.get("last_saved_path")
                    if path and os.path.exists(path):
                        self.last_saved_img = Image.open(path).convert("RGBA")
                        self.last_saved_path = path
                        self.log(f"Memoria visual recuperada: {path}")
            except Exception as e:
                self.log(f"Error cargando persistencia: {e}")

    def send_telegram(self, msg, img_path=None):
        token = self.config.get("tg_token")
        chat_id = self.config.get("tg_chat")
        if not token or not chat_id: return
        try:
            method = "sendDocument" if img_path else "sendMessage"
            url = f"https://api.telegram.org/bot{token}/{method}"
            data = {'chat_id': chat_id, 'caption' if img_path else 'text': f"🤖 *Tarea {self.id}*\n{msg}", 'parse_mode': 'Markdown'}
            files = {'document': open(img_path, 'rb')} if img_path else None
            requests.post(url, data=data, files=files, timeout=10)
        except: pass

    def calculate_diff(self, img1, img2):
        if img1.size != img2.size: return 100.0
        i1, i2 = img1.convert("RGB"), img2.convert("RGB")
        pairs = zip(i1.getdata(), i2.getdata())
        dif = sum(abs(c1-c2) for p1,p2 in pairs for c1,c2 in zip(p1,p2))
        return (dif / 255.0 * 100) / (i1.size[0] * i1.size[1] * 3)

    def download_area(self):
        c = self.config['coords']
        w, h = c['x_end']-c['x_start'], c['y_end']-c['y_start']
        full_img = Image.new("RGBA", (w, h))
        tx_s, tx_e = c['x_start']//1000, (c['x_end']-1)//1000
        ty_s, ty_e = c['y_start']//1000, (c['y_end']-1)//1000
        for tx in range(tx_s, tx_e + 1):
            for ty in range(ty_s, ty_e + 1):
                r = requests.get(f"https://backend.wplace.live/files/s0/tiles/{tx}/{ty}.png", timeout=10)
                tile = Image.open(BytesIO(r.content)).convert("RGBA")
                full_img.paste(tile, ((tx*1000)-c['x_start'], (ty*1000)-c['y_start']), tile)
        return full_img

    def run_loop(self):
        self.running = True
        self.status = "running"
        if not self.start_time_ts: self.start_time_ts = time.time()
        
        self.log("Iniciada.")
        self.send_telegram("🚀 Tarea iniciada.")

        while self.running:
            if self.paused:
                self.status = "paused"
                time.sleep(1)
                continue
            
            self.status = "running"
            
            # Control de Tiempo
            duracion = float(self.config.get('duration_hours', 0))
            if duracion > 0:
                elapsed = (time.time() - self.start_time_ts) / 3600
                if elapsed >= duracion:
                    self.stop()
                    self.send_telegram("🏁 Finalizada por tiempo.")
                    break

            try:
                current_img = self.download_area()

                # Lógica Centinela
                if self.config.get('sentry'):
                    if self.last_img is None:
                        self.last_img = current_img.copy()
                    else:
                        diff = self.calculate_diff(self.last_img, current_img)
                        self.current_diff = diff
                        if diff >= self.config.get('alert_pct', 5.0):
                            ts = datetime.now().strftime("%H%M%S")
                            path = os.path.join(self.sentry_dir, f"alert_{self.id}_{ts}.png")
                            current_img.save(path, "PNG")
                            self.send_telegram(f"⚠️ *¡ATAQUE!* Dif: `{diff:.2f}%`", path)
                            self.last_img = current_img.copy()

                # Lógica Timelapse
                if self.config.get('save_timelapse'):
                    should_save = False
                    if self.last_saved_img is None:
                        should_save = True
                    else:
                        diff_t = self.calculate_diff(self.last_saved_img, current_img)
                        if diff_t > 0.0001: should_save = True
                    
                    if should_save:
                        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                        path = os.path.join(self.data_dir, f"cap_{self.id}_{ts}.png")
                        current_img.save(path, "PNG")
                        self.last_saved_img = current_img.copy()
                        self.last_saved_path = path
                        self.captures_count += 1
                        self.save_persistence()
                        self.log(f"Foto guardada: {path}")

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
        restante = "Inf"
        if dur > 0 and self.start_time_ts:
            elapsed = (time.time() - self.start_time_ts) / 3600
            restante = f"{max(0, dur - elapsed):.2f}h"

        return {
            "id": self.id,
            "name": self.config.get("name", "Area"),
            "status": self.status,
            "captures": self.captures_count,
            "restante": restante,
            "diff_actual": f"{self.current_diff:.4f}%"
        }