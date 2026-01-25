import psutil
import os
from task_worker import TaskWorker

class TaskManager:
    def __init__(self):
        self.tasks = {} # Diccionario {id: worker_instance}
        self.data_dir = "timelapse_data"
        self.sentry_dir = "sentry_data"
        for d in [self.data_dir, self.sentry_dir]:
            if not os.path.exists(d): os.makedirs(d)

    def create_task(self, task_config):
        # Generar ID único (simple)
        task_id = str(len(self.tasks) + 1)
        if "id" in task_config: task_id = str(task_config["id"])
        
        worker = TaskWorker(task_id, task_config, self.data_dir, self.sentry_dir)
        self.tasks[task_id] = worker
        return task_id

    def start_task(self, task_id):
        if task_id in self.tasks:
            # Regla de Recursos: No iniciar si la CPU > 90%
            if psutil.cpu_percent() > 90:
                return False, "CPU Saturada"
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
            # Limpiar archivo de estado
            try: os.remove(f"task_{task_id}_state.json")
            except: pass
            return True, "Eliminada"
        return False, "No encontrada"

    def get_all_status(self):
        # Información del Sistema
        sys_info = {
            "cpu": psutil.cpu_percent(),
            "ram": psutil.virtual_memory().percent,
            "tasks_active": sum(1 for t in self.tasks.values() if t.status == "running")
        }
        
        # Información de Tareas
        tasks_info = [t.get_info() for t in self.tasks.values()]
        
        return {"system": sys_info, "tasks": tasks_info}

    def stop_all(self):
        for t in self.tasks.values():
            t.stop()