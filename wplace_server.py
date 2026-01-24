import os, time, json, threading, requests, zipfile
from flask import Flask, request, jsonify, send_file
from PIL import Image
from io import BytesIO
from datetime import datetime

app = Flask(__name__)

# --- RUTAS ---
DATA_DIR = "timelapse_data"
SENTRY_DIR = "sentry_data"
for d in [DATA_DIR, SENTRY_DIR]:
    if not os.path.exists(d): os.makedirs(d)

class WPlaceServer:
    def __init__(self):
        self.running = False
        self.config = {}
        self.start_time = None
        self.captures_count = 0
        self.last_img = None

    def log(self, msg):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    def send_telegram(self, message, image_path=None):
        token = self.config.get("tg_token")
        chat_id = self.config.get("tg_chat")
        if not token or not chat_id: return
        try:
            if image_path:
                requests.post(f"https://api.telegram.org/bot{token}/sendPhoto", 
                              data={'chat_id': chat_id, 'caption': message}, 
                              files={'photo': open(image_path, 'rb')})
            else:
                requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                              data={'chat_id': chat_id, 'text': message})
        except Exception as e: self.log(f"Error TG: {e}")

    def calculate_diff(self, img1, img2):
        if img1.size != img2.size: return 100.0
        pairs = zip(img1.convert("RGB").getdata(), img2.convert("RGB").getdata())
        dif = sum(abs(c1-c2) for p1,p2 in pairs for c1,c2 in zip(p1,p2))
        return (dif / 255.0 * 100) / (img1.size[0] * img1.size[1] * 3)

    def worker(self):
        modos = []
        if self.config.get('save_timelapse'): modos.append("📷 Timelapse")
        if self.config.get('sentry'): modos.append("🛡️ Centinela")
        
        modo_str = " + ".join(modos) if modos else "Ninguno (Solo Test)"
        duracion = self.config.get('duration_hours', 0)
        dur_str = f"{duracion}h" if duracion > 0 else "♾️ Indefinida"
        
        self.log(f">>> TAREA: {modo_str} | DURACIÓN: {dur_str}")
        self.send_telegram(f"🚀 **Tarea Iniciada**\n🔹 Modos: {modo_str}\n⏱️ Duración: {dur_str}\n🔄 Ciclo: {self.config.get('interval')} min")
        
        while self.running:
            # Lógica de Duración (0 = Infinito)
            if duracion > 0:
                elapsed = (datetime.now() - self.start_time).total_seconds() / 3600
                if elapsed >= duracion:
                    self.send_telegram(f"🏁 **Tarea Finalizada**\nSe cumplió el tiempo programado ({duracion}h).")
                    break

            try:
                # Descargar área (Aseguramos máxima calidad)
                c = self.config['coords']
                full_img = Image.new("RGBA", (c['x_end']-c['x_start'], c['y_end']-c['y_start']))
                
                # ... (Lógica de descarga de tiles igual) ...
                for tx in range(c['x_start']//1000, (c['x_end']-1)//1000 + 1):
                    for ty in range(c['y_start']//1000, (c['y_end']-1)//1000 + 1):
                        r = requests.get(f"https://backend.wplace.live/files/s0/tiles/{tx}/{ty}.png", timeout=10)
                        tile = Image.open(BytesIO(r.content)).convert("RGBA")
                        full_img.paste(tile, ((tx*1000)-c['x_start'], (ty*1000)-c['y_start']), tile)

                # CENTINELA
                if self.config.get('sentry'):
                    if self.last_img is None:
                        self.log("Centinela: Imagen base establecida.")
                        self.last_img = full_img.copy()
                    else:
                        diff = self.calculate_diff(self.last_img, full_img)
                        if diff >= self.config.get('alert_pct', 5.0):
                            self.log(f"¡ALERTA! Cambio: {diff:.2f}%")
                            path = os.path.join(SENTRY_DIR, "alert.png")
                            # Guardamos con calidad máxima antes de enviar
                            full_img.save(path, "PNG", optimize=True)
                            self.send_telegram(f"⚠️ **¡ATAQUE DETECTADO!**\n📉 Variación: {diff:.2f}%\n📍 Coords: {c['x_start']},{c['y_start']}", path)
                            self.last_img = full_img.copy()

                # TIMELAPSE
                if self.config.get('save_timelapse'):
                    # (Lógica de guardado timelapse igual) ...
                    pass

            except Exception as e:
                self.log(f"Error en ciclo: {e}")

            time.sleep(self.config.get('interval', 1) * 60)
        
        self.running = False
        self.save_state()

server = WPlaceServer()

@app.route('/start_task', methods=['POST'])
def start():
    server.config = request.json
    server.running = True
    server.start_time = datetime.now()
    server.captures_count = 0
    server.last_img = None
    threading.Thread(target=server.worker, daemon=True).start()
    return jsonify({"status": "ok"})

@app.route('/stop_task', methods=['POST'])
def stop():
    server.running = False
    return jsonify({"status": "stopped"})

@app.route('/status', methods=['GET'])
def status():
    return jsonify({"running": server.running, "captures": server.captures_count, 
                    "start_time": server.start_time.isoformat() if server.start_time else None})

@app.route('/download_zip')
def download():
    with zipfile.ZipFile("data.zip", 'w') as z:
        for f in os.listdir(DATA_DIR): z.write(os.path.join(DATA_DIR, f), f)
    return send_file("data.zip", as_attachment=True)

@app.route('/clear_data', methods=['POST'])
def clear():
    for d in [DATA_DIR, SENTRY_DIR]:
        for f in os.listdir(d): os.remove(os.path.join(d, f))
    return jsonify({"status": "cleared"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)