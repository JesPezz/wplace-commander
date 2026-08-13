import os
import json
import logging

logger = logging.getLogger("WPlaceCommander.Telegram")
CONFIG_FILE = "telegram_config.json"


class TelegramConfig:
    """
    Credenciales globales de Telegram del servidor.
    Valen como valor por defecto para todas las tareas, misiones y el planificador.
    """

    def __init__(self):
        self.config = {"token": "", "chat_id": ""}
        self.load_config()

    def load_config(self):
        """Carga el archivo telegram_config.json si existe en el directorio de trabajo."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.config.update({
                        "token": str(data.get("token", "")).strip(),
                        "chat_id": str(data.get("chat_id", "")).strip()
                    })
            except Exception as e:
                logger.error(f"Error cargando {CONFIG_FILE}: {e}")
        if not self.is_configured():
            self._seed_from_manifest()

    def _seed_from_manifest(self):
        """Si no hay configuración global, adopta las credenciales de la primera
        tarea de tasks_manifest.json que las tenga (migración de instalaciones previas)."""
        if not os.path.exists("tasks_manifest.json"):
            return
        try:
            with open("tasks_manifest.json", "r", encoding="utf-8") as f:
                manifest = json.load(f)
            for tid in sorted(manifest.keys(), key=lambda x: int(x)):
                cfg = manifest[tid]
                tok = str(cfg.get("tg_token", "")).strip()
                chat = str(cfg.get("tg_chat", "")).strip()
                if tok and chat:
                    self.config = {"token": tok, "chat_id": chat}
                    self.set_config(tok, chat)
                    logger.info("Credenciales globales de Telegram sembradas desde la tarea %s", tid)
                    return
        except Exception as e:
            logger.error(f"Error sembrando credenciales de Telegram: {e}")

    def is_configured(self):
        return bool(self.config.get("token") and self.config.get("chat_id"))

    def set_config(self, token, chat_id):
        """Actualiza la configuración en memoria y la persiste en el disco."""
        self.config = {
            "token": str(token or "").strip(),
            "chat_id": str(chat_id or "").strip()
        }
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
            return True
        except Exception as e:
            logger.error(f"Error guardando {CONFIG_FILE}: {e}")
            return False


# Instancia Singleton
telegram_cfg = TelegramConfig()