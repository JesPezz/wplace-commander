import threading
import time
import random
import requests
import math

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

def pixel_a_url(tile_x, tile_y, x, y, zoom=15.0):
    """Matemática exacta del canvas de WPlace para lat/lng"""
    gx = (tile_x * 1000) + x
    gy = (tile_y * 1000) + y
    map_size = 2048000.0

    lng = (gx / map_size) * 360.0 - 180.0
    n = math.pi * (1.0 - (2.0 * gy / map_size))
    lat = math.degrees(math.atan(math.sinh(n)))

    return f"https://wplace.live/?lat={lat:.15f}&lng={lng:.15f}&zoom={zoom:.2f}"

class SabuesoWorker:
    def __init__(self):
        self.running = False
        self.state = {
            "status": "idle", 
            "progress": "Esperando objetivo...", 
            "result": None,
            "target": None
        }
        self.thread = None

    def start(self, target_id, tile_x, tile_y, x_min, x_max, y_min, y_max):
        if self.running: 
            return False
        
        self.running = True
        self.state = {
            "status": "searching", 
            "progress": "Iniciando rastreo sigiloso...", 
            "result": None, 
            "target": target_id
        }
        self.thread = threading.Thread(
            target=self._search_loop, 
            args=(target_id, tile_x, tile_y, x_min, x_max, y_min, y_max), 
            daemon=True
        )
        self.thread.start()
        return True

    def stop(self):
        self.running = False
        if self.state["status"] == "searching":
            self.state["status"] = "stopped"
            self.state["progress"] = "Búsqueda abortada por el usuario."

    def get_status(self):
        return self.state

    def _search_loop(self, target_id, tile_x, tile_y, x_min, x_max, y_min, y_max):
        puntos = [(x, y) for x in range(x_min, x_max + 1) for y in range(y_min, y_max + 1)]
        random.shuffle(puntos)
        total = len(puntos)
        
        for i, (x, y) in enumerate(puntos, start=1):
            if not self.running: 
                break
            
            url_api = f"https://backend.wplace.live/s0/pixel/{tile_x}/{tile_y}?x={x}&y={y}"
            
            try:
                res = requests.get(url_api, headers=HEADERS, timeout=5)
                if res.status_code == 200:
                    data = res.json()
                    painted_by = data.get("paintedBy", {})
                    uid = painted_by.get("id")
                    uname = painted_by.get("name", "Anónimo")
                    
                    self.state["progress"] = f"[{i}/{total}] Escaneando ({x}, {y}) -> Visto: {uname}"
                    
                    if str(uid) == str(target_id):
                        url_mapa = pixel_a_url(tile_x, tile_y, x, y)
                        self.state["result"] = {
                            "uname": uname,
                            "uid": uid,
                            "coordenadas": f"Tile ({tile_x}, {tile_y}) -> X={x}, Y={y}",
                            "url": url_mapa
                        }
                        self.state["status"] = "found"
                        self.state["progress"] = f"🎯 ¡OBJETIVO LOCALIZADO EN EL INTENTO {i}!"
                        self.running = False
                        return
                        
                elif res.status_code == 429:
                    self.state["progress"] = "⚠️ Rate limit del servidor. Pausando 10s..."
                    time.sleep(10)
                    
            except Exception as e:
                self.state["progress"] = f"⚠️ Error de red en ({x}, {y})"

            # Pausa orgánica
            espera = random.gauss(1.2, 0.4)
            time.sleep(max(0.5, espera))
            
        if self.running:
            self.state["status"] = "not_found"
            self.state["progress"] = "❌ Zona limpia. No se encontró al usuario."
            self.running = False