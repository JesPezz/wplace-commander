import os, time, json, threading, requests, zipfile
from flask import Flask, request, jsonify, send_file
from PIL import Image
from io import BytesIO
from datetime import datetime

app = Flask(__name__)

# --- RUTAS Y ARCHIVOS ---
DATA_DIR = "timelapse_data"
SENTRY_DIR = "sentry_data"
STATE_FILE = "wplace_state.json" # Archivo donde guardaremos el progreso

for d in [DATA_DIR, SENTRY_DIR]:
    if not os.path.exists(d): os.makedirs(d)

class WPlaceServer:
    def __init__(self):
        self.running = False
        self.config = {}
        self.start_time = None
        self.captures_count = 0
        self.last_img = None
        
        # INTENTAR CARGAR ESTADO PREVIO AL INICIAR
        self.load_state()

    def log(self, msg):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    def save_state(self):
        """Guarda la configuración y el progreso actual en un archivo JSON"""
        try:
            state = {
                "running": self.running,
                "config": self.config,
                "captures_count": self.captures_count,
                "start_time": self.start_time.isoformat() if self.start_time else None
            }
            with open(STATE_FILE, "w") as f:
                json.dump(state, f, indent=4)
        except Exception as e:
            self.log(f"Error guardando estado: {e}")

    def load_state(self):
        """Carga el estado del disco y reanuda la tarea si estaba activa"""
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    state = json.load(f)
                    self.running = state.get("running", False)
                    self.config = state.get("config", {})
                    self.captures_count = state.get("captures_count", 0)
                    st = state.get("start_time")
                    self.start_time = datetime.fromisoformat(st) if st else None
                
                if self.running:
                    self.log("♻️ Tarea interrumpida detectada. Reanudando...")
                    threading.Thread(target=self.worker, daemon=True).start()
            except Exception as e:
                self.log(f"Error cargando estado previo: {e}")

    def send_telegram(self, message, image_path=None):
        token = self.config.get("tg_token")
        chat_id = self.config.get("tg_chat")
        if not token or not chat_id: return
        try:
            if image_path:
                url = f"https://api.telegram.org/bot{token}/sendDocument"
                with open(image_path, 'rb') as f:
                    requests.post(url, data={'chat_id': chat_id, 'caption': message, 'parse_mode': 'Markdown'}, files={'document': f})
            else:
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                requests.post(url, data={'chat_id': chat_id, 'text': message, 'parse_mode': 'Markdown'})
        except Exception as e: self.log(f"Error TG: {e}")

    def calculate_diff(self, img1, img2):
        if img1.size != img2.size: return 100.0
        pairs = zip(img1.convert("RGB").getdata(), img2.convert("RGB").getdata())
        dif = sum(abs(c1-c2) for p1,p2 in pairs for c1,c2 in zip(p1,p2))
        return (dif / 255.0 * 100) / (img1.size[0] * img1.size[1] * 3)

    def worker(self):
        modos = []
        if self.config.get('save_timelapse'): modos.append("📷 *Timelapse*")
        if self.config.get('sentry'): modos.append("🛡️ *Centinela*")
        modo_str = " + ".join(modos) if modos else "Ninguno"
        
        duracion = float(self.config.get('duration_hours', 0))
        dur_str = f"{duracion}h" if duracion > 0 else "♾️ *Indefinida*"
        
        # Avisar que se ha reanudado o iniciado
        self.send_telegram(f"🔄 *Sistema Activo*\n\n✅ *Modos:* {modo_str}\n⏱️ *Duración:* {dur_str}\n📦 *Fotos previas:* {self.captures_count}")

        while self.running:
            if duracion > 0:
                elapsed = (datetime.now() - self.start_time).total_seconds() / 3600
                if elapsed >= duracion:
                    self.send_telegram(f"🏁 *Tarea Finalizada*")
                    self.running = False
                    self.save_state()
                    break

            try:
                c = self.config['coords']
                full_img = Image.new("RGBA", (c['x_end']-c['x_start'], c['y_end']-c['y_start']))
                for tx in range(c['x_start']//1000, (c['x_end']-1)//1000 + 1):
                    for ty in range(c['y_start']//1000, (c['y_end']-1)//1000 + 1):
                        r = requests.get(f"https://backend.wplace.live/files/s0/tiles/{tx}/{ty}.png", timeout=10)
                        tile = Image.open(BytesIO(r.content)).convert("RGBA")
                        full_img.paste(tile, ((tx*1000)-c['x_start'], (ty*1000)-c['y_start']), tile)

                # LÓGICA CENTINELA
                if self.config.get('sentry'):
                    if self.last_img is None:
                        self.last_img = full_img.copy()
                    else:
                        diff = self.calculate_diff(self.last_img, full_img)
                        if diff >= self.config.get('alert_pct', 5.0):
                            path = os.path.join(SENTRY_DIR, "alert.png")
                            full_img.save(path, "PNG")
                            self.send_telegram(f"⚠️ *¡ATAQUE DETECTADO!*\n📉 Variación: `{diff:.2f}%`", path)
                            self.last_img = full_img.copy()

                # LÓGICA TIMELAPSE
                if self.config.get('save_timelapse'):
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    path = os.path.join(DATA_DIR, f"cap_{ts}.png")
                    full_img.save(path, "PNG")
                    self.captures_count += 1
                    self.save_state() # Guardamos progreso en cada foto
                    self.log(f"Timelapse: Foto {self.captures_count} guardada")

            except Exception as e: self.log(f"Error: {e}")
            
            time.sleep(self.config.get('interval', 1) * 60)

server = WPlaceServer()

@app.route('/start_task', methods=['POST'])
def start():
    server.config = request.json
    server.running = True
    server.start_time = datetime.now()
    server.captures_count = 0
    server.last_img = None
    server.save_state() # Guardar estado al arrancar
    threading.Thread(target=server.worker, daemon=True).start()
    return jsonify({"status": "ok"})

@app.route('/stop_task', methods=['POST'])
def stop():
    server.running = False
    server.save_state() # Guardar estado al detener
    return jsonify({"status": "stopped"})

@app.route('/status', methods=['GET'])
def status():
    return jsonify({
        "running": server.running, 
        "captures": server.captures_count, 
        "start_time": server.start_time.isoformat() if server.start_time else None
    })

# ... (Resto de rutas download_zip y clear_data igual) ...

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)