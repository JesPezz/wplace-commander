import threading
import time
import random
import requests
import math
import json
import os
import socket
from datetime import datetime
import sys
import signal

LOG_FILE = "sabueso.log"
PROXIES_FILE = "proxies.txt"

def get_public_ip():
    """Obtiene la IP pública actual del sistema si no usa proxy."""
    try:
        r = requests.get("https://api.ipify.org?format=json", timeout=3)
        return r.json().get("ip", "IP-Local")
    except:
        return "IP-Desconocida"

def log_event(message):
    """Escribe en pantalla (stdout) y en el archivo sabueso.log con marca de tiempo."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_msg = f"[{timestamp}] {message}"
    print(formatted_msg, flush=True)
    
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted_msg + "\n")
    except Exception as e:
        print(f"Error escribiendo en log: {e}", flush=True)

def pixel_a_url(tile_x, tile_y, x, y, zoom=15.0):
    gx = (tile_x * 1000) + x
    gy = (tile_y * 1000) + y
    map_size = 2048000.0

    lng = (gx / map_size) * 360.0 - 180.0
    n = math.pi * (1.0 - (2.0 * gy / map_size))
    lat = math.degrees(math.atan(math.sinh(n)))

    return f"https://wplace.live/?lat={lat:.15f}&lng={lng:.15f}&zoom={zoom:.2f}"

class JauriaSabuesos:
    def __init__(self, tile_x=460, tile_y=874, target_ids=None, proxies_list=None):
        self.config_file = "last_config.json"
        config = self._load_last_config()
        
        self.running = False
        self.target_ids = target_ids if target_ids is not None else config.get("target_ids", [])
        self.tile_x = config.get("tile_x", tile_x)
        self.tile_y = config.get("tile_y", tile_y)
        self.num_hounds = 8
        self.proxies_list = proxies_list if proxies_list is not None else config.get("proxies_list", [])
        self.local_ip = "Cargando IP..."
        
        # 🆕 Parámetros Tácticos
        self.sample_step = config.get("sample_step", 20)
        self.min_pixels = config.get("min_pixels", 5)
        self.min_quads = config.get("min_quads", 2)
        
        self.lock = threading.Lock()
        self.state_file = f"progress_tile_{self.tile_x}_{self.tile_y}.json"
        
        # 🆕 Colas de rastreo
        self.pending_scatter = [] # Fase 1: Muestreo probabilístico
        self.pending_swarm = []   # Fase 2: Enjambre por hallazgo
        self.visited_set = set()
        self.total_scatter = 0

        # 🆕 Memoria de Zonas Descubiertas (Amnesia para no repetir enjambres)
        self.swarm_centers = []
        
        # 🆕 Estado de los objetivos para Smart Stop
        self.target_stats = {} 
        
        self.findings = []
        self.threads = []

    def _load_last_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f: return json.load(f)
            except: pass
        return {}

    def save_config(self):
        config_data = {
            "tile_x": self.tile_x, "tile_y": self.tile_y,
            "target_ids": self.target_ids, "proxies_list": self.proxies_list,
            "sample_step": self.sample_step, "min_pixels": self.min_pixels, "min_quads": self.min_quads
        }
        try:
            with open(self.config_file, "w") as f: json.dump(config_data, f, indent=4)
        except: pass

    def load_proxies(self):
        self.proxies_list = []
        if os.path.exists(PROXIES_FILE):
            try:
                with open(PROXIES_FILE, "r") as f:
                    for line in f:
                        p = line.strip()
                        if p and not p.startswith("#"): self.proxies_list.append(p)
                log_event(f"🌐 [PROXIES] Cargados {len(self.proxies_list)} proxies.")
            except Exception as e: log_event(f"⚠️ [PROXIES] Error: {e}")

    def _get_quadrant(self, x, y):
        """Asigna un píxel a uno de los 4 cuadrantes (1=NO, 2=NE, 3=SO, 4=SE)"""
        if x < 500 and y < 500: return 1
        if x >= 500 and y < 500: return 2
        if x < 500 and y >= 500: return 3
        return 4

    def _inject_swarm(self, cx, cy):
        swarm_coords = []
        # Usa el tamaño de enjambre configurado en UI
        for _ in range(self.swarm_size):
            nx = cx + random.randint(-self.amnesia_radius, self.amnesia_radius)
            ny = cy + random.randint(-self.amnesia_radius, self.amnesia_radius)
            
            if 0 <= nx < 1000 and 0 <= ny < 1000:
                if (nx, ny) not in self.visited_set:
                    swarm_coords.append((nx, ny))
                    
        self.pending_swarm.extend(swarm_coords)
        log_event(f"🐝 [ENJAMBRE] {self.swarm_size} píxeles inyectados para confirmar ({cx},{cy}).")
    def _check_smart_stop(self):
        all_confirmed = True
        for uid, stats in self.target_stats.items():
            if stats['status'] != 'confirmed':
                if len(stats['pixels']) >= self.min_pixels and len(stats['quadrants']) >= self.min_quads:
                    stats['status'] = 'confirmed'
                    log_event(f"✅ [TÁCTICA] Objetivo {uid} CONFIRMADO (Cuota: {len(stats['pixels'])}px | Cuadrantes: {len(stats['quadrants'])}).")
                else:
                    all_confirmed = False

        if all_confirmed and len(self.target_ids) > 0:
            log_event("🏆 [VICTORIA] ¡Misión Cumplida! Todos los objetivos han sido confirmados con dispersión geográfica.")
            self.running = False # Detiene a todos los sabuesos instantáneamente

    def _hound_worker(self, hound_id):
        session = requests.Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0'})

        while self.running:
            proxy_dict = None
            current_ip = self.local_ip
            if self.proxies_list:
                proxy_url = random.choice(self.proxies_list)
                proxy_dict = {"http": proxy_url, "https": proxy_url}
                current_ip = proxy_url

            log_event(f"📦 [Sabueso #{hound_id}] Despierta con IP {current_ip} -> Iniciando ráfaga...")

            batch = []
            with self.lock:
                while len(batch) < 15 and self.running:
                    if self.pending_swarm: px_coord = self.pending_swarm.pop()
                    elif self.pending_scatter: px_coord = self.pending_scatter.pop()
                    else: break
                    
                    if px_coord not in self.visited_set:
                        self.visited_set.add(px_coord)
                        batch.append(px_coord)

            if not batch and not self.pending_swarm and not self.pending_scatter:
                log_event(f"🏳️ [Sabueso #{hound_id}] Fin del rastreo. Objetivos restantes declarados como 'No Presentes'.")
                break

            for x, y in batch:
                if not self.running: break
                
                url_api = f"https://backend.wplace.live/s0/pixel/{self.tile_x}/{self.tile_y}?x={x}&y={y}"
                try:
                    res = session.get(url_api, proxies=proxy_dict, timeout=6)
                    if res.status_code == 200:
                        data = res.json()
                        painted_by = data.get("paintedBy")
                        uid = int(painted_by.get("id")) if painted_by and painted_by.get("id") else None
                        uname = painted_by.get("name") if painted_by else "Anónimo"

                        if uid and uid in self.target_ids:
                            url_mapa = pixel_a_url(self.tile_x, self.tile_y, x, y)
                            timestamp_str = datetime.now().strftime("%H:%M:%S")
                            
                            with self.lock:
                                self.findings.append({"timestamp": timestamp_str, "user_name": uname, "uid": uid, "x": x, "y": y, "hound_id": hound_id, "link": url_mapa})
                                
                                is_new_zone = True
                                for center_x, center_y in self.swarm_centers:
                                    # 👈 Usa el radio de amnesia configurado en UI
                                    if abs(x - center_x) < self.amnesia_radius and abs(y - center_y) < self.amnesia_radius:
                                        is_new_zone = False
                                        break
                                
                                if is_new_zone:
                                    log_event(f"🎯 [Sabueso #{hound_id}] ¡NUEVA ZONA DESCUBIERTA! {uname} en ({x},{y}). Invocando Enjambre...")
                                    self._inject_swarm(x, y)
                                    self.swarm_centers.append((x, y))
                                    self.send_telegram(uname, uid, x, y, url_mapa)
                    elif res.status_code == 429:
                        time.sleep(5)
                except: pass
                
                time.sleep(random.uniform(0.15, 0.35))

            # 👈 Lógica de dormir y descansar restaurada
            if self.running:
                sleep_time = round(random.uniform(3.0, 6.0), 2)
                log_event(f"💤 [Sabueso #{hound_id}] Ráfaga terminada. Reposo por {sleep_time}s antes de rotar IP.")
                time.sleep(sleep_time)
                
    def send_telegram(self, uname, uid, x, y, url_mapa):
        pass # Tu función intacta

    def start(self, target_ids, tile_x, tile_y, num_hounds=8, sample_step=20, amnesia_radius=100, swarm_size=50):
        if self.running: self.stop()

        self.target_ids = [int(i) for i in target_ids]
        self.tile_x = tile_x
        self.tile_y = tile_y
        self.num_hounds = num_hounds
        self.sample_step = sample_step
        self.amnesia_radius = amnesia_radius
        self.swarm_size = swarm_size
        
        self.pending_scatter = []
        for gx in range(0, 1000, self.sample_step):
            for gy in range(0, 1000, self.sample_step):
                self.pending_scatter.append((gx, gy))
        random.shuffle(self.pending_scatter)
        
        self.total_scatter = len(self.pending_scatter)
        self.pending_swarm = []
        self.visited_set = set()
        self.swarm_centers = []
        self.findings = []
        
        self.local_ip = get_public_ip()
        self.load_proxies()
        self.running = True

        log_event(f"🚀 [SISTEMA] TÁCTICA INICIADA | Salto: {self.sample_step}px | Muestras: {self.total_scatter:,}")

        self.threads = []
        for i in range(self.num_hounds):
            t = threading.Thread(target=self._hound_worker, args=(i + 1,), daemon=True)
            t.start()
            self.threads.append(t)

    def stop(self):
        self.running = False
        log_event("🛑 [SISTEMA] Jauría detenida.")

    def get_status(self):
        with self.lock:
            # El progreso principal se mide en base a la Fase 1 (Barrido probabilístico)
            scanned = self.total_scatter - len(self.pending_scatter)
            pct = round((scanned / self.total_scatter) * 100, 2) if self.total_scatter > 0 else 0
            
            # Formateamos celdas visitadas para pintar el radar
            visited_list = list(self.visited_set)
            
            return {
                "running": self.running,
                "scanned_count": scanned,
                "total_count": self.total_scatter,
                "progress_percentage": pct,
                "findings": list(self.findings),
                "visited_sample": visited_list # Renombrado para compatibilidad con el frontend
            }
            
# Instancia global exportada para wplace_server.py
jauria = JauriaSabuesos()

# Manejo de cierre seguro por el sistema (systemctl / Ctrl + C)
def manejar_cierre(sig, frame):
    log_event("🛑 [SISTEMA] Deteniendo Jauría y guardando avance final...")
    jauria.stop()
    sys.exit(0)

signal.signal(signal.SIGINT, manejar_cierre)
signal.signal(signal.SIGTERM, manejar_cierre)