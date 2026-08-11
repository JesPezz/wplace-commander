"""
fluent.py - Paleta de estilos Fluent Design y utilidades de UI para WPlace Commander.

Diseñado para maximizar la fidelidad a Microsoft Fluent Design System dentro de
las capacidades de Tkinter. Nota técnica: Tk no expone Mica/Acrylic nativos,
Per-Monitor DPI, Snap Layouts ni la translucidez del sistema; este módulo
aproxima esos efectos con paletas/materiales coherentes y aplica lo que Tk sí
puede lograr (tema dinámico claro/oscuro/alto contraste, tipografía Segoe UI,
NavigationView colapsable, transiciones y accesibilidad).
"""

import ctypes
import os
import platform
import subprocess
import tkinter as tk
from tkinter import ttk

__all__ = [
    "ACCENT", "FONT_UI", "FONT_FALLBACK", "DEFAULT_TOUCH",
    "is_windows", "enable_dpi_awareness", "FluentTheme", "system_font",
    "configure_styles", "apply_focus_highlight", "set_automation_name",
    "schedule_transition", "show_toast",
]

ACCENT = "#0078D4"
ACCENT_DARK = "#60CDFF"

FONT_UI = "Segoe UI Variable Text"
FONT_FALLBACK = "Segoe UI"
DEFAULT_TOUCH = 40  # píxeles lógicos mínimos recomendados por las pautas de touch Fluent

# Tipografía: la escala tipográfica estándar de Windows (Caption/Body/Subtitle/Title)
TYPE = {
    "caption": 12,
    "body": 14,
    "bodyStrong": 14,
    "subtitle": 20,
    "title": 28,
    "titleLarge": 40,
}


def is_windows():
    return platform.system() == "Windows"


# =====================================================================
# HIGH DPI AWARENESS
# =====================================================================
_PMDA_V2 = 2      # PROCESS_PER_MONITOR_DPI_AWARE
_PMDA_V1 = 1      # PROCESS_SYSTEM_DPI_AWARE


def enable_dpi_awareness():
    """Activa la mejor awareness DPI disponible (Per-Monitor V2) si es Windows.

    Tk no escala por monitor a nivel de sistema, pero declarar la awareness
    evita que Windows "des-dibuje" (bluree) la ventana al moverla de monitor.
    """
    if not is_windows():
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(_PMDA_V2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def system_font():
    """Devuelve la familia de fuente nativa del sistema (Segoe UI Variable en Windows)."""
    return FONT_UI if is_windows() else FONT_FALLBACK


# =====================================================================
# TEMA FLUENT
# =====================================================================
class FluentTheme:
    """Tokens de color según el modo del sistema (claro/oscuro/alto contraste)."""

    def __init__(self, mode="auto"):
        self.mode = mode  # "auto" | "light" | "dark" | "high_contrast"

    def resolve(self):
        m = self.mode
        if m == "auto":
            m = self._system_mode()
        if m == "high_contrast":
            return self._hc_tokens()
        dark = (m == "dark")
        return {
            "mode": "dark" if dark else "light",
            "bg": "#202020" if dark else "#F3F3F3",
            "card": "#2B2B2B" if dark else "#FFFFFF",
            "card2": "#323232" if dark else "#F9F9F9",
            "text": "#FFFFFF" if dark else "#1B1B1B",
            "subtext": "#B0B0B0" if dark else "#5D5D5D",
            "border": "#3F3F3F" if dark else "#E5E5E5",
            "accent": ACCENT_DARK if dark else ACCENT,
            "accent_fg": "#1B1B1B" if dark else "#FFFFFF",
            "acrylic": "#E6202020" if dark else "#E6F3F3F3",
            "hover": "#333333" if dark else "#E1E1E1",
            "selection": ACCENT_DARK if dark else "#CCE4F7",
            "table_header": "#323232" if dark else "#F0F0F0",
            "nav": "#2A2A2A" if dark else "#F9F9F9",
            "nav_selected": ACCENT_DARK if dark else ACCENT,
            "green": "#6CCB5F" if dark else "#107C10",
            "red": "#FF99A4" if dark else "#C42B1C",
            "orange": "#FFB900" if dark else "#CC7000",
            "blue": ACCENT_DARK if dark else ACCENT,
        }

    @staticmethod
    def _system_mode():
        """Lee el modo claro/oscuro del sistema en Windows (registro)."""
        if not is_windows():
            return "light"
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return "light" if value == 1 else "dark"
        except Exception:
            return "light"

    @staticmethod
    def _hc_tokens():
        return {
            "mode": "high_contrast",
            "bg": "#000000", "card": "#000000", "card2": "#000000",
            "text": "#FFFFFF", "subtext": "#FFFFFF", "border": "#FFFFFF",
            "accent": "#FFFF00", "accent_fg": "#000000", "acrylic": "#000000",
            "hover": "#1A1A1A", "selection": "#FFFF00", "table_header": "#000000",
            "nav": "#000000", "nav_selected": "#FFFF00",
            "green": "#FFFFFF", "red": "#FFFFFF", "orange": "#FFFFFF", "blue": "#FFFFFF",
        }


# =====================================================================
# ESTILOS TTK FLUENT
# =====================================================================
def configure_styles(style, token):
    """Aplica los estilos ttk con los tokens del tema actual."""
    font_body = (system_font(), TYPE["body"])
    font_body_bold = (system_font(), TYPE["body"], "bold")

    style.theme_use("clam")
    style.configure(".", font=font_body, background=token["bg"], foreground=token["text"])

    # Frames y paneles
    style.configure("TFrame", background=token["bg"])
    style.configure("Card.TFrame", background=token["card"], relief="flat", borderwidth=1)
    style.configure("Nav.TFrame", background=token["nav"], relief="flat", borderwidth=0)
    style.configure("Content.TFrame", background=token["bg"])

    # Labels
    style.configure("TLabel", background=token["bg"], foreground=token["text"])
    style.configure("Card.TLabel", background=token["card"], foreground=token["text"])
    style.configure("Subtle.TLabel", background=token["bg"], foreground=token["subtext"])
    style.configure(
        "Title.TLabel", background=token["bg"], foreground=token["text"],
        font=(system_font(), TYPE["subtitle"], "bold"),
    )
    style.configure(
        "Header.TLabel", background=token["nav"], foreground=token["text"],
        font=(system_font(), TYPE["bodyStrong"], "bold"),
    )

    # Botones (padding mínimo para touch target de 40px)
    pad = (14, 10)
    style.configure(
        "Accent.TButton", font=font_body_bold, background=token["accent"],
        foreground=token["accent_fg"], borderwidth=0, padding=pad,
    )
    style.map("Accent.TButton", background=[("active", token["hover"]), ("pressed", token["hover"])])

    style.configure(
        "TButton", font=font_body, background=token["card"], foreground=token["text"],
        borderwidth=1, relief="flat", padding=pad,
    )
    style.map(
        "TButton",
        background=[("active", token["hover"]), ("pressed", token["hover"])],
        bordercolor=[("focus", token["accent"])],
    )
    style.configure(
        "Outline.TButton", font=font_body, background=token["card2"],
        foreground=token["text"], borderwidth=1, padding=pad,
    )

    for name, color in (("Green", token["green"]), ("Red", token["red"]),
                        ("Orange", token["orange"]), ("Blue", token["blue"])):
        style.configure(
            f"{name}.TButton", font=font_body_bold, background=color,
            foreground=token["accent_fg"], borderwidth=0, padding=pad,
        )
        style.map(f"{name}.TButton", background=[("active", token["hover"])])
    style.configure(
        "Warning.TButton", font=font_body_bold, background=token["orange"],
        foreground="#1B1B1B", borderwidth=0, padding=pad,
    )

    # Entradas
    style.configure(
        "TEntry", fieldbackground=token["card"], foreground=token["text"],
        bordercolor=token["border"], insertcolor=token["text"], padding=6,
    )
    style.map("TEntry", bordercolor=[("focus", token["accent"])])
    style.configure(
        "TSpinbox", fieldbackground=token["card"], foreground=token["text"],
        bordercolor=token["border"], arrowsize=14, padding=6,
    )
    style.map("TSpinbox", bordercolor=[("focus", token["accent"])])

    # Checkbutton / Radiobutton
    style.configure(
        "TCheckbutton", background=token["bg"], foreground=token["text"],
        padding=(6, 6), font=font_body,
    )
    style.map("TCheckbutton", background=[("active", token["bg"])])
    style.configure(
        "TRadiobutton", background=token["bg"], foreground=token["text"],
        padding=(6, 6), font=font_body,
    )

    # Combobox
    style.configure(
        "TCombobox", fieldbackground=token["card"], background=token["card"],
        foreground=token["text"], arrowcolor=token["text"],
        bordercolor=token["border"], padding=6,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", token["card"])],
        selectbackground=[("readonly", token["selection"])],
    )

    # Treeview (Radar de Tareas)
    style.configure(
        "Treeview", background=token["card"], fieldbackground=token["card"],
        foreground=token["text"], borderwidth=0, rowheight=DEFAULT_TOUCH,
    )
    style.map(
        "Treeview",
        background=[("selected", token["accent"])],
        foreground=[("selected", token["accent_fg"])],
    )
    style.configure(
        "Treeview.Heading", font=font_body_bold, background=token["table_header"],
        foreground=token["text"], padding=(8, 10),
    )

    # PanedWindow y progreso
    style.configure("TPanedwindow", background=token["border"], sashwidth=6)
    style.configure(
        "Horizontal.TProgressbar", background=token["accent"],
        troughcolor=token["card"], bordercolor=token["border"], thickness=6,
    )


# =====================================================================
# FOCUS VISUAL Y AUTOMATIZACIÓN
# =====================================================================
def apply_focus_highlight(widget, color):
    """Añade un anillo de foco visible (FocusVisual) a widgets de Tk clásicos."""
    try:
        widget.configure(highlightthickness=2, highlightbackground=color)
        widget.bind(
            "<FocusIn>",
            lambda e: e.widget.configure(highlightthickness=2, highlightcolor=color),
        )
        widget.bind(
            "<FocusOut>",
            lambda e: e.widget.configure(highlightthickness=2, highlightbackground=color),
        )
    except tk.TclError:
        pass  # ttk no admite highlightthickness; se confía en el bordercolor "focus"


def set_automation_name(widget, name, description=None):
    """Asocia un nombre (y descripción) accesible a un widget.

    Tk no expone la API UIA completa del Narrador, pero marcamos el widget con
    metadatos utilizables por herramientas de accesibilidad asistentes y
    garantizamos que sea enfocable por teclado.
    """
    try:
        widget.configure(takefocus=1)
        widget.accessible_name = name
        widget.accessible_description = description or name
    except Exception:
        pass


# =====================================================================
# TRANSICIONES Y SKELETON
# =====================================================================
def schedule_transition(widget, color, steps=10, interval=16):
    """Anima de forma ligera (60 Hz) un cambio de color de fondo de un canvas.

    No bloquea la UI: programa pasos con after(). Es la aproximación de Tk a
    las transiciones suaves de Fluent.
    """
    try:
        base = widget.cget("background")
    except Exception:
        base = "#000000"
    try:
        target = _hex_to_rgb(color)
        start = _hex_to_rgb(base)
    except Exception:
        return

    def step(i):
        if i > steps:
            return
        t = i / steps
        rgb = tuple(int(start[c] + (target[c] - start[c]) * t) for c in range(3))
        try:
            widget.configure(background="#%02x%02x%02x" % rgb)
        except Exception:
            return
        widget.after(interval, lambda: step(i + 1))

    step(1)


def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# =====================================================================
# TOAST NOTIFICATIONS (notificaciones nativas de Windows)
# =====================================================================
_SHELL_SCRIPT = r"""
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.NotifyIcon]$n = New-Object System.Windows.Forms.NotifyIcon
$n.Icon = [System.Drawing.SystemIcons]::Information
$n.Visible = $true
$n.BalloonTipTitle = $env:TOAST_TITLE
$n.BalloonTipText = $env:TOAST_BODY
$n.ShowBalloonTip(6000)
Start-Sleep -Seconds 6
$n.Dispose()
"""


def show_toast(title, body, app_id="WPlace.Commander"):
    """Muestra una notificación nativa del sistema (balloon/Toast) en Windows.

    Utiliza PowerShell + Windows.Forms, que es lo más cercano a una Toast
    nativa sin WinRT. En plataformas no Windows no hace nada.
    """
    if not is_windows():
        return
    try:
        proc = subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", _SHELL_SCRIPT],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={
                **dict(os.environ),
                "TOAST_TITLE": title,
                "TOAST_BODY": body,
            },
        )
        return proc
    except Exception:
        return None
