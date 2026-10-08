APP_VERSION = "18.8.0"
import os
import sys
import json
import time
import re
import math
import threading
import platform
import subprocess
from datetime import datetime, timedelta

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, Menu, filedialog
from PIL import Image, ImageTk, ImageDraw, PngImagePlugin
import requests
import pyperclip
import tiles
import fluent


def check_for_updates():
    try:
        import requests
        r = requests.get("https://api.github.com/repos/JesPezz/wplace-commander/releases/latest", timeout=5)
        if r.status_code == 200:
            data = r.json()
            latest = data.get("tag_name","").lstrip("v")
            cur = APP_VERSION.lstrip("v")
            # compare simple
            def v2l(v):
                return [int(x) for x in v.split(".") if x.isdigit()]
            l = v2l(latest); c = v2l(cur)
            for a,b in zip(l,c):
                if a>b: return True, latest, data.get("html_url","")
                if a<b: return False, latest, data.get("html_url","")
            if len(l)>len(c): return True, latest, data.get("html_url","")
            return False, latest, data.get("html_url","")
    except Exception:
        pass
    return False, APP_VERSION, ""

CONFIG_FILE = "client_config.json"
OUTPUT_FOLDER = "wplace_downloads"
DEFAULT_TOUCH = fluent.DEFAULT_TOUCH

# Lienzo WPlace: proyección Web Mercator sobre un mundo de 2048000px.
# Fuente de la conversión: sabueso_worker.py (versión anterior del proyecto, pixel_a_url).
WPLACE_MAP_SIZE = 2_048_000.0


def wplace_pixel_from_latlng(lat, lng):
    """Convierte lat/lng a píxel absoluto del lienzo WPlace (Web Mercator, mapa 2048000px)."""
    gx = (lng + 180.0) / 360.0 * WPLACE_MAP_SIZE
    n = math.asinh(math.tan(math.radians(lat)))
    gy = (WPLACE_MAP_SIZE / 2.0) * (1.0 - n / math.pi)
    return gx, gy

# =====================================================================
# 🛠️ HELPER DE RECURSOS (Para compatibilidad con PyInstaller y .exe)
# =====================================================================
def get_resource_path(relative_path: str) -> str:
    """ 
    Obtiene la ruta absoluta de un recurso. 
    Funciona tanto en desarrollo local como empaquetado en .exe con PyInstaller.
    """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


class WPlaceClient:
    def __init__(self, root):
        self.root = root
        fluent.enable_dpi_awareness()
        self.root.title(f"WPlace Commander v{APP_VERSION}")
        self.root.geometry("1280x850")
        self.root.minsize(1000, 640)

        # Cargar configuración persistente
        self.config = self.cargar_config()

        # --- Tema Fluent dinámico (claro/oscuro/alto contraste) ---
        self.theme = fluent.FluentTheme(mode=self.config.get("theme", "auto"))
        self.tk_style = ttk.Style(self.root)
        self.apply_theme()

        # State de navegación lateral (NavigationView)
        self.nav_expanded = True
        self.nav_buttons = {}
        self.nav_frames = {}
        self.current_view = None

        # Variables de estado
        self.server_ip = tk.StringVar(value=self.config.get("server_ip", "http://192.168.1.107:5000"))
        self.preview_image_raw = None
        self.zoom_level = 1.0
        self.click_count = 0
        self.running = True

        # --- Carga Defensiva de Icono ---
        icon_path = get_resource_path("wplace_icon.ico")
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except Exception as e:
                print(f"[Aviso] No se pudo asignar el icono: {e}")

        # --- Montaje de la navegación lateral (NavigationView) ---
        self.build_navigation()

        # --- Inicializar Vistas (Frames colapsables) ---
        self.setup_tab_new()
        self.setup_tab_manager()
        self.setup_tab_planner()
        self.setup_tab_telegram()
        self.setup_tab_system()
        self.show_view("new")
        self.root.after(0, self._update_nav_collapse)
        self.root.bind("<Configure>", self._on_resize)

        # Carga asíncrona de credenciales de Telegram desde el servidor (respaldo local)
        threading.Thread(target=self.cargar_tg_desde_servidor, daemon=True).start()

        # Cierre limpio
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Atajos de teclado (Ctrl+N/S, Esc)
        self.root.bind_all("<Control-n>", lambda e: self.show_view("new"))
        self.root.bind_all("<Control-s>", lambda e: self.show_view("system"))
        self.root.bind_all("<Escape>", self._on_escape)

        # Iniciar monitoreo en hilo secundario (Background Thread)
        # Menubar
        menubar = Menu(self.root)
        self.root.config(menu=menubar)
        help_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ayuda", menu=help_menu)
        help_menu.add_command(label=f"Versión v{APP_VERSION}")
        help_menu.add_command(label="Comprobar actualizaciones", command=self.check_updates)
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()

    # =========================================================================
    # NAVEGACIÓN LATERAL (NAVIGATIONVIEW COLABSABLE) Y TEMA
    # =========================================================================
    def build_navigation(self):
        """Construye el panel lateral expandible al estilo NavigationView."""
        self.body = ttk.Frame(self.root, style="Content.TFrame")
        self.body.pack(fill="both", expand=True)

        self.nav = ttk.Frame(self.body, style="Nav.TFrame", width=200)
        self.nav.pack(side="left", fill="y")

        ttk.Label(self.nav, text="WPlace", style="Header.TLabel").pack(
            fill="x", padx=10, pady=(12, 4)
        )
        ttk.Separator(self.nav, orient="horizontal").pack(fill="x", padx=6, pady=4)

        self.content = ttk.Frame(self.body, style="Content.TFrame")
        self.content.pack(side="left", fill="both", expand=True)

        nav_items = [
            ("new", "🚀  Misión"),
            ("manager", "📡  Radar"),
            ("planner", "📅  Planificador"),
            ("telegram", "📱  Telegram"),
            ("system", "⚙️  Sistema"),
        ]
        for key, label in nav_items:
            btn = tk.Button(
                self.nav, text=label, anchor="w", bd=0, relief="flat",
                font=(fluent.system_font(), 12), padx=12, pady=10,
                cursor="hand2", command=lambda k=key: self.show_view(k),
            )
            btn.pack(fill="x", padx=6, pady=1)
            btn._nav_label = label
            btn._nav_short = label[:3]
            fluent.attach_tooltip(btn, f"Vista {label}", name=label)
            self.nav_buttons[key] = btn
            self.nav_frames[key] = ttk.Frame(self.content, style="Content.TFrame")
            self.nav_frames[key].place(x=0, y=0, relwidth=1, relheight=1)

        self.tab_new = self.nav_frames["new"]
        self.tab_manager = self.nav_frames["manager"]
        self.tab_planner = self.nav_frames["planner"]
        self.tab_telegram = self.nav_frames["telegram"]
        self.tab_system = self.nav_frames["system"]

    def show_view(self, key):
        """Muestra una vista y resalta el elemento activo del panel lateral."""
        self.current_view = key
        for k, frame in self.nav_frames.items():
            if k == key:
                frame.lift()
        token = self.theme.resolve()
        for k, btn in self.nav_buttons.items():
            if k == key:
                # Transición suave (60 Hz) hacia el color de selección Fluent
                fluent.schedule_transition(btn, token["nav_selected"], steps=10, interval=16)
                btn.configure(foreground=token["accent_fg"])
            else:
                btn.configure(background=token["nav"], foreground=token["text"])

    def _refresh_nav_highlight(self):
        token = self.theme.resolve()
        for k, btn in self.nav_buttons.items():
            if k == self.current_view:
                btn.configure(
                    background=token["nav_selected"],
                    foreground=token["accent_fg"],
                )
            else:
                btn.configure(
                    background=token["nav"],
                    foreground=token["text"],
                )

    def _update_nav_collapse(self):
        """Colapsa/expande el panel lateral según el ancho de la ventana."""
        w = self.root.winfo_width()
        if w < 1080 and self.nav_expanded:
            self.nav_expanded = False
        elif w >= 1080 and not self.nav_expanded:
            self.nav_expanded = True
        self.nav.configure(width=48 if not self.nav_expanded else 200)
        for btn in self.nav_buttons.values():
            btn.configure(
                anchor="center" if not self.nav_expanded else "w",
                text=btn._nav_short if not self.nav_expanded else btn._nav_label,
            )

    def _on_resize(self, event):
        if event.widget is self.root:
            self.root.after(60, self._update_nav_collapse)

    def _on_escape(self, event):
        # Esc en la vista del visor cierra ventanas hijas; si no hay, no hace nada
        return "break"

    def apply_theme(self):
        """(Re)aplica el tema Fluent sin reiniciar la aplicación."""
        token = self.theme.resolve()
        fluent.configure_styles(self.tk_style, token)
        self.root.configure(background=token["bg"])
        self._token = token
        for btn in getattr(self, "nav_buttons", {}).values():
            btn.configure(
                background=token["nav"], foreground=token["text"], activebackground=token["hover"],
            )
        for lbl in (getattr(self, "lbl_cpu", None), getattr(self, "lbl_ram", None), getattr(self, "lbl_plan_res", None)):
            if lbl is not None:
                try:
                    lbl.configure(foreground=token["text"])
                except tk.TclError:
                    pass
        if hasattr(self, "tree"):
            self.tree.tag_configure('run', foreground=token["success_fg"])
            self.tree.tag_configure('err', foreground=token["error_fg"])
        if hasattr(self, "canvas"):
            try:
                self.canvas.configure(bg=token["bg"])
            except tk.TclError:
                pass
        self._refresh_nav_highlight() if hasattr(self, "current_view") else None

    def set_theme_mode(self, mode):
        """Cambia el modo de tema en caliente: auto/light/dark/high_contrast."""
        self.theme.mode = mode
        self.config["theme"] = mode
        self.guardar_config()
        self.apply_theme()

    def _busy(self, btn, busy_text):
        """Deshabilita un botón y muestra estado de carga (evita dobles envíos)."""
        if btn is None:
            return
        try:
            if not hasattr(btn, "_texto_idle"):
                btn._texto_idle = btn.cget("text")
            btn.configure(text=busy_text, state="disabled")
            btn.update_idletasks()
        except tk.TclError:
            pass

    def _idle(self, btn):
        """Restaura el texto y el estado de un botón tras una operación."""
        if btn is None:
            return
        try:
            btn.configure(text=getattr(btn, "_texto_idle", btn.cget("text")), state="normal")
        except tk.TclError:
            pass

    def on_close(self):
        self.running = False
        self.guardar_config()
        self.root.destroy()

    # =========================================================================
    # PESTAÑA TELEGRAM Y PROXY (Manejo Defensivo de Widgets)
    # =========================================================================
    def setup_tab_telegram(self):
        main_f = ttk.Frame(self.tab_telegram)
        main_f.pack(fill='both', expand=True, padx=20, pady=10)

        # --- Frame Telegram ---
        f = ttk.LabelFrame(main_f, text="📱 Credenciales Globales de Telegram")
        f.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(f, text="Bot Token:").grid(row=0, column=0, padx=10, pady=5, sticky='e')
        self.et_tok = ttk.Entry(f, width=45)
        self.et_tok.insert(0, self.config.get("tg_token", ""))
        self.et_tok.grid(row=0, column=1, padx=10, pady=5)
        fluent.set_automation_name(self.et_tok, "Bot Token de Telegram", "Token del bot que envía las alertas")
        
        ttk.Label(f, text="Chat ID:").grid(row=1, column=0, padx=10, pady=5, sticky='e')
        self.et_chat = ttk.Entry(f, width=45)
        self.et_chat.insert(0, self.config.get("tg_chat", ""))
        self.et_chat.grid(row=1, column=1, padx=10, pady=5)
        fluent.set_automation_name(self.et_chat, "Chat ID de Telegram", "Identificador del chat que recibe las alertas")
        
        self.btn_guardar_tg = ttk.Button(f, text="💾 GUARDAR CREDENCIALES TELEGRAM", style="Accent.TButton", command=self.guardar_tg)
        self.btn_guardar_tg.grid(row=2, column=0, columnspan=2, pady=10)

        # --- Frame Proxy Server ---
        f_proxy = ttk.LabelFrame(main_f, text="🌐 Configuración del Proxy Server")
        f_proxy.pack(fill='x', padx=5, pady=10)

        self.var_proxy_enable = tk.BooleanVar(value=False)
        chk_en = ttk.Checkbutton(f_proxy, text="Habilitar uso de Proxy HTTP/HTTPS/SOCKS5", variable=self.var_proxy_enable)
        chk_en.grid(row=0, column=0, columnspan=2, sticky='w', padx=10, pady=5)

        ttk.Label(f_proxy, text="Host / IP:").grid(row=1, column=0, padx=10, pady=2, sticky='e')
        self.et_proxy_host = ttk.Entry(f_proxy, width=30)
        self.et_proxy_host.grid(row=1, column=1, padx=10, pady=2, sticky='w')
        fluent.set_automation_name(self.et_proxy_host, "Host del proxy", "Dirección IP o dominio del servidor proxy")

        ttk.Label(f_proxy, text="Puerto:").grid(row=2, column=0, padx=10, pady=2, sticky='e')
        self.et_proxy_port = ttk.Entry(f_proxy, width=15)
        self.et_proxy_port.grid(row=2, column=1, padx=10, pady=2, sticky='w')
        fluent.set_automation_name(self.et_proxy_port, "Puerto del proxy", "Puerto de escucha del servidor proxy")

        ttk.Label(f_proxy, text="Usuario:").grid(row=3, column=0, padx=10, pady=2, sticky='e')
        self.et_proxy_user = ttk.Entry(f_proxy, width=30)
        self.et_proxy_user.grid(row=3, column=1, padx=10, pady=2, sticky='w')
        fluent.set_automation_name(self.et_proxy_user, "Usuario del proxy", "Usuario para autenticación del proxy (opcional)")

        ttk.Label(f_proxy, text="Contraseña:").grid(row=4, column=0, padx=10, pady=2, sticky='e')
        self.et_proxy_pass = ttk.Entry(f_proxy, width=30, show="*")
        self.et_proxy_pass.grid(row=4, column=1, padx=10, pady=2, sticky='w')
        fluent.set_automation_name(self.et_proxy_pass, "Contraseña del proxy", "Contraseña para autenticación del proxy (opcional)")

        self.lbl_proxy_status = ttk.Label(f_proxy, text="Estado Proxy: Cargando...", font=(fluent.system_font(), 12, 'italic'))
        self.lbl_proxy_status.grid(row=5, column=0, columnspan=2, pady=5)

        btn_box = ttk.Frame(f_proxy)
        btn_box.grid(row=6, column=0, columnspan=2, pady=10)

        self.btn_guardar_proxy = ttk.Button(btn_box, text="⚙️ APLICAR Y GUARDAR PROXY", style="Accent.TButton", command=self.guardar_proxy)
        self.btn_guardar_proxy.pack(side='left', padx=5)
        ttk.Button(btn_box, text="🚫 DESACTIVAR PROXY", style="Red.TButton", command=self.desactivar_proxy).pack(side='left', padx=5)
        self.btn_verificar_ip = ttk.Button(btn_box, text="🔍 VERIFICAR IP DE SALIDA", style="Blue.TButton", command=self.verificar_ip_salida)
        self.btn_verificar_ip.pack(side='left', padx=5)

        # Consulta inicial solo cuando todos los elementos de la pestaña existen
        self.consultar_proxy_status()

    def consultar_proxy_status(self):
        """Consulta al servidor local el estado del proxy de forma resiliente."""
        try:
            url = f"{self.server_ip.get().rstrip('/')}/proxy/status"
            r = requests.get(url, timeout=3)
            if r.status_code == 200:
                d = r.json()
                cfg = d.get("config", {})
                
                if hasattr(self, 'var_proxy_enable'):
                    self.var_proxy_enable.set(cfg.get("enabled", False))
                    self.et_proxy_host.delete(0, tk.END)
                    self.et_proxy_host.insert(0, cfg.get("host", ""))
                    self.et_proxy_port.delete(0, tk.END)
                    self.et_proxy_port.insert(0, cfg.get("port", ""))
                    self.et_proxy_user.delete(0, tk.END)
                    self.et_proxy_user.insert(0, cfg.get("user", ""))

                sanitized = d.get("sanitized", "Sin proxy")
                if hasattr(self, 'lbl_proxy_status'):
                    if cfg.get("enabled"):
                        self.lbl_proxy_status.config(
                            text=f"✅ Proxy activo: {sanitized}",
                            foreground=self._token["success_fg"],
                        )
                    else:
                        self.lbl_proxy_status.config(
                            text=f"⚪ Sin proxy: {sanitized}",
                            foreground=self._token["subtext"],
                        )
        except Exception as e:
            if hasattr(self, 'lbl_proxy_status'):
                self.lbl_proxy_status.config(
                    text="⚠️ Estado Proxy: servidor local no disponible",
                    foreground=self._token["warning_fg"],
                )

    def guardar_proxy(self):
        payload = {
            "enabled": self.var_proxy_enable.get(),
            "host": self.et_proxy_host.get().strip(),
            "port": self.et_proxy_port.get().strip(),
            "user": self.et_proxy_user.get().strip(),
            "pass": self.et_proxy_pass.get().strip()
        }

        if payload["enabled"] and (not payload["host"] or not payload["port"]):
            messagebox.showwarning("Atención", "Para habilitar el proxy debes ingresar Host y Puerto.")
            return

        self._busy(self.btn_guardar_proxy, "⏳ GUARDANDO…")
        try:
            url = f"{self.server_ip.get().rstrip('/')}/proxy/set"
            r = requests.post(url, json=payload, timeout=8)
            if r.status_code == 200:
                messagebox.showinfo("Éxito", f"¡Proxy guardado con éxito!\n\n{r.json().get('message')}")
                self.consultar_proxy_status()
            else:
                err = r.json().get('message', r.text)
                messagebox.showerror("Error de Proxy", f"No se pudo guardar la configuración:\n{err}")
        except Exception as e:
            messagebox.showerror("Error de Conexión", f"Fallo al conectar con el servidor local:\n{e}")
        finally:
            self._idle(self.btn_guardar_proxy)

    def desactivar_proxy(self):
        self.var_proxy_enable.set(False)
        self.guardar_proxy()

    def verificar_ip_salida(self):
        self._busy(self.btn_verificar_ip, "⏳ VERIFICANDO…")
        try:
            url = f"{self.server_ip.get().rstrip('/')}/proxy/check_ip"
            r = requests.get(url, timeout=6)
            if r.status_code == 200:
                d = r.json()
                ip = d.get("ip_detectada", "Desconocida")
                proxy_str = d.get("sanitized_proxy", "")
                
                msg = (
                    f"🌐 IP Pública del Servidor: {ip}\n\n"
                    f"• Estado Proxy: {proxy_str}\n"
                    f"• Usando Proxy: {'SÍ (Tráfico Enrutado)' if d.get('using_proxy') else 'NO (Conexión Directa)'}"
                )
                messagebox.showinfo("Diagnóstico de Red", msg)
            else:
                messagebox.showerror("Error", f"Error del servidor: {r.json().get('message')}")
        except Exception as e:
            messagebox.showerror("Error de Conexión", f"No se pudo consultar al servidor local:\n{e}")
        finally:
            self._idle(self.btn_verificar_ip)

    def guardar_tg(self):
        self._busy(self.btn_guardar_tg, "⏳ GUARDANDO…")
        try:
            self.config["tg_token"] = self.et_tok.get().strip()
            self.config["tg_chat"] = self.et_chat.get().strip()
            self.guardar_config()
            try:
                url = f"{self.server_ip.get().rstrip('/')}/telegram/set"
                requests.post(url, json={
                    "token": self.config["tg_token"],
                    "chat_id": self.config["tg_chat"]
                }, timeout=6)
            except Exception:
                pass
            messagebox.showinfo("Guardado", "Credenciales de Telegram guardadas globalmente (y enviadas al servidor).")
        finally:
            self._idle(self.btn_guardar_tg)

    # ================= PESTAÑA PLANIFICADOR =================
    def setup_tab_planner(self):
        main_f = ttk.Frame(self.tab_planner)
        main_f.pack(fill='both', expand=True, padx=15, pady=10)

        f = ttk.LabelFrame(main_f, text="Calculadora Estratégica Híbrida")
        f.pack(fill='x', padx=5, pady=5)
        
        f_in = ttk.Frame(f)
        f_in.pack(fill='x', padx=10, pady=5)

        ttk.Label(f_in, text="Píxeles Actuales (Reserva):").grid(row=0, column=0, padx=10, pady=5, sticky='e')
        self.pl_actuales = ttk.Entry(f_in, width=15)
        self.pl_actuales.grid(row=0, column=1, padx=10, pady=5, sticky='w')
        fluent.set_automation_name(self.pl_actuales, "Píxeles actuales", "Píxeles disponibles en reserva ahora mismo")
        
        ttk.Label(f_in, text="Capacidad Máxima:").grid(row=1, column=0, padx=10, pady=5, sticky='e')
        self.pl_max = ttk.Entry(f_in, width=15)
        self.pl_max.insert(0, str(self.config.get("pl_max", "7404")))
        self.pl_max.grid(row=1, column=1, padx=10, pady=5, sticky='w')
        fluent.set_automation_name(self.pl_max, "Capacidad máxima", "Máximo de píxeles acumulables")
        
        ttk.Label(f_in, text="Objetivo de Disparo (%):").grid(row=2, column=0, padx=10, pady=5, sticky='e')
        self.pl_obj = ttk.Entry(f_in, width=15)
        self.pl_obj.insert(0, str(self.config.get("pl_obj", "85")))
        self.pl_obj.grid(row=2, column=1, padx=10, pady=5, sticky='w')
        fluent.set_automation_name(self.pl_obj, "Objetivo de disparo", "Porcentaje de capacidad al que se activa la alerta")
        
        ttk.Label(f_in, text="Reserva de Defensa (%):").grid(row=3, column=0, padx=10, pady=5, sticky='e')
        self.pl_res = ttk.Entry(f_in, width=15)
        self.pl_res.insert(0, str(self.config.get("pl_res", "25")))
        self.pl_res.grid(row=3, column=1, padx=10, pady=5, sticky='w')
        fluent.set_automation_name(self.pl_res, "Reserva de defensa", "Porcentaje que se conserva sin gastar")

        # === NUEVA BARRA DE PROGRESO ===
        self.prog_bar = ttk.Progressbar(f_in, orient='horizontal', mode='determinate', length=300)
        self.prog_bar.grid(row=4, column=0, columnspan=2, pady=10)
        self.lbl_prog = ttk.Label(f_in, text="Generación: -- / -- (0%)", font=(fluent.system_font(), 12, 'bold'))
        self.lbl_prog.grid(row=5, column=0, columnspan=2, pady=2)
        
        self.btn_calcular = ttk.Button(f, text="CALCULAR Y ACTIVAR ALERTA", style="Accent.TButton", command=self.calcular_plan)
        self.btn_calcular.pack(pady=10)
        
        f_diag = ttk.LabelFrame(main_f, text="🛡️ Evaluador de Daños (Sincronizado con Radar)")
        f_diag.pack(fill='x', padx=5, pady=5)
        
        f_diag_in = ttk.Frame(f_diag)
        f_diag_in.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(f_diag_in, text="Píxeles Dañados (Total):").grid(row=0, column=0, padx=5, pady=5, sticky='e')
        self.entry_damage = ttk.Entry(f_diag_in, width=15)
        self.entry_damage.insert(0, "0")
        self.entry_damage.grid(row=0, column=1, padx=5, pady=5, sticky='w')
        fluent.set_automation_name(self.entry_damage, "Píxeles dañados", "Total de píxeles dañados a reparar")
        
        self.btn_diag = ttk.Button(f_diag_in, text="🔍 ANALIZAR CAPACIDAD DE REPARACIÓN", style="Blue.TButton", command=self.analizar_dano)
        self.btn_diag.grid(row=0, column=2, padx=15, pady=5)

        res_f = ttk.LabelFrame(main_f, text="Resultados y Cronograma")
        res_f.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.lbl_plan_res = ttk.Label(res_f, text="Ingresa tus datos para generar el plan...", justify="left", font=(fluent.system_font(), 12))
        self.lbl_plan_res.pack(padx=15, pady=15, anchor="w")

    def analizar_dano(self):
        try:
            px_danados = int(self.entry_damage.get())
            actuales = int(self.pl_actuales.get() or "0")
            
            if actuales >= px_danados:
                sobrantes = actuales - px_danados
                messagebox.showinfo(
                    "✅ REPARACIÓN VIABLE",
                    f"¡Tienes suficientes píxeles para reparar el daño de inmediato!\n\n"
                    f"• Píxeles necesarios: {px_danados} px\n"
                    f"• Reserva actual: {actuales} px\n"
                    f"• Te quedarán: {sobrantes} px en reserva después de reparar."
                )
            else:
                faltantes = px_danados - actuales
                minutos_espera = (faltantes * 30) // 60
                horas_espera = round(minutos_espera / 60.0, 2)
                
                messagebox.showwarning(
                    "⚠️ RESERVA INSUFICIENTE",
                    f"No tienes suficientes píxeles para reparar el daño completo en este momento.\n\n"
                    f"• Píxeles necesarios: {px_danados} px\n"
                    f"• Reserva actual: {actuales} px\n"
                    f"• Píxeles faltantes: {faltantes} px\n\n"
                    f"⏳ Tiempo estimado de recarga requerido: {horas_espera} hrs ({minutos_espera} min)."
                )
        except ValueError:
            messagebox.showerror("Error", "Ingresa una cantidad numérica válida de píxeles dañados.")

    def calcular_plan(self):
        self._busy(self.btn_calcular, "⏳ CALCULANDO…")
        try:
            actuales = int(self.pl_actuales.get())
            maximos = int(self.pl_max.get())
            obj_pct = float(self.pl_obj.get())
            res_pct = float(self.pl_res.get())

            # --- NUEVO: Persistencia de datos de UI en el cliente ---
            self.config["pl_max"] = maximos
            self.config["pl_obj"] = obj_pct
            self.config["pl_res"] = res_pct
            self.guardar_config()
            # ---------------------------------------------------------
            
            px_objetivo = int(maximos * (obj_pct / 100))
            px_reserva = int(maximos * (res_pct / 100))
            px_gastar = px_objetivo - px_reserva
            
            px_faltantes = max(0, px_objetivo - actuales)
            segundos_espera = px_faltantes * 30
            fecha_alerta = datetime.now() + timedelta(seconds=segundos_espera)
            horas_margen = ((maximos - px_objetivo) * 30) / 3600.0
            
            txt = (
                f"🎯 Objetivo a alcanzar: {px_objetivo} px ({obj_pct}%)\n"
                f"🛡️ Reserva a dejar: {px_reserva} px ({res_pct}%)\n"
                f"🖌️ Píxeles a pintar por sesión: {px_gastar} px\n\n"
                f"⏱️ Tiempo de recarga estimado: {round(segundos_espera / 3600.0, 2)} horas\n"
                f"⏰ Hora de notificación: {fecha_alerta.strftime('%d/%m/%Y a las %H:%M:%S')}\n"
                f"🔋 Margen de inactividad antes de perder píxeles: {round(horas_margen, 2)} horas"
            )
            self.lbl_plan_res.config(text=txt)
            
            token = self.et_tok.get()
            chat_id = self.et_chat.get()
            
            if not token or not chat_id:
                messagebox.showwarning("Aviso", "Ve a la pestaña 'Telegram' y configura tus credenciales para recibir la alerta.")
                return

            if px_faltantes > 0:
                payload = {
                    "segundos_espera": segundos_espera,
                    "px_objetivo": px_objetivo,
                    "token": token,
                    "chat_id": chat_id,
                    "config_txt": txt 
                }
                r = requests.post(f"{self.server_ip.get().rstrip('/')}/plan/set", json=payload, timeout=3)
                if r.status_code == 200:
                    messagebox.showinfo("Alerta Activada", "¡Plan calculado! El servidor te avisará por Telegram en el momento exacto.")
                else:
                    messagebox.showerror("Error", f"El servidor devolvió el código {r.status_code}.")
            else:
                messagebox.showinfo("Listo", "¡Ya tienes los píxeles necesarios para pintar!")
                
        except ValueError:
            messagebox.showerror("Error de Datos", "Asegúrate de ingresar solo números válidos en las casillas.")
        except Exception as e:
            messagebox.showerror("Error Crítico", f"El programa se detuvo por este error:\n{str(e)}")
        finally:
            self._idle(self.btn_calcular)

    def cargar_config(self):
        if os.path.exists(CONFIG_FILE):
            try: 
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception: 
                pass
        return {"favorites": {}}

    def guardar_config(self):
        self.config["server_ip"] = self.server_ip.get()
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f: 
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error guardando configuración: {e}")

    def cargar_tg_desde_servidor(self):
        """Descarga las credenciales globales de Telegram desde el servidor al arrancar.

        Prioridad: si el servidor responde con credenciales, las usa y las persiste
        en client_config.json. Si el servidor no responde o viene vacío, conserva
        las que ya estén guardadas localmente.
        """
        try:
            url = f"{self.server_ip.get().rstrip('/')}/telegram/status"
            r = requests.get(url, timeout=5)
            r.raise_for_status()
            d = r.json()
        except Exception:
            return
        if d.get("has_token") or d.get("has_chat"):
            self.config["tg_token"] = d.get("token", self.config.get("tg_token", ""))
            self.config["tg_chat"] = d.get("chat_id", self.config.get("tg_chat", ""))
            self.guardar_config()
            self.root.after(0, self._aplicar_credenciales_tg)

    def _aplicar_credenciales_tg(self):
        for widget, key in ((getattr(self, "et_tok", None), "tg_token"),
                            (getattr(self, "et_chat", None), "tg_chat")):
            if widget is not None:
                widget.delete(0, tk.END)
                widget.insert(0, self.config.get(key, ""))

    def abrir_carpeta(self, path):
        path = os.path.abspath(path)
        if platform.system() == "Windows": os.startfile(path)
        elif platform.system() == "Darwin": subprocess.Popen(["open", path])
        else: subprocess.Popen(["xdg-open", path])

    def coords_to_str(self, x, y):
        return f"(Tl X: {x//1000}, Tl Y: {y//1000}, Px X: {x%1000}, Px Y: {y%1000})"

    def str_to_coords(self, text):
        match = re.search(r"Tl X:\s*(\d+).*?Tl Y:\s*(\d+).*?Px X:\s*(\d+).*?Px Y:\s*(\d+)", text)
        if match: 
            return (int(match.group(1)) * 1000) + int(match.group(3)), (int(match.group(2)) * 1000) + int(match.group(4))
        try: 
            parts = text.replace('(', '').replace(')', '').split(',')
            return int(parts[0]), int(parts[1])
        except Exception: 
            raise ValueError("Formato de coordenadas incorrecto")

    # ================= PESTAÑA MISIÓN (VISOR TÁCTICO) =================
    def setup_tab_new(self):
        paned = tk.PanedWindow(self.tab_new, orient=tk.HORIZONTAL, sashwidth=6, sashrelief=tk.RAISED, bg=self._token["bg"])
        paned.pack(fill='both', expand=True)

        left = ttk.Frame(paned, width=400)
        paned.add(left, minsize=380)
        
        l1 = ttk.LabelFrame(left, text="1. Datos de Misión")
        l1.pack(fill='x', padx=5, pady=5)
        ttk.Label(l1, text="IP:").grid(row=0, column=0, sticky='e')
        e_ip = ttk.Entry(l1, textvariable=self.server_ip, width=22)
        e_ip.grid(row=0, column=1, pady=2)
        fluent.set_automation_name(e_ip, "IP del servidor", "Dirección del servidor local")
        ttk.Label(l1, text="Nombre:").grid(row=1, column=0, sticky='e')
        self.task_name = ttk.Entry(l1, width=22)
        self.task_name.grid(row=1, column=1, pady=2)
        fluent.set_automation_name(self.task_name, "Nombre de la tarea", "Nombre de la misión a monitorear")
        fluent.apply_focus_highlight(self.task_name, self._token["accent"])
        
        ttk.Label(l1, text="Objetivo:").grid(row=2, column=0, sticky='e')
        self.combo_source = ttk.Combobox(l1, values=["WPlace"], state="readonly", width=20)
        self.combo_source.current(0)
        self.combo_source.grid(row=2, column=1, pady=5)

        l2 = ttk.LabelFrame(left, text="2. Coordenadas")
        l2.pack(fill='x', padx=5, pady=5)
        ttk.Label(l2, text="P1:").grid(row=0, column=0)
        self.entry_p1 = ttk.Entry(l2, width=35)
        self.entry_p1.grid(row=0, column=1, pady=2)
        fluent.set_automation_name(self.entry_p1, "Coordenada P1", "Punto inicial de la región")
        fluent.apply_focus_highlight(self.entry_p1, self._token["accent"])
        ttk.Label(l2, text="P2:").grid(row=1, column=0)
        self.entry_p2 = ttk.Entry(l2, width=35)
        self.entry_p2.grid(row=1, column=1, pady=2)
        fluent.set_automation_name(self.entry_p2, "Coordenada P2", "Punto final de la región")
        fluent.apply_focus_highlight(self.entry_p2, self._token["accent"])
        
        f_fav = ttk.Frame(l2)
        f_fav.grid(row=2, column=0, columnspan=2, pady=5)
        self.combo_favs = ttk.Combobox(f_fav, width=20, state="readonly", values=list(self.config.get("favorites", {}).keys()))
        self.combo_favs.pack(side='left')
        self.combo_favs.bind("<<ComboboxSelected>>", self.cargar_fav)
        fluent.set_automation_name(self.combo_favs, "Zonas favoritas", "Selecciona una zona guardada")
        btn_save_fav = ttk.Button(f_fav, text="💾", width=3, command=self.guardar_fav)
        btn_save_fav.pack(side='left', padx=2)
        fluent.attach_tooltip(btn_save_fav, "Guardar la zona actual como favorita", name="Guardar favorito")
        btn_del_fav = ttk.Button(f_fav, text="🗑", width=3, command=self.del_fav)
        btn_del_fav.pack(side='left', padx=2)
        fluent.attach_tooltip(btn_del_fav, "Eliminar la zona favorita seleccionada", name="Eliminar favorito")
        btn_overlay = ttk.Button(l2, text="📥 Importar Overlay (.wplace)", command=self.importar_overlay)
        btn_overlay.grid(row=3, column=0, columnspan=2, sticky='ew', padx=5, pady=2)
        fluent.attach_tooltip(btn_overlay, "Importar coordenadas desde un overlay de WPlace", name="Importar Overlay")

        l3 = ttk.LabelFrame(left, text="3. Configuración")
        l3.pack(fill='x', padx=5, pady=5)
        self.chk_time = tk.BooleanVar(value=True)
        self.chk_sent = tk.BooleanVar(value=False)
        chk_time = ttk.Checkbutton(l3, text="Timelapse", variable=self.chk_time)
        chk_time.grid(row=0, column=0, sticky='w')
        fluent.set_automation_name(chk_time, "Timelapse", "Guardar capturas periódicas de la región")
        chk_sent = ttk.Checkbutton(l3, text="Centinela", variable=self.chk_sent)
        chk_sent.grid(row=0, column=1, sticky='w')
        fluent.set_automation_name(chk_sent, "Centinela", "Vigilar cambios y generar alertas")
        ttk.Label(l3, text="Min:").grid(row=1, column=0, sticky='e')
        self.sp_int = ttk.Spinbox(l3, from_=1, to=120, width=5)
        self.sp_int.set(1)
        self.sp_int.grid(row=1, column=1)
        fluent.set_automation_name(self.sp_int, "Intervalo en minutos", "Cada cuántos minutos capturar")
        ttk.Label(l3, text="Hrs:").grid(row=1, column=2, sticky='e')
        self.sp_dur = ttk.Spinbox(l3, from_=0, to=48, width=5)
        self.sp_dur.set(0)
        self.sp_dur.grid(row=1, column=3)
        fluent.set_automation_name(self.sp_dur, "Duración en horas", "Horas de duración; 0 es infinito")
        ttk.Label(l3, text="MB:").grid(row=2, column=0, sticky='e')
        self.sp_mb = ttk.Spinbox(l3, from_=100, to=5000, width=5)
        self.sp_mb.set(1000)
        self.sp_mb.grid(row=2, column=1)
        fluent.set_automation_name(self.sp_mb, "Límite de MB", "Tamaño máximo de almacenamiento")
        ttk.Label(l3, text="Alert:").grid(row=2, column=2, sticky='e')
        self.sp_sens = ttk.Spinbox(l3, from_=0.1, to=50, width=5, increment=0.1)
        self.sp_sens.set(5.0)
        self.sp_sens.grid(row=2, column=3)
        fluent.set_automation_name(self.sp_sens, "Sensibilidad de alerta", "Porcentaje de cambio que dispara alerta")
       
        self.btn_lanzar = ttk.Button(left, text="🚀 LANZAR TAREA", style="Accent.TButton", command=self.lanzar)
        self.btn_lanzar.pack(fill='x', padx=10, pady=15, ipady=5)

        right = ttk.LabelFrame(paned, text="Visor Táctico")
        paned.add(right, minsize=400, stretch="always")
        tool = ttk.Frame(right)
        tool.pack(fill='x', pady=2)
        self.btn_preview = ttk.Button(tool, text="📷 Cargar Vista", command=self.preview)
        self.btn_preview.pack(side='left', padx=2)
        fluent.attach_tooltip(self.btn_preview, "Descargar y mostrar la región seleccionada", name="Cargar Vista")
        self.btn_snap = ttk.Button(tool, text="💾 PNG", command=self.snap_local)
        self.btn_snap.pack(side='left', padx=2)
        fluent.attach_tooltip(self.btn_snap, "Guardar la vista actual como imagen PNG", name="Guardar PNG")
        btn_zoom_in = ttk.Button(tool, text="➕", width=3, command=lambda: self.zoom(1.2))
        btn_zoom_in.pack(side='right', padx=2)
        fluent.attach_tooltip(btn_zoom_in, "Acercar la vista", name="Acercar")
        btn_zoom_out = ttk.Button(tool, text="➖", width=3, command=lambda: self.zoom(0.8))
        btn_zoom_out.pack(side='right', padx=2)
        fluent.attach_tooltip(btn_zoom_out, "Alejar la vista", name="Alejar")

        self.canvas = tk.Canvas(right, bg=self._token["bg"], cursor="cross", highlightthickness=0)
        sx = ttk.Scrollbar(right, orient="horizontal", command=self.canvas.xview)
        sy = ttk.Scrollbar(right, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=sx.set, yscrollcommand=sy.set)
        sx.pack(side="bottom", fill="x")
        sy.pack(side="right", fill="y")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self.map_click)
        self.prepare_checkerboard()

    def prepare_checkerboard(self):
        check = Image.new("RGB", (20, 20), "#CCCCCC")
        d = ImageDraw.Draw(check)
        d.rectangle([10,0,20,10], fill="#999999")
        d.rectangle([0,10,10,20], fill="#999999")
        self.checker_tile = check

    def map_click(self, e):
        cx, cy = self.canvas.canvasx(e.x), self.canvas.canvasy(e.y)
        rx, ry = int(cx / self.zoom_level), int(cy / self.zoom_level)
        txt = self.coords_to_str(rx, ry)
        if self.click_count % 2 == 0: 
            self.entry_p1.delete(0, tk.END)
            self.entry_p1.insert(0, txt)
        else: 
            self.entry_p2.delete(0, tk.END)
            self.entry_p2.insert(0, txt)
        self.click_count += 1
        r = 5 * self.zoom_level
        self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r, outline="#00FF00", width=2, tags="marker")

    def preview(self):
        """Descarga la región de forma asíncrona sin bloquear la UI, mostrando un indicador de carga."""
        try:
            target_source = self.combo_source.get()
            p1 = self.str_to_coords(self.entry_p1.get() or "0,0")
            p2 = self.str_to_coords(self.entry_p2.get() or "1000,1000")
            c = {"x_start": min(p1[0], p2[0]), "y_start": min(p1[1], p2[1]), "x_end": max(p1[0], p2[0]), "y_end": max(p1[1], p2[1])}
            w, h = c['x_end']-c['x_start'], c['y_end']-c['y_start']
            if w*h > 25000000 and not messagebox.askyesno("Alerta", "Área gigante. ¿Seguir?"):
                return

        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        # Indicador de carga no bloqueante (skeleton) sobre el visor
        self._show_skeleton(f"Descargando de {target_source}…")
        self._busy(self.btn_preview, "⏳ CARGANDO…")

        def worker():
            img = tiles.download_area(c, target_source, timeout=2)
            self.root.after(0, lambda: self._finish_preview(img))

        threading.Thread(target=worker, daemon=True).start()

    def _show_skeleton(self, text):
        self._clear_skel()
        self.skel = ttk.Label(self.canvas, text=f"⏳ {text}", style="Title.TLabel")
        self.canvas.create_window(self.canvas.winfo_width() // 2,
                                  self.canvas.winfo_height() // 2, window=self.skel)

    def _clear_skel(self):
        if hasattr(self, "skel") and self.skel.winfo_exists():
            self.skel.destroy()
        self.canvas.delete("skeleton")

    def _finish_preview(self, img):
        self._clear_skel()
        self._idle(self.btn_preview)
        self.root.title(f"WPlace Commander v{APP_VERSION}")
        if img is None:
            messagebox.showerror("Error", "Área inválida o excesiva. Ajusta las coordenadas.")
            return
        self.preview_image_raw = img
        self.zoom_level = 1.0
        self.render_image()

    def zoom(self, f):
        if not self.preview_image_raw: return
        self.zoom_level *= f
        self.render_image()
    
    def render_image(self):
        if not self.preview_image_raw: return
        w, h = self.preview_image_raw.size
        nw, nh = int(w*self.zoom_level), int(h*self.zoom_level)
        bg = Image.new("RGB", (nw, nh))
        pat = Image.new("RGB", (100, 100))
        for i in range(0, 100, 20):
            for j in range(0, 100, 20): 
                pat.paste(self.checker_tile, (i, j))
        for i in range(0, nw, 100):
            for j in range(0, nh, 100): 
                bg.paste(pat, (i, j))
        resized = self.preview_image_raw.resize((nw, nh), Image.Resampling.NEAREST)
        bg.paste(resized, (0, 0), resized)
        self.tk_image_ref = ImageTk.PhotoImage(bg)
        self.canvas.delete("all")
        self.canvas.config(scrollregion=(0, 0, nw, nh))
        self.canvas.create_image(0, 0, image=self.tk_image_ref, anchor="nw")

    def snap_local(self):
        if self.preview_image_raw:
            try:
                if not os.path.exists(OUTPUT_FOLDER): 
                    os.makedirs(OUTPUT_FOLDER)
                path = f"{OUTPUT_FOLDER}/snap_{datetime.now().strftime('%H%M%S')}.png"
                p1_str = self.entry_p1.get()
                try:
                    p1_x, p1_y = self.str_to_coords(p1_str)
                    meta_data = {
                        "Tl": {"X": p1_x // 1000, "Y": p1_y // 1000},
                        "Px": {"X": p1_x % 1000, "Y": p1_y % 1000}
                    }
                    meta = PngImagePlugin.PngInfo()
                    meta.add_text("Description", json.dumps(meta_data, indent=2))
                    self.preview_image_raw.save(path, "PNG", pnginfo=meta)
                except Exception: 
                    self.preview_image_raw.save(path)
                messagebox.showinfo("OK", f"Guardado:\n{path}")
                self.abrir_carpeta(OUTPUT_FOLDER)
            except Exception as e: 
                messagebox.showerror("Error", str(e))
        else: 
            messagebox.showwarning("Ops", "Sin vista previa.")

    def guardar_fav(self):
        n = simpledialog.askstring("Nombre", "Nombre zona:")
        if n: 
            if "favorites" not in self.config: self.config["favorites"] = {}
            self.config["favorites"][n] = {"p1": self.entry_p1.get(), "p2": self.entry_p2.get()}
            self.guardar_config()
            self.combo_favs['values'] = list(self.config["favorites"].keys())
            self.combo_favs.set(n)

    def importar_overlay(self):
        """Importa un overlay exportado por WPlace (.wplace.json) y lo guarda como favorito.

        Convierte los bounds geográficos (north/south/west/east) a píxeles absolutos
        del lienzo WPlace (Web Mercator, mapa de 2048000px) y rellena P1/P2.
        """
        path = filedialog.askopenfilename(
            title="Importar Overlay de WPlace",
            filetypes=[("Overlays de WPlace", "*.wplace"), ("Overlays de WPlace (JSON)", "*.wplace.json"), ("Archivos JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            b = data.get("bounds")
            if not b or any(k not in b for k in ("north", "south", "west", "east")):
                raise ValueError("El archivo no tiene un campo 'bounds' válido (north/south/west/east).")
            x1, y1 = wplace_pixel_from_latlng(b["north"], b["west"])
            x2, y2 = wplace_pixel_from_latlng(b["south"], b["east"])
            x1, y1, x2, y2 = map(int, map(round, (x1, y1, x2, y2)))
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo importar el overlay:\n{e}")
            return

        self.entry_p1.delete(0, tk.END)
        self.entry_p1.insert(0, self.coords_to_str(x1, y1))
        self.entry_p2.delete(0, tk.END)
        self.entry_p2.insert(0, self.coords_to_str(x2, y2))

        default = os.path.splitext(data.get("name", os.path.basename(path)))[0]
        name = simpledialog.askstring("Nombre", "Nombre de la zona:", initialvalue=default or "Overlay")
        if name:
            if "favorites" not in self.config: self.config["favorites"] = {}
            self.config["favorites"][name] = {"p1": self.entry_p1.get(), "p2": self.entry_p2.get()}
            self.guardar_config()
            self.combo_favs['values'] = list(self.config["favorites"].keys())
            self.combo_favs.set(name)
            self.task_name.delete(0, tk.END)
            self.task_name.insert(0, name)

    def del_fav(self):
        n = self.combo_favs.get()
        if n in self.config.get("favorites", {}): 
            del self.config["favorites"][n]
            self.guardar_config()
            self.combo_favs['values'] = list(self.config["favorites"].keys())
            self.combo_favs.set('')

    def cargar_fav(self, e):
        name = self.combo_favs.get()
        d = self.config.get("favorites", {}).get(name)
        if d: 
            self.entry_p1.delete(0, tk.END)
            self.entry_p1.insert(0, d['p1'])
            self.entry_p2.delete(0, tk.END)
            self.entry_p2.insert(0, d['p2'])
            self.task_name.delete(0, tk.END)
            self.task_name.insert(0, name)

    def lanzar(self):
        self._busy(self.btn_lanzar, "⏳ LANZANDO…")
        try:
            p1 = self.str_to_coords(self.entry_p1.get())
            p2 = self.str_to_coords(self.entry_p2.get())
            c = {"x_start": min(p1[0], p2[0]), "y_start": min(p1[1], p2[1]), "x_end": max(p1[0], p2[0]), "y_end": max(p1[1], p2[1])}
            data = {
                "name": self.task_name.get(), "coords": c, 
                "source": self.combo_source.get(),
                "save_timelapse": self.chk_time.get(), "sentry": self.chk_sent.get(), 
                "interval": int(self.sp_int.get()), "duration_hours": float(self.sp_dur.get()), 
                "limit_mb": int(self.sp_mb.get()), "alert_pct": float(self.sp_sens.get()), 
                "tg_token": self.et_tok.get(), "tg_chat": self.et_chat.get()
            }
            r = requests.post(f"{self.server_ip.get().rstrip('/')}/tasks/create", json=data, timeout=3)
            if r.status_code == 200: 
                tid = r.json()['task_id']
                requests.post(f"{self.server_ip.get().rstrip('/')}/tasks/{tid}/start", timeout=2)
                messagebox.showinfo("OK", f"Tarea iniciada (ID {tid})")
                fluent.show_toast("WPlace Commander", f"Tarea {tid} iniciada correctamente")
                self.show_view("manager")
                self.guardar_config()
            else: 
                messagebox.showerror("Error", r.text)
        except Exception as e: 
            messagebox.showerror("Error", str(e))
        finally:
            self._idle(self.btn_lanzar)

    # ================= PESTAÑA RADAR DE TAREAS =================
    def setup_tab_manager(self):
        f = ttk.LabelFrame(self.tab_manager, text="Estado Global")
        f.pack(fill='x', padx=10, pady=5)
        self.lbl_cpu = ttk.Label(f, text="🖥️ CPU: --%", font=(fluent.system_font(), 12, 'bold'), foreground=self._token["text"])
        self.lbl_cpu.pack(side='left', padx=20)
        self.lbl_ram = ttk.Label(f, text="🧠 RAM: --%", font=(fluent.system_font(), 12, 'bold'), foreground=self._token["text"])
        self.lbl_ram.pack(side='left', padx=20)
        
        self.ctx_menu = Menu(self.root, tearoff=0)
        self.ctx_menu.add_command(label="▶ Reanudar", command=lambda: self.do_act("start"))
        self.ctx_menu.add_command(label="⏸ Pausar/Detener", command=lambda: self.do_act("stop"))
        self.ctx_menu.add_command(label="✏️ Editar Tarea", command=self.open_edit_task_dialog) 
        self.ctx_menu.add_command(label="📥 Descargar Datos", command=self.do_down)
        self.ctx_menu.add_separator()
        self.ctx_menu.add_command(label="🗑 ELIMINAR TAREA", command=lambda: self.do_act("delete"))

        cols = ("ID", "Nombre", "Fuente", "Modos", "Inicio", "Estado", "Fotos", "Restante", "Dif %")
        self.tree = ttk.Treeview(self.tab_manager, columns=cols, show='headings', selectmode='browse')
        for c, w in zip(cols, [40, 180, 80, 120, 100, 80, 60, 80, 80]): 
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w, anchor="center")
        self.tree.pack(fill='both', expand=True, padx=10, pady=5)
        self.tree.bind("<Button-3>", lambda e: (self.tree.selection_set(self.tree.identify_row(e.y)), self.ctx_menu.post(e.x_root, e.y_root)) if self.tree.identify_row(e.y) else None)
        self.tree.bind("<Double-1>", lambda e: self.open_edit_task_dialog())
        self.tree.bind("<Return>", lambda e: self.open_edit_task_dialog())
        self.tree.bind("<Delete>", lambda e: self.do_act("delete"))
        self.tree.bind("<Menu>", self._popup_menu)
        self.tree.bind("<Shift-F10>", self._popup_menu)
        fluent.set_automation_name(self.tree, "Lista de tareas", "Tareas activas; usa Menú o Shift+F10 para acciones")

        bf = ttk.Frame(self.tab_manager)
        bf.pack(fill='x', padx=10, pady=10)
        ttk.Button(bf, text="▶ START", style="Green.TButton", command=lambda: self.do_act("start")).pack(side='left', padx=2)
        ttk.Button(bf, text="⏸ STOP", style="Blue.TButton", command=lambda: self.do_act("stop")).pack(side='left', padx=2)
        ttk.Button(bf, text="✏️ EDITAR", style="Blue.TButton", command=self.open_edit_task_dialog).pack(side='left', padx=5) 
        ttk.Button(bf, text="📥 ZIP", style="Orange.TButton", command=self.do_down).pack(side='left', padx=2)
        ttk.Button(bf, text="🗑 BORRAR", style="Red.TButton", command=lambda: self.do_act("delete")).pack(side='right', padx=2)

    def _popup_menu(self, event):
        """Abre el menú contextual por teclado (Menú / Shift+F10) si hay selección."""
        sel = self.tree.selection()
        if not sel:
            return
        bbox = self.tree.bbox(sel[0])
        if bbox:
            x, y, _, h = bbox
            self.ctx_menu.tk_popup(self.tree.winfo_rootx() + x, self.tree.winfo_rooty() + y + h)
        else:
            self.ctx_menu.tk_popup(self.tree.winfo_rootx() + 20, self.tree.winfo_rooty() + 20)
        self.ctx_menu.grab_release()

    def open_edit_task_dialog(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Atención", "Selecciona una tarea de la lista para editar.")
            return
            
        item = self.tree.item(selected[0])
        raw_values = item['values']
        if not raw_values:
            messagebox.showwarning("Atención", "No se pudieron obtener los datos de la fila seleccionada.")
            return

        task_id = raw_values[0]
        
        try:
            url = f"{self.server_ip.get().rstrip('/')}/status"
            r = requests.get(url, timeout=5)
            if r.status_code != 200:
                messagebox.showerror("Error", f"Servidor devolvió código {r.status_code}")
                return
                
            tasks_data = r.json().get('tasks', [])
            current_task = None
            for t in tasks_data:
                tid = t.get('id') if t.get('id') is not None else t.get('task_id')
                if str(tid).strip() == str(task_id).strip():
                    current_task = t
                    break

            if not current_task:
                messagebox.showerror("Error", f"No se encontraron los datos de la Tarea #{task_id} en el servidor.")
                return

        except Exception as e:
            messagebox.showerror("Error", f"Error de conexión al consultar tarea: {e}")
            return

        cfg = current_task.get('config', {})

        edit_win = tk.Toplevel(self.root)
        edit_win.title(f"Editar Tarea #{task_id}")
        edit_win.geometry("380x350")
        edit_win.transient(self.root)
        edit_win.grab_set()
        edit_win.bind("<Escape>", lambda e: edit_win.destroy())

        f = ttk.Frame(edit_win, padding=15)
        f.pack(fill='both', expand=True)

        ttk.Label(f, text="Nombre:").grid(row=0, column=0, sticky='w', pady=5)
        entry_name = ttk.Entry(f, width=25)
        entry_name.insert(0, cfg.get('name', current_task.get('name', '')))
        entry_name.grid(row=0, column=1, pady=5)
        fluent.set_automation_name(entry_name, "Nombre de la tarea", "Nombre de la misión")

        ttk.Label(f, text="Intervalo (Min):").grid(row=1, column=0, sticky='w', pady=5)
        entry_interval = ttk.Entry(f, width=25)
        entry_interval.insert(0, str(cfg.get('interval', 1)))
        entry_interval.grid(row=1, column=1, pady=5)
        fluent.set_automation_name(entry_interval, "Intervalo en minutos", "Cada cuántos minutos capturar")

        ttk.Label(f, text="Sensibilidad Alerta (%):").grid(row=2, column=0, sticky='w', pady=5)
        entry_alert = ttk.Entry(f, width=25)
        entry_alert.insert(0, str(cfg.get('alert_pct', 5.0)))
        entry_alert.grid(row=2, column=1, pady=5)
        fluent.set_automation_name(entry_alert, "Sensibilidad de alerta", "Porcentaje de cambio que dispara alerta")

        ttk.Label(f, text="Límite MB:").grid(row=3, column=0, sticky='w', pady=5)
        entry_mb = ttk.Entry(f, width=25)
        entry_mb.insert(0, str(cfg.get('limit_mb', 1000)))
        entry_mb.grid(row=3, column=1, pady=5)
        fluent.set_automation_name(entry_mb, "Límite de MB", "Tamaño máximo de almacenamiento")

        ttk.Label(f, text="Duración (Horas, 0=Inf):").grid(row=4, column=0, sticky='w', pady=5)
        entry_dur = ttk.Entry(f, width=25)
        entry_dur.insert(0, str(cfg.get('duration_hours', 0)))
        entry_dur.grid(row=4, column=1, pady=5)
        fluent.set_automation_name(entry_dur, "Duración en horas", "Horas de duración; 0 es infinito")

        var_timelapse = tk.BooleanVar(value=cfg.get('save_timelapse', True))
        var_sentry = tk.BooleanVar(value=cfg.get('sentry', True))

        chk_time = ttk.Checkbutton(f, text="📷 Activar Timelapse", variable=var_timelapse)
        chk_time.grid(row=5, column=0, columnspan=2, sticky='w', pady=5)
        fluent.set_automation_name(chk_time, "Activar Timelapse", "Guardar capturas periódicas")

        chk_sent = ttk.Checkbutton(f, text="🛡️ Activar Centinela", variable=var_sentry)
        chk_sent.grid(row=6, column=0, columnspan=2, sticky='w', pady=5)
        fluent.set_automation_name(chk_sent, "Activar Centinela", "Vigilar cambios y generar alertas")

        entry_name.focus_set()

        def guardar_cambios():
            self._busy(btn_save, "⏳ GUARDANDO…")
            try:
                payload = {
                    "id": int(task_id),
                    "config": {
                        "name": entry_name.get(),
                        "interval": float(entry_interval.get()),
                        "alert_pct": float(entry_alert.get()),
                        "limit_mb": float(entry_mb.get()),
                        "duration_hours": float(entry_dur.get()),
                        "save_timelapse": var_timelapse.get(),
                        "sentry": var_sentry.get()
                    }
                }
                res = requests.post(f"{self.server_ip.get().rstrip('/')}/tasks/update", json=payload, timeout=5)
                if res.status_code == 200 and res.json().get('status') == 'ok':
                    messagebox.showinfo("Éxito", "¡Tarea actualizada correctamente!")
                    edit_win.destroy()
                    self.refresh()
                else:
                    messagebox.showerror("Error", f"No se pudo guardar: {res.text}")
            except Exception as ex:
                messagebox.showerror("Error", f"Fallo al guardar cambios: {ex}")
            finally:
                self._idle(btn_save)

        btn_save = ttk.Button(f, text="💾 GUARDAR CAMBIOS", style="Accent.TButton", command=guardar_cambios)
        btn_save.grid(row=7, column=0, columnspan=2, pady=15)

    def do_act(self, act):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Atención", "Selecciona primero una tarea de la lista.")
            return
        try: 
            requests.post(f"{self.server_ip.get().rstrip('/')}/tasks/{self.tree.item(sel[0])['values'][0]}/{act}", timeout=2)
            self.refresh()
        except Exception as e: 
            messagebox.showerror("Error", f"No se pudo ejecutar la acción «{act}»:\n{e}")
            
    def do_down(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Atención", "Selecciona primero una tarea de la lista.")
            return
        self.descargar_zip(self.tree.item(sel[0])['values'][0])

    def monitor_loop(self):
        """Bucle en hilo secundario para refrescar el estado global de forma asíncrona."""
        while self.running: 
            try: 
                self.refresh() 
            except Exception: 
                pass
            time.sleep(2)

    def refresh(self):
        try:
            r = requests.get(f"{self.server_ip.get().rstrip('/')}/status", timeout=2)
            r_plan = requests.get(f"{self.server_ip.get().rstrip('/')}/plan/status", timeout=2)
            
            if r.status_code == 200:
                d = r.json()
                p = r_plan.json() if r_plan.status_code == 200 else {"active": False}
                self.root.after(0, lambda: self.upd_ui(d, p))
        except Exception: 
            pass

    def upd_ui(self, d, p):
        # 1. ACTUALIZAR EVALUADOR DE DAÑOS
        total_dano_px = sum(int(t.get('diff_px', 0)) for t in d.get('tasks', []))
        
        # Solo sobreescribe si el usuario no tiene seleccionado el campo (UX amigable)
        if hasattr(self, 'entry_damage') and str(self.root.focus_get()) != str(self.entry_damage):
            self.entry_damage.delete(0, tk.END)
            self.entry_damage.insert(0, str(total_dano_px))

        # 2. ACTUALIZAR BARRA DE PROGRESO DE PÍXELES
        if hasattr(self, 'prog_bar') and p.get("active"):
            try:
                maximos_str = self.pl_max.get()
                if maximos_str.isdigit():
                    max_px = int(maximos_str)
                    px_objetivo = p.get('px_objetivo', 0)
                    restante_sec = p.get('restante', 0)
                    
                    # Cálculo de píxeles disponibles basado en el tiempo restante
                    # (Si faltan N segundos, se descuentan a razón de 1px / 30s)
                    px_actuales = max(0, px_objetivo - int(restante_sec / 30))
                    
                    # Actualizar UI
                    if str(self.root.focus_get()) != str(self.pl_actuales):
                        self.pl_actuales.delete(0, tk.END)
                        self.pl_actuales.insert(0, str(px_actuales))
                    
                    porcentaje = (px_actuales / max_px) * 100.0 if max_px > 0 else 0
                    self.prog_bar['value'] = min(porcentaje, 100.0)
                    completo = porcentaje >= 100
                    self.lbl_prog.config(
                        text=f"{'✅' if completo else '⏳'} Generación: {px_actuales} / {max_px} px ({porcentaje:.1f}%)",
                        foreground=self._token["success_fg"] if completo else self._token["text"]
                    )
            except Exception:
                pass

        sid = None
        sel = self.tree.selection()
        if sel: 
            sid = self.tree.item(sel[0])['values'][0]
            
        self.lbl_cpu.config(text=f"CPU: {d['system']['cpu']}%")
        self.lbl_ram.config(text=f"RAM: {d['system']['ram']}%")
        
        for r in self.tree.get_children(): 
            self.tree.delete(r)
            
        for t in d['tasks']:
            m = []
            if "T" in t['mode']: m.append("Timelapse")
            if "S" in t['mode']: m.append("Centinela")
            tag = 'run' if t['status']=='running' else 'stop'
            if t['status']=='error': tag='err'
            
            source_show = t.get('source', 'WPlace') 
            
            item = self.tree.insert("", "end", values=(
                t['id'], t['name'], source_show, " + ".join(m) or "Inactivo", 
                t.get('start_str'), t['status'].upper(), t['captures'], t['restante'], t['diff_actual']
            ), tags=(tag,))
            
            if str(t['id']) == str(sid): 
                self.tree.selection_set(item)
                
        self.tree.tag_configure('run', foreground=self._token["success_fg"])
        self.tree.tag_configure('err', foreground=self._token["error_fg"])

        if hasattr(self, 'lbl_plan_res'):
            if p.get("active"):
                config_txt = p.get('config_txt', '')
                if p.get("expired"):
                    estado_completado = f"✅ ¡TIEMPO CUMPLIDO - LISTO PARA PINTAR!\n\n{config_txt}"
                    self.lbl_plan_res.config(text=estado_completado, foreground=self._token["success_fg"])
                else:
                    rest = p['restante']
                    hrs = int(rest // 3600)
                    mins = int((rest % 3600) // 60)
                    estado_vivo = f"⏳ ALERTA ACTIVA EN SERVIDOR: Faltan {hrs}h {mins}m\n\n{config_txt}"
                    self.lbl_plan_res.config(text=estado_vivo, foreground=self._token["info_fg"])
            else:
                if "ALERTA ACTIVA" in self.lbl_plan_res.cget("text") or "TIEMPO CUMPLIDO" in self.lbl_plan_res.cget("text"):
                    self.lbl_plan_res.config(text="Ingresa tus datos para generar el plan...", foreground=self._token["text"])

    # ================= PESTAÑA SISTEMA =================
    def setup_tab_system(self):
        f = ttk.LabelFrame(self.tab_system, text="Apariencia (Fluent)")
        f.pack(fill='x', padx=20, pady=(20, 5))
        ttk.Label(f, text="Tema del sistema:").pack(side='left', padx=10, pady=8)
        self.var_theme = tk.StringVar(value=self.theme.mode)
        for mode, txt in (("auto", "Automático"), ("light", "Claro"),
                          ("dark", "Oscuro"), ("high_contrast", "Alto contraste")):
            rb = ttk.Radiobutton(
                f, text=txt, value=mode, variable=self.var_theme,
                command=lambda m=mode: self.set_theme_mode(m),
            )
            rb.pack(side='left', padx=8)
            fluent.set_automation_name(rb, f"Tema {txt}", f"Usar el tema {txt}")

        g = ttk.LabelFrame(self.tab_system, text="Gestión Global")
        g.pack(fill='both', padx=20, pady=10)
        self.btn_inspeccionar = ttk.Button(g, text="🔍 INSPECCIONAR CAPTURA", style="Accent.TButton", command=self.inspect_file)
        self.btn_inspeccionar.pack(pady=10, fill='x')
        fluent.attach_tooltip(self.btn_inspeccionar, "Leer los metadatos de un PNG de captura", name="Inspeccionar captura")
        self.btn_backup = ttk.Button(g, text="📥 DESCARGAR BACKUP COMPLETO", style="Orange.TButton", command=lambda: self.descargar_zip(None, btn=self.btn_backup))
        self.btn_backup.pack(pady=10, fill='x')
        fluent.attach_tooltip(self.btn_backup, "Descargar un ZIP con todas las fotos", name="Descargar backup")
        btn_carpeta = ttk.Button(g, text="📂 ABRIR CARPETA LOCAL", style="Blue.TButton", command=lambda: self.abrir_carpeta(OUTPUT_FOLDER))
        btn_carpeta.pack(pady=10, fill='x')
        fluent.attach_tooltip(btn_carpeta, "Abrir la carpeta local de descargas", name="Abrir carpeta local")
        
        f2 = ttk.LabelFrame(self.tab_system, text="Zona de Peligro")
        f2.pack(fill='x', padx=20, pady=10)
        self.btn_del_tasks = ttk.Button(f2, text="🧹 ELIMINAR TODAS LAS TAREAS", style="Warning.TButton", command=self.del_all_tasks)
        self.btn_del_tasks.pack(side='left', expand=True, padx=5, pady=10)
        fluent.attach_tooltip(self.btn_del_tasks, "Peligro: borra todas las tareas del servidor", name="Eliminar todas las tareas")
        self.btn_del_photos = ttk.Button(f2, text="🔥 ELIMINAR TODAS LAS FOTOS", style="Red.TButton", command=self.del_all_photos)
        self.btn_del_photos.pack(side='right', expand=True, padx=5, pady=10)
        fluent.attach_tooltip(self.btn_del_photos, "Peligro: borra todas las fotos guardadas", name="Eliminar todas las fotos")

    def inspect_file(self):
        f = filedialog.askopenfilename(title="Seleccionar PNG", filetypes=[("PNG", "*.png")])
        if f:
            try:
                img = Image.open(f)
                img.load()
                raw_data = img.info.get("Description") or img.text.get("Description")
                if raw_data:
                    json_data = json.loads(raw_data)
                    formatted_json = json.dumps(json_data, indent=2)
                    pyperclip.copy(formatted_json)
                    messagebox.showinfo("Inspección", f"📁 {os.path.basename(f)}\n\n📍 JSON:\n{formatted_json}\n\n✅ Copiado al portapapeles!")
                else: 
                    messagebox.showwarning("Aviso", "Sin metadatos JSON.")
            except Exception as e: 
                messagebox.showerror("Error", str(e))

    def descargar_zip(self, tid=None, btn=None):
        self._busy(btn, "⏳ DESCARGANDO…")
        try:
            url = f"{self.server_ip.get().rstrip('/')}/download_zip" + (f"?task_id={tid}" if tid else "")
            r = requests.get(url, stream=True, timeout=10)
            if r.status_code == 200:
                if not os.path.exists(OUTPUT_FOLDER): 
                    os.makedirs(OUTPUT_FOLDER)
                p = f"{OUTPUT_FOLDER}/{f'task_{tid}' if tid else 'full'}_{datetime.now().strftime('%H%M%S')}.zip"
                with open(p, 'wb') as f: 
                    for chunk in r.iter_content(8192): 
                        f.write(chunk)
                messagebox.showinfo("OK", f"Descargado en:\n{p}")
                self.abrir_carpeta(OUTPUT_FOLDER)
        except Exception as e: 
            messagebox.showerror("Error", str(e))
        finally:
            self._idle(btn)

    def del_all_tasks(self): 
        if messagebox.askyesno("CONFIRMAR", "¿Borrar todas las tareas?"): 
            try: requests.post(f"{self.server_ip.get().rstrip('/')}/delete_tasks", timeout=3)
            except Exception as e: messagebox.showerror("Error", str(e))

    def del_all_photos(self): 
        if messagebox.askyesno("PELIGRO", "¿Borrar todas las fotos?"): 
            try: requests.post(f"{self.server_ip.get().rstrip('/')}/delete_photos", timeout=3)
            except Exception as e: messagebox.showerror("Error", str(e))

    def stop_all(self): 
        try: requests.post(f"{self.server_ip.get().rstrip('/')}/stop_all", timeout=3)
        except Exception as e: print(f"Error stop_all: {e}")


    def check_updates(self):
        try:
            has, latest, url = check_for_updates()
            if has:
                import webbrowser
                if messagebox.askyesno("Actualización disponible", f"Nueva versión v{latest} disponible. ¿Abrir descarga?"):
                    webbrowser.open(url)
            else:
                messagebox.showinfo("Sin actualizaciones", "Estás en la última versión (v{0})".format(APP_VERSION))
        except Exception as e:
            messagebox.showerror("Error", str(e))
if __name__ == "__main__":
    root = tk.Tk()
    app = WPlaceClient(root)
    root.mainloop()