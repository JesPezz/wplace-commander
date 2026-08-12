import os, time, json, requests, threading
from datetime import datetime
from PIL import Image, PngImagePlugin
import numpy as np
import tiles
from telegram_config import telegram_cfg

class TaskWorker:
    def __init__(self, task_id, config, data_dir, sentry_dir):
        self.id = task_id
        self.config = config
        self.data_dir = data_dir
        self.sentry_dir = sentry_dir
        if self.config.get('source', 'WPlace') != 'WPlace':
            self.config['source'] = 'WPlace'
        
        self.running = False
        self.paused = False
        self.status = "stopped"
        self.start_time_ts = None
        self.captures_count = 0
        self.last_img = None
        self.last_saved_img = None
        self.last_saved_path = None
        self.current_diff = 0.0
        self.current_diff_px = 0
        
        self.load_persistence()

    def log(self, msg):
        modos = "T" if self.config.get('save_timelapse') else ""
        modos += "S" if self.config.get('sentry') else ""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [T{self.id}|{modos}] {msg}", flush=True)

    def get_persistence_file(self):
        return f"task_{self.id}_state.json"

    def save_persistence(self):
        try:
            state = {
                "captures_count": self.captures_count,
                "start_timestamp": self.start_time_ts,
                "last_saved_path": self.last_saved_path
            }
            with open(self.get_persistence_file(), "w") as f: 
                json.dump(state, f)
        except Exception as e: 
            self.log(f"Error Persistencia: {e}")

    def load_persistence(self):
        f = self.get_persistence_file()
        if os.path.exists(f):
            try:
                with open(f, "r") as file:
                    state = json.load(file)
                    self.captures_count = state.get("captures_count", 0)
                    self.start_time_ts = state.get("start_timestamp")
                    path = state.get("last_saved_path")
                    if path and os.path.exists(path):
                        self.last_saved_img = Image.open(path).convert("RGBA")
                        self.last_saved_path = path
                        self.log(f"Memoria visual cargada: {path}")
            except: 
                pass

    def save_image_with_metadata(self, img, path):
        c = self.config['coords']
        meta_data = {
            "Tl": {"X": c['x_start'] // 1000, "Y": c['y_start'] // 1000},
            "Px": {"X": c['x_start'] % 1000, "Y": c['y_start'] % 1000}
        }
        meta = PngImagePlugin.PngInfo()
        meta.add_text("Description", json.dumps(meta_data, indent=2))
        img.save(path, "PNG", pnginfo=meta)

    def send_telegram(self, title, details, img_path=None):
        token = self.config.get("tg_token")
        chat_id = self.config.get("tg_chat")
        if not token or not chat_id:
            token = telegram_cfg.config.get("token", "")
            chat_id = telegram_cfg.config.get("chat_id", "")
            if not token or not chat_id: 
                return
        
        start_str = datetime.fromtimestamp(self.start_time_ts).strftime('%H:%M') if self.start_time_ts else "--:--"
        dur = float(self.config.get('duration_hours', 0))
        restante_str = "♾️ Infinito"
        if dur > 0 and self.start_time_ts:
            elapsed = (time.time() - self.start_time_ts) / 3600
            rest = max(0, dur - elapsed)
            restante_str = f"{rest:.2f}h"

        modos = []
        if self.config.get('save_timelapse'): modos.append("📷 Timelapse")
        if self.config.get('sentry'): modos.append("🛡️ Centinela")
        
        src = self.config.get('source', 'WPlace')

        caption = (
            f"🤖 *Tarea {self.id} ({src}): {self.config.get('name')}*\n"
            f"{title}\n\n"
            f"⚙️ *Modos:* {' + '.join(modos)}\n"
            f"🕒 *Inicio:* {start_str}\n"
            f"⏳ *Restante:* {restante_str}\n"
            f"📦 *Capturas:* {self.captures_count}\n"
            f"{details}"
        )
        try:
            url = f"https://api.telegram.org/bot{token}/{'sendDocument' if img_path else 'sendMessage'}"
            data = {'chat_id': chat_id, 'caption' if img_path else 'text': caption, 'parse_mode': 'Markdown'}
            files = {'document': open(img_path, 'rb')} if img_path else None
            requests.post(url, data=data, files=files, timeout=10)
        except Exception as e: 
            self.log(f"Error TG: {e}")

    def calculate_diff_exact(self, img1, img2):
        """
        Evalúa la diferencia exacta de píxeles alterados usando operaciones matriciales vectorizadas.
        Retorna: (porcentaje_alterado, cantidad_exacta_px)
        """
        if img1.size != img2.size: 
            return 100.0, 0
            
        arr1 = np.array(img1.convert("RGB"))
        arr2 = np.array(img2.convert("RGB"))
        
        # Máscara booleana: True donde cualquier canal (R, G o B) difiera
        diff_mask = np.any(arr1 != arr2, axis=-1)
        
        # Conteo absoluto de píxeles alterados
        px_alterados = int(np.count_nonzero(diff_mask))
        total_px = arr1.shape[0] * arr1.shape[1]
        
        porcentaje = (px_alterados / total_px) * 100.0 if total_px > 0 else 0.0
        return porcentaje, px_alterados

    def download_area(self):
        return tiles.download_area(self.config['coords'], self.config.get('source', 'WPlace'))

    def run_loop(self):
        self.running = True
        self.status = "running"
        if not self.start_time_ts: 
            self.start_time_ts = time.time()
            self.save_persistence()
        
        self.log("INICIANDO LOOP")
        self.send_telegram("🚀 *Iniciada*", "El sistema está monitoreando el objetivo.")

        while self.running:
            if self.paused: 
                self.status = "paused"
                time.sleep(1)
                continue
                
            dur = float(self.config.get('duration_hours', 0))
            if dur > 0 and (time.time() - self.start_time_ts)/3600 >= dur:
                self.stop()
                self.send_telegram("🏁 *Finalizada*", "Tiempo cumplido.")
                break

            try:
                self.save_persistence()
                limit_mb = float(self.config.get('limit_mb', 1000))
                current_mb = sum(os.path.getsize(os.path.join(self.data_dir, f)) for f in os.listdir(self.data_dir)) / (1024*1024)
                if current_mb > limit_mb: 
                    self.stop()
                    self.send_telegram("🛑 *Detenida*", "Límite de MB excedido.")
                    break

                self.log("Descargando...")
                current = self.download_area()
                if current is None:
                    self.log("Región inválida o excesiva; se omite este ciclo")

                if current is not None and self.config.get('sentry'):
                    sens = float(self.config.get('alert_pct', 5.0))
                    if self.last_img is None: 
                        self.last_img = current.copy()
                    else:
                        # Utilizar el nuevo método exacto
                        diff_pct, px_alterados = self.calculate_diff_exact(self.last_img, current)
                        self.current_diff = diff_pct
                        self.current_diff_px = px_alterados
                        
                        if diff_pct >= sens:
                            path = os.path.join(self.sentry_dir, f"alert_{self.id}.png")
                            self.save_image_with_metadata(current, path)
                            
                            # DIAGNÓSTICO MATEMÁTICO DIRECTO (Sin estimaciones)
                            diag_txt = f"📉 *Variación:* `{diff_pct:.2f}%` (`{px_alterados} px` alterados detectados)\n"
                            
                            if os.path.exists("plan_state.json"):
                                try:
                                    with open("plan_state.json", "r") as f:
                                        p_data = json.load(f)
                                    restante_sec = max(0, p_data['alert_time'] - time.time())
                                    px_obj = p_data['px_objetivo']
                                    px_disp = max(0, px_obj - int(restante_sec / 30))
                                    
                                    diag_txt += f"🔋 *Reserva disponible estimada:* `{px_disp} px`\n"
                                    if px_disp >= px_alterados:
                                        diag_txt += "⚡ *Diagnóstico:* ¡Reserva suficiente! Puedes reparar el 100% del daño inmediatamente."
                                    else:
                                        faltan = px_alterados - px_disp
                                        hrs_req = round((faltan * 30) / 3600.0, 2)
                                        diag_txt += f"⚠️ *Diagnóstico:* Te faltan `{faltan} px`. Tiempo para recuperar la reserva: `{hrs_req} hrs`."
                                except Exception:
                                    pass

                            self.send_telegram("⚠️ *¡ATAQUE DETECTADO!*", diag_txt, path)
                            self.last_img = current.copy()
                            self.log(f"ALERTA. Dif: {diff_pct:.2f}% ({px_alterados}px)")

                if current is not None and self.config.get('save_timelapse'):
                    should_save = False
                    if self.last_saved_img is None: 
                        should_save = True
                    else:
                        d_t_pct, d_t_px = self.calculate_diff_exact(self.last_saved_img, current)
                        if d_t_px > 0: # Si hay al menos 1 píxel diferente
                            should_save = True
                        else: 
                            self.log("Sin cambios visuales reales.")

                    if should_save:
                        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                        path = os.path.join(self.data_dir, f"cap_{self.id}_{ts}.png")
                        self.save_image_with_metadata(current, path)
                        self.last_saved_img = current.copy()
                        self.last_saved_path = path
                        self.captures_count += 1
                        self.save_persistence()
                        self.log(f"Guardado: {path}")

            except Exception as e: 
                self.log(f"Error: {e}")
                self.status = "error"
                
            time.sleep(self.config.get('interval', 1) * 60)

    def start(self): 
        threading.Thread(target=self.run_loop, daemon=True).start()
        
    def stop(self): 
        self.running = False
        self.status = "stopped"
        self.save_persistence()
    
    def get_info(self):
        # Actualizamos la salida para que el cliente reciba la cantidad exacta
        dur = float(self.config.get('duration_hours', 0))
        rest = "Inf"
        if dur > 0 and self.start_time_ts: 
            rest = f"{max(0, dur - (time.time()-self.start_time_ts)/3600):.2f}h"
        m = []
        if self.config.get('save_timelapse'): m.append("T")
        if self.config.get('sentry'): m.append("S")
        return {
            "id": self.id, 
            "name": self.config.get("name"), 
            "source": self.config.get('source', 'WPlace'),
            "mode": "+".join(m),
            "status": self.status, 
            "captures": self.captures_count,
            "restante": rest, 
            "diff_actual": f"{self.current_diff:.2f}%",
            "diff_px": getattr(self, 'current_diff_px', 0) # Nuevo campo exportado
        }