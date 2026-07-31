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
        
        # Primero cargamos los píxeles pendientes
        self.pending_pixels = self._load_or_init_progress()
        self.scanned_count = 1000000 - len(self.pending_pixels)
        self.total_count = 1000000
        
        self.findings = []
        self.visited_sample = []
        self.threads = []

    def _load_last_config(self):
        """Lee la última configuración de Tile e IDs guardada en disco."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def save_config(self, tile_x, tile_y, target_ids):
        """Guarda los parámetros recibidos para que persistan ante un reinicio."""
        self.tile_x = tile_x
        self.tile_y = tile_y
        self.target_ids = target_ids
        self.state_file = f"progress_tile_{self.tile_x}_{self.tile_y}.json"
        
        config_data = {
            "tile_x": self.tile_x,
            "tile_y": self.tile_y,
            "target_ids": self.target_ids,
            "proxies_list": self.proxies_list
        }
        try:
            with open(self.config_file, "w") as f:
                json.dump(config_data, f, indent=4)
        except Exception:
            pass

    def load_proxies(self):
        self.proxies_list = []
        if os.path.exists(PROXIES_FILE):
            try:
                with open(PROXIES_FILE, "r") as f:
                    for line in f:
                        p = line.strip()
                        if p and not p.startswith("#"):
                            self.proxies_list.append(p)
                log_event(f"🌐 [PROXIES] Cargados {len(self.proxies_list)} proxies desde {PROXIES_FILE}.")
            except Exception as e:
                log_event(f"⚠️ [PROXIES] Error al cargar {PROXIES_FILE}: {e}")
        else:
            log_event("🌐 [PROXIES] No se detectó proxies.txt. Se usará conexión directa de la Pi.")

    def _load_or_init_progress(self):
        """Carga los píxeles pendientes desde disco o genera la lista completa."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    pending = json.load(f)
                log_event(f"💾 [PERSISTENCIA] Avance recuperado de '{self.state_file}'. Píxeles pendientes: {len(pending)}")
                return pending
            except Exception as e:
                log_event(f"⚠️ [PERSISTENCIA] Error al leer archivo de estado ({e}). Generando mapa nuevo.")
        
        log_event("🆕 [PERSISTENCIA] Iniciando nuevo rastreo completo de Tile.")
        initial_pixels = [[x, y] for x in range(1000) for y in range(1000)]
        random.shuffle(initial_pixels)
        return initial_pixels

    def save_progress(self):
        """Guarda la lista de píxeles pendientes actual en disco."""
        with self.lock:
            temp_file = f"{self.state_file}.tmp"
            with open(temp_file, "w") as f:
                json.dump(self.pending_pixels, f)
            os.replace(temp_file, self.state_file)
            log_event(f"💾 [PERSISTENCIA] Avance guardado correctamente. Pendientes: {len(self.pending_pixels)}")

    def _hound_worker(self, hound_id):
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json'
        })
        
        proxy_dict = None
        current_ip = self.local_ip
        if self.proxies_list:
            proxy_url = random.choice(self.proxies_list)
            proxy_dict = {"http": proxy_url, "https": proxy_url}
            current_ip = proxy_url

        log_event(f"🐺 [Sabueso #{hound_id}] Inicializado. Usando IP/Proxy: {current_ip}")
        batches_processed = 0

        while self.running:
            batch = []
            with self.lock:
                if not self.pending_pixels:
                    log_event(f"🏁 [Sabueso #{hound_id}] Sin más píxeles pendientes. Finalizando tarea.")
                    break
                batch_size = min(150, len(self.pending_pixels))
                for _ in range(batch_size):
                    batch.append(self.pending_pixels.pop())

            if not batch:
                break

            batches_processed += 1
            log_event(f"📦 [Sabueso #{hound_id}] Inicia Lote #{batches_processed} ({len(batch)} px)")

            unprocessed_pixels = []

            for x, y in batch:
                if not self.running:
                    unprocessed_pixels.append([x, y])
                    continue

                url_api = f"https://backend.wplace.live/s0/pixel/{self.tile_x}/{self.tile_y}?x={x}&y={y}"

                try:
                    res = session.get(url_api, proxies=proxy_dict, timeout=6)

                    if res.status_code == 200:
                        data = res.json()
                        painted_by = data.get("paintedBy")
                        
                        if not painted_by or painted_by.get("id") is None:
                            user_str = "empty"
                            uid = None
                        else:
                            uname = painted_by.get("name") or "Anónimo"
                            uid = painted_by.get("id")
                            user_str = f"{uname} (ID: {uid})"

                        with self.lock:
                            self.scanned_count += 1
                            if len(self.visited_sample) < 500:
                                self.visited_sample.append([x, y])
                            elif random.random() < 0.1:
                                self.visited_sample[random.randint(0, 499)] = [x, y]

                        log_event(f"🔍 [Sabueso #{hound_id}][Lote #{batches_processed}] Px ({x},{y}) -> {user_str}")

                        if uid and int(uid) in self.target_ids:
                            url_mapa = pixel_a_url(self.tile_x, self.tile_y, x, y)
                            timestamp_str = datetime.now().strftime("%H:%M:%S")
                            hallazgo = {
                                "timestamp": timestamp_str, "user_name": uname,
                                "uid": uid, "x": x, "y": y, "hound_id": hound_id, "link": url_mapa
                            }
                            with self.lock:
                                self.findings.append(hallazgo)
                            log_event(f"🎯 [Sabueso #{hound_id}] ¡HALLAZGO! {uname} en ({x},{y}) | Map: {url_mapa}")
                            self.send_telegram(uname, uid, x, y, url_mapa)

                    elif res.status_code == 429:
                        log_event(f"⚠️ [Sabueso #{hound_id}] Rate Limit (429). Pausa 15s...")
                        unprocessed_pixels.append([x, y])
                        time.sleep(15)
                        if self.proxies_list:
                            proxy_url = random.choice(self.proxies_list)
                            proxy_dict = {"http": proxy_url, "https": proxy_url}
                            current_ip = proxy_url
                            log_event(f"🔄 [Sabueso #{hound_id}] Rotando a nuevo Proxy: {current_ip}")
                    else:
                        unprocessed_pixels.append([x, y])

                except requests.exceptions.ProxyError:
                    log_event(f"⚠️ [Sabueso #{hound_id}] Fallo de red/proxy en Px ({x},{y}). Conservando píxel...")
                    unprocessed_pixels.append([x, y])
                except requests.exceptions.Timeout:
                    log_event(f"⏱️ [Sabueso #{hound_id}] Timeout en Px ({x},{y}). Conservando píxel...")
                    unprocessed_pixels.append([x, y])
                except Exception as ex:
                    log_event(f"❌ [Sabueso #{hound_id}] Error en Px ({x},{y}): {ex}")
                    unprocessed_pixels.append([x, y])

                time.sleep(random.uniform(0.08, 0.18))

            if unprocessed_pixels:
                with self.lock:
                    self.pending_pixels.extend(unprocessed_pixels)

            if self.running:
                sleep_time = round(random.uniform(2.5, 6.0), 2)
                log_event(f"💤 [Sabueso #{hound_id}] Reposo por {sleep_time}s...")
                
                if hound_id == 1:
                    self.save_progress()

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
        if self.running:
            self.stop()

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
        
        # CARGAR AVANCE PREVIO O CREAR NUEVO (Sin sobrescribir si ya existe)
        self.pending_pixels = self._load_or_init_progress()
        self.total_count = 1000000
        self.scanned_count = self.total_count - len(self.pending_pixels)
        
        self.findings = []
        self.visited_sample = []
        self.local_ip = get_public_ip()
        self.load_proxies()
        self.running = True

        log_event(f"🚀 [SISTEMA] Soltando Jauría con {self.num_hounds} Sabuesos.")
        log_event(f"🎯 [SISTEMA] Objetivos a rastrear: {self.target_ids}")
        log_event(f"📍 [SISTEMA] Coordenadas: Tile ({self.tile_x},{self.tile_y}) | Pendientes a rastrear: {len(self.pending_pixels):,} px | Escaneados previamente: {self.scanned_count:,} px")

        self.threads = []
        for i in range(self.num_hounds):
            t = threading.Thread(target=self._hound_worker, args=(i + 1,), daemon=True)
            t.start()
            self.threads.append(t)

    def stop(self):
        self.running = False
        self.save_progress()
        log_event("🛑 [SISTEMA] Orden de detención enviada a la Jauría y avance guardado.")

    def get_status(self):
        with self.lock:
            pct = round((self.scanned_count / self.total_count * 100), 2) if self.total_count > 0 else 0
            return {
                "running": self.running,
                "scanned_count": self.scanned_count,
                "total_count": self.total_count,
                "progress_percentage": pct,
                "findings": list(self.findings),
                "visited_sample": list(self.visited_sample[-300:])
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