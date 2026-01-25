import os, time, json, threading, requests, zipfile
from flask import Flask, request, jsonify, send_file
from PIL import Image
from io import BytesIO
from datetime import datetime

app = Flask(__name__)

# --- RUTAS Y ARCHIVOS ---
DATA_DIR = "timelapse_data"
SENTRY_DIR = "sentry_data"
STATE_FILE = "wplace_state.json"

for d in [DATA_DIR, SENTRY_DIR]:
    if not os.path.exists(d): os.makedirs(d)

class WPlaceServer:
    def __init__(self):
        self.running = False
        self.config = {}
        self.start_time_ts = None # Usaremos Timestamp (float)
        self.captures_count = 0
        self.last_img = None
        self.load_state()

    def log(self, msg):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    def save_state(self):
        try:
            state = {
                "running": self.running,
                "config": self.config,
                "captures_count": self.captures_count,
                "start_timestamp": self.start_time_ts
            }
            with open(STATE_FILE, "w") as f:
                json.dump(state, f, indent=4)
        except Exception as e:
            self.log(f"Error guardando estado: {e}")

    def load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    state = json.load(f)
                    self.running = state.get("running", False)
                    self.config = state.get("config", {})
                    self.captures_count = state.get("captures_count", 0)
                    self.start_time_ts = state.get("start_timestamp")
                
                if self.running:
                    self.log("♻️ Reanudando tarea detectada...")
                    threading.Thread(target=self.worker, daemon=True).start()
            except Exception as e:
                self.log(f"Error cargando estado: {e}")

    def send_telegram(self, message, image_path=None):
        token = self.config.get("tg_token")
        chat_id = self.config.get("tg_chat")
        if not token or not chat_id: return
        try:
            method = "sendDocument" if image_path else "sendMessage"
            url = f"https://api.telegram.org/bot{token}/{method}"
            data = {'chat_id': chat_id, 'caption' if image_path else 'text': message, 'parse_mode': 'Markdown'}
            files = {'document': open(image_path, 'rb')} if image_path else None
            requests.post(url, data=data, files=files)
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
        
        duracion_h = float(self.config.get('duration_hours', 0))
        
        # Cálculo de tiempo restante al (re)iniciar
        if duracion_h > 0 and self.start_time_ts:
            horas_pasadas = (time.time() - self.start_time_ts) / 3600
            restante = max(0, duracion_h - horas_pasadas)
            dur_str = f"{duracion_h}h (Faltan: *{restante:.2f}h*)"
        else:
            dur_str = "♾️ *Indefinida*"

        self.send_telegram(f"🔄 *Sistema Activo*\n\n✅ *Modos:* {modo_str}\n⏱️ *Tiempo:* {dur_str}\n📦 *Capturas:* {self.captures_count}")

        while self.running:
            if duracion_h > 0:
                horas_pasadas = (time.time() - self.start_time_ts) / 3600
                if horas_pasadas >= duracion_h:
                    self.send_telegram(f"🏁 *Tarea Finalizada*\nEl tiempo ha expirado.")
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

                if self.config.get('save_timelapse'):
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    path = os.path.join(DATA_DIR, f"cap_{ts}.png")
                    full_img.save(path, "PNG")
                    self.captures_count += 1
                    self.save_state()
                    self.log(f"Timelapse: Foto {self.captures_count} guardada")

            except Exception as e: self.log(f"Error: {e}")
            time.sleep(self.config.get('interval', 1) * 60)

server = WPlaceServer()

@app.route('/start_task', methods=['POST'])
def start():
    server.config = request.json
    server.running = True
    server.start_time_ts = time.time() # Guardamos inicio exacto
    server.captures_count = 0
    server.last_img = None
    server.save_state()
    threading.Thread(target=server.worker, daemon=True).start()
    return jsonify({"status": "ok"})

@app.route('/stop_task', methods=['POST'])
def stop():
    server.running = False
    server.save_state()
    return jsonify({"status": "stopped"})

@app.route('/status', methods=['GET'])
def status():
    # Cálculo dinámico para el cliente
    return jsonify({
        "running": server.running, 
        "captures": server.captures_count, 
        "start_time": datetime.fromtimestamp(server.start_time_ts).isoformat() if server.start_time_ts else None
    })

@app.route('/download_zip')
def download():
    zip_p = "data.zip"
    with zipfile.ZipFile(zip_p, 'w') as z:
        for f in os.listdir(DATA_DIR): z.write(os.path.join(DATA_DIR, f), f)
    return send_file(zip_p, as_attachment=True)

@app.route('/clear_data', methods=['POST'])
def clear():
    for d in [DATA_DIR, SENTRY_DIR]:
        for f in os.listdir(d): os.remove(os.path.join(d, f))
    return jsonify({"status": "cleared"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)