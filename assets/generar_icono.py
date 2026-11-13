"""Genera assets/icono.ico y assets/icono.png (ejecutar una vez)."""
from pathlib import Path
from PIL import Image, ImageDraw

S = 1024  # se dibuja grande y se reduce para que quede suave
aqui = Path(__file__).parent

img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# Fondo: cuadrado redondeado oscuro
d.rounded_rectangle((32, 32, S - 32, S - 32), radius=200, fill=(30, 34, 46, 255))

# "Foto": cielo degradado + montañas + sol
fx0, fy0, fx1, fy1 = 150, 210, S - 150, S - 210
foto = Image.new("RGBA", (fx1 - fx0, fy1 - fy0))
fd = ImageDraw.Draw(foto)
fw, fh = foto.size
for y in range(fh):
    t = y / fh
    fd.line((0, y, fw, y), fill=(int(255 - 120 * t), int(140 + 40 * t), int(90 + 120 * t), 255))
fd.ellipse((fw * 0.62, fh * 0.14, fw * 0.82, fh * 0.14 + fw * 0.2), fill=(255, 236, 160, 255))
fd.polygon([(0, fh), (fw * 0.3, fh * 0.42), (fw * 0.55, fh), ], fill=(48, 92, 88, 255))
fd.polygon([(fw * 0.3, fh), (fw * 0.68, fh * 0.5), (fw, fh * 0.85), (fw, fh)], fill=(34, 66, 70, 255))
img.alpha_composite(foto, (fx0, fy0))

# Zona fuera del recorte oscurecida
sombra = Image.new("RGBA", (S, S), (0, 0, 0, 0))
sd = ImageDraw.Draw(sombra)
cx0, cy0, cx1, cy1 = 250, 300, S - 250, S - 300
for caja in [(fx0, fy0, fx1, cy0), (fx0, cy1, fx1, fy1), (fx0, cy0, cx0, cy1), (cx1, cy0, fx1, cy1)]:
    sd.rectangle(caja, fill=(0, 0, 0, 140))
img.alpha_composite(sombra)

# Marco de recorte con esquinas gruesas
cian = (0, 208, 255, 255)
d = ImageDraw.Draw(img)
d.rectangle((cx0, cy0, cx1, cy1), outline=cian, width=12)
L, G = 130, 44  # largo y grosor de las esquinas


def rect(xa, ya, xb, yb):
    d.rectangle((min(xa, xb), min(ya, yb), max(xa, xb), max(ya, yb)), fill=cian)


for x, y, sx, sy in [(cx0, cy0, 1, 1), (cx1, cy0, -1, 1), (cx0, cy1, 1, -1), (cx1, cy1, -1, -1)]:
    rect(x - sx * G // 2, y - sy * G // 2, x + sx * L, y + sy * G // 2)   # brazo horizontal
    rect(x - sx * G // 2, y - sy * G // 2, x + sx * G // 2, y + sy * L)   # brazo vertical

final = img.resize((256, 256), Image.LANCZOS)
final.save(aqui / "icono.png")
final.save(aqui / "icono.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("ok")
