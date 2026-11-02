# INCIDENTES — WPlace Automation System

Bitácora de fallos: fecha · app · síntoma · causa raíz · solución · lección.

---

## 2026-11-02 · Servidor · Alertas falsas «¡ATAQUE DETECTADO!» tras reiniciar la Raspberry

**Síntoma.** A las 12:55:58 llegó `[T26] 55,78 % (19153 px)` y a las 13:20:58 `[T34] 47,61 % (43598 px)`,
ambas con «⚠️ *¡ATAQUE DETECTADO!*». No había ataque: los PNG `alert_26.png` / `alert_34.png` contenían la
imagen normal del mapa. En el journal, las capturas de las **12:50:56** salieron 100 % negras
(`cap_33` 2.667 B 658×971, `cap_36` 227 B 130×74, `cap_37` 247 B 145×102, un solo color `(0,0,0)`), frente a
las del día anterior (193 KB / 9,8 KB con 47+ colores).

**Causa raíz (doble).**
1. `wplace.service` solo tenía `After=network.target`, que no espera DNS ni conectividad. La Pi arrancó a las
   12:50:47 y el servicio a las 12:50:54: la primera descarga de cada tarea ocurrió con la red sin resolver
   (`Temporary failure in name resolution` en las alertas de Telegram de las 12:50:56).
2. `tiles.download_area` creaba `Image.new("RGBA", ...)` y **omitía en silencio** los tiles que fallaban, así que
   devolvía un lienzo transparente (negro al pasarlo a RGB) como si fuera una imagen válida. El worker
   (`task_worker.py:181-218`) sembró con ella el baseline del centinela (`self.last_img`) y la memoria visual
   (`last_saved_path`), y la guardó como fotograma del timelapse. La siguiente captura real difirió 47-56 % de
   ese negro y disparó la alerta. Había 7 tareas más (T21-25, T32, T33, intervalo 60 min) a punto de repetirlo
   a las ~13:50.

**Solución.**
- `tiles.py`: si no se cargó **ningún** tile, devuelve `None` (es un fallo, no una imagen vacía). Los dos
  llamadores ya manejan el `None` (`task_worker` omite el ciclo sin tocar baseline ni timelapse; el cliente
  muestra «Área inválida o excesiva»).
- `wplace.service`: `Wants=network-online.target` + `After=network.target network-online.target`.
- Reinicio del servicio a las 13:30:29: las primeras capturas salieron con 63 / 47 / 35 colores, 11/11 tareas
  `running` y `diff_actual` 0.00 %.
- Limpieza: **50** PNG negros en `timelapse_data/` (no solo los 3 del día: restos del mismo fallo desde
  jul-2026), borrados; `last_saved_path` reseteado en las tareas 33, 36 y 37.

**Lección.** Una descarga parcialmente fallida no debe producir un artefacto «válido»: el total de fallos hay
que tratarlo como error. Y el baseline del centinela nunca debe sembrarse con una imagen sin validar. Regla
práctica: cualquier «ataque» cuya captura sea de un solo color es un falso positivo del arranque.

---

## 2026-11-02 · Servidor · Reinicio de la Raspberry a las 12:50 (investigación)

**Síntoma.** El servicio apareció resucitado a las 12:50:54 con baseline negro; el usuario no sabía que la Pi
se hubiera reiniciado.

**Qué se pudo establecer.**
| Evidencia | Valor |
|---|---|
| Kernel anterior en marcha | Plex escribió a las **12:49:58**; `opencode.log` tiene actividad hasta las 12:49:13 |
| Arranque del kernel | **12:50:47** (downtime < 47 s) |
| Ext4 raíz (`nvme0n1p2`) | montada **limpia**, sin `EXT4-fs: recovery complete` → desmontaje ordenado |
| Apagado por botón | imposible: `logind.conf` tiene `HandlePowerKey = ignore` |
| Actualizaciones | `Unattended-Upgrade::Automatic-Reboot "false"`, sin `/var/run/reboot-required`, sin actividad dpkg hoy |
| Cron / timers | ningún trabajo que reinicie (`autofix-bloqueado`, `incident-watch`, `wakealarm`, `omv-*` revisados) |
| opencode | sin `spawning process` entre 12:49:13 y 12:52:15 → no lo lanzó el agente |
| pstore / throttling | `/sys/fs/pstore` vacío; `vcgencmd get_throttled=0x0` |

**Conclusión.** Fue un **reinicio ordenado por software** (`reboot`/`shutdown -r`), no un corte de luz ni un
cuelgue: un corte habría dejado el ext4 sucio con replay de journal, y la máquina volvió a arrancar sola 47 s
después. La sesión de consola `tty1` está siempre iniciada (`agetty --autologin jespezz`), así que un comando
tecleado ahí o por SSH encaja con toda la evidencia… pero **no se puede saber quién ni desde dónde**: el journal
es volátil (`/var/log/journal` vacío → escribe en `/run/log/journal`) y logrotate trunca `wtmp`/`lastlog` en el
arranque (`wtmp.1` quedó en 0 B), perdiendo los registros del boot anterior.

Nota: el aviso `FAT-fs (nvme0n1p1): Volume was not properly unmounted` es un flag **rancio** de un evento
anterior (vfat no lo limpia si no corre `fsck.vfat`) y no implica que este reinicio fuera sucio.

**Pendiente recomendado.** Activar el journal persistente para poder auditar el próximo reinicio:

```bash
sudo mkdir -p /var/log/journal
sudo sed -i 's/^#\?Storage=.*/Storage=persistent/' /etc/systemd/journald.conf
sudo systemctl restart systemd-journald
```

Y, si se quiere cerrar el aviso del FAT, `sudo dosfsck -a /dev/nvme0n1p1` con la partición desmontada.

## 2026-11-02 · Servidor · El journal no puede ser persistente: el registro va por rsyslog

**Síntoma.** Tras aplicar el «pendiente» de la entrada anterior (`Storage=persistent` + `mkdir /var/log/journal`),
`journald` seguía anunciando solo `Runtime Journal (/run/log/journal/…)` y dejaba `/var/log/journal/<machine-id>/`
vacío, sin ningún aviso, incluso tras montarle un `--bind` a un directorio del NVMe (comprobado desde su propio
namespace con `nsenter`) y crearle a mano el subdirectorio por `machine-id`. Sí leía el fichero (un
`RuntimeMaxUse=1G` cambiaba el mensaje), y `Storage=none` lo dejaba sin socket, así que la clave se parseaba.

**Causa raíz.** `/var/log` **no es un directorio del disco**: `folder2ram` (OMV) lo monta en **tmpfs** y guarda
la copia real en `/var/folder2ram/var/log`. Con esa disposición `journald` no persiste aunque se le pida. Y el
otro registro posible estaba mudo: `rsyslog` está activo pero **todas las reglas de salida de
`/etc/rsyslog.conf` están comentadas**, así que `/var/log/auth.log` y `/var/log/syslog` llevaban en **0 B desde
el 2025-09-14** → no existía ningún registro de logins SSH (de ahí que el reinicio no se pueda atribuir).

**Solución.** Se descartó forzar `journald` (se revirtió a `Storage=volatile`, se eliminó la unit
`journal-a-disco.service` y su drop-in, que no hacían nada) y se activó el registro duradero por `rsyslog` con
`/etc/rsyslog.d/00-local-registro.conf`:

```
*.*;auth,authpriv.none                -/var/log/syslog
auth,authpriv.*                       /var/log/auth.log
```

Verificado: un `logger -p authpriv.notice` y un intento de SSH real (`sshd[33956]: Connection closed by
authenticating user root 127.0.0.1`) aparecen en `/var/log/auth.log` al instante.

**Lección.** No perseguir `journald` en esta máquina: `measure` primero si `/var/log` es disco o tmpfs. El
registro que sobrevive a un reinicio ordenado es el de `rsyslog` en `/var/log` (folder2ram lo sincroniza al
apagar); un corte de luz se lo lleva igual. Y ojo con `/etc/rsyslog.conf` comentado: parece que hay logs y no
hay nada.


## 2026-11-02 · Servidor · Cierre de la superficie expuesta (root por 0.0.0.0)

**Síntoma.** Al auditar el reinicio del 02-nov apareció el flanco real, bastante peor de lo que sugerían los
logs: `opencode serve` escuchaba en **0.0.0.0:4096 como root**, con `OPENCODE_PERMISSION` que **auto-aprueba
`bash`** (root sin restricciones para quien entre), `sshd` aceptaba **login de root con contraseña**,
`Portainer` estaba publicado en 9000/9443 **con `/var/run/docker.sock` montado** (root equivalente), y el
`wplace_server` y `vhusbdarm64` (USB por IP) también en 0.0.0.0. `iptables -P INPUT ACCEPT`, sin firewall.

**Solución aplicada.**
1. `sshd` (`/etc/ssh/sshd_config`, backup en `/tmp/sshd_config.bak`): `PermitRootLogin prohibit-password`,
   `PasswordAuthentication no`, `MaxAuthTries 3`. Verificado con `sshd -T` y con un intento real: responde
   `Permission denied (publickey)`. Ojo: ese fichero **no tiene `Include sshd_config.d/*.conf`**, así que un
   drop-in en `sshd_config.d/` se ignora en silencio (el primer intento no surtió efecto por eso).
2. Unit `/etc/systemd/system/fw-lan-guard.service` (no versionada, enabled): limita los puertos de procesos del
   host **4096, 5000 y 7575** a LAN `192.168.1.0/24` y Tailscale `100.64.0.0/10`; el resto, `DROP`.
   Comprobado que localhost sigue respondiendo (`127.0.0.1:5000 → 200` y `192.168.1.107:5000 → 200`).
3. `portainer` detenido y con `--restart=no` (`docker start portainer` para recuperarlo).

**Dos trampas.** (a) Los paquetes a 127.0.0.1 **también pasan por `INPUT`**: sin un `-A INPUT -i lo -j ACCEPT`
*el primero de la cadena* el DROP deja los servicios inaccesibles incluso en local (pasó: `000`); y como cada
`-I INPUT` inserta al principio, ese ACCEPT hay que añadirlo **al final** (`ExecStartPost`), o acaba debajo de
los DROP. (b) Los puertos publicados por **Docker no pasan por `INPUT`** (DNAT en `PREROUTING` → `FORWARD`):
para cerrarlos habría que usar la cadena `DOCKER-USER` o cambiar el mapeo del contenedor.

**Pendiente.** Revisar en el router si 22, 222, 4096, 5000, 5678, 5800, 9000, 8200 o 8780 están reenviados a
Internet (zapto.org sugiere que algo sí). Cambiar la contraseña `OPENCODE_SERVER_PASSWORD` del unit
`opencode.service` (está en claro y es débil) y, si no se usa la web desde fuera de la LAN, pasar su
`--hostname` a `127.0.0.1`. `n8n` (5678), `jdownloader` (5800) y `appapi-harp` (8200/8780/8782) siguen
publicados en 0.0.0.0 por Docker.

**Lección.** Antes de mirar quién reinició, mirar qué estaba escuchando: el journal voluntariamente vacío es un
problema de auditoría, un `opencode serve` con bash como root en 0.0.0.0 es un incidente en espera.
