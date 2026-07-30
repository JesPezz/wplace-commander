import threading
import time
import random
import requests
import math
import os
import json

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

STATE_FILE = "sabueso_state.json"

# =========================================================
# 🌐 CONFIGURACIÓN DE TU POOL DE PROXIES RESIDENCIALES
# =========================================================
PROXY_CONFIG_FILE = "proxy_config.json"

def get_proxy_config():
    """Carga credenciales desde un archivo local fuera de Git."""
    if os.path.exists(PROXY_CONFIG_FILE):
        try:
            with open(PROXY_CONFIG_FILE, "r") as f:
                cfg = json.load(f)
                if cfg.get("enabled", False):
                    user = cfg.get("user", "")
                    password = cfg.get("pass", "")
                    host = cfg.get("host", "")
                    port = cfg.get("port", "")
                    proxy_url = f"http://{user}:{password}@{host}:{port}"
                    return {
                        "http": proxy_url,
                        "https": proxy_url
                    }
        except Exception as e:
            print(f"[Sabueso Proxy Error]: No se pudo cargar el archivo de proxies: {e}")
    return None

# Carga dinámica al iniciar o ejecutar la tarea
PROXIES_CONFIG = get_proxy_config()


def pixel_a_url(tile_x, tile_y, x, y, zoom=15.0):
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
        self.thread = None
        self.state = {
            "status": "idle",
            "progress": "En espera de objetivos...",
            "findings": [],
            "scanned_count": 0,
            "total_count": 0
        }
        self.load_state()

    def send_telegram(self, tg_token, tg_chat, msg):
        if not tg_token or not tg_chat:
            return
        try:
            url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
            requests.post(url, json={"chat_id": tg_chat, "text": msg, "parse_mode": "Markdown"}, timeout=10)
        except Exception as e:
            print(f"[Sabueso TG Error]: {e}")

    def save_state(self, visited_set, config):
        try:
            data = {
                "config": config,
                "visited": list(visited_set),
                "findings": self.state["findings"],
                "status": self.state["status"]
            }
            with open(STATE_FILE, "w") as f:
                json.dump(data, f)
        except Exception as e:
            print(f"[Sabueso Save Error]: {e}")

    def load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    data = json.load(f)
                    self.state["status"] = data.get("status", "idle")
                    self.state["findings"] = data.get("findings", [])
            except:
                pass

    def start(self, target_ids, tile_x, tile_y, x_min=0, x_max=999, y_min=0, y_max=999, continuous=True, tg_token=None, tg_chat=None):
        if self.running:
            return False

        # Convertir a lista de strings
        if isinstance(target_ids, (int, str)):
            target_ids = [str(target_ids)]
        else:
            target_ids = [str(i).strip() for i in target_ids]

        self.running = True
        config = {
            "target_ids": target_ids,
            "tile_x": tile_x,
            "tile_y": tile_y,
            "x_min": x_min, "x_max": x_max,
            "y_min": y_min, "y_max": y_max,
            "continuous": continuous,
            "tg_token": tg_token,
            "tg_chat": tg_chat
        }

        self.state["status"] = "searching"
        self.state["progress"] = f"Iniciando rastreo de {len(target_ids)} objetivo(s)..."

        self.thread = threading.Thread(target=self._search_loop, args=(config,), daemon=True)
        self.thread.start()
        return True

    def stop(self):
        self.running = False
        if self.state["status"] == "searching":
            self.state["status"] = "stopped"
            self.state["progress"] = "Rastreo pausado por el usuario."

    def get_status(self):
        return self.state

    def _search_loop(self, config):
        visited = set()
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    saved_data = json.load(f)
                    if saved_data.get("config", {}).get("tile_x") == config["tile_x"] and \
                       saved_data.get("config", {}).get("tile_y") == config["tile_y"]:
                        visited = set(tuple(p) for p in saved_data.get("visited", []))
            except:
                pass

        all_points = [(x, y) for x in range(config["x_min"], config["x_max"] + 1)
                            for y in range(config["y_min"], config["y_max"] + 1)]
        
        self.state["total_count"] = len(all_points)

        while self.running:
            pending = [p for p in all_points if p not in visited]
            self.state["scanned_count"] = len(visited)

            if not pending:
                self.state["status"] = "completed"
                self.state["progress"] = f"✅ Área totalmente explorada ({len(visited)} px). Encontrados: {len(self.state['findings'])}"
                self.running = False
                break

            # Reordenar de forma aleatoria en cada ciclo
            random.shuffle(pending)
            batch_size = min(random.randint(150, 250), len(pending))
            current_batch = pending[:batch_size]

            for x, y in current_batch:
                if not self.running:
                    break

                url_api = f"https://backend.wplace.live/s0/pixel/{config['tile_x']}/{config['tile_y']}?x={x}&y={y}"

                try:
                    # Se envían las peticiones a través de los Proxies Residenciales
                    res = requests.get(url_api, headers=HEADERS, proxies=PROXIES_CONFIG, timeout=8)
                    
                    if res.status_code == 200:
                        data = res.json()
                        painted_by = data.get("paintedBy", {})
                        uid = str(painted_by.get("id"))
                        uname = painted_by.get("name", "Anónimo")

                        visited.add((x, y))
                        self.state["scanned_count"] = len(visited)
                        self.state["progress"] = f"Escaneados: {len(visited)}/{len(all_points)} | Hallazgos: {len(self.state['findings'])} | Ult: ({x},{y})"

                        # Verificar si coincide con alguno de la lista de IDs
                        if uid in config["target_ids"]:
                            url_mapa = pixel_a_url(config["tile_x"], config["tile_y"], x, y)
                            hallazgo = {
                                "uname": uname,
                                "uid": uid,
                                "coordenadas": f"Tile ({config['tile_x']}, {config['tile_y']}) -> X={x}, Y={y}",
                                "url": url_mapa,
                                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                            }
                            
                            self.state["findings"].append(hallazgo)
                            self.save_state(visited, config)

                            # Enviar alerta instantánea a Telegram
                            msg = (
                                f"🎯 *¡HALLAZGO DE SABUESO!* (#{len(self.state['findings'])})\n\n"
                                f"👤 *Usuario:* `{uname}`\n"
                                f"🆔 *ID:* `{uid}`\n"
                                f"📍 *Coordenada:* Tile ({config['tile_x']}, {config['tile_y']}) -> X={x}, Y={y}\n\n"
                                f"🌐 *Link directo al mapa:*\n{url_mapa}"
                            )
                            self.send_telegram(config.get("tg_token"), config.get("tg_chat"), msg)

                            if not config.get("continuous", True):
                                self.state["status"] = "found"
                                self.state["progress"] = "🎯 Objetivo localizado."
                                self.running = False
                                return

                    elif res.status_code == 429:
                        self.state["progress"] = "⚠️ Rate limit. Pausando 15s..."
                        time.sleep(15)

                except Exception as e:
                    pass

                # Pausa humana leve por píxel (gracias a los proxies residenciales no necesitamos pausas largas)
                time.sleep(random.uniform(0.3, 0.7))

            self.save_state(visited, config)

            if self.running:
                # Con proxies residenciales, el tiempo de reposo se reduce a solo 10 a 30 segundos entre lotes
                self.state["progress"] = f"🔄 Lote completado. Rotando proxy/IP... Hallazgos: {len(self.state['findings'])}"
                time.sleep(random.randint(10, 30))