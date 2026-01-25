from flask import Flask, request, jsonify, send_file
from task_manager import TaskManager
import zipfile, os

app = Flask(__name__)
manager = TaskManager()

@app.route('/tasks/create', methods=['POST'])
def create_task(): return jsonify({"status": "ok", "task_id": manager.create_task(request.json)})

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
def global_status(): return jsonify(manager.get_all_status())

@app.route('/download_zip')
def download():
    # Parámetro opcional ?task_id=X
    tid = request.args.get('task_id')
    zip_name = f"data_task_{tid}.zip" if tid else "full_backup.zip"
    
    with zipfile.ZipFile(zip_name, 'w') as z:
        # Si hay TID, filtra solo archivos de esa tarea
        if tid:
            for f in os.listdir("timelapse_data"):
                if f.startswith(f"cap_{tid}_"): z.write(os.path.join("timelapse_data", f), f)
            # Agregar alertas de esa tarea si existen
            if os.path.exists("sentry_data"):
                for f in os.listdir("sentry_data"):
                    if f.startswith(f"alert_{tid}"): z.write(os.path.join("sentry_data", f), f)
        else:
            # Backup completo
            for d in ["timelapse_data", "sentry_data"]:
                if os.path.exists(d):
                    for f in os.listdir(d): z.write(os.path.join(d, f), f"{d}/{f}")
                    
    return send_file(zip_name, as_attachment=True)

@app.route('/stop_all', methods=['POST'])
def stop_all(): manager.stop_all(); return jsonify({"status": "all_stopped"})

@app.route('/clear_all', methods=['POST'])
def clear_all(): manager.clear_all_data(); return jsonify({"status": "cleared"})

if __name__ == '__main__': app.run(host='0.0.0.0', port=5000, debug=False)