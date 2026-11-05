#!/usr/bin/env python3
"""Genera el full de respostes en PDF, compatible amb corregir-examens-escanejats.py.

Ús:
    python3 plantilla-examens-escanejats.py NUM_PREGUNTES NUM_PERMUTACIONS [-o plantilla.pdf]

Crea una pàgina per permutació. A cada pàgina hi ha:
  - els 4 cercles negres de les cantonades (corregir-examens-escanejats.py els
    fa servir per redreçar el full),
  - el requadre de dades de l'estudiant (Nom, Cognoms, Grup, DNI, CODI) amb el
    número de permutació ja escrit al camp CODI,
  - la graella del DNI (8 columnes, dígits 1..9,0) i la columna CODI amb la
    casella de la permutació ja marcada,
  - les preguntes amb 4 caselles A, B, C, D. Fins a 30 preguntes per columna;
    amb més preguntes es reparteixen en 2 o 3 columnes (màxim 90). Es numeren
    de dalt a baix i d'esquerra a dreta, tal com les llegeix
    corregir-examens-escanejats.py.

Les mides reprodueixen les del full original (A4), de manera que
corregir-examens-escanejats.py reconeix les caselles: les del DNI són més
allargades (5,8 x 2,2 mm) que les de les preguntes (5,1 x 2,7 mm).

Cal reportlab (paquet python3-reportlab o pip install reportlab).
"""

import argparse
import math
import sys

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

AMPLADA, ALCADA = A4                  # en punts
MAX_FILES = 30                        # preguntes per columna
MAX_COLUMNES = 3
MAX_PREGUNTES = MAX_FILES * MAX_COLUMNES
DIGITS = "1234567890"                 # ordre de les files de la graella del DNI
LLETRES = "ABCD"
LINIA = 0.6                           # gruix de línia de les caselles (pt)

# --- mides en mm, mesurades des de la cantonada superior esquerra de la pàgina ---
CERCLE_RADI = 2.5
CERCLE_MARGE_X, CERCLE_MARGE_Y = 10, 12

DADES_X0, DADES_X1, DADES_Y0, DADES_Y1 = 12, 77.5, 29.5, 63

DNI_X0 = 86.1                         # vora esquerra de la 1a columna del DNI
DNI_PAS_X = 8.55
CODI_X0 = 157.5
DNI_Y0 = 29.3                         # vora superior de la fila del dígit 1
DNI_PAS_Y = 3.47
DNI_CASELLA = (5.8, 2.2)
MARC_X0, MARC_X1, MARC_Y0, MARC_Y1 = 83.9, 166.3, 27.5, 64.4
SEPARADOR_X = 154.6

PREG_Y0 = 73.5                        # vora superior de la 1a fila de preguntes
PREG_PAS_Y = 6.4
PREG_PAS_X = 7.35
PREG_CASELLA = (5.1, 2.7)
BLOC_NUMERO = 8.5                     # espai per al número de pregunta
BLOC_AMPLADA = BLOC_NUMERO + 3 * PREG_PAS_X + PREG_CASELLA[0]
BLOC_SEPARACIO = 16


def y(mm_des_de_dalt):
    """Converteix una coordenada vertical en mm des de dalt a punts de reportlab."""
    return ALCADA - mm_des_de_dalt * mm


def casella(c, x0, y0, mida, text, plena=False):
    """Casella amb la vora superior esquerra a (x0, y0) mm."""
    w, h = mida
    if plena:
        c.rect(x0 * mm, y(y0 + h), w * mm, h * mm, stroke=1, fill=1)
        return
    c.rect(x0 * mm, y(y0 + h), w * mm, h * mm, stroke=1, fill=0)
    c.setFont("Helvetica", 5)
    c.drawCentredString((x0 + w / 2) * mm, y(y0 + h / 2 + 0.6), text)


def cantonades(c):
    for cx in (CERCLE_MARGE_X, 210 - CERCLE_MARGE_X):
        for cy in (CERCLE_MARGE_Y, 297 - CERCLE_MARGE_Y):
            c.circle(cx * mm, y(cy), CERCLE_RADI * mm, stroke=0, fill=1)
    # quadrat superior central (referència visual d'orientació)
    c.rect(102.5 * mm, y(CERCLE_MARGE_Y + 2.5), 5 * mm, 5 * mm, stroke=0, fill=1)


def dades_estudiant(c, permutacio):
    c.setLineWidth(0.8)
    c.roundRect(DADES_X0 * mm, y(DADES_Y1), (DADES_X1 - DADES_X0) * mm,
                (DADES_Y1 - DADES_Y0) * mm, 2 * mm, stroke=1, fill=0)
    c.setLineWidth(0.5)
    camps = ["Nom", "Cognoms", "Grup", "DNI", "CODI"]
    for i, camp in enumerate(camps):
        base = 35.5 + i * 6.4
        c.setFont("Helvetica", 8)
        c.drawString(14.5 * mm, y(base), camp)
        c.line(33 * mm, y(base + 0.8), 74 * mm, y(base + 0.8))
    c.setFont("Helvetica", 13)
    c.drawString(38 * mm, y(35.5 + 4 * 6.4), str(permutacio))


def graella_dni(c, permutacio):
    c.setLineWidth(0.8)
    c.rect(MARC_X0 * mm, y(MARC_Y1), (MARC_X1 - MARC_X0) * mm,
           (MARC_Y1 - MARC_Y0) * mm, stroke=1, fill=0)
    c.line(SEPARADOR_X * mm, y(MARC_Y0), SEPARADOR_X * mm, y(MARC_Y1))

    c.setFont("Helvetica", 9)
    centre_dni = DNI_X0 + (7 * DNI_PAS_X + DNI_CASELLA[0]) / 2
    c.drawCentredString(centre_dni * mm, y(MARC_Y0 - 2), "DNI")
    c.drawCentredString((CODI_X0 + DNI_CASELLA[0] / 2) * mm, y(MARC_Y0 - 2), "CODI")

    c.setLineWidth(LINIA)
    for fila, digit in enumerate(DIGITS):
        y0 = DNI_Y0 + fila * DNI_PAS_Y
        c.setFont("Helvetica", 6)
        c.drawCentredString((MARC_X0 - 2.2) * mm, y(y0 + 1.8), digit)
        c.drawCentredString((MARC_X1 + 2.2) * mm, y(y0 + 1.8), digit)
        for col in range(8):
            casella(c, DNI_X0 + col * DNI_PAS_X, y0, DNI_CASELLA, digit)
        casella(c, CODI_X0, y0, DNI_CASELLA, digit,
                plena=(digit == str(permutacio)))


def preguntes(c, num_preguntes):
    columnes = math.ceil(num_preguntes / MAX_FILES)
    files = math.ceil(num_preguntes / columnes)       # repartiment equilibrat
    amplada_total = columnes * BLOC_AMPLADA + (columnes - 1) * BLOC_SEPARACIO
    x_inici = (210 - amplada_total) / 2

    c.setLineWidth(LINIA)
    for n in range(num_preguntes):
        bloc, fila = divmod(n, files)
        x_num = x_inici + bloc * (BLOC_AMPLADA + BLOC_SEPARACIO)
        y0 = PREG_Y0 + fila * PREG_PAS_Y
        c.setFont("Helvetica", 7)
        c.drawRightString((x_num + BLOC_NUMERO - 2.5) * mm, y(y0 + 2.1), str(n + 1))
        for k, lletra in enumerate(LLETRES):
            casella(c, x_num + BLOC_NUMERO + k * PREG_PAS_X, y0, PREG_CASELLA, lletra)


def pagina(c, num_preguntes, permutacio):
    cantonades(c)
    dades_estudiant(c, permutacio)
    graella_dni(c, permutacio)
    preguntes(c, num_preguntes)
    c.showPage()


def main():
    ap = argparse.ArgumentParser(description="Genera el full de respostes en PDF "
                                             "(una pàgina per permutació).")
    ap.add_argument("preguntes", type=int, help=f"nombre de preguntes (1..{MAX_PREGUNTES})")
    ap.add_argument("permutacions", type=int, help="nombre de permutacions (1..9)")
    ap.add_argument("-o", "--sortida", default="plantilla.pdf",
                    help="fitxer PDF de sortida (per defecte: plantilla.pdf)")
    args = ap.parse_args()

    if not 1 <= args.preguntes <= MAX_PREGUNTES:
        sys.exit(f"ERROR: el nombre de preguntes ha de ser entre 1 i {MAX_PREGUNTES}")
    if not 1 <= args.permutacions <= 9:
        sys.exit("ERROR: el nombre de permutacions ha de ser entre 1 i 9 "
                 "(la columna CODI té els dígits 1..9)")

    c = canvas.Canvas(args.sortida, pagesize=A4)
    c.setTitle(f"Full de respostes: {args.preguntes} preguntes, "
               f"{args.permutacions} permutacions")
    for p in range(1, args.permutacions + 1):
        pagina(c, args.preguntes, p)
    c.save()
    print(f"{args.sortida}: {args.permutacions} pàgines, {args.preguntes} preguntes")


if __name__ == "__main__":
    main()
