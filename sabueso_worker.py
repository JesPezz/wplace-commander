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
        self.xmin = 0
        self.xmax = 999
        self.ymin = 0
        self.ymax = 999
        self.num_hounds = 8
        self.proxies_list = proxies_list if proxies_list is not None else config.get("proxies_list", [])
        self.local_ip = "Cargando IP..."
        
        self.lock = threading.Lock()
        self.state_file = f"progress_tile_{self.tile_x}_{self.tile_y}.json"
        
        # Arquitectura basada en 10,000 Lotes (Celdas de 10x10 px)
        self.total_batches = 10000 
        self.pending_batches = self._load_or_init_progress()
        
        # Calcular los lotes ya completados restando los pendientes del total
        all_batches = set((x, y) for x in range(100) for y in range(100))
        pend_set = set(tuple(b) for b in self.pending_batches)
        self.completed_batches = list(all_batches - pend_set)
        
        self.findings = []
        self.threads = []

    def _load_last_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    return json.load(f)
            except: pass
        return {}

    def save_config(self, tile_x, tile_y, target_ids):
        self.tile_x = tile_x
        self.tile_y = tile_y
        self.target_ids = target_ids
        self.state_file = f"progress_tile_{self.tile_x}_{self.tile_y}.json"
        
        config_data = {
            "tile_x": self.tile_x, "tile_y": self.tile_y,
            "target_ids": self.target_ids, "proxies_list": self.proxies_list
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

    def _load_or_init_progress(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    pending = json.load(f)
                log_event(f"💾 [PERSISTENCIA] Lotes pendientes recuperados: {len(pending)}")
                return pending
            except: pass
        
        log_event("🆕 [PERSISTENCIA] Iniciando nuevo rastreo por Lotes (10,000 bloques).")
        initial_batches = [[gx, gy] for gx in range(100) for gy in range(100)]
        random.shuffle(initial_batches)
        return initial_batches

    def save_progress(self):
        with self.lock:
            temp_file = f"{self.state_file}.tmp"
            with open(temp_file, "w") as f: json.dump(self.pending_batches, f)
            os.replace(temp_file, self.state_file)

    def _hound_worker(self, hound_id):
        session = requests.Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})

        while self.running:
            # 1. ROTAR IP AL DESPERTAR
            proxy_dict = None
            current_ip = self.local_ip
            if self.proxies_list:
                proxy_url = random.choice(self.proxies_list)
                proxy_dict = {"http": proxy_url, "https": proxy_url}
                current_ip = proxy_url

            # 2. TOMAR UN LOTE ÚNICO
            with self.lock:
                if not self.pending_batches:
                    log_event(f"🏁 [Sabueso #{hound_id}] Misión Cumplida. No hay más lotes.")
                    break
                gx, gy = self.pending_batches.pop()

            lote_id = f"{gx}-{gy}"
            log_event(f"📦 [Sabueso #{hound_id}] Despierta con IP {current_ip} -> Inicia Lote Global #{lote_id}")

            target_found = False

            # 3. ESCANEAR LOS 100 PIXELES DEL LOTE (10x10)
            for px in range(10):
                if target_found or not self.running: break
                for py in range(10):
                    if not self.running: break
                    
                    x = (gx * 10) + px
                    y = (gy * 10) + py
                    url_api = f"https://backend.wplace.live/s0/pixel/{self.tile_x}/{self.tile_y}?x={x}&y={y}"

                    try:
                        res = session.get(url_api, proxies=proxy_dict, timeout=6)
                        if res.status_code == 200:
                            data = res.json()
                            painted_by = data.get("paintedBy")
                            uid = painted_by.get("id") if painted_by else None
                            uname = painted_by.get("name") if painted_by else "Anónimo"

                            if uid and int(uid) in self.target_ids:
                                target_found = True
                                url_mapa = pixel_a_url(self.tile_x, self.tile_y, x, y)
                                timestamp_str = datetime.now().strftime("%H:%M:%S")
                                hallazgo = {
                                    "timestamp": timestamp_str, "user_name": uname,
                                    "uid": uid, "x": x, "y": y, "hound_id": hound_id, "link": url_mapa
                                }
                                with self.lock:
                                    self.findings.append(hallazgo)
                                log_event(f"🎯 [Sabueso #{hound_id}] ¡OBJETIVO EN LOTE #{lote_id}! {uname} en ({x},{y})")
                                self.send_telegram(uname, uid, x, y, url_mapa)
                                break # Aborta el resto del lote

                        elif res.status_code == 429:
                            time.sleep(5) # Pequeña pausa si hay rate limit interno
                    except: pass
                    
                    # Pausa segura entre píxeles (0.15 a 0.30 segs)
                    time.sleep(random.uniform(0.15, 0.30))

            # 4. MARCAR LOTE COMO COMPLETADO Y DORMIR
            if self.running:
                with self.lock:
                    self.completed_batches.append([gx, gy])
                
                estado = "🔴 CANCELADO POR HALLAZGO" if target_found else "🟢 LIMPIO"
                sleep_time = round(random.uniform(4.0, 8.0), 2)
                log_event(f"💤 [Sabueso #{hound_id}] Lote #{lote_id} Finalizado ({estado}). Reposo por {sleep_time}s antes de rotar IP.")
                
                if hound_id == 1: self.save_progress()
                time.sleep(sleep_time)

    def send_telegram(self, uname, uid, x, y, url_mapa):
        if os.path.exists("plan_state.json"):
            try:
                with open("plan_state.json", "r") as f:
                    p = json.load(f)
                token = p.get("token")
                chat_id = p.get("chat_id")
                if token and chat_id:
                    msg = (
                        f"🎯 *¡HALLAZGO DE JAURÍA!*\n\n"
                        f"👤 *Usuario:* `{uname}`\n"
                        f"🆔 *ID:* `{uid}`\n"
                        f"📍 *Ubicación:* Tile ({self.tile_x}, {self.tile_y}) -> X={x}, Y={y}\n\n"
                        f"🌐 *Link directo al mapa:*\n{url_mapa}"
                    )
                    url_tg = f"https://api.telegram.org/bot{token}/sendMessage"
                    requests.post(url_tg, json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}, timeout=5)
            except Exception as ex:
                log_event(f"⚠️ Error enviando Telegram: {ex}")

    def start(self, target_ids, tile_x, tile_y, xmin=0, xmax=999, ymin=0, ymax=999, num_hounds=8):
        if self.running: self.stop()

        self.target_ids = [int(i) for i in target_ids]
        self.tile_x = tile_x
        self.tile_y = tile_y
        self.xmin = xmin
        self.xmax = xmax
        self.ymin = ymin
        self.ymax = ymax
        self.num_hounds = num_hounds
        
        # Guardar la última configuración recibida
        self.save_config(self.tile_x, self.tile_y, self.target_ids)
        
        # Asignar archivo de estado para este Tile
        self.state_file = f"progress_tile_{self.tile_x}_{self.tile_y}.json"
        self.pending_batches = self._load_or_init_progress()
        
        all_batches = set((x, y) for x in range(100) for y in range(100))
        pend_set = set(tuple(b) for b in self.pending_batches)
        self.completed_batches = list(all_batches - pend_set)
        
        self.findings = []
        self.local_ip = get_public_ip()
        self.load_proxies()
        self.running = True

        log_event(f"🚀 [SISTEMA] Jauría desplegada. {len(self.pending_batches):,} Lotes pendientes.")

        self.threads = []
        for i in range(self.num_hounds):
            t = threading.Thread(target=self._hound_worker, args=(i + 1,), daemon=True)
            t.start()
            self.threads.append(t)

    def stop(self):
        self.running = False
        self.save_progress()
        log_event("🛑 [SISTEMA] Jauría detenida.")

    def get_status(self):
        with self.lock:
            scanned = len(self.completed_batches)
            pct = round((scanned / self.total_batches) * 100, 2)
            return {
                "running": self.running,
                "scanned_count": scanned,
                "total_count": self.total_batches,
                "progress_percentage": pct,
                "findings": list(self.findings),
                "completed_batches": list(self.completed_batches)
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