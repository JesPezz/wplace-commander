# AGENTS.md — WPlace Automation System

Toda comunicación, código y commits en **español**. Proyecto Python puro (sin framework de tests, sin lint, sin CI).

**Ubicación del repositorio:** `/root/WPlace-Automation-System`

## Arquitectura

- `wplace_server.py` — API Flask para Raspberry Pi (0.0.0.0:5000). Punto de entrada del servidor.
- `task_manager.py` — `TaskManager`: ciclo de vida de tareas, persistencia, resurrección en boot.
- `task_worker.py` — `TaskWorker`: bucle de descarga por tiles, detección centinela (numpy), timelapse, alertas Telegram.
- `wplace_client.py` — GUI Tkinter (PC operador). Se conecta por HTTP al servidor.
- `tiles.py` — descarga de regiones por tiles de la fuente WPlace (usa `requests.Session`). Compartido entre `TaskWorker` y `WPlaceClient`.
- `fluent.py` — estilos y utilidades Fluent Design para el cliente (tema claro/oscuro/alto contraste dinámico, tipografía Segoe UI, NavigationView lateral colapsable, DPI awareness, accesibilidad y toasts).
- `proxy_manager.py` — singleton `proxy_mgr`; todos los requests salientes del servidor deberían pasar por `proxy_mgr.request(...)` o `proxy_mgr.get_requests_dict()`.
- `android/` — cliente Android (Kotlin + Jetpack Compose) que replica `wplace_client.py`: misma API REST y misma fuente de tiles. `gradle-wrapper.jar` no está versionado: hay que regenerarlo con `gradle wrapper` antes de compilar.

Cliente y servidor se comunican vía REST (`/tasks/*`, `/status`, `/plan/*`, `/proxy/*`). El cliente NO importa código del servidor.

## Comandos

- Servidor (RPi): `python3 wplace_server.py`
- Cliente en modo consola (debug Windows): `Lanzar_Cliente.bat`; manual: `python wplace_client.py`
- Compilar EXE (Windows): `construir_exe.bat` → genera icono (`generar_icono.py`) y corre PyInstaller `--onedir --windowed`; salida en `dist\wplace_client\wplace_client.exe`.
- Compilar APK (Android): en `android/`, regenerar `gradle wrapper` si falta `gradle/wrapper/gradle-wrapper.jar` y luego `./gradlew assembleDebug`; el APK queda en `app/build/outputs/apk/debug/app-debug.apk`. Requiere JDK 17 y Android SDK (`local.properties` → `sdk.dir`).
- **Firma del APK:** usa SIEMPRE `android/wplace-commander.keystore` (alias `androiddebugkey`, pass `android`), configurado en `signingConfigs` para debug y release. Es la clave con la que están instaladas las versiones en los teléfonos; si compilas con el `debug.keystore` por defecto de otra máquina (RPi vs PC), el APK NO actualiza ("App not installed"). Copia ese keystore a cualquier máquina que compile.
- No hay suite de tests; la verificación es ejecutar/compilar cuando el usuario lo pida.

## Gotchas operativos

- `requirements.txt` está incompleto: el servidor necesita además `numpy` y `psutil`; el cliente necesita `pyperclip`.
- Al arrancar, el servidor **resucita y AUTO-INICIA** todas las tareas de `tasks_manifest.json`. No edites/borres ese archivo ni los `task_<id>_state.json` con el servidor corriendo; el estado guarda `last_saved_path` para restaurar la memoria visual (evita duplicar timelapses).
- `interval` está en **minutos** (se multiplica ×60 en el sleep). `duration_hours: 0` = duración infinita.
- Coordenadas de config: `x_start/y_start/x_end/y_end`. En metadatos PNG (`tEXt` clave `Description`) se codifica `Tl` = coords//1000 y `Px` = coords%1000 (formato BlueMarble).
- Fuente única de tiles (1000px c/u): WPlace `https://backend.wplace.live/files/s0/tiles`; URL `/tx/ty.png`. Usar `tiles.download_area(coords, source)` en vez de descargar manualmente; retorna `None` si la región supera `MAX_PIXELS` (25 MP). BPlace ya no existe: no reintroducir esa fuente.
- `delete_all_tasks` borra configs + `*_state.json` pero NO fotos; `delete_all_photos` vacía `timelapse_data/` y `sentry_data/`, detiene todo y resetea la memoria visual.
- El cliente usa por defecto `http://192.168.1.107:5000` como servidor. Los clientes Android y PC comparten este default.
- `tasks_manifest.json`, `client_config.json` y `proxy_config.json` contienen tokens de Telegram/credenciales de proxy: los tres están en `.gitignore`. Nunca los comitees.
- El README menciona `wplace.service` (systemd) pero ese archivo no está en el repo.
- Versión: aparece en el título del README (v18.6). El `root.title()` del cliente es solo `WPlace Commander` (sin número). No hay variable central; sincronizar manualmente. El tema de UI persiste en `client_config.json` bajo `theme` (`auto|light|dark|high_contrast`).

## Commits / Release

- Repos remotos: GitHub (`JesPezz/wplace-commander`, rama `main`). Estilo de commits: prefijos tipo `feat(...)`, `fix(...)`, `refactor`, en español.
- Solo commitear/pushear/publicar release cuando el usuario lo pida (ver reglas globales: release como pre-release con `gh release create --prerelease`).
