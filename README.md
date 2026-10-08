# 🍓 WPlace Automation System v18.8.0 (Ultimate)

Sistema profesional de monitoreo, timelapse y vigilancia centinela para el lienzo de WPlace. Diseñado para ejecutarse en **Raspberry Pi** (Servidor) y controlarse remotamente desde una **PC** (Cliente).



## 🌟 Características Principales

- **Arquitectura Multitarea:** Monitorea múltiples sectores del lienzo simultáneamente con hilos independientes.
- **Persistencia Total:** Las tareas sobreviven a reinicios del servidor y cortes de luz, manteniendo el tiempo de ejecución exacto.
- **Smart Timelapse:** Solo guarda capturas si detecta cambios reales en los píxeles, optimizando el almacenamiento.
- **Vigilancia Centinela:** Sistema de alertas por Telegram con detección de ataques basada en porcentaje de variación.
- **Metadatos Forenses:** Las capturas (locales y remotas) incluyen coordenadas en formato JSON dentro de los metadatos PNG para una inspección rápida.
- **Visor Táctico:** Cliente con zoom, fondo de ajedrez para transparencia y gestión de favoritos.

## 🏗️ Estructura del Proyecto

El sistema se divide en módulos para facilitar la colaboración:

- `wplace_server.py`: Punto de entrada de la API Flask en la Raspberry Pi.
- `task_manager.py`: El cerebro que gestiona el ciclo de vida de las tareas y los recursos (CPU/RAM).
- `task_worker.py`: La lógica individual de cada tarea (Descarga, Diff, Telegram, Metadatos).
- `wplace_client.py`: Interfaz gráfica (Tkinter) para el operador.

## 🚀 Instalación y Despliegue

### 1. Servidor (Raspberry Pi)
**Requisitos:** Python 3.9+, `Pillow`, `Flask`, `requests`, `psutil`.

```bash
# Instalar dependencias del sistema
sudo apt update && sudo apt install python3-psutil python3-pil -y

# Clonar y ejecutar
python3 wplace_server.py

```

*Se recomienda configurar el servidor como un servicio de `systemd` usando el archivo `wplace.service` incluido.*

### 2. Cliente (PC Operador)

**Requisitos:** `Pillow`, `requests`, `pyperclip`.

```bash
pip install pillow requests pyperclip
python wplace_client.py

```

## 🛠️ Guía del Usuario

### Configuración de Tarea

1. **Pestaña Misión:** Introduce las coordenadas manualmente o haz clic en el **Visor Táctico**. El formato compatible es el de BlueMarble: `(Tl X: 0, Tl Y: 0, Px X: 0, Px Y: 0)`.
2. **Lanzamiento:** Configura el intervalo (minutos) y la duración. Dale a **Iniciar Tarea**.
3. **Radar:** Monitorea en tiempo real el progreso, las fotos tomadas y el tiempo restante.

### Inspección de Evidencia

Si tienes una captura y necesitas saber a qué coordenadas pertenece:

* Ve a la pestaña **Sistema**.
* Haz clic en **🔍 Inspeccionar Captura**.
* El sistema leerá el JSON oculto en el PNG y copiará las coordenadas automáticamente a tu portapapeles.

## 👨‍💻 Guía para Desarrolladores

### Formato de Metadatos

El sistema inyecta un chunk `tEXt` bajo la clave `Description` en los archivos PNG con la siguiente estructura:

```json
{
  "Tl": { "X": 123, "Y": 45 },
  "Px": { "X": 500, "Y": 250 }
}

```

### Endpoints de la API

* `POST /tasks/create`: Registra una nueva configuración.
* `GET /status`: Devuelve el estado de salud de la RPi y la lista de tareas.
* `GET /download_zip?task_id=X`: Descarga un paquete estructurado de una tarea específica.

---

© 2026 WPlace Automation Team.

```

---

