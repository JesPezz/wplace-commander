import os
import json
import requests
import logging
from typing import Optional, Dict, Tuple

logger = logging.getLogger("WPlaceCommander.Proxy")
CONFIG_FILE = "proxy_config.json"


class ProxyManager:
    """
    Gestor de proxies con soporte para JSON estructurado (host, port, user, pass)
    y manejo defensivo de red.
    """

    def __init__(self):
        self.config = {
            "enabled": False,
            "host": "",
            "port": "",
            "user": "",
            "pass": ""
        }
        self.load_config()

    def load_config(self):
        """Carga el archivo proxy_config.json si existe en el directorio de trabajo."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.config.update({
                        "enabled": bool(data.get("enabled", False)),
                        "host": str(data.get("host", "")).strip(),
                        "port": str(data.get("port", "")).strip(),
                        "user": str(data.get("user", "")).strip(),
                        "pass": str(data.get("pass", "")).strip()
                    })
            except Exception as e:
                logger.error(f"Error cargando {CONFIG_FILE}: {e}")

    @property
    def active_proxy(self) -> Optional[str]:
        """Propiedad que devuelve la URL compilada si el proxy está habilitado."""
        return self.build_proxy_url()

    def build_proxy_url(self, cfg: Optional[dict] = None) -> Optional[str]:
        """Construye la URL del proxy basada en el diccionario de configuración."""
        target = cfg if cfg is not None else self.config

        if not target.get("enabled") or not target.get("host") or not target.get("port"):
            return None

        user = target.get("user", "")
        password = target.get("pass", "")
        host = target.get("host", "")
        port = target.get("port", "")

        auth_str = f"{user}:{password}@" if (user and password) else ""
        return f"http://{auth_str}{host}:{port}"

    def sanitize_display(self) -> str:
        """Retorna una representación formateada sin exponer credenciales."""
        if not self.config.get("enabled") or not self.config.get("host"):
            return "Desactivado (Conexión Directa)"

        user = self.config.get("user")
        host = self.config.get("host")
        port = self.config.get("port")

        if user:
            return f"http://***:***@{host}:{port}"
        return f"http://{host}:{port}"

    def set_proxy_dict(self, new_cfg: dict) -> bool:
        """Actualiza la configuración en memoria y la persiste en el disco."""
        self.config.update({
            "enabled": bool(new_cfg.get("enabled", False)),
            "host": str(new_cfg.get("host", "")).strip(),
            "port": str(new_cfg.get("port", "")).strip(),
            "user": str(new_cfg.get("user", "")).strip(),
            "pass": str(new_cfg.get("pass", "")).strip()
        })
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
            return True
        except Exception as e:
            logger.error(f"Error guardando {CONFIG_FILE}: {e}")
            return False

    def test_connection(self, test_cfg: Optional[dict] = None) -> Tuple[bool, str]:
        """Realiza un ping de diagnóstico para verificar que el proxy esté operativo."""
        proxy_url = self.build_proxy_url(test_cfg)
        if not proxy_url:
            return True, "Conexión directa activa"

        proxies = {"http": proxy_url, "https": proxy_url}
        try:
            r = requests.get("https://api.ipify.org?format=json", proxies=proxies, timeout=5)
            if r.status_code == 200:
                ip_detectada = r.json().get("ip", "OK")
                return True, f"Proxy funcional (IP pública: {ip_detectada})"
            return False, f"El proxy devolvió código HTTP {r.status_code}"
        except Exception as e:
            return False, f"Fallo de conexión vía proxy: {str(e)}"

    def get_requests_dict(self) -> Optional[Dict[str, str]]:
        """Retorna el diccionario estructurado para pasar como argumento a requests."""
        url = self.build_proxy_url()
        if not url:
            return None
        return {"http": url, "https": url}

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Wrapper centralizado HTTP para el servidor Flask."""
        kwargs.setdefault("timeout", 10)
        proxies = self.get_requests_dict()
        if proxies:
            kwargs["proxies"] = proxies
        return requests.request(method, url, **kwargs)


# Instancia Singleton
proxy_mgr = ProxyManager()