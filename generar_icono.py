from PIL import Image, ImageDraw

def crear_icono_wplace():
    # Crear una imagen con fondo transparente
    size = (256, 256)
    icono = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(icono)

    # Dibujar un cuadrado redondeado de fondo (Color Raspberry/Comando)
    # Usamos el color rosa/fucsia de la Raspberry Pi
    draw.rounded_rectangle([10, 10, 246, 246], radius=40, fill=(233, 30, 99, 255))

    # Dibujar una "mira" o "píxel" central
    # Cuadrado blanco central (El Píxel)
    draw.rectangle([80, 80, 176, 176], fill=(255, 255, 255, 255))
    
    # Líneas de mira (Comando)
    draw.rectangle([120, 30, 136, 70], fill=(255, 255, 255, 255)) # Arriba
    draw.rectangle([120, 186, 136, 226], fill=(255, 255, 255, 255)) # Abajo
    draw.rectangle([30, 120, 70, 136], fill=(255, 255, 255, 255)) # Izquierda
    draw.rectangle([186, 120, 226, 136], fill=(255, 255, 255, 255)) # Derecha

    # Guardar como ICO (incluyendo tamaños estándar de Windows)
    icono.save("wplace_icon.ico", format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("✅ Archivo 'wplace_icon.ico' creado con éxito.")

if __name__ == "__main__":
    crear_icono_wplace()