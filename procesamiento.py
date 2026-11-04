# Procesamiento de fotos: difuminar rostros y placas, y comprimir.
# Se hace ANTES de subir la foto, para no publicar datos sensibles.

import io

import cv2
import numpy as np
from PIL import Image, ImageOps

# Detectores de OpenCV que ya vienen con la librería.
DETECTOR_ROSTROS = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
DETECTOR_PLACAS = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_russian_plate_number.xml")


def preparar_foto(contenido):
    """Devuelve (bytes del JPG listo para subir, cantidad de zonas difuminadas)."""
    # Abrimos la foto y la giramos según cómo se tomó con el celular.
    imagen = ImageOps.exif_transpose(Image.open(io.BytesIO(contenido))).convert("RGB")
    # Reducimos antes de pasar a OpenCV para evitar consumir demasiada memoria.
    imagen.thumbnail((1600, 1600))
    imagen_cv = cv2.cvtColor(np.array(imagen), cv2.COLOR_RGB2BGR)

    # Buscamos rostros y placas.
    gris = cv2.cvtColor(imagen_cv, cv2.COLOR_BGR2GRAY)
    zonas = list(DETECTOR_ROSTROS.detectMultiScale(gris, 1.1, 5, minSize=(30, 30)))
    zonas += list(DETECTOR_PLACAS.detectMultiScale(gris, 1.1, 4, minSize=(40, 15)))

    # Pixelamos cada zona: la achicamos a 8x8 y la volvemos a agrandar.
    for (x, y, ancho, alto) in zonas:
        pequena = cv2.resize(imagen_cv[y:y + alto, x:x + ancho], (8, 8))
        imagen_cv[y:y + alto, x:x + ancho] = cv2.resize(pequena, (ancho, alto), interpolation=cv2.INTER_NEAREST)

    # Achicamos a 1280 px y guardamos como JPG calidad 80 (así también se borran los datos GPS)
    imagen = Image.fromarray(cv2.cvtColor(imagen_cv, cv2.COLOR_BGR2RGB))
    imagen.thumbnail((1280, 1280))
    salida = io.BytesIO()
    imagen.save(salida, format="JPEG", quality=80)
    return salida.getvalue(), len(zonas)
