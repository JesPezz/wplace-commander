import os, time, json, threading, requests, zipfile, sys
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
        self.start_time_ts = None
        self.captures_count = 0
        self.last_img = None  # Referencia para Centinela
        self.last_saved_timelapse_img = None # Referencia para Timelapse
        self.load_state()

    def log(self, msg):
        # Forzamos flush para ver los logs en tiempo real en journalctl
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"[{timestamp}] {msg}", flush=True)

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
                    self.log("♻️ REANUDANDO TAREA DETECTADA TRAS REINICIO")
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
            requests.post(url, data=data, files=files, timeout=10)
        except Exception as e: self.log(f"Error TG: {e}")

    def calculate_diff(self, img1, img2):
        if img1.size != img2.size: return 100.0
        i1, i2 = img1.convert("RGB"), img2.convert("RGB")
        pairs = zip(i1.getdata(), i2.getdata())
        dif = sum(abs(c1-c2) for p1,p2 in pairs for c1,c2 in zip(p1,p2))
        return (dif / 255.0 * 100) / (i1.size[0] * i1.size[1] * 3)

    def download_area(self, c):
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

    def worker(self):
        self.log(">>> INICIANDO HILO DE TRABAJO (WORKER)")
        
        # 1. Definición de Modos
        modos = []
        if self.config.get('save_timelapse'): modos.append("📷 *Timelapse*")
        if self.config.get('sentry'): modos.append("🛡️ *Centinela*")
        modo_str = " + ".join(modos) if modos else "Ninguno"
        
        # 2. Cálculo de Tiempo (RECUPERADO)
        duracion_h = float(self.config.get('duration_hours', 0))
        if duracion_h > 0 and self.start_time_ts:
            # Usamos TimeStamp para precisión absoluta post-reinicio
            horas_pasadas = (time.time() - self.start_time_ts) / 3600
            restante = max(0, duracion_h - horas_pasadas)
            dur_str = f"{duracion_h}h (Faltan: *{restante:.2f}h*)"
        else:
            dur_str = "♾️ *Indefinida*"

        # 3. Envío de Mensaje Completo
        msg = (
            f"🔄 *Sistema Activo*\n"
            f"🔹 *Modos:* {modo_str}\n"
            f"⏱️ *Tiempo:* {dur_str}\n"
            f"📦 *Capturas previas:* {self.captures_count}"
        )
        self.send_telegram(msg)
        self.log(f"Status enviado. Tiempo: {dur_str}")

        while self.running:
            # Check Tiempo
            if duracion_h > 0 and self.start_time_ts:
                horas_pasadas = (time.time() - self.start_time_ts) / 3600
                if horas_pasadas >= duracion_h:
                    self.send_telegram("🏁 *Tarea Finalizada por Tiempo*")
                    self.running = False; self.save_state(); break

            try:
                self.log("Descargando lienzo actual...")
                current_img = self.download_area(self.config['coords'])

                # --- 🛡️ LÓGICA CENTINELA (FIXED) ---
                if self.config.get('sentry'):
                    if self.last_img is None:
                        self.last_img = current_img.copy()
                        self.log("Centinela: Imagen base establecida.")
                    else:
                        diff = self.calculate_diff(self.last_img, current_img)
                        self.log(f"Centinela: Dif = {diff:.4f}%")
                        
                        if diff >= self.config.get('alert_pct', 5.0):
                            self.log(f"⚠️ ¡ATAQUE DETECTADO! Variación: {diff:.2f}%")
                            path = os.path.join(SENTRY_DIR, "alert.png")
                            current_img.save(path, "PNG")
                            self.send_telegram(f"⚠️ *¡ATAQUE DETECTADO!*\n📉 Variación: `{diff:.2f}%`", path)
                            # ACTUALIZAMOS BASE PARA NO REPETIR ALERTA
                            self.last_img = current_img.copy()

                # --- 📷 LÓGICA TIMELAPSE (SMART) ---
                if self.config.get('save_timelapse'):
                    should_save = False
                    if self.last_saved_timelapse_img is None:
                        should_save = True
                        self.log("Timelapse: Primera foto.")
                    else:
                        diff_t = self.calculate_diff(self.last_saved_timelapse_img, current_img)
                        # Umbral mínimo para evitar basura
                        if diff_t > 0.0001: 
                            should_save = True
                            self.log(f"Timelapse: Cambio detectado ({diff_t:.4f}%)")
                        else:
                            self.log("💤 Timelapse: Sin cambios significativos.")

                    if should_save:
                        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                        path = os.path.join(DATA_DIR, f"cap_{ts}.png")
                        current_img.save(path, "PNG")
                        self.last_saved_timelapse_img = current_img.copy()
                        self.captures_count += 1
                        self.save_state()
                        self.log(f"✅ TIMELAPSE GUARDADO: {path}")

            except Exception as e:
                self.log(f"❌ ERROR: {e}")

            time.sleep(self.config.get('interval', 1) * 60)
        
        self.log(">>> HILO FINALIZADO")

server = WPlaceServer()

@app.route('/start_task', methods=['POST'])
def start():
    server.log("Recibida orden: START")
    server.config = request.json
    server.running = True
    server.start_time_ts = time.time()
    server.captures_count = 0
    server.last_img = None
    server.last_saved_timelapse_img = None
    server.save_state()
    threading.Thread(target=server.worker, daemon=True).start()
    return jsonify({"status": "ok"})

@app.route('/stop_task', methods=['POST'])
def stop():
    server.log("Recibida orden: STOP")
    server.running = False
    server.save_state()
    return jsonify({"status": "stopped"})

@app.route('/status', methods=['GET'])
def status():
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
    app.run(host='0.0.0.0', port=5000, debug=False)