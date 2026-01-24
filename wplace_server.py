import time
import threading
import os
import json
import shutil
import requests
from flask import Flask, request, jsonify, send_file
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from io import BytesIO
from datetime import datetime, timedelta
import hashlib
from concurrent.futures import ThreadPoolExecutor
last_image_hash = None

app = Flask(__name__)

# --- CONFIGURACIÓN ---
STORAGE_DIR = "timelapse_data"
STATE_FILE = "wplace_state.json"
TILE_SIZE = 1000
BASE_URL = "https://backend.wplace.live/files/s0/tiles"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# Estado Global en Memoria
state = {
    "running": False,
    "coords": {},
    "interval": 30,
    "limit_mb": 1000,
    "duration_hours": 24,    # Nuevo
    "start_time": None,       # Nuevo
    "last_hash": None
}

def save_state_to_disk():
    """Guarda la configuración actual en disco para sobrevivir reinicios"""
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

def load_state_from_disk():
    """Carga configuración y reanuda si estaba corriendo"""
    global state
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                saved = json.load(f)
                state.update(saved)
                # Si estaba corriendo, reanudamos el hilo
                if state["running"]:
                    print(">>> REANUDANDO TAREA TRAS REINICIO...")
                    start_thread()
        except Exception as e:
            print(f"Error cargando estado: {e}")

def check_disk_usage_ok(limit_mb):
    if not os.path.exists(STORAGE_DIR): return True
    total = sum(d.stat().st_size for d in os.scandir(STORAGE_DIR) if d.is_file())
    return (total / (1024 * 1024)) < limit_mb

def fetch_tile(tx, ty):
    """Función auxiliar para descargar un solo tile"""
    try:
        url = f"{BASE_URL}/{tx}/{ty}.png"
        r = requests.get(url, headers=HEADERS, timeout=8)
        if r.status_code == 200:
            # Retornamos las coordenadas y la imagen convertida
            return (tx, ty, Image.open(BytesIO(r.content)).convert("RGBA"))
    except Exception:
        pass
    return (tx, ty, None)

def worker_timelapse():
    print(">>> [SISTEMA] Worker iniciado: Paralelismo Activo + Detección de Cambios")

    # 1. Recuperar info del tiempo (Persistencia de reinicio)
    try:
        start_dt = datetime.fromisoformat(state["start_time"])
        duration_h = state["duration_hours"]
        end_dt = start_dt + timedelta(hours=duration_h)
    except:
        print(">>> [ERROR] Error en formato de tiempo. Abortando worker.")
        state["running"] = False
        return

    while state["running"]:
        # 2. Verificar si el tiempo real ya expiró
        if datetime.now() >= end_dt:
            print(">>> [FIN] Se alcanzó el tiempo límite de la tarea.")
            state["running"] = False
            state["last_hash"] = None 
            save_state_to_disk()
            break

        try:
            c = state["coords"]
            x_start, x_end = c["x_start"], c["x_end"]
            y_start, y_end = c["y_start"], c["y_end"]
            width, height = x_end - x_start, y_end - y_start
            
            lienzo = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            
            # 3. PREPARAR LISTA DE TILES
            t_start_x, t_end_x = x_start // TILE_SIZE, (x_end - 1) // TILE_SIZE
            t_start_y, t_end_y = y_start // TILE_SIZE, (y_end - 1) // TILE_SIZE
            
            tiles_to_download = []
            for tx in range(t_start_x, t_end_x + 1):
                for ty in range(t_start_y, t_end_y + 1):
                    tiles_to_download.append((tx, ty))

            # 4. DESCARGA EN PARALELO (Punto 2)
            # max_workers=10 es un buen equilibrio para una Raspberry Pi
            with ThreadPoolExecutor(max_workers=10) as executor:
                # Disparamos las descargas
                future_results = [executor.submit(fetch_tile, tx, ty) for tx, ty in tiles_to_download]
                
                for future in future_results:
                    tx, ty, tile_img = future.result()
                    if tile_img:
                        # Pegamos el tile en la posición correcta del lienzo
                        paste_x = (tx * TILE_SIZE) - x_start
                        paste_y = (ty * TILE_SIZE) - y_start
                        lienzo.paste(tile_img, (paste_x, paste_y), tile_img)

            # 5. COMPARACIÓN DE CAMBIOS (MD5 sobre bytes puros)
            current_hash = hashlib.md5(lienzo.tobytes()).hexdigest()

            if current_hash == state.get("last_hash"):
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Sin cambios en el área. Omitiendo guardado.")
            else:
                if not os.path.exists(STORAGE_DIR): os.makedirs(STORAGE_DIR)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                fname = os.path.join(STORAGE_DIR, f"cap_{ts}.png")
                
                meta = PngInfo()
                meta.add_text("WPlace_Source", c.get("raw_text", ""))
                lienzo.save(fname, pnginfo=meta)
                
                # Persistimos el hash para el siguiente ciclo o reinicio
                state["last_hash"] = current_hash 
                save_state_to_disk() 
                print(f"✅ [NUEVO] ¡Cambio detectado! Guardado: {fname}")
            
        except Exception as e:
            print(f"!!! [ERROR CRÍTICO] En el loop de captura: {e}")

        # 6. Espera del intervalo con interrupción rápida
        interval_sec = int(state.get("interval", 1) * 60)
        for _ in range(interval_sec):
            if not state["running"]: break
            time.sleep(1)

def start_thread():
    h = threading.Thread(target=worker_timelapse)
    h.daemon = True
    h.start()

# --- ENDPOINTS ---

@app.route('/start_task', methods=['POST'])
def start():
    data = request.json
    if state["running"]: return jsonify({"status": "error", "message": "Ya corre una tarea"}), 400
    
    state["coords"] = data["coords"]
    state["interval"] = int(data["interval_min"])
    state["limit_mb"] = int(data["limit_mb"])
    state["duration_hours"] = float(data.get("duration_hours", 24))
    state["running"] = True
    state["start_time"] = datetime.now().isoformat()
    
    save_state_to_disk() # Persistencia
    start_thread()
    return jsonify({"status": "ok", "message": "Tarea iniciada y persistida"})

@app.route('/stop_task', methods=['POST'])
def stop():
    state["running"] = False
    save_state_to_disk()
    return jsonify({"status": "ok", "message": "Deteniendo tarea..."})

@app.route('/clear_data', methods=['POST'])
def clear():
    if state["running"]: return jsonify({"status": "error", "message": "Detén la tarea antes de borrar"}), 400
    try:
        if os.path.exists(STORAGE_DIR):
            shutil.rmtree(STORAGE_DIR)
            os.makedirs(STORAGE_DIR)
        return jsonify({"status": "ok", "message": "Datos eliminados"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/download_zip', methods=['GET'])
def download():
    shutil.make_archive('timelapse_pack', 'zip', STORAGE_DIR)
    return send_file('timelapse_pack.zip', as_attachment=True)

@app.route('/status', methods=['GET'])
def get_status():
    count = len(os.listdir(STORAGE_DIR)) if os.path.exists(STORAGE_DIR) else 0
    return jsonify({
        "running": state["running"],
        "files_count": count,
        "start_time": state["start_time"]
    })

load_state_from_disk() # Cargar estado al iniciar script

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)