import psutil
import os
import json
import shutil
from task_worker import TaskWorker

MANIFEST_FILE = "tasks_manifest.json"

class TaskManager:
    def __init__(self):
        self.tasks = {} 
        self.data_dir = "timelapse_data"
        self.sentry_dir = "sentry_data"
        for d in [self.data_dir, self.sentry_dir]:
            if not os.path.exists(d): os.makedirs(d)
        
        # 🧠 RECUPERACIÓN DE MEMORIA AL INICIAR
        self.load_manifest()

    def save_manifest(self):
        """Guarda la configuración de todas las tareas vivas"""
        manifest = {}
        for tid, worker in self.tasks.items():
            manifest[tid] = worker.config
        with open(MANIFEST_FILE, "w") as f:
            json.dump(manifest, f, indent=4)

    def load_manifest(self):
        """Resucita las tareas tras un reinicio"""
        if os.path.exists(MANIFEST_FILE):
            try:
                with open(MANIFEST_FILE, "r") as f:
                    manifest = json.load(f)
                
                print(f">>> SISTEMA: Resucitando {len(manifest)} tareas...")
                for tid, config in manifest.items():
                    # Recreamos el trabajador
                    worker = TaskWorker(tid, config, self.data_dir, self.sentry_dir)
                    self.tasks[tid] = worker
                    
                    # Si estaba corriendo antes, lo arrancamos (opcional, por seguridad arrancamos auto)
                    # O verificamos recursos antes de arrancar masivamente
                    worker.start()
                    print(f">>> SISTEMA: Tarea {tid} restaurada y activa.")
            except Exception as e:
                print(f"Error cargando manifest: {e}")

    def create_task(self, task_config):
        task_id = str(int(list(self.tasks.keys())[-1]) + 1) if self.tasks else "1"
        if "id" in task_config: task_id = str(task_config["id"])
        
        worker = TaskWorker(task_id, task_config, self.data_dir, self.sentry_dir)
        self.tasks[task_id] = worker
        self.save_manifest() # Guardamos cambio
        return task_id

    def start_task(self, task_id):
        if task_id in self.tasks:
            if psutil.cpu_percent() > 95: return False, "CPU Crítica (>95%)"
            self.tasks[task_id].start()
            return True, "Iniciada"
        return False, "No encontrada"

    def stop_task(self, task_id):
        if task_id in self.tasks:
            self.tasks[task_id].stop()
            return True, "Detenida"
        return False, "No encontrada"

    def delete_task(self, task_id):
        if task_id in self.tasks:
            self.tasks[task_id].stop()
            del self.tasks[task_id]
            self.save_manifest() # Actualizamos manifest
            
            # Limpieza de archivos asociados
            try: os.remove(f"task_{task_id}_state.json")
            except: pass
            
            # Opcional: Borrar fotos de esta tarea específica? 
            # Dejamos las fotos por seguridad, el usuario debe borrarlas manual o "Vaciar Server"
            return True, "Eliminada"
        return False, "No encontrada"

    def get_all_status(self):
        sys_info = {
            "cpu": psutil.cpu_percent(),
            "ram": psutil.virtual_memory().percent,
            "tasks_active": sum(1 for t in self.tasks.values() if t.status == "running")
        }
        tasks_info = [t.get_info() for t in self.tasks.values()]
        return {"system": sys_info, "tasks": tasks_info}

    def stop_all(self):
        for t in self.tasks.values(): t.stop()
        
    def clear_all_data(self):
        self.stop_all()
        self.tasks = {}
        self.save_manifest() # Vaciar manifest
        # Borrar carpetas y recrearlas
        for d in [self.data_dir, self.sentry_dir]:
            shutil.rmtree(d)
            os.makedirs(d)
        # Borrar jsons de estado
        for f in os.listdir("."):
            if f.endswith("_state.json") or f == MANIFEST_FILE:
                os.remove(f)