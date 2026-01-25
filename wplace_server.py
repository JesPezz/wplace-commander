from flask import Flask, request, jsonify, send_file
from task_manager import TaskManager
import zipfile, os

app = Flask(__name__)
manager = TaskManager()

# --- ENDPOINTS DE TAREAS ---

@app.route('/tasks/create', methods=['POST'])
def create_task():
    # El cliente envía la config del favorito
    config = request.json
    tid = manager.create_task(config)
    return jsonify({"status": "ok", "task_id": tid})

@app.route('/tasks/<tid>/start', methods=['POST'])
def start_task(tid):
    success, msg = manager.start_task(tid)
    return jsonify({"status": "ok" if success else "error", "msg": msg})

@app.route('/tasks/<tid>/stop', methods=['POST'])
def stop_task(tid):
    success, msg = manager.stop_task(tid)
    return jsonify({"status": "ok" if success else "error", "msg": msg})

@app.route('/tasks/<tid>/delete', methods=['POST'])
def delete_task(tid):
    success, msg = manager.delete_task(tid)
    return jsonify({"status": "ok" if success else "error", "msg": msg})

@app.route('/status', methods=['GET'])
def global_status():
    # Devuelve estado de TODAS las tareas y del sistema
    return jsonify(manager.get_all_status())

@app.route('/download_zip')
def download():
    # Empaqueta todo (podríamos mejorarlo para filtrar por tarea)
    zip_p = "data.zip"
    with zipfile.ZipFile(zip_p, 'w') as z:
        for f in os.listdir("timelapse_data"): 
            z.write(os.path.join("timelapse_data", f), f)
    return send_file(zip_p, as_attachment=True)

@app.route('/stop_all', methods=['POST'])
def stop_all():
    manager.stop_all()
    return jsonify({"status": "all_stopped"})

if __name__ == '__main__':
    # Necesario instalar psutil: pip install psutil
    app.run(host='0.0.0.0', port=5000, debug=False)