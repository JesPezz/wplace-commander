# WPlace Commander — Cliente Android

Aplicación Android (Kotlin + Jetpack Compose) para controlar el servidor Flask
de WPlace-Automation-System desde un teléfono o tablet. Replica las funciones
del cliente Windows (`wplace_client.py`): crear supervisiones, ver tiles en
tiempo real, monitorizar tareas, planificador, Telegram/proxy y ajustes.

## Requisitos

- **Android Studio** (Koala 2024.1.2 o superior) con JDK 17 y Android SDK (API 34).
- O bien la **línea de comandos de Gradle** con un JDK 17.

> **Importante:** el proyecto se compila en una máquina x86_64 (Android Studio
> o PC). El `gradle-wrapper.jar` no puede generarse dentro de este entorno;
> ábrelo una vez en Android Studio (o ejecuta `gradle wrapper` en `android/`)
> para regenerarlo antes de compilar.

## Estructura

```
android/
├── settings.gradle.kts
├── build.gradle.kts
├── gradle.properties
├── local.properties          (ruta del SDK local, no se commitea)
├── gradlew                   (script; el jar del wrapper se completa en tu equipo)
└── app/
    ├── build.gradle.kts
    ├── proguard-rules.pro
    └── src/main/
        ├── AndroidManifest.xml
        ├── java/com/wplace/commander/
        │   ├── MainActivity.kt            (navegación lateral + tema)
        │   ├── data/Models.kt             (DTO de la API)
        │   ├── network/WPlaceApi.kt       (endpoints REST)
        │   ├── network/ApiClient.kt       (Retrofit + base URL configurable)
        │   └── ui/
        │       ├── WPlaceViewModel.kt     (estado + polling)
        │       ├── theme/Theme.kt         (claro/oscuro/alto contraste)
        │       ├── mission/               (formulario + visor de tiles)
        │       ├── radar/                 (lista de tareas)
        │       ├── planner/
        │       ├── telegram/              (Telegram + Proxy)
        │       └── system/                (IP, tema, backup, zona de peligro)
        └── res/
```

## Cómo compilar

### Opción A — Android Studio (recomendada)

1. Abre Android Studio → *Open* → selecciona la carpeta `android/`.
2. Espera a que Gradle sincronice (descargará dependencias).
3. *Build* → *Build APK(s)*.
4. El APK estará en `android/app/build/outputs/apk/debug/app-debug.apk`.

### Opción B — Línea de comandos

```bash
cd android
# Si no existe android/gradle/wrapper/gradle-wrapper.jar:
gradle wrapper
# Generar el APK de depuración:
./gradlew assembleDebug
```

## Configuración inicial en el dispositivo

1. Asegúrate de que el teléfono y la Raspberry Pi estén en la misma red.
2. Abre la app → pestaña **Sistema** → ajusta la **Dirección del servidor**
   (por defecto `http://192.168.1.107:5000`) → **Conectar**.
3. La app usa HTTP sin cifrar (`usesCleartextTraffic="true"`), igual que el
   servidor. No se requiere configuración TLS.

## Funciones

- **Misión:** crea una supervisión con nombre, coordenadas, intervalo (min),
  duración (horas, 0 = infinita), cuota y alerta; vista previa del tile en vivo.
- **Radar:** lista las tareas con estado, capturas, cambio (px), inicio y
  restante; botones iniciar/detener/eliminar; métricas de CPU/RAM.
- **Planificador:** ajusta espera, píxeles objetivo y credenciales del servidor.
- **Telegram / Proxy:** credenciales y activación/verificación de proxy.
- **Sistema:** tema (auto/claro/oscuro/alto contraste), IP del servidor,
  exportar respaldo ZIP y acciones de borrado masivo.

## Notas técnicas

- API documentada en `WPlace-Automation-System/wplace_server.py`.
- Fuente de tiles: `https://backend.wplace.live/files/s0/tiles/{tx}/{ty}.png`
  (tiles de 1000 px). Solo WPlace; BPlace ya no existe.
- Los tokens de Telegram y credenciales de proxy viven en el servidor
  (`tasks_manifest.json` / `proxy_config.json`, en `.gitignore`); la app solo
  envía lo que el usuario introduzca.
- No hay suite de tests en este proyecto; la verificación es compilar el APK.
