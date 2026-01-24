# 🍓 WPlace Automation System

Sistema cliente-servidor para la automatización de capturas de timelapses en WPlace (Pixel Art Canvas).

## 🏗 Arquitectura

El proyecto consta de dos módulos principales:

### 1. Servidor (Raspberry Pi) - `wplace_server.py`
- Backend ligero basado en **Flask**.
- Sistema de **persistencia de estado** (sobrevive a reinicios).
- Descarga de tiles en **paralelo** (Multi-threading).
- Detección inteligente de cambios (Hashing MD5) para ahorrar espacio.
- API REST para control remoto.

### 2. Cliente (PC) - `wplace_client.py`
- Interfaz gráfica moderna (**Tkinter**).
- **Monitor en tiempo real** del estado de la Raspberry Pi.
- Herramientas de coordenadas y favoritos.
- Previsualización local antes de lanzar la tarea.

## 🚀 Instalación

### Servidor (Raspberry Pi)
```bash
pip install -r requirements.txt
python wplace_server.py
# Se recomienda usar systemd para ejecución automática

Cliente (Windows/Linux/Mac)
Bash
pip install -r requirements.txt
python wplace_client.py

🛠 Uso
1.-Inicia el servidor en la Raspberry Pi.

2.-Abre el cliente en tu PC.

3.-Introduce la IP de la Raspberry.

4.-Pega las coordenadas, configura el intervalo y dale a INICIAR.