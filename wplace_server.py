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
def stop_all(): manager.stop_all(); return jsonify({"status": "all_stopped"})

@app.route('/delete_tasks', methods=['POST'])
def delete_tasks(): manager.delete_all_tasks(); return jsonify({"status": "tasks_deleted"})

@app.route('/delete_photos', methods=['POST'])
def delete_photos(): manager.delete_all_photos(); return jsonify({"status": "photos_deleted"})

if __name__ == '__main__': app.run(host='0.0.0.0', port=5000, debug=False)