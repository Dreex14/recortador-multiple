"""
Recortador Múltiple: recorta muchas imágenes a la vez con un editor visual.
(Recortador Múltiple: crop many images at once with a visual editor.)

1. Abre una carpeta con imagenes (o arrastra la carpeta encima de este archivo).
2. Ajusta el recorte en una imagen arrastrando las esquinas, los lados o el
   rectangulo entero (o escribiendo los numeros exactos).
3. Pulsa "Recortar" y despues elige si aplicar el mismo recorte al resto
   de imagenes de la carpeta.

Los recortes se guardan en la subcarpeta "recortadas" ("cropped" en ingles).
Los originales no se tocan.

Idioma: si la distribucion del teclado es espanola (de Espana o latinoamericana)
la interfaz sale en espanol; con cualquier otra, en ingles.

Uso:
    python recortar.pyw
    python recortar.pyw "C:/ruta/a/la/carpeta"

Hecho por Dreex · Licencia MIT
"""
import locale
import os
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

EXTENSIONES = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}
TAM_ASA = 5          # medio lado del cuadradito de las asas (px de pantalla)
ALCANCE_ASA = 10     # distancia a la que se "engancha" un asa o lado
MIN_LADO = 4         # tamano minimo del recorte (px reales)
LUPA_RADIO = 24      # px reales alrededor del cursor que muestra la lupa
LUPA_ZOOM = 5

TEXTOS = {
    "es": {
        "salida": "recortadas",
        "abrir": "Abrir carpeta...",
        "sin_carpeta": "Ninguna carpeta abierta",
        "X": "X", "Y": "Y", "W": "Ancho", "H": "Alto",
        "auto": "Quitar bordes negros (auto)",
        "todo": "Seleccionar todo",
        "recortar": "Recortar  ✂",
        "ayuda": "Arrastra esquinas o lados para ajustar · dentro para mover · "
                 "fuera para dibujar uno nuevo · flechas = 1 px (Mayús = 10 px)",
        "elige": "Elige la carpeta con las imágenes",
        "sin_imgs_t": "Sin imágenes",
        "sin_imgs": "No hay imágenes en:\n{carpeta}",
        "error": "Error",
        "error_guardar": "No se pudo guardar {nombre}:\n{ex}",
        "hecho": "Hecho",
        "guardada_en": "Guardada en:\n{salida}",
        "lote_t": "Recortar las demás",
        "lote": "Guardada «{nombre}» ({ancho}×{alto}).\n\n"
                "¿Aplicar el mismo recorte a las otras {n} imágenes de la carpeta?\n\n"
                "Solo se recortarán las que midan {rw}×{rh}; las demás se saltan.\n"
                "Se guardan en «{carpeta}», los originales no se tocan.",
        "progreso": "Recortando {i}/{n} · {nombre}",
        "listo": "Listo: {n} imágenes recortadas en {salida}",
        "resumen": "{n} imágenes recortadas en:\n{salida}",
        "saltadas": "{n} saltadas por tener otro tamaño:",
        "errores": "{n} con error:",
    },
    "en": {
        "salida": "cropped",
        "abrir": "Open folder...",
        "sin_carpeta": "No folder open",
        "X": "X", "Y": "Y", "W": "Width", "H": "Height",
        "auto": "Remove black borders (auto)",
        "todo": "Select all",
        "recortar": "Crop  ✂",
        "ayuda": "Drag corners or edges to resize · inside to move · "
                 "outside to draw a new one · arrows = 1 px (Shift = 10 px)",
        "elige": "Choose the folder with the images",
        "sin_imgs_t": "No images",
        "sin_imgs": "There are no images in:\n{carpeta}",
        "error": "Error",
        "error_guardar": "Could not save {nombre}:\n{ex}",
        "hecho": "Done",
        "guardada_en": "Saved to:\n{salida}",
        "lote_t": "Crop the rest",
        "lote": "Saved \"{nombre}\" ({ancho}×{alto}).\n\n"
                "Apply the same crop to the other {n} images in the folder?\n\n"
                "Only images that are {rw}×{rh} will be cropped; the rest are skipped.\n"
                "They are saved in \"{carpeta}\"; the originals are not modified.",
        "progreso": "Cropping {i}/{n} · {nombre}",
        "listo": "Done: {n} images cropped in {salida}",
        "resumen": "{n} images cropped in:\n{salida}",
        "saltadas": "{n} skipped because they are a different size:",
        "errores": "{n} with errors:",
    },
}


ESPANOL = 0x0A  # identificador de idioma principal del español en Windows (LANGID)


def es_espanol(langid):
    """Cualquier variante: España (0x040A, 0x0C0A), México (0x080A),
    Latinoamérica (0x580A), etc. comparten el idioma principal 0x0A."""
    return langid & 0x3FF == ESPANOL


def detectar_idioma():
    """Español si el teclado de Windows es español (castellano o latinoamericano);
    en cualquier otro caso, inglés. La variable RECORTADOR_IDIOMA=es|en lo fuerza."""
    forzado = os.environ.get("RECORTADOR_IDIOMA", "").lower()
    if forzado in TEXTOS:
        return forzado
    if sys.platform == "win32":
        try:
            import ctypes
            u32 = ctypes.windll.user32
            # Idioma de entrada activo (parte baja del HKL)...
            if es_espanol(u32.GetKeyboardLayout(0) & 0xFFFF):
                return "es"
            # ...y distribución física del teclado (KLID, p. ej. "0000080A" = latinoamericano)
            buf = ctypes.create_unicode_buffer(9)
            if u32.GetKeyboardLayoutNameW(buf) and es_espanol(int(buf.value, 16) & 0xFFFF):
                return "es"
            return "en"
        except (AttributeError, OSError, ValueError):
            pass
    nombre = (locale.getlocale()[0] or os.environ.get("LANG", "")).lower()
    return "es" if nombre.startswith(("es", "spanish")) else "en"


def recurso(nombre):
    """Ruta a un archivo de assets/, tanto desde el script como dentro del .exe."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / "assets" / nombre


CURSORES = {
    frozenset("l"): "sb_h_double_arrow", frozenset("r"): "sb_h_double_arrow",
    frozenset("t"): "sb_v_double_arrow", frozenset("b"): "sb_v_double_arrow",
    frozenset("lt"): "size_nw_se", frozenset("rb"): "size_nw_se",
    frozenset("rt"): "size_ne_sw", frozenset("lb"): "size_ne_sw",
}


def listar_imagenes(carpeta: Path):
    return sorted(p for p in carpeta.iterdir()
                  if p.is_file() and p.suffix.lower() in EXTENSIONES)


def guardar_recorte(origen: Path, destino: Path, caja):
    with Image.open(origen) as im:
        recorte = im.crop(caja)
        opciones = {}
        if origen.suffix.lower() in (".jpg", ".jpeg"):
            opciones = {"quality": 95, "subsampling": 0}
            if recorte.mode not in ("RGB", "L"):
                recorte = recorte.convert("RGB")
        recorte.save(destino, **opciones)


def detectar_bordes(im: Image.Image, umbral=8, proporcion=0.6):
    """Caja sin los bordes negros. Una columna/fila del borde cuenta como franja
    si al menos `proporcion` de sus pixeles son negros (asi se ignoran pequenos
    elementos superpuestos, como la pantalla tactil del emulador)."""
    w, h = im.size
    negro = im.convert("L").point(lambda v: 255 if v <= umbral else 0)

    def recortar_extremos(fracciones):
        ini, fin = 0, len(fracciones)
        while ini < fin and fracciones[ini] >= proporcion:
            ini += 1
        while fin > ini and fracciones[fin - 1] >= proporcion:
            fin -= 1
        return ini, fin

    def valores(im1d):
        # getdata() esta obsoleto desde Pillow 13; se mantiene por compatibilidad
        f = getattr(im1d, "get_flattened_data", None) or im1d.getdata
        return [v / 255 for v in f()]

    cols = valores(negro.resize((w, 1), Image.BOX))
    x0, x1 = recortar_extremos(cols)
    if x1 - x0 < MIN_LADO:
        return (0, 0, w, h)
    filas = valores(negro.crop((x0, 0, x1, h)).resize((1, h), Image.BOX))
    y0, y1 = recortar_extremos(filas)
    if y1 - y0 < MIN_LADO:
        return (0, 0, w, h)
    return (x0, y0, x1, y1)


class Editor(tk.Tk):
    def __init__(self, carpeta=None):
        super().__init__()
        self.title("Recortador Múltiple")
        self.geometry("1280x820")
        self.minsize(800, 500)
        try:
            self.iconbitmap(default=str(recurso("icono.ico")))
        except tk.TclError:
            pass

        self.idioma = detectar_idioma()
        self.carpeta = None
        self.imagenes = []
        self.indice = 0
        self.img = None              # imagen original (PIL)
        self.caja = [0, 0, 1, 1]     # recorte en px reales: x0, y0, x1, y1
        self.escala = 1.0
        self.ox = self.oy = 0        # desplazamiento de la imagen en el lienzo
        self._tk_img = None
        self._cache_vista = None
        self._arrastre = None
        self._sync = False
        self._cola = queue.Queue()

        self._construir_ui()
        self.bind("<Configure>", lambda e: self._programar_redibujo())
        for tecla, (dx, dy) in {"Left": (-1, 0), "Right": (1, 0),
                                "Up": (0, -1), "Down": (0, 1)}.items():
            self.bind(f"<{tecla}>", lambda e, d=(dx, dy): self._mover_teclado(*d, 1))
            self.bind(f"<Shift-{tecla}>", lambda e, d=(dx, dy): self._mover_teclado(*d, 10))

        if carpeta:
            self.after(50, lambda: self.abrir_carpeta(Path(carpeta)))
        else:
            self.after(50, self.elegir_carpeta)

    # ---------------------------------------------------------------- UI
    def _construir_ui(self):
        barra = ttk.Frame(self, padding=6)
        barra.pack(side="top", fill="x")
        self.btn_abrir = ttk.Button(barra, command=self.elegir_carpeta)
        self.btn_abrir.pack(side="left")
        ttk.Button(barra, text="◀", width=3, command=lambda: self.cambiar_imagen(-1)).pack(side="left", padx=(12, 0))
        ttk.Button(barra, text="▶", width=3, command=lambda: self.cambiar_imagen(1)).pack(side="left")
        self.lbl_info = ttk.Label(barra)
        self.lbl_info.pack(side="left", padx=10)

        panel = ttk.Frame(self, padding=(6, 0, 6, 6))
        panel.pack(side="bottom", fill="x")

        self.vars, self.lbl_campos = {}, {}
        for nombre in ("X", "Y", "W", "H"):
            self.lbl_campos[nombre] = ttk.Label(panel)
            self.lbl_campos[nombre].pack(side="left", padx=(8, 2))
            v = tk.IntVar()
            sb = ttk.Spinbox(panel, from_=0, to=99999, width=6, textvariable=v,
                             command=self._desde_campos)
            sb.pack(side="left")
            sb.bind("<Return>", lambda e: self._desde_campos())
            sb.bind("<FocusOut>", lambda e: self._desde_campos())
            self.vars[nombre] = v

        self.btn_auto = ttk.Button(panel, command=self.auto_bordes)
        self.btn_auto.pack(side="left", padx=(16, 4))
        self.btn_todo = ttk.Button(panel, command=self.seleccionar_todo)
        self.btn_todo.pack(side="left")

        self.btn_recortar = ttk.Button(panel, command=self.recortar)
        self.btn_recortar.pack(side="right")

        estado = ttk.Frame(self, padding=(6, 0))
        estado.pack(side="bottom", fill="x")
        self.progreso = ttk.Progressbar(estado, mode="determinate")
        self.progreso.pack(side="right", fill="x", expand=False, ipadx=100)
        self.lbl_estado = ttk.Label(estado)
        self.lbl_estado.pack(side="left")

        self.lienzo = tk.Canvas(self, bg="#202020", highlightthickness=0)
        self.lienzo.pack(fill="both", expand=True)
        self.lienzo.bind("<ButtonPress-1>", self._pulsar)
        self.lienzo.bind("<B1-Motion>", self._arrastrar)
        self.lienzo.bind("<ButtonRelease-1>", self._soltar)
        self.lienzo.bind("<Motion>", self._mover_raton)
        self._aplicar_textos()

    # ------------------------------------------------------------ idioma
    def t(self, clave, **datos):
        return TEXTOS[self.idioma][clave].format(**datos)

    def _aplicar_textos(self):
        self.btn_abrir.config(text=self.t("abrir"))
        self.btn_auto.config(text=self.t("auto"))
        self.btn_todo.config(text=self.t("todo"))
        self.btn_recortar.config(text=self.t("recortar"))
        for clave, lbl in self.lbl_campos.items():
            lbl.config(text=self.t(clave))
        self.lbl_estado.config(text=self.t("ayuda"))
        if self.img is None:
            self.lbl_info.config(text=self.t("sin_carpeta"))

    # ----------------------------------------------------------- carpeta
    def elegir_carpeta(self):
        ruta = filedialog.askdirectory(title=self.t("elige"),
                                       initialdir=self.carpeta or Path.cwd())
        if ruta:
            self.abrir_carpeta(Path(ruta))
        elif self.carpeta is None:
            self.destroy()

    def abrir_carpeta(self, carpeta: Path):
        imgs = listar_imagenes(carpeta)
        if not imgs:
            messagebox.showwarning(self.t("sin_imgs_t"), self.t("sin_imgs", carpeta=carpeta))
            if self.carpeta is None:
                self.elegir_carpeta()
            return
        self.carpeta, self.imagenes, self.indice = carpeta, imgs, 0
        self.cargar_imagen(primera_vez=True)

    def cambiar_imagen(self, paso):
        if not self.imagenes:
            return
        self.indice = (self.indice + paso) % len(self.imagenes)
        self.cargar_imagen()

    def cargar_imagen(self, primera_vez=False):
        ruta = self.imagenes[self.indice]
        anterior = self.img.size if self.img else None
        with Image.open(ruta) as im:
            im.load()
            self.img = im.convert("RGB")
        self._cache_vista = None
        # Se mantiene el recorte al pasar entre imagenes del mismo tamano
        if primera_vez or self.img.size != anterior:
            self.caja = list(detectar_bordes(self.img))
        self._limitar_caja()
        w, h = self.img.size
        self.lbl_info.config(text=f"{self.indice + 1}/{len(self.imagenes)} · {ruta.name} · {w}×{h} px"
                                  f"   —   {self.carpeta}")
        self._a_campos()
        self.redibujar()

    # ----------------------------------------------------------- dibujo
    def _programar_redibujo(self):
        if getattr(self, "_redibujo_pend", None):
            self.after_cancel(self._redibujo_pend)
        self._redibujo_pend = self.after(30, self.redibujar)

    def redibujar(self):
        self._redibujo_pend = None
        c = self.lienzo
        c.delete("all")
        if self.img is None:
            return
        cw, ch = max(c.winfo_width(), 50), max(c.winfo_height(), 50)
        w, h = self.img.size
        self.escala = min((cw - 20) / w, (ch - 20) / h, 1.0)
        vw, vh = max(1, round(w * self.escala)), max(1, round(h * self.escala))
        self.ox, self.oy = (cw - vw) // 2, (ch - vh) // 2
        if self._cache_vista != (vw, vh):
            self._tk_img = ImageTk.PhotoImage(self.img.resize((vw, vh), Image.LANCZOS))
            self._cache_vista = (vw, vh)
        c.create_image(self.ox, self.oy, anchor="nw", image=self._tk_img)
        self._dibujar_caja()

    def _dibujar_caja(self):
        c = self.lienzo
        c.delete("caja")
        x0, y0 = self._a_pantalla(self.caja[0], self.caja[1])
        x1, y1 = self._a_pantalla(self.caja[2], self.caja[3])
        ix0, iy0 = self._a_pantalla(0, 0)
        ix1, iy1 = self._a_pantalla(*self.img.size)
        sombra = dict(fill="black", stipple="gray50", width=0, tags="caja")
        c.create_rectangle(ix0, iy0, ix1, y0, **sombra)
        c.create_rectangle(ix0, y1, ix1, iy1, **sombra)
        c.create_rectangle(ix0, y0, x0, y1, **sombra)
        c.create_rectangle(x1, y0, ix1, y1, **sombra)
        # tercios como guia
        for i in (1, 2):
            gx = x0 + (x1 - x0) * i / 3
            gy = y0 + (y1 - y0) * i / 3
            c.create_line(gx, y0, gx, y1, fill="#ffffff", dash=(2, 4), tags="caja")
            c.create_line(x0, gy, x1, gy, fill="#ffffff", dash=(2, 4), tags="caja")
        c.create_rectangle(x0, y0, x1, y1, outline="#00d0ff", width=2, tags="caja")
        for hx, hy in self._posiciones_asas(x0, y0, x1, y1).values():
            c.create_rectangle(hx - TAM_ASA, hy - TAM_ASA, hx + TAM_ASA, hy + TAM_ASA,
                               fill="white", outline="#00d0ff", tags="caja")
        ancho, alto = self.caja[2] - self.caja[0], self.caja[3] - self.caja[1]
        ty = y0 - 12 if y0 - 12 > iy0 else y0 + 12
        c.create_text(x0 + 4, ty, anchor="w", text=f"{ancho} × {alto}",
                      fill="white", font=("Segoe UI", 10, "bold"), tags="caja")

    def _dibujar_lupa(self, ix, iy):
        c = self.lienzo
        c.delete("lupa")
        r = LUPA_RADIO
        region = Image.new("RGB", (2 * r, 2 * r), (60, 0, 60))
        region.paste(self.img.crop((ix - r, iy - r, ix + r, iy + r)), (0, 0))
        grande = region.resize((2 * r * LUPA_ZOOM, 2 * r * LUPA_ZOOM), Image.NEAREST)
        self._tk_lupa = ImageTk.PhotoImage(grande)
        lado = 2 * r * LUPA_ZOOM
        cw = c.winfo_width()
        cursor_x, _ = self._a_pantalla(ix, iy)
        lx = 12 if cursor_x > cw / 2 else cw - lado - 12   # al lado contrario del cursor
        ly = 12
        c.create_image(lx, ly, anchor="nw", image=self._tk_lupa, tags="lupa")
        # lineas del recorte dentro de la lupa
        def a_lupa(px, py):
            return lx + (px - (ix - r)) * LUPA_ZOOM, ly + (py - (iy - r)) * LUPA_ZOOM
        x0, y0 = a_lupa(self.caja[0], self.caja[1])
        x1, y1 = a_lupa(self.caja[2], self.caja[3])
        for x in (x0, x1):
            if lx <= x <= lx + lado:
                c.create_line(x, ly, x, ly + lado, fill="#00d0ff", width=2, tags="lupa")
        for y in (y0, y1):
            if ly <= y <= ly + lado:
                c.create_line(lx, y, lx + lado, y, fill="#00d0ff", width=2, tags="lupa")
        c.create_rectangle(lx, ly, lx + lado, ly + lado, outline="white", width=2, tags="lupa")
        c.create_text(lx + 6, ly + lado + 10, anchor="w", fill="white",
                      text=f"x={ix}  y={iy}", font=("Segoe UI", 9), tags="lupa")

    # ------------------------------------------------------- coordenadas
    def _a_pantalla(self, x, y):
        return self.ox + x * self.escala, self.oy + y * self.escala

    def _a_imagen(self, sx, sy):
        w, h = self.img.size
        x = round((sx - self.ox) / self.escala)
        y = round((sy - self.oy) / self.escala)
        return min(max(x, 0), w), min(max(y, 0), h)

    @staticmethod
    def _posiciones_asas(x0, y0, x1, y1):
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        return {"lt": (x0, y0), "t": (mx, y0), "rt": (x1, y0), "r": (x1, my),
                "rb": (x1, y1), "b": (mx, y1), "lb": (x0, y1), "l": (x0, my)}

    def _detectar_zona(self, sx, sy):
        x0, y0 = self._a_pantalla(self.caja[0], self.caja[1])
        x1, y1 = self._a_pantalla(self.caja[2], self.caja[3])
        for nombre, (hx, hy) in self._posiciones_asas(x0, y0, x1, y1).items():
            if abs(sx - hx) <= ALCANCE_ASA and abs(sy - hy) <= ALCANCE_ASA:
                return frozenset(nombre)
        dentro_y = y0 - ALCANCE_ASA <= sy <= y1 + ALCANCE_ASA
        dentro_x = x0 - ALCANCE_ASA <= sx <= x1 + ALCANCE_ASA
        bordes = set()
        if dentro_y and abs(sx - x0) <= ALCANCE_ASA:
            bordes.add("l")
        elif dentro_y and abs(sx - x1) <= ALCANCE_ASA:
            bordes.add("r")
        if dentro_x and abs(sy - y0) <= ALCANCE_ASA:
            bordes.add("t")
        elif dentro_x and abs(sy - y1) <= ALCANCE_ASA:
            bordes.add("b")
        if bordes:
            return frozenset(bordes)
        if x0 < sx < x1 and y0 < sy < y1:
            return "mover"
        return "nuevo"

    # ----------------------------------------------------------- raton
    def _mover_raton(self, e):
        if self.img is None or self._arrastre:
            return
        zona = self._detectar_zona(e.x, e.y)
        cursor = CURSORES.get(zona, "fleur" if zona == "mover" else "crosshair")
        self.lienzo.config(cursor=cursor)

    def _pulsar(self, e):
        if self.img is None:
            return
        self.focus_set()
        zona = self._detectar_zona(e.x, e.y)
        ix, iy = self._a_imagen(e.x, e.y)
        if zona == "nuevo":
            self.caja = [ix, iy, ix, iy]
            zona = frozenset("rb")
        self._arrastre = (zona, ix, iy, list(self.caja))

    def _arrastrar(self, e):
        if not self._arrastre:
            return
        zona, ix0, iy0, caja0 = self._arrastre
        ix, iy = self._a_imagen(e.x, e.y)
        w, h = self.img.size
        x0, y0, x1, y1 = caja0
        if zona == "mover":
            dx = min(max(ix - ix0, -x0), w - x1)
            dy = min(max(iy - iy0, -y0), h - y1)
            self.caja = [x0 + dx, y0 + dy, x1 + dx, y1 + dy]
        else:
            if "l" in zona: x0 = ix
            if "r" in zona: x1 = ix
            if "t" in zona: y0 = iy
            if "b" in zona: y1 = iy
            self.caja = [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]
        self._dibujar_caja()
        self._a_campos()
        if zona != "mover":
            self._dibujar_lupa(ix, iy)

    def _soltar(self, _e):
        if not self._arrastre:
            return
        self._arrastre = None
        self.lienzo.delete("lupa")
        self._limitar_caja()
        self._a_campos()
        self._dibujar_caja()

    def _mover_teclado(self, dx, dy, paso):
        if self.img is None or isinstance(self.focus_get(), ttk.Spinbox):
            return
        w, h = self.img.size
        x0, y0, x1, y1 = self.caja
        dx = min(max(dx * paso, -x0), w - x1)
        dy = min(max(dy * paso, -y0), h - y1)
        self.caja = [x0 + dx, y0 + dy, x1 + dx, y1 + dy]
        self._a_campos()
        self._dibujar_caja()

    # ----------------------------------------------------------- campos
    def _limitar_caja(self):
        w, h = self.img.size
        x0, y0, x1, y1 = self.caja
        x0, x1 = sorted((min(max(x0, 0), w), min(max(x1, 0), w)))
        y0, y1 = sorted((min(max(y0, 0), h), min(max(y1, 0), h)))
        if x1 - x0 < MIN_LADO:
            x1 = min(x0 + MIN_LADO, w); x0 = x1 - MIN_LADO
        if y1 - y0 < MIN_LADO:
            y1 = min(y0 + MIN_LADO, h); y0 = y1 - MIN_LADO
        self.caja = [x0, y0, x1, y1]

    def _a_campos(self):
        self._sync = True
        x0, y0, x1, y1 = self.caja
        for k, v in zip(("X", "Y", "W", "H"), (x0, y0, x1 - x0, y1 - y0)):
            self.vars[k].set(v)
        self._sync = False

    def _desde_campos(self):
        if self._sync or self.img is None:
            return
        try:
            x, y = self.vars["X"].get(), self.vars["Y"].get()
            an, al = self.vars["W"].get(), self.vars["H"].get()
        except (tk.TclError, ValueError):
            self._a_campos()
            return
        self.caja = [x, y, x + an, y + al]
        self._limitar_caja()
        self._a_campos()
        self._dibujar_caja()

    def auto_bordes(self):
        if self.img is not None:
            self.caja = list(detectar_bordes(self.img))
            self._limitar_caja()
            self._a_campos()
            self._dibujar_caja()

    def seleccionar_todo(self):
        if self.img is not None:
            self.caja = [0, 0, *self.img.size]
            self._a_campos()
            self._dibujar_caja()

    # ----------------------------------------------------------- recorte
    def recortar(self):
        if self.img is None:
            return
        self._desde_campos()
        caja = tuple(self.caja)
        salida = self.carpeta / self.t("salida")
        salida.mkdir(exist_ok=True)
        actual = self.imagenes[self.indice]
        try:
            guardar_recorte(actual, salida / actual.name, caja)
        except Exception as ex:
            messagebox.showerror(self.t("error"), self.t("error_guardar", nombre=actual.name, ex=ex))
            return

        resto = [p for p in self.imagenes if p != actual]
        ancho, alto = caja[2] - caja[0], caja[3] - caja[1]
        if not resto:
            messagebox.showinfo(self.t("hecho"), self.t("guardada_en", salida=salida))
            return
        if messagebox.askyesno(
                self.t("lote_t"),
                self.t("lote", nombre=actual.name, ancho=ancho, alto=alto, n=len(resto),
                       rw=self.img.width, rh=self.img.height, carpeta=salida.name)):
            self._lote(resto, caja, self.img.size, salida)

    def _lote(self, rutas, caja, tam_ref, salida):
        self.btn_recortar.config(state="disabled")
        self.progreso.config(maximum=len(rutas), value=0)

        def trabajo():
            hechas, saltadas, errores = 1, [], []
            for i, ruta in enumerate(rutas, 1):
                try:
                    with Image.open(ruta) as im:
                        tam = im.size
                    if tam != tam_ref:
                        saltadas.append(f"{ruta.name} ({tam[0]}×{tam[1]})")
                    else:
                        guardar_recorte(ruta, salida / ruta.name, caja)
                        hechas += 1
                except Exception as ex:
                    errores.append(f"{ruta.name}: {ex}")
                self._cola.put(("prog", i, ruta.name))
            self._cola.put(("fin", hechas, saltadas, errores))

        threading.Thread(target=trabajo, daemon=True).start()
        self._revisar_cola(salida)

    def _revisar_cola(self, salida):
        try:
            while True:
                msg = self._cola.get_nowait()
                if msg[0] == "prog":
                    self.progreso.config(value=msg[1])
                    self.lbl_estado.config(text=self.t("progreso", i=msg[1], n=int(self.progreso["maximum"]),
                                                         nombre=msg[2]))
                else:
                    _, hechas, saltadas, errores = msg
                    self.btn_recortar.config(state="normal")
                    self.lbl_estado.config(text=self.t("listo", n=hechas, salida=salida))
                    texto = self.t("resumen", n=hechas, salida=salida)
                    if saltadas:
                        texto += "\n\n" + self.t("saltadas", n=len(saltadas)) + "\n" + \
                                 "\n".join(saltadas[:15]) + ("\n..." if len(saltadas) > 15 else "")
                    if errores:
                        texto += "\n\n" + self.t("errores", n=len(errores)) + "\n" + "\n".join(errores[:10])
                    messagebox.showinfo(self.t("hecho"), texto)
                    return
        except queue.Empty:
            pass
        self.after(50, lambda: self._revisar_cola(salida))


if __name__ == "__main__":
    Editor(sys.argv[1] if len(sys.argv) > 1 else None).mainloop()
