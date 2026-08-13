import zipfile, os, json, time, threading, re, requests, psutil
from collections import deque
from flask import Flask, request, jsonify, send_file
from task_manager import TaskManager
from proxy_manager import proxy_mgr
from telegram_config import telegram_cfg

# 1. INICIALIZAR LA APP
app = Flask(__name__)
manager = TaskManager()

PLAN_FILE = "plan_state.json"

# ==========================================
# 2. RUTAS DEL TASK MANAGER
# ==========================================
@app.route('/tasks/create', methods=['POST'])
def create_task():
    data = request.json or {}
    # Si la tarea no trae credenciales de Telegram, usar las globales del servidor
    for key, gc_key in (("tg_token", "token"), ("tg_chat", "chat_id")):
        if not str(data.get(key, "")).strip():
            data[key] = telegram_cfg.config.get(gc_key, "")
    return jsonify({"status": "ok", "task_id": manager.create_task(data)})

@app.route('/tasks/<tid>/start', methods=['POST'])
def start_task(tid): 
    s, m = manager.start_task(tid)
    return jsonify({"status": "ok" if s else "error", "msg": m})

@app.route('/tasks/<tid>/stop', methods=['POST'])
def stop_task(tid):
    s, m = manager.stop_task(tid)
    return jsonify({"status": "ok" if s else "error", "msg": m})

@app.route('/tasks/<tid>/delete', methods=['POST'])
def delete_task(tid):
    s, m = manager.delete_task(tid)
    return jsonify({"status": "ok" if s else "error", "msg": m})

@app.route('/status', methods=['GET'])
def get_status():
    tasks_info = []
    for t_id, worker in manager.tasks.items():
        info = worker.get_info()
        # No exponer credenciales (tg_token/tg_chat) por la API
        info['config'] = {k: v for k, v in worker.config.items() if k not in ("tg_token", "tg_chat")}
        tasks_info.append(info)
        
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    
    return jsonify({
        "status": "ok",
        "system": {"cpu": cpu, "ram": ram},
        "tasks": tasks_info
    })

@app.route('/tasks/update', methods=['POST'])
def update_task():
    try:
        data = request.json or {}
        task_id = str(data.get('id', '')).strip()
        new_config = data.get('config', {})

        if not task_id:
            return jsonify({"status": "error", "message": "ID de tarea inválido"}), 400

        # 1. Actualizar en memoria
        worker = manager.tasks.get(int(task_id)) or manager.tasks.get(task_id)
        if worker and hasattr(worker, 'config'):
            worker.config.update(new_config)

        # 2. Actualizar en disco
        manifest_path = "tasks_manifest.json"
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                file_content = f.read().strip()
                manifest = json.loads(file_content) if file_content else {}
            
            if manifest is None:
                manifest = {}

            if task_id in manifest:
                manifest[task_id].update(new_config)
                with open(manifest_path, "w", encoding="utf-8") as f:
                    json.dump(manifest, f, indent=4)
                return jsonify({"status": "ok", "message": f"Tarea #{task_id} actualizada correctamente"})
            else:
                return jsonify({"status": "error", "message": f"Tarea #{task_id} no encontrada en JSON"}), 404
        else:
            return jsonify({"status": "error", "message": "El archivo tasks_manifest.json no existe"}), 404

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/download_zip')
def download():
    tid_req = request.args.get('task_id')
    if tid_req is not None and not re.fullmatch(r"\d+", tid_req):
        return jsonify({"status": "error", "message": "task_id inválido"}), 400
    zip_name = f"data_task_{tid_req}.zip" if tid_req else "full_backup.zip"
    
    with zipfile.ZipFile(zip_name, 'w') as z:
        tasks_map = {t.id: t.config['name'] for t in manager.tasks.values()}
        def add_files_from(directory):
            if os.path.exists(directory):
                for f in os.listdir(directory):
                    parts = f.split('_')
                    if len(parts) > 1 and parts[1].isdigit():
                        file_tid = parts[1]
                        if tid_req and file_tid != tid_req: continue
                        folder_name = tasks_map.get(file_tid, f"Tarea_{file_tid}")
                        folder_name = "".join([c if c.isalnum() or c in " -_" else "_" for c in folder_name])
                        z.write(os.path.join(directory, f), f"{folder_name}/{f}")
        add_files_from("timelapse_data")
        add_files_from("sentry_data")
    return send_file(zip_name, as_attachment=True)

@app.route('/stop_all', methods=['POST'])
def stop_all(): 
    manager.stop_all()
    return jsonify({"status": "all_stopped"})

@app.route('/delete_tasks', methods=['POST'])
def delete_tasks(): 
    manager.delete_all_tasks()
    return jsonify({"status": "tasks_deleted"})

@app.route('/delete_photos', methods=['POST'])
def delete_photos(): 
    manager.delete_all_photos()
    return jsonify({"status": "photos_deleted"})

# ==========================================
# 3. RUTAS DEL PLANIFICADOR ESTRATÉGICO
# ==========================================
@app.route('/plan/set', methods=['POST'])
def set_plan():
    data = request.json
    alert_time = time.time() + data['segundos_espera']
    
    plan_data = {
        "alert_time": alert_time,
        "px_objetivo": data['px_objetivo'],
        "token": data['token'],
        "chat_id": data['chat_id'],
        "config_txt": data.get('config_txt', ''),
        "expired": False,
        "notified": False
    }
    with open(PLAN_FILE, "w", encoding="utf-8") as f:
        json.dump(plan_data, f)
        
    return jsonify({"status": "ok"})

@app.route('/plan/status', methods=['GET'])
def get_plan_status():
    if os.path.exists(PLAN_FILE):
        try:
            with open(PLAN_FILE, "r", encoding="utf-8") as f:
                plan = json.load(f)
            restante = plan['alert_time'] - time.time()
            is_expired = plan.get("expired", False) or (restante <= 0)
            
            return jsonify({
                "active": True, 
                "expired": is_expired,
                "restante": max(0, restante), 
                "px_objetivo": plan['px_objetivo'], 
                "config_txt": plan.get('config_txt', ''),
                "token": plan.get('token', ''),
                "chat_id": plan.get('chat_id', '')
            })
        except:
            return jsonify({"active": False})
    return jsonify({"active": False})

# ==========================================
# 4. HILO VIGILANTE Y ARRANQUE
# ==========================================
def monitor_plan():
    while True:
        if os.path.exists(PLAN_FILE):
            try:
                with open(PLAN_FILE, "r", encoding="utf-8") as f:
                    plan = json.load(f)
                
                if time.time() >= plan['alert_time'] and not plan.get("notified", False):
                    url = f"https://api.telegram.org/bot{plan['token']}/sendMessage"
                    msg = f"🚨 *[ALERTA TÁCTICA WPLACE]* 🚨\n\nTu reserva ha alcanzado el objetivo de *{plan['px_objetivo']}* píxeles.\n\n¡Es hora de pintar!"
                    
                    # 👈 Inyección de Proxy Global
                    proxies = proxy_mgr.get_requests_dict()
                    try:
                        requests.post(url, json={"chat_id": plan['chat_id'], "text": msg, "parse_mode": "Markdown"}, proxies=proxies, timeout=10)
                    except Exception as e:
                        print(f"Error enviando mensaje: {e}")
                    
                    plan["notified"] = True
                    plan["expired"] = True
                    with open(PLAN_FILE, "w", encoding="utf-8") as f:
                        json.dump(plan, f)
            except Exception as e:
                print(f"Error en monitor_plan: {e}")
        time.sleep(5)

@app.route('/proxy/check_ip', methods=['GET'])
def check_server_ip():
    """
    Realiza una petición saliente usando la configuración actual del proxy 
    y devuelve la IP pública visible que el servidor presenta en internet.
    """
    try:
        # Petición saliente usando el wrapper centralizado con proxy
        resp = proxy_mgr.request("GET", "https://api.ipify.org?format=json", timeout=5)
        if resp.status_code == 200:
            ip_publica = resp.json().get("ip")
            using_proxy = bool(proxy_mgr.active_proxy)
            
            return jsonify({
                "status": "ok",
                "ip_detectada": ip_publica,
                "using_proxy": using_proxy,
                "sanitized_proxy": proxy_mgr.sanitize_display(),
                "message": f"Servidor conectando a internet desde IP: {ip_publica}"
            })
        return jsonify({"status": "error", "message": f"Servidor externo devolvió código {resp.status_code}"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": f"Fallo al realizar verificación saliente: {str(e)}"}), 500


@app.route('/proxy/status', methods=['GET'])
def get_proxy_status():
    return jsonify({
        "status": "ok",
        "config": {k: v for k, v in proxy_mgr.config.items() if k != "pass"},
        "has_pass": bool(proxy_mgr.config.get("pass")),
        "sanitized": proxy_mgr.sanitize_display()
    })

@app.route('/proxy/set', methods=['POST'])
def set_proxy_route():
    data = request.json or {}

    # Conservar la contraseña existente si no se envía una nueva (nunca viaja por la API)
    if not data.get("pass") and proxy_mgr.config.get("pass"):
        data["pass"] = proxy_mgr.config["pass"]

    # Validar primero antes de aplicar
    if data.get("enabled"):
        is_ok, msg = proxy_mgr.test_connection(data)
        if not is_ok:
            return jsonify({"status": "error", "message": f"Prueba de conexión fallida: {msg}"}), 400

    if proxy_mgr.set_proxy_dict(data):
        return jsonify({
            "status": "ok", 
            "message": "Configuración de proxy guardada con éxito", 
            "sanitized": proxy_mgr.sanitize_display()
        })
    return jsonify({"status": "error", "message": "No se pudo escribir el archivo proxy_config.json"}), 500

@app.route('/telegram/status', methods=['GET'])
def get_telegram_status():
    return jsonify({
        "status": "ok",
        "token": telegram_cfg.config.get("token", ""),
        "chat_id": telegram_cfg.config.get("chat_id", ""),
        "has_token": bool(telegram_cfg.config.get("token")),
        "has_chat": bool(telegram_cfg.config.get("chat_id"))
    })

@app.route('/telegram/set', methods=['POST'])
def set_telegram_route():
    data = request.json or {}
    token = str(data.get('token', '')).strip()
    chat_id = str(data.get('chat_id', '')).strip()
    if telegram_cfg.set_config(token, chat_id):
        msg = "Credenciales globales de Telegram guardadas"
        if not token and not chat_id:
            msg = "Credenciales globales de Telegram eliminadas"
        return jsonify({"status": "ok", "message": msg})
    return jsonify({"status": "error", "message": "No se pudo escribir el archivo telegram_config.json"}), 500

if __name__ == '__main__':
    threading.Thread(target=monitor_plan, daemon=True).start()
    app.run(host='0.0.0.0', port=5000, debug=False)
