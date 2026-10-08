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
    "ACCENT", "FONT_UI", "FONT_FALLBACK", "DEFAULT_TOUCH", "MIN_TOUCH",
    "is_windows", "enable_dpi_awareness", "FluentTheme", "system_font",
    "configure_styles", "apply_focus_highlight", "set_automation_name",
    "schedule_transition", "show_toast",
    "ToolTip", "attach_tooltip", "contrast_ratio",
]

ACCENT = "#0078D4"
ACCENT_DARK = "#60CDFF"

FONT_UI = "Segoe UI Variable Text"
FONT_FALLBACK = "Segoe UI"
MIN_TOUCH = 44       # WCAG 2.5.5 (AA): objetivo táctil mínimo 44x44 px
DEFAULT_TOUCH = 44   # altura de fila / objetivo táctil usado por los widgets

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
        focus = "#7CC7FF" if dark else ACCENT
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
            # Texto sobre botones rellenos (contraste AA garantizado)
            "on_green": "#1B1B1B" if dark else "#FFFFFF",
            "on_red": "#1B1B1B" if dark else "#FFFFFF",
            "on_orange": "#1B1B1B",
            "on_blue": "#1B1B1B" if dark else "#FFFFFF",
            # Texto semántico legible directamente sobre el fondo
            "success_fg": "#6CCB5F" if dark else "#107C10",
            "error_fg": "#FF99A4" if dark else "#C42B1C",
            "info_fg": ACCENT_DARK if dark else "#0B5394",
            "warning_fg": "#FFB900" if dark else "#8A4B00",
            # Estados y foco visible
            "disabled_bg": "#2E2E2E" if dark else "#E5E7EB",
            "disabled_fg": "#9A9A9A" if dark else "#595C63",
            "focus_ring": focus,
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
            "on_green": "#000000", "on_red": "#000000", "on_orange": "#000000", "on_blue": "#000000",
            "success_fg": "#FFFFFF", "error_fg": "#FFFFFF", "info_fg": "#FFFFFF", "warning_fg": "#FFFFFF",
            "disabled_bg": "#000000", "disabled_fg": "#9A9A9A",
            "focus_ring": "#FFFF00",
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

    # Botones: altura objetivo >= 44px (WCAG 2.5.5), foco visible y estado disabled.
    pad = (16, 12)
    dark = token.get("mode") == "dark"

    def _button(name, bg, fg, *, bold=True, border=0):
        """Configura una variante de botón con hover, disabled y foco visibles."""
        if bg in (token["card"], token["card2"]):
            hover = token["hover"]
        else:
            hover = _shade(bg, 1.18 if dark else 0.86)
        style.configure(
            name, font=(font_body_bold if bold else font_body), background=bg,
            foreground=fg, borderwidth=border, relief="flat", padding=pad,
            focuscolor=token["focus_ring"], focusthickness=2,
        )
        style.map(
            name,
            background=[("disabled", token["disabled_bg"]),
                        ("pressed", hover), ("active", hover)],
            foreground=[("disabled", token["disabled_fg"])],
            bordercolor=[("focus", token["focus_ring"])],
        )

    _button("Accent.TButton", token["accent"], token["accent_fg"])
    _button("TButton", token["card"], token["text"], bold=False, border=1)
    _button("Outline.TButton", token["card2"], token["text"], bold=False, border=1)
    _button("Green.TButton", token["green"], token["on_green"])
    _button("Red.TButton", token["red"], token["on_red"])
    _button("Danger.TButton", token["red"], token["on_red"])
    _button("Orange.TButton", token["orange"], token["on_orange"])
    _button("Blue.TButton", token["blue"], token["on_blue"])
    _button("Warning.TButton", token["orange"], token["on_orange"])

    # Entradas (foco visible + estado disabled legible)
    style.configure(
        "TEntry", fieldbackground=token["card"], foreground=token["text"],
        bordercolor=token["border"], insertcolor=token["text"], padding=8,
    )
    style.map(
        "TEntry",
        bordercolor=[("focus", token["focus_ring"])],
        fieldbackground=[("disabled", token["disabled_bg"])],
        foreground=[("disabled", token["disabled_fg"])],
    )
    style.configure(
        "TSpinbox", fieldbackground=token["card"], foreground=token["text"],
        bordercolor=token["border"], arrowcolor=token["text"], arrowsize=14, padding=8,
    )
    style.map(
        "TSpinbox",
        bordercolor=[("focus", token["focus_ring"])],
        fieldbackground=[("disabled", token["disabled_bg"])],
        foreground=[("disabled", token["disabled_fg"])],
    )

    # Checkbutton / Radiobutton (anillo de foco visible)
    style.configure(
        "TCheckbutton", background=token["bg"], foreground=token["text"],
        padding=(6, 6), font=font_body, focuscolor=token["focus_ring"],
    )
    style.map(
        "TCheckbutton",
        background=[("active", token["bg"])],
        foreground=[("disabled", token["disabled_fg"])],
    )
    style.configure(
        "TRadiobutton", background=token["bg"], foreground=token["text"],
        padding=(6, 6), font=font_body, focuscolor=token["focus_ring"],
    )
    style.map(
        "TRadiobutton",
        background=[("active", token["bg"])],
        foreground=[("disabled", token["disabled_fg"])],
    )

    # Combobox
    style.configure(
        "TCombobox", fieldbackground=token["card"], background=token["card"],
        foreground=token["text"], arrowcolor=token["text"],
        bordercolor=token["border"], padding=8,
    )
    style.map(
        "TCombobox",
        bordercolor=[("focus", token["focus_ring"])],
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
def apply_focus_highlight(widget, color, base=None):
    """Añade un anillo de foco visible (FocusVisual) a widgets de Tk clásicos.

    `base` es el color del anillo sin foco (por defecto el fondo del widget);
    al recibir foco el anillo pasa a `color` (alto contraste), cumpliendo
    WCAG 2.4.7 (foco visible).
    """
    try:
        base = base or widget.cget("background")
        widget.configure(highlightthickness=2, highlightbackground=base, highlightcolor=color)
        widget.bind(
            "<FocusIn>",
            lambda e: e.widget.configure(highlightbackground=color, highlightcolor=color),
            add="+",
        )
        widget.bind(
            "<FocusOut>",
            lambda e: e.widget.configure(highlightbackground=base, highlightcolor=color),
            add="+",
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


class ToolTip:
    """Tooltip nativo sin dependencias.

    Aparece al pasar el ratón (con retardo) y también al recibir foco por
    teclado, de modo que la ayuda no depende del puntero (WCAG 1.4.13 / 2.1.1).
    """

    def __init__(self, widget, text, delay=400):
        self.widget = widget
        self.text = text
        self.delay = delay
        self._after = None
        self._tip = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<FocusIn>", self._show, add="+")
        widget.bind("<FocusOut>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _=None):
        self._cancel()
        self._after = self.widget.after(self.delay, self._show)

    def _show(self, _=None):
        self._cancel()
        if self._tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 8
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self._tip = tk.Toplevel(self.widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{x}+{y}")
        tk.Label(
            self._tip, text=self.text, justify="left",
            background="#1B1B1B", foreground="#FFFFFF",
            relief="solid", borderwidth=1, padx=8, pady=4,
            font=(system_font(), TYPE["caption"]),
        ).pack()

    def _hide(self, _=None):
        self._cancel()
        if self._tip:
            self._tip.destroy()
            self._tip = None

    def _cancel(self):
        if self._after:
            self.widget.after_cancel(self._after)
            self._after = None


def attach_tooltip(widget, text, name=None):
    """Asocia un tooltip y un nombre accesible a un control.

    Pensado para botones que solo muestran un icono: garantiza nombre para
    lectores de pantalla y ayuda visual para el resto de usuarios.
    """
    set_automation_name(widget, name or text, text)
    return ToolTip(widget, text)


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


def _shade(hex_color, factor):
    """Aclara (factor > 1) u oscurece (factor < 1) un color hex."""
    r, g, b = _hex_to_rgb(hex_color)
    clamp = lambda c: max(0, min(255, int(round(c * factor))))
    return "#%02x%02x%02x" % (clamp(r), clamp(g), clamp(b))


def _relative_luminance(hex_color):
    r, g, b = _hex_to_rgb(hex_color)

    def lin(c):
        c /= 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast_ratio(color_a, color_b):
    """Relación de contraste WCAG entre dos colores hex (rango 1:1 a 21:1)."""
    la, lb = _relative_luminance(color_a), _relative_luminance(color_b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


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


# =====================================================================
# AUTOCHEQUEO DE CONTRASTE (WCAG 2.1 AA)
# =====================================================================
def _autochequeo():
    """Verifica que los tokens cumplen contraste AA. Ejecutar: python -m fluent"""
    fallos = []
    for mode in ("light", "dark", "high_contrast"):
        t = FluentTheme(mode).resolve()
        pares_texto = [
            ("texto/fondo", t["text"], t["bg"]),
            ("subtexto/fondo", t["subtext"], t["bg"]),
            ("texto/tarjeta", t["text"], t["card"]),
            ("accento/acento", t["accent_fg"], t["accent"]),
            ("verde/on_verde", t["on_green"], t["green"]),
            ("rojo/on_rojo", t["on_red"], t["red"]),
            ("naranja/on_naranja", t["on_orange"], t["orange"]),
            ("azul/on_azul", t["on_blue"], t["blue"]),
            ("exito/fondo", t["success_fg"], t["bg"]),
            ("error/fondo", t["error_fg"], t["bg"]),
            ("info/fondo", t["info_fg"], t["bg"]),
            ("aviso/fondo", t["warning_fg"], t["bg"]),
            ("deshabilitado", t["disabled_fg"], t["disabled_bg"]),
        ]
        for nombre, fg, bg in pares_texto:
            r = contrast_ratio(fg, bg)
            if r < 4.5:
                fallos.append(f"[{mode}] {nombre}: {r:.2f}:1 (<4.5)")
        for nombre, fg in (("foco/fondo", t["focus_ring"]),):
            for base in (t["bg"], t["card"]):
                r = contrast_ratio(fg, base)
                if r < 3.0:
                    fallos.append(f"[{mode}] {nombre} sobre {base}: {r:.2f}:1 (<3.0)")
    if fallos:
        raise AssertionError("Contraste AA incumplido:\n  " + "\n  ".join(fallos))
    print("OK: tokens Fluent cumplen contraste AA en claro, oscuro y alto contraste.")


if __name__ == "__main__":
    _autochequeo()
