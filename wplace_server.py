import zipfile, os, json, time, threading, requests, psutil
from flask import Flask, request, jsonify, send_file
from task_manager import TaskManager

# 1. INICIALIZAR LA APP
app = Flask(__name__)
manager = TaskManager()

PLAN_FILE = "plan_state.json"

# ==========================================
# 2. RUTAS ORIGINALES DEL TASK MANAGER
# ==========================================
@app.route('/tasks/create', methods=['POST'])
def create_task(): 
    return jsonify({"status": "ok", "task_id": manager.create_task(request.json)})

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
        info['config'] = worker.config
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

        # 1. ACTUALIZAR EN MEMORIA (Worker activo)
        # Esto aplica los cambios sin tener que detener ni reiniciar la tarea
        worker = manager.tasks.get(int(task_id)) or manager.tasks.get(task_id)
        if worker and hasattr(worker, 'config'):
            worker.config.update(new_config)

        # 2. ACTUALIZAR EN DISCO (Modificando el JSON directamente)
        manifest_path = "tasks_manifest.json"
        if os.path.exists(manifest_path):
            with open(manifest_path, "r") as f:
                file_content = f.read().strip()
                # Cargamos el JSON de forma segura. Si está vacío, creamos un diccionario.
                manifest = json.loads(file_content) if file_content else {}
            
            # Protección extra por si el JSON en disco era "null"
            if manifest is None:
                manifest = {}

            # Si el ID existe en el archivo, lo actualizamos y guardamos
            if task_id in manifest:
                manifest[task_id].update(new_config)
                with open(manifest_path, "w") as f:
                    json.dump(manifest, f, indent=4)
                return jsonify({"status": "ok", "message": f"Tarea #{task_id} actualizada correctamente"})
            else:
                return jsonify({"status": "error", "message": f"Tarea #{task_id} no encontrada en JSON"}), 404
        else:
            return jsonify({"status": "error", "message": "El archivo tasks_manifest.json no existe"}), 404

    except Exception as e:
        import traceback
        traceback.print_exc() # Imprime el error exacto en la consola de la Pi
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/download_zip')
def download():
    tid_req = request.args.get('task_id')
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
    with open(PLAN_FILE, "w") as f:
        json.dump(plan_data, f)
        
    return jsonify({"status": "ok"})

@app.route('/plan/status', methods=['GET'])
def get_plan_status():
    if os.path.exists(PLAN_FILE):
        try:
            with open(PLAN_FILE, "r") as f:
                plan = json.load(f)
            restante = plan['alert_time'] - time.time()
            is_expired = plan.get("expired", False) or (restante <= 0)
            
            return jsonify({
                "active": True, 
                "expired": is_expired,
                "restante": max(0, restante), 
                "px_objetivo": plan['px_objetivo'], 
                "config_txt": plan.get('config_txt', '')
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
                with open(PLAN_FILE, "r") as f:
                    plan = json.load(f)
                
                if time.time() >= plan['alert_time'] and not plan.get("notified", False):
                    url = f"https://api.telegram.org/bot{plan['token']}/sendMessage"
                    msg = f"🚨 *[ALERTA TÁCTICA WPLACE]* 🚨\n\nTu reserva ha alcanzado el objetivo de *{plan['px_objetivo']}* píxeles.\n\n¡Es hora de pintar!"
                    try:
                        requests.post(url, json={"chat_id": plan['chat_id'], "text": msg, "parse_mode": "Markdown"})
                    except Exception as e:
                        print(f"Error enviando mensaje: {e}")
                    
                    plan["notified"] = True
                    plan["expired"] = True
                    with open(PLAN_FILE, "w") as f:
                        json.dump(plan, f)
            except Exception as e:
                print(f"Error en monitor_plan: {e}")
        time.sleep(5) 

if __name__ == '__main__':
    threading.Thread(target=monitor_plan, daemon=True).start()
    app.run(host='0.0.0.0', port=5000, debug=False)