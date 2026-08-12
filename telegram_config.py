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