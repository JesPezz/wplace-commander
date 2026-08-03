import os
from PIL import Image, ImageDraw

def crear_icono_wplace():
    # 1. Dibujar a súper alta resolución (512x512) para evitar pixeles dentados
    render_size = (512, 512)
    icono_hd = Image.new("RGBA", render_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(icono_hd)

    # Base con bordes suavemente redondeados (Fondo Rosa/Magenta Raspberry)
    draw.rounded_rectangle([20, 20, 492, 492], radius=80, fill=(233, 30, 99, 255))

    # El Píxel central (Cuadrado Blanco)
    draw.rectangle([160, 160, 352, 352], fill=(255, 255, 255, 255))
    
    # Miras tácticas (Líneas de comando)
    draw.rectangle([240, 60, 272, 140], fill=(255, 255, 255, 255))   # Arriba
    draw.rectangle([240, 372, 272, 452], fill=(255, 255, 255, 255))  # Abajo
    draw.rectangle([60, 240, 140, 272], fill=(255, 255, 255, 255))   # Izquierda
    draw.rectangle([372, 240, 452, 272], fill=(255, 255, 255, 255))  # Derecha

    # 2. Generar versiones escaladas con filtrado de alta calidad (LANCZOS)
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    icon_images = [icono_hd.resize(s, Image.Resampling.LANCZOS) for s in sizes]

    # 3. Guardar como ICO compuesto en el directorio actual
    output_path = "wplace_icon.ico"
    icon_images[0].save(
        output_path,
        format="ICO",
        append_images=icon_images[1:],
        sizes=sizes
    )
    print(f"✅ Icono profesional creado correctamente en: {os.path.abspath(output_path)}")

if __name__ == "__main__":
    crear_icono_wplace()
