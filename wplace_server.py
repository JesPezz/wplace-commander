from flask import Flask, request, jsonify, send_file
from task_manager import TaskManager
import zipfile, os, json, time, threading, requests

# 1. INICIALIZAR LA APP PRIMERO
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
def global_status(): 
    return jsonify(manager.get_all_status())

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
# 3. NUEVAS RUTAS DEL PLANIFICADOR ESTRATÉGICO
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
                
                # Si ya es la hora y no se ha notificado
                if time.time() >= plan['alert_time'] and not plan.get("notified", False):
                    url = f"https://api.telegram.org/bot{plan['token']}/sendMessage"
                    msg = f"🚨 *[ALERTA TÁCTICA WPLACE]* 🚨\n\nTu reserva ha alcanzado el objetivo de *{plan['px_objetivo']}* píxeles.\n\n¡Es hora de pintar!"
                    try:
                        requests.post(url, json={"chat_id": plan['chat_id'], "text": msg, "parse_mode": "Markdown"})
                    except Exception as e:
                        print(f"Error enviando mensaje: {e}")
                    
                    # Marcamos como notificado y expirado sin borrar el archivo
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