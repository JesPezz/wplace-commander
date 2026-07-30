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
            "progress": "En espera de objetivo...",
            "result": None,
            "target": None,
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
                "result": self.state["result"],
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
                    self.state["result"] = data.get("result")
            except:
                pass

    def start(self, target_id, tile_x, tile_y, x_min=0, x_max=999, y_min=0, y_max=999, tg_token=None, tg_chat=None):
        if self.running:
            return False

        self.running = True
        config = {
            "target_id": str(target_id),
            "tile_x": tile_x,
            "tile_y": tile_y,
            "x_min": x_min, "x_max": x_max,
            "y_min": y_min, "y_max": y_max,
            "tg_token": tg_token,
            "tg_chat": tg_chat
        }

        self.state["status"] = "searching"
        self.state["progress"] = "Iniciando rastreo autónomo pasivo..."

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
        # 1. Recuperar memoria previa si coincide con la misma configuración
        visited = set()
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    saved_data = json.load(f)
                    if saved_data.get("config", {}).get("target_id") == config["target_id"] and \
                       saved_data.get("config", {}).get("tile_x") == config["tile_x"] and \
                       saved_data.get("config", {}).get("tile_y") == config["tile_y"]:
                        visited = set(tuple(p) for p in saved_data.get("visited", []))
            except:
                pass

        # Universo total de puntos
        all_points = [(x, y) for x in range(config["x_min"], config["x_max"] + 1)
                            for y in range(config["y_min"], config["y_max"] + 1)]
        
        self.state["total_count"] = len(all_points)

        while self.running:
            # Filtrar puntos aún no visitados
            pending = [p for p in all_points if p not in visited]
            self.state["scanned_count"] = len(visited)

            if not pending:
                self.state["status"] = "not_found"
                self.state["progress"] = f"❌ Área totalmente explorada ({len(visited)} px). No se encontró el ID."
                self.running = False
                break

            # 2. Reordenar dinámicamente los pendientes en cada ciclo
            random.shuffle(pending)
            
            # Tomar un lote pequeño (ej. 150 a 200 píxeles por tanda)
            batch_size = min(random.randint(150, 200), len(pending))
            current_batch = pending[:batch_size]

            for x, y in current_batch:
                if not self.running:
                    break

                url_api = f"https://backend.wplace.live/s0/pixel/{config['tile_x']}/{config['tile_y']}?x={x}&y={y}"

                try:
                    res = requests.get(url_api, headers=HEADERS, timeout=5)
                    if res.status_code == 200:
                        data = res.json()
                        painted_by = data.get("paintedBy", {})
                        uid = str(painted_by.get("id"))
                        uname = painted_by.get("name", "Anónimo")

                        visited.add((x, y))
                        self.state["scanned_count"] = len(visited)
                        self.state["progress"] = f" Escaneados: {len(visited)}/{len(all_points)} | Último: ({x},{y}) -> {uname}"

                        # ¡OBJETIVO LOCALIZADO!
                        if uid == config["target_id"]:
                            url_mapa = pixel_a_url(config["tile_x"], config["tile_y"], x, y)
                            self.state["result"] = {
                                "uname": uname,
                                "uid": uid,
                                "coordenadas": f"Tile ({config['tile_x']}, {config['tile_y']}) -> X={x}, Y={y}",
                                "url": url_mapa
                            }
                            self.state["status"] = "found"
                            self.state["progress"] = "🎯 ¡OBJETIVO LOCALIZADO!"
                            self.save_state(visited, config)

                            # Enviar notificación a Telegram
                            msg = (
                                f"🎯 *¡SABUESO LOCALIZÓ AL OBJETIVO!*\n\n"
                                f"👤 *Usuario:* `{uname}`\n"
                                f"🆔 *ID:* `{uid}`\n"
                                f"📍 *Ubicación:* Tile ({config['tile_x']}, {config['tile_y']}) -> X={x}, Y={y}\n"
                                f"📊 *Progreso:* {len(visited)} de {len(all_points)} píxeles evaluados\n\n"
                                f"🌐 *Link directo al mapa:*\n{url_mapa}"
                            )
                            self.send_telegram(config.get("tg_token"), config.get("tg_chat"), msg)
                            self.running = False
                            return

                    elif res.status_code == 429:
                        self.state["progress"] = "⚠️ Rate limit. Pausando 30s..."
                        time.sleep(30)

                except Exception:
                    pass

                # Pausa humana por píxel (0.8s a 1.5s)
                time.sleep(random.uniform(0.8, 1.5))

            # Guardar progreso en disco al terminar el lote
            self.save_state(visited, config)

            if self.running:
                # 3. PERIODO DE DESCANSO LARGO ENTRE LOTES (15 a 25 minutos)
                descanso_min = random.randint(15, 25)
                self.state["progress"] = f"💤 Lote completado. Enfriando IP durante {descanso_min} min para evitar bloqueos..."
                
                # Desglose de espera en tramos cortos para permitir abortar el hilo si el usuario lo pide
                for _ in range(descanso_min * 60):
                    if not self.running:
                        break
                    time.sleep(1)