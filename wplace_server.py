import time
import threading
import os
import json
import shutil
import requests
from flask import Flask, request, jsonify, send_file
from PIL import Image, ImageChops, ImageStat
from PIL.PngImagePlugin import PngInfo
from io import BytesIO
from datetime import datetime, timedelta
import hashlib
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

# --- CONFIGURACIÓN ---
STORAGE_DIR = "timelapse_data"
STATE_FILE = "wplace_state.json"
TILE_SIZE = 1000
BASE_URL = "https://backend.wplace.live/files/s0/tiles"
HEADERS = {"User-Agent": "Mozilla/5.0"}

state = {
    "running": False,
    "coords": {},
    "interval": 30,
    "limit_mb": 1000,
    "duration_hours": 24,
    "start_time": None,
    "last_hash": None,
    # --- NUEVO: CONFIG TELEGRAM ---
    "telegram_token": "8484800468:AAET6mXnQKRavmMGlidhoqfKntkFfciYjjo",
    "telegram_chat_id": "6921079409",
    "alert_threshold": 5.0,  # % de cambio para considerar ataque
    "sentry_mode": False
}

# --- UTILIDADES TELEGRAM ---
def send_telegram(msg, warning=False):
    token = state.get("telegram_token")
    chat_id = state.get("telegram_chat_id")
    if not token or not chat_id: return

    prefix = "🚨 <b>ALERTA WPLACE</b> 🚨\n" if warning else "ℹ️ <b>WPlace Info</b>\n"
    text = prefix + msg
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=5)
    except Exception as e:
        print(f"Error Telegram: {e}")

# --- PERSISTENCIA ---
def save_state_to_disk():
    with open(STATE_FILE, 'w') as f: json.dump(state, f)

def load_state_from_disk():
    global state
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                saved = json.load(f)
                state.update(saved)
                if state["running"]:
                    print(">>> Reanudando tarea...")
                    start_thread()
                    send_telegram("🔋 <b>Servidor Reiniciado:</b> Tarea reanudada automáticamente.")
        except Exception as e: print(f"Error carga: {e}")

# --- MOTOR DE CAPTURA ---
def fetch_tile(tx, ty):
    try:
        r = requests.get(f"{BASE_URL}/{tx}/{ty}.png", headers=HEADERS, timeout=8)
        if r.status_code == 200:
            return (tx, ty, Image.open(BytesIO(r.content)).convert("RGBA"))
    except: pass
    return (tx, ty, None)

def calculate_change_percentage(img1, img2):
    """Calcula qué porcentaje de píxeles son diferentes entre dos imágenes"""
    try:
        # Diferencia absoluta
        diff = ImageChops.difference(img1, img2)
        # Si la diferencia es negra pura, no hay cambios.
        if not diff.getbbox(): return 0.0
        
        # Contamos píxeles no negros (que cambiaron)
        # Convertimos a escala de grises para simplificar cálculo
        diff_l = diff.convert('L')
        # Histograma devuelve lista de conteo de píxeles por valor (0-255)
        hist = diff_l.histogram()
        # El valor en el índice 0 son los píxeles negros (sin cambio)
        total_pixels = img1.size[0] * img1.size[1]
        unchanged_pixels = hist[0]
        changed_pixels = total_pixels - unchanged_pixels
        
        return (changed_pixels / total_pixels) * 100.0
    except:
        return 0.0

def worker_timelapse():
    print(">>> [SENTRY] Worker Iniciado")
    send_telegram(f"▶️ <b>Tarea Iniciada</b>\nIntervalo: {state['interval']}m\nModo Centinela: {'ACTIVADO' if state['sentry_mode'] else 'OFF'}")

    try:
        start_dt = datetime.fromisoformat(state["start_time"])
        end_dt = start_dt + timedelta(hours=state["duration_hours"])
    except:
        state["running"] = False; return

    last_image_obj = None # Para comparar cambios visuales

    while state["running"]:
        if datetime.now() >= end_dt:
            print(">>> Tiempo completado.")
            state["running"] = False
            state["last_hash"] = None
            save_state_to_disk()
            send_telegram("✅ <b>Tarea Finalizada</b>\nEl tiempo programado ha concluido.")
            break

        try:
            c = state["coords"]
            x_start, x_end = c["x_start"], c["x_end"]
            y_start, y_end = c["y_start"], c["y_end"]
            width, height = x_end - x_start, y_end - y_start
            
            lienzo = Image.new("RGBA", (width, height))
            tiles_req = [(tx, ty) for tx in range(x_start//TILE_SIZE, (x_end-1)//TILE_SIZE+1) 
                                  for ty in range(y_start//TILE_SIZE, (y_end-1)//TILE_SIZE+1)]

            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(fetch_tile, tx, ty) for tx, ty in tiles_req]
                for f in futures:
                    tx, ty, img = f.result()
                    if img: lienzo.paste(img, ((tx*TILE_SIZE)-x_start, (ty*TILE_SIZE)-y_start), img)

            current_hash = hashlib.md5(lienzo.tobytes()).hexdigest()

            if current_hash != state.get("last_hash"):
                # --- LÓGICA CENTINELA ---
                if state["sentry_mode"] and last_image_obj:
                    percent = calculate_change_percentage(last_image_obj, lienzo)
                    if percent >= state["alert_threshold"]:
                        msg = (f"⚔️ <b>ATAQUE DETECTADO</b>\n"
                               f"Cambio masivo: <b>{percent:.2f}%</b> del lienzo.\n"
                               f"Umbral: {state['alert_threshold']}%\n"
                               f"Hora: {datetime.now().strftime('%H:%M:%S')}")
                        send_telegram(msg, warning=True)
                        print(f"!!! ALERTA: Cambio del {percent:.2f}%")
                
                # Guardar imagen
                if not os.path.exists(STORAGE_DIR): os.makedirs(STORAGE_DIR)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                fname = os.path.join(STORAGE_DIR, f"cap_{ts}.png")
                
                meta = PngInfo()
                meta.add_text("WPlace_Source", c.get("raw_text", ""))
                lienzo.save(fname, pnginfo=meta)
                
                state["last_hash"] = current_hash 
                last_image_obj = lienzo.copy() # Actualizamos referencia visual
                save_state_to_disk() 
                print(f"✅ Cambio guardado: {fname}")
            else:
                print("Sin cambios.")
            
        except Exception as e:
            print(f"Error: {e}")
            send_telegram(f"⚠️ <b>Error en Worker:</b> {str(e)}")

        for _ in range(int(state["interval"] * 60)):
            if not state["running"]: break
            time.sleep(1)

def start_thread():
    threading.Thread(target=worker_timelapse, daemon=True).start()

# --- RUTAS ---
@app.route('/start_task', methods=['POST'])
def start():
    data = request.json
    state.update({
        "coords": data.get("coords"),
        "interval": float(data.get("interval", 30)),
        "duration_hours": float(data.get("duration_hours", 24)),
        "telegram_token": data.get("tg_token", ""),
        "telegram_chat_id": data.get("tg_chat", ""),
        "alert_threshold": float(data.get("alert_pct", 5.0)),
        "sentry_mode": data.get("sentry", False),
        "running": True,
        "start_time": datetime.now().isoformat(),
        "last_hash": None
    })
    save_state_to_disk()
    start_thread()
    return jsonify({"status": "ok"})

@app.route('/stop_task', methods=['POST'])
def stop():
    state["running"] = False
    save_state_to_disk()
    send_telegram("⏹ <b>Tarea Detenida Manualmente</b>")
    return jsonify({"status": "ok"})

@app.route('/status', methods=['GET'])
def get_status():
    c = len(os.listdir(STORAGE_DIR)) if os.path.exists(STORAGE_DIR) else 0
    return jsonify({"running": state["running"], "captures": c, "start_time": state["start_time"], "duration_hours": state["duration_hours"]})

@app.route('/download_zip', methods=['GET'])
def download():
    shutil.make_archive('pack', 'zip', STORAGE_DIR)
    return send_file('pack.zip', as_attachment=True)

@app.route('/clear_data', methods=['POST'])
def clear():
    if os.path.exists(STORAGE_DIR): shutil.rmtree(STORAGE_DIR)
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    if not os.path.exists(STORAGE_DIR): os.makedirs(STORAGE_DIR)
    load_state_from_disk()
    app.run(host='0.0.0.0', port=5000)