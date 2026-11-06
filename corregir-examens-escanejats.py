#!/usr/bin/env python3
"""Corrector automàtic d'exàmens tipus test a partir de fulls de respostes escanejats.

Cal OpenCV (paquet python3-opencv o pip install opencv-python-headless).

Ús:
    python3 corregir-examens-escanejats.py [imatges_o_directoris ...] [-r respostes.csv] [-o correccio.csv]

Per defecte corregeix tots els .jpg/.jpeg del directori "test" amb les
respostes de "respostes.csv" i escriu "correccio.csv".

respostes.csv: una línia per permutació de l'examen; el primer camp és el
número de permutació (columna CODI del full) i després van les lletres
correctes, p. ex.  2;C;D;C;D;A;...  Una X en lloc de la lletra indica una
pregunta eliminada: no es corregeix i no compta ni com a correcta, ni com a
errònia, ni com a sense resposta.

correccio.csv: una capçalera amb els noms dels camps i una línia per examen:
    DNI;permutacio;correctes;erronies;sense_resposta;avaluades;eliminades;fitxer
on avaluades és el nombre de preguntes no eliminades
(= correctes + erronies + sense_resposta).

A més, per a cada imatge X.jpg es genera X-cor.jpg (al mateix directori) amb
un cercle verd a les respostes correctes, una creu vermella a les errònies i
una ratlla blava que tatxa les preguntes eliminades.

Funcionament:
  1. La imatge es redueix a ~300 ppp, es binaritza (llindar d'Otsu) i es
     corregeix la perspectiva amb els 4 cercles negres de les cantonades (gir,
     inclinació i deformació en trapezi, p. ex. en fotos de mòbil).
  2. Es localitzen les caselles buides: components buits amb forma de
     quadrilàter (cv2.convexHull + cv2.approxPolyDP). A partir d'aquestes es
     dedueixen les files i les columnes de les graelles, de manera que també se
     sap on són les caselles omplertes (que ja no són buides). Les caselles del
     DNI (més allargades) se separen de les de les preguntes per la forma.
  3. Graella del DNI: 10 files (dígits 1..9,0), 8 columnes de DNI i una 9a
     columna amb el CODI (permutació). Preguntes: 4 caselles A,B,C,D per fila.
  4. Es mesura la foscor (nivell de gris) de l'interior de cada casella i se li
     resta el fons de les caselles buides amb la mateixa lletra/dígit. Una
     casella està marcada si supera el llindar (detecta també marques fluixes
     de llapis).
  5. Si una pregunta té diverses marques i alguna està anul·lada amb una creu
     (la "X" sobresurt per sobre i per sota de la casella), es descarta
     l'anul·lada. Si encara hi queden diverses marques, la pregunta compta com
     a errònia.
"""

import argparse
import csv
import glob
import os
import sys

import cv2
import numpy as np

LLETRES = "ABCD"
DIGITS_DNI = "1234567890"  # ordre de les files a la graella del DNI
LLINDAR_MARCA = 0.06    # foscor per sobre del fons per considerar una casella marcada
LLINDAR_CREU = 0.06     # foscor per sobre+sota de la casella que indica una creu
ELIMINADA = "X"         # al fitxer de respostes, marca una pregunta eliminada


# ----------------------------------------------------------------- imatge ----

AMPLADA_TREBALL = 2500   # la imatge es redueix a ~300 ppp: més ràpid i menys memòria


def components(binaria):
    """Components connexos de la imatge binària (uint8, 255 = tinta)."""
    n, etiquetes, stats, _ = cv2.connectedComponentsWithStats(binaria, connectivity=4)
    res = []
    for i in range(1, n):
        x0, y0, w, h, area = stats[i]
        res.append(dict(id=i, x0=int(x0), y0=int(y0), w=int(w), h=int(h), area=int(area),
                        cx=x0 + w / 2, cy=y0 + h / 2))
    return res, etiquetes


def cercles_cantonades(comps, W, H):
    """Centres dels 4 cercles negres de les cantonades: (sup_esq, sup_dre,
    inf_esq, inf_dre), o None si no es troben."""
    mida = 0.024 * W
    punts = [c for c in comps
             if 0.6 * mida < c["w"] < 1.6 * mida and 0.6 * mida < c["h"] < 1.6 * mida
             and 0.65 < c["area"] / (c["w"] * c["h"]) < 0.88]     # cercle ple
    cantonades = []
    for ex, ey in ((0, 0), (W, 0), (0, H), (W, H)):
        a_prop = [c for c in punts
                  if abs(c["cx"] - ex) < 0.15 * W and abs(c["cy"] - ey) < 0.15 * H]
        if not a_prop:
            return None
        c = min(a_prop, key=lambda c: (c["cx"] - ex) ** 2 + (c["cy"] - ey) ** 2)
        cantonades.append((c["cx"], c["cy"]))
    return cantonades


def carregar(ruta):
    """Retorna (binaria, foscor): imatge en blanc i negre i nivell de gris 0..1.

    El full es redreça amb una transformació de perspectiva que porta els
    4 cercles de les cantonades a un rectangle perfecte (corregeix el gir, la
    inclinació i la deformació en trapezi)."""
    gris = cv2.imread(ruta, cv2.IMREAD_GRAYSCALE)
    if gris is None:
        raise ValueError("no es pot llegir la imatge")
    if gris.shape[1] > AMPLADA_TREBALL * 1.2:
        f = AMPLADA_TREBALL / gris.shape[1]
        gris = cv2.resize(gris, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
    H, W = gris.shape
    llindar, binaria = cv2.threshold(gris, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)

    cantonades = cercles_cantonades(components(binaria)[0], W, H)
    if cantonades is None:
        print(f"AVÍS {ruta}: no es troben els 4 cercles de les cantonades; "
              "no es corregeix la perspectiva", file=sys.stderr)
    else:
        (se, sd, ie, id_) = cantonades
        esq, dre = (se[0] + ie[0]) / 2, (sd[0] + id_[0]) / 2
        dalt, baix = (se[1] + sd[1]) / 2, (ie[1] + id_[1]) / 2
        origen = np.float32(cantonades)
        desti = np.float32([(esq, dalt), (dre, dalt), (esq, baix), (dre, baix)])
        M = cv2.getPerspectiveTransform(origen, desti)
        gris = cv2.warpPerspective(gris, M, (W, H), flags=cv2.INTER_LINEAR,
                                   borderMode=cv2.BORDER_CONSTANT, borderValue=255)
        _, binaria = cv2.threshold(gris, llindar, 255, cv2.THRESH_BINARY_INV)

    foscor = (255 - gris).astype(np.float32) / 255
    return binaria, foscor


def es_rectangle(etiquetes, c):
    """True si el component té forma de rectangle. Es fa servir l'envolupant
    convexa per tolerar vores de casella amb petits talls de l'escaneig."""
    mascara = (etiquetes[c["y0"]:c["y0"] + c["h"], c["x0"]:c["x0"] + c["w"]]
               == c["id"]).astype(np.uint8)
    punts = cv2.findNonZero(mascara)
    if punts is None:
        return False
    envolupant = cv2.convexHull(punts)
    aprox = cv2.approxPolyDP(envolupant, 0.04 * cv2.arcLength(envolupant, True), True)
    # el rectangle ha d'ocupar gairebé tota la seva capsa (descarta fletxes i gargots)
    return len(aprox) == 4 and cv2.contourArea(envolupant) > 0.85 * c["w"] * c["h"]


# ---------------------------------------------------------------- graella ----

def agrupar(valors, tolerancia):
    """Agrupa valors 1D propers; retorna la mitjana de cada grup (ordenada) i
    el nombre d'elements de cada grup."""
    valors = sorted(valors)
    grups = [[valors[0]]]
    for v in valors[1:]:
        if v - grups[-1][-1] <= tolerancia:
            grups[-1].append(v)
        else:
            grups.append([v])
    return [float(np.mean(g)) for g in grups], [len(g) for g in grups]


def caselles_buides(comps, etiquetes, W, H):
    res = []
    for c in comps:
        w, h = c["w"], c["h"]
        if not (0.015 * W < w < 0.045 * W and 0.005 * H < h < 0.015 * H and w > 1.3 * h):
            continue
        if c["area"] / (w * h) > 0.40:        # plena -> no és una casella buida
            continue
        if c["cx"] < 0.1 * W:                 # marques d'alineació del marge
            continue
        if not es_rectangle(etiquetes, c):
            continue
        res.append(c)
    return res


def construir_graelles(binaria):
    H, W = binaria.shape
    comps, etiquetes = components(binaria)
    caselles = caselles_buides(comps, etiquetes, W, H)
    if len(caselles) < 20:
        raise ValueError("no es troben les caselles del full")

    # Les caselles del DNI/CODI són més allargades que les de les preguntes:
    # se separen en dos grups segons la proporció amplada/alçada (2-mitjanes).
    prop = np.array([c["w"] / c["h"] for c in caselles])
    m1, m2 = np.percentile(prop, 10), np.percentile(prop, 90)
    for _ in range(20):
        tall = (m1 + m2) / 2
        m1, m2 = prop[prop < tall].mean(), prop[prop >= tall].mean()
    g1 = [c for c, p in zip(caselles, prop) if p < tall]
    g2 = [c for c, p in zip(caselles, prop) if p >= tall]
    if not g1 or not g2:
        raise ValueError("no es distingeixen les caselles del DNI de les de les preguntes")
    # la graella del DNI és la que està més amunt
    if np.median([c["cy"] for c in g1]) < np.median([c["cy"] for c in g2]):
        g1, g2 = g2, g1
    caselles_preg, caselles_dni = g1, g2

    def mida_homogenia(cs):
        """Descarta objectes que no tenen la mida típica de les caselles (gargots, fletxes)."""
        w_med = np.median([c["w"] for c in cs])
        h_med = np.median([c["h"] for c in cs])
        return [c for c in cs if abs(c["w"] - w_med) < 0.2 * w_med
                and abs(c["h"] - h_med) < 0.2 * h_med]

    def columnes(cs):
        w_med = np.median([c["w"] for c in cs])
        cols, n = agrupar([c["cx"] for c in cs], w_med / 2)
        cols = [x for x, k in zip(cols, n) if k >= 0.3 * max(n)]  # descarta columnes espúries
        mida = (np.median([c["w"] for c in cs]), np.median([c["h"] for c in cs]))
        # descarta objectes que no són a cap columna
        cs = [c for c in cs if min(abs(c["cx"] - x) for x in cols) < w_med / 2]
        return cols, mida, cs

    caselles_dni = mida_homogenia(caselles_dni)
    caselles_preg = mida_homogenia(caselles_preg)
    if not caselles_preg:
        raise ValueError("no es troben les caselles de les preguntes")

    cols_dni, mida_dni, caselles_dni = columnes(caselles_dni)
    files_dni, n = agrupar([c["cy"] for c in caselles_dni], mida_dni[1] / 2)
    files_dni = [y for y, k in zip(files_dni, n) if k >= 3]   # descarta files espúries
    if len(files_dni) != 10:
        raise ValueError(f"graella del DNI amb {len(files_dni)} files (se n'esperaven 10)")

    if len(cols_dni) < 8:
        raise ValueError(f"graella del DNI amb {len(cols_dni)} columnes (se n'esperaven 8)")
    col_codi = cols_dni[8] if len(cols_dni) > 8 else None  # 9a columna: CODI
    cols_dni = cols_dni[:8]

    # les preguntes són per sota de la graella del DNI
    caselles_preg = [c for c in caselles_preg if c["cy"] > files_dni[-1] + 2 * mida_dni[1]]
    if not caselles_preg:
        raise ValueError("no es troben les caselles de les preguntes")
    cols_preg, mida_preg, caselles_preg = columnes(caselles_preg)
    files_preg, _ = agrupar([c["cy"] for c in caselles_preg], mida_preg[1] / 2)
    if len(cols_preg) % 4:
        raise ValueError(f"{len(cols_preg)} columnes de resposta (no és múltiple de 4)")

    # Preguntes: per blocs de 4 columnes (A,B,C,D), d'esquerra a dreta;
    # dins de cada bloc, de dalt a baix.
    preguntes = []
    for b in range(0, len(cols_preg), 4):
        xs = cols_preg[b:b + 4]
        al_bloc = [c for c in caselles_preg if xs[0] - mida_preg[0] < c["cx"] < xs[3] + mida_preg[0]]
        ys = [f for f in files_preg
              if any(abs(c["cy"] - f) < mida_preg[1] / 2 for c in al_bloc)]
        for y in ys:
            preguntes.append([(x, y) for x in xs])

    dni = [[(x, y) for y in files_dni] for x in cols_dni]  # per columna: 10 dígits
    codi = [(col_codi, y) for y in files_dni] if col_codi is not None else None
    return dni, codi, mida_dni, preguntes, mida_preg


def emplenat(foscor, centre, mida, marge=0.15):
    """Foscor mitjana (0..1) de l'interior de la casella."""
    x, y = centre
    w, h = mida[0] * (1 - 2 * marge), mida[1] * (1 - 2 * marge)
    y0, y1 = int(round(y - h / 2)), int(round(y + h / 2))
    x0, x1 = int(round(x - w / 2)), int(round(x + w / 2))
    return float(foscor[y0:y1, x0:x1].mean())


def sobresurt(foscor, centre, mida):
    """Foscor just per sobre i per sota de la casella (les creus "X" sobresurten)."""
    x, y = centre
    w, h = mida
    x0, x1 = int(round(x - w / 2)), int(round(x + w / 2))
    dalt = foscor[int(y - 1.0 * h):int(y - 0.6 * h), x0:x1].mean()
    baix = foscor[int(y + 0.6 * h):int(y + 1.0 * h), x0:x1].mean()
    return float(dalt + baix)


def sobre_fons(m):
    """Resta a cada valor el fons de la seva columna (cada lletra/dígit imprès
    enfosqueix la casella de manera diferent). El fons és la mediana de la
    columna sense comptar el valor màxim de cada fila (que pot ser la marca)."""
    m = np.asarray(m, dtype=float)
    lliure = np.ones_like(m, dtype=bool)
    lliure[np.arange(len(m)), m.argmax(axis=1)] = False
    # si una columna no té cap valor lliure (p. ex. graella en blanc), es fa
    # servir tota la columna
    fons = np.array([np.median(m[lliure[:, j], j]) if lliure[:, j].any()
                     else np.median(m[:, j]) for j in range(m.shape[1])])
    return m - fons


def treure_anullades(foscor, marques, posicions, mida):
    """Si hi ha diverses marques i alguna està anul·lada amb una creu, la
    descarta. Retorna (marques, anul·lades)."""
    if len(marques) < 2:
        return marques, []
    s = {i: sobresurt(foscor, posicions[i], mida) for i in marques}
    minim = min(s.values())
    # anul·lada: la creu sobresurt clarament i molt més que la marca més neta
    anullades = [i for i in marques if s[i] >= LLINDAR_CREU and s[i] >= 3 * minim]
    resta = [i for i in marques if i not in anullades]
    if anullades and len(resta) == 1:
        return resta, anullades
    return marques, []


# -------------------------------------------------------------- correcció ----

def llegir_full(ruta, llindar=LLINDAR_MARCA):
    """Retorna (dni, codi, respostes, avisos, geometria). Cada resposta és una
    cadena amb les lletres marcades ("" = en blanc, "AB" = diverses marques).
    geometria = (foscor, posicions de les caselles, mida) per dibuixar."""
    binaria, foscor = carregar(ruta)
    dni_pos, codi_pos, mida_dni, preg_pos, mida_preg = construir_graelles(binaria)
    avisos = []

    # DNI i CODI: una fila de la matriu per columna del full, 10 dígits
    columnes = dni_pos + ([codi_pos] if codi_pos else [])
    d = sobre_fons([[emplenat(foscor, p, mida_dni) for p in col] for col in columnes])
    digits = []
    for k, (fila, pos) in enumerate(zip(d, columnes)):
        m, anullades = treure_anullades(foscor, list(np.flatnonzero(fila >= llindar)),
                                        pos, mida_dni)
        if anullades:
            nom = f"DNI columna {k + 1}" if k < 8 else "CODI"
            avisos.append(f"{nom}: {','.join(DIGITS_DNI[i] for i in anullades)} anul·lat, "
                          f"es pren {DIGITS_DNI[m[0]]}")
        digits.append(DIGITS_DNI[m[0]] if len(m) == 1 else "?")
    dni = "".join(digits[:8])
    codi = digits[8] if codi_pos else "?"

    q = sobre_fons([[emplenat(foscor, p, mida_preg) for p in fila] for fila in preg_pos])
    respostes = []
    for n, (fila, pos) in enumerate(zip(q, preg_pos), 1):
        m, anullades = treure_anullades(foscor, list(np.flatnonzero(fila >= llindar)),
                                        pos, mida_preg)
        if anullades:
            avisos.append(f"pregunta {n}: {''.join(LLETRES[i] for i in anullades)} "
                          f"anul·lada, es pren {LLETRES[m[0]]}")
        respostes.append("".join(LLETRES[i] for i in m))
    geometria = (foscor, preg_pos, mida_preg)
    return dni, codi, respostes, avisos, geometria


def llegir_solucions(ruta):
    """Llegeix les solucions de cada permutació.

    Cada línia: número de permutació (CODI) seguit de les lletres correctes,
    p. ex. "2;C;D;A;..." (separador ";" o ","; també val "2;CDA...").
    Una X indica una pregunta eliminada. Retorna {codi: [lletres]}.
    """
    solucions = {}
    with open(ruta, newline="", encoding="utf-8-sig") as f:
        for n, linia in enumerate(f, 1):
            linia = linia.strip()
            if not linia:
                continue
            sep = ";" if ";" in linia else ","
            camps = [x.strip().upper() for x in linia.split(sep) if x.strip()]
            codi, lletres = camps[0], "".join(camps[1:])
            if not codi.isdigit():
                raise ValueError(f"{ruta}, línia {n}: la línia ha de començar pel "
                                 f"número de permutació (s'ha llegit '{camps[0]}')")
            if set(lletres) - set(LLETRES + ELIMINADA):
                raise ValueError(f"{ruta}, línia {n}: lletres no vàlides a les respostes")
            if codi in solucions:
                raise ValueError(f"{ruta}, línia {n}: permutació {codi} repetida")
            solucions[codi] = list(lletres)
    if not solucions:
        raise ValueError(f"{ruta} no conté solucions")
    return solucions


def corregir(respostes, solucio):
    """Retorna (correctes, errònies, sense resposta, eliminades). Les preguntes
    eliminades (X a la solució) no compten com a correctes, errònies ni sense
    resposta."""
    correctes = erronies = blanques = eliminades = 0
    for i, sol in enumerate(solucio):
        r = respostes[i] if i < len(respostes) else ""
        if sol == ELIMINADA:
            eliminades += 1
            continue
        if r == "":
            blanques += 1
        elif r == sol:
            correctes += 1
        else:                       # incorrecta o més d'una marca
            erronies += 1
    return correctes, erronies, blanques, eliminades


SUFIX_CORREGIDA = "-cor.jpg"
VERD, VERMELL, BLAU = (0, 170, 0), (0, 0, 230), (220, 90, 0)   # colors BGR d'OpenCV


def nom_corregida(ruta):
    return os.path.splitext(ruta)[0] + SUFIX_CORREGIDA


def creu(img, x, y, radi, color, gruix):
    """Dibuixa una creu (X) centrada a (x, y), de la mateixa mida que el cercle."""
    d = radi * 0.75
    for sx in (-1, 1):
        cv2.line(img, (int(round(x - sx * d)), int(round(y - d))),
                 (int(round(x + sx * d)), int(round(y + d))), color, gruix,
                 lineType=cv2.LINE_AA)


def desar_corregida(ruta, geometria, respostes, solucio):
    """Desa <nom>-cor.jpg amb un cercle verd a cada resposta correcta i una creu
    vermella a cada errònia (si hi ha diverses marques, a totes). Les preguntes
    eliminades es tatxen amb una ratlla blava, del número fins a la casella D."""
    foscor, preg_pos, mida = geometria
    img = cv2.cvtColor(((1 - foscor) * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
    radi = int(round(0.7 * mida[0]))
    gruix = max(2, int(round(mida[1] / 10)))
    for n, (resp, pos) in enumerate(zip(respostes, preg_pos)):
        if n < len(solucio) and solucio[n] == ELIMINADA:
            (xa, y), (xd, _) = pos[0], pos[-1]
            inici = (int(round(xa - 1.6 * mida[0])), int(round(y)))   # inclou el número
            final = (int(round(xd + 0.8 * mida[0])), int(round(y)))
            cv2.line(img, inici, final, BLAU, 2 * gruix, lineType=cv2.LINE_AA)
            continue
        if not resp or n >= len(solucio):
            continue
        correcta = resp == solucio[n]
        for lletra in resp:
            x, y = pos[LLETRES.index(lletra)]
            if correcta:
                cv2.circle(img, (int(round(x)), int(round(y))), radi, VERD, gruix,
                           lineType=cv2.LINE_AA)
            else:
                creu(img, x, y, radi, VERMELL, gruix)
    desti = nom_corregida(ruta)
    if not cv2.imwrite(desti, img, [cv2.IMWRITE_JPEG_QUALITY, 90]):
        raise OSError(f"no es pot escriure {desti}")
    return desti


def llista_imatges(entrades):
    res = []
    for e in entrades:
        if os.path.isdir(e):
            for ext in ("*.jpg", "*.jpeg", "*.JPG", "*.JPEG"):
                res += glob.glob(os.path.join(e, ext))
        else:
            res.append(e)
    # no es tornen a corregir les imatges generades per aquest programa
    return sorted(r for r in set(res) if not r.lower().endswith(SUFIX_CORREGIDA))


def main():
    ap = argparse.ArgumentParser(description="Corregeix fulls de respostes escanejats.")
    ap.add_argument("entrades", nargs="*", default=["test"],
                    help="fitxers jpg o directoris (per defecte: test)")
    ap.add_argument("-r", "--respostes", default="respostes.csv",
                    help="fitxer amb les respostes correctes de cada permutació "
                         "(per defecte: respostes.csv)")
    ap.add_argument("-o", "--sortida", default="correccio.csv",
                    help="fitxer de resultats (per defecte: correccio.csv)")
    ap.add_argument("-u", "--llindar", type=float, default=LLINDAR_MARCA,
                    help="foscor (0..1) per sobre del fons per considerar "
                         f"una casella marcada (per defecte: {LLINDAR_MARCA})")
    ap.add_argument("-v", "--detall", action="store_true",
                    help="mostra les respostes llegides de cada examen")
    args = ap.parse_args()

    try:
        solucions = llegir_solucions(args.respostes)
    except (OSError, ValueError) as e:
        sys.exit(f"ERROR: {e}")
    imatges = llista_imatges(args.entrades)
    if not imatges:
        sys.exit("No hi ha imatges per corregir")

    with open(args.sortida, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["DNI", "permutacio", "correctes", "erronies", "sense_resposta",
                    "avaluades", "eliminades", "fitxer"])
        for ruta in imatges:
            try:
                dni, codi, resp, avisos, geometria = llegir_full(ruta, args.llindar)
            except Exception as e:
                print(f"ERROR {ruta}: {e}", file=sys.stderr)
                continue
            if codi not in solucions:
                print(f"ERROR {ruta}: DNI {dni}, permutació (CODI) '{codi}' no llegida "
                      f"o no és a {args.respostes}; examen no corregit", file=sys.stderr)
                continue
            solucio = solucions[codi]
            if len(resp) != len(solucio):
                print(f"ERROR {ruta}: DNI {dni}, {len(resp)} preguntes al full però "
                      f"{len(solucio)} a la permutació {codi} de {args.respostes}; "
                      "examen no corregit", file=sys.stderr)
                continue
            for a in avisos:
                print(f"AVÍS {ruta}: {a}", file=sys.stderr)
            if "?" in dni:
                print(f"AVÍS {ruta}: DNI no llegit correctament ({dni})", file=sys.stderr)
            for i, r in enumerate(resp, 1):
                if len(r) > 1 and not (i <= len(solucio) and solucio[i - 1] == ELIMINADA):
                    print(f"AVÍS {ruta}: pregunta {i} amb diverses marques ({r}), "
                          "compta com a errònia", file=sys.stderr)
            c, e, b, elim = corregir(resp, solucio)
            avaluades = len(solucio) - elim
            w.writerow([dni, codi, c, e, b, avaluades, elim, os.path.basename(ruta)])
            try:
                desar_corregida(ruta, geometria, resp, solucio)
            except OSError as err:
                print(f"AVÍS {ruta}: {err}", file=sys.stderr)
            print(f"{os.path.basename(ruta)}: DNI {dni}  CODI {codi}  correctes {c}  "
                  f"errònies {e}  sense resposta {b}  avaluades {avaluades}  "
                  f"eliminades {elim}")
            if args.detall:
                print("   " + " ".join(f"{i}:{r or '-'}" for i, r in enumerate(resp, 1)))


if __name__ == "__main__":
    main()
