import psutil
import os
import json
import shutil
from datetime import datetime
from task_worker import TaskWorker

MANIFEST_FILE = "tasks_manifest.json"

class TaskManager:
    def __init__(self):
        self.tasks = {} 
        self.data_dir = "timelapse_data"
        self.sentry_dir = "sentry_data"
        for d in [self.data_dir, self.sentry_dir]:
            if not os.path.exists(d): os.makedirs(d)
        self.load_manifest()

    def save_manifest(self):
        manifest = {tid: worker.config for tid, worker in self.tasks.items()}
        with open(MANIFEST_FILE, "w") as f: json.dump(manifest, f, indent=4)

    def load_manifest(self):
        if os.path.exists(MANIFEST_FILE):
            try:
                with open(MANIFEST_FILE, "r") as f: manifest = json.load(f)
                print(f">>> SISTEMA: Resucitando {len(manifest)} tareas...")
                for tid, config in manifest.items():
                    worker = TaskWorker(tid, config, self.data_dir, self.sentry_dir)
                    self.tasks[tid] = worker
                    worker.start() # Auto-arranque al reiniciar
            except Exception as e: print(f"Error manifest: {e}")

    def generate_unique_name(self, base_name):
        if not base_name.strip(): base_name = "Tarea"
        final_name = base_name
        count = 1
        # Obtener nombres existentes
        existing = [t.config['name'] for t in self.tasks.values()]
        
        while final_name in existing:
            final_name = f"{base_name} ({count})"
            count += 1
        return final_name

    def create_task(self, task_config):
        # 1. Asignar ID
        next_id = 1
        if self.tasks:
            ids = [int(k) for k in self.tasks.keys()]
            next_id = max(ids) + 1
        task_id = str(next_id)

        # 2. Sanitizar Nombre (Auto-Incremento)
        task_config['name'] = self.generate_unique_name(task_config.get('name', ''))
        
        # 3. Crear Worker
        worker = TaskWorker(task_id, task_config, self.data_dir, self.sentry_dir)
        self.tasks[task_id] = worker
        self.save_manifest()
        return task_id

    def start_task(self, task_id):
        if task_id in self.tasks:
            if psutil.cpu_percent() > 95: return False, "CPU Crítica"
            self.tasks[task_id].start()
            return True, "Iniciada"
        return False, "404"

    def stop_task(self, task_id):
        if task_id in self.tasks:
            self.tasks[task_id].stop()
            return True, "Detenida"
        return False, "404"

    def delete_task(self, task_id):
        if task_id in self.tasks:
            self.tasks[task_id].stop()
            del self.tasks[task_id]
            self.save_manifest()
            try: os.remove(f"task_{task_id}_state.json")
            except: pass
            return True, "Eliminada"
        return False, "404"

    def get_all_status(self):
        sys = {
            "cpu": psutil.cpu_percent(),
            "ram": psutil.virtual_memory().percent,
            "tasks_active": sum(1 for t in self.tasks.values() if t.status == "running")
        }
        # Añadimos start_time formateado para el cliente
        tasks = []
        for t in self.tasks.values():
            info = t.get_info()
            # Formatear fecha inicio
            if t.start_time_ts:
                info['start_str'] = datetime.fromtimestamp(t.start_time_ts).strftime("%d/%m %H:%M")
            else:
                info['start_str'] = "--/-- --:--"
            tasks.append(info)
            
        return {"system": sys, "tasks": tasks}

    def stop_all(self):
        for t in self.tasks.values(): t.stop()
        
    def clear_all_data(self):
        self.stop_all()
        self.tasks = {}
        self.save_manifest()
        for d in [self.data_dir, self.sentry_dir]:
            shutil.rmtree(d)
            os.makedirs(d)
        for f in os.listdir("."):
            if f.endswith("_state.json") or f == MANIFEST_FILE: os.remove(f)