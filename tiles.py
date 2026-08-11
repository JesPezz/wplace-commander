import requests
from io import BytesIO
from PIL import Image

SOURCES = {
    "WPlace": "https://backend.wplace.live/files/s0/tiles",
}

MAX_PIXELS = 25_000_000

_session = None


def _get_session():
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({"User-Agent": "Mozilla/5.0"})
    return _session


def download_area(coords, source="WPlace", timeout=10):
    """Descarga una región de tiles (1000px c/u) y la compone en una sola imagen RGBA.

    Retorna None si la región es inválida o excede MAX_PIXELS.
    Los tiles que fallan se omiten en silencio (tolerancia a regiones incompletas).
    """
    base_url = SOURCES.get(source, SOURCES["WPlace"])
    w = coords["x_end"] - coords["x_start"]
    h = coords["y_end"] - coords["y_start"]
    if w <= 0 or h <= 0 or w * h > MAX_PIXELS:
        return None

    full_img = Image.new("RGBA", (w, h))
    tx_s, tx_e = coords["x_start"] // 1000, (coords["x_end"] - 1) // 1000
    ty_s, ty_e = coords["y_start"] // 1000, (coords["y_end"] - 1) // 1000
    session = _get_session()
    for tx in range(tx_s, tx_e + 1):
        for ty in range(ty_s, ty_e + 1):
            url = f"{base_url}/{tx}/{ty}.png"
            try:
                r = session.get(url, timeout=timeout)
                if r.status_code == 200:
                    tile = Image.open(BytesIO(r.content)).convert("RGBA")
                    full_img.paste(tile, ((tx * 1000) - coords["x_start"], (ty * 1000) - coords["y_start"]), tile)
            except Exception:
                pass
    return full_img
