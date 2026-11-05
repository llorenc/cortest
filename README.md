# Correcció automàtica d'exàmens tipus test

Dos programes en Python per fer exàmens tipus test amb full de respostes en
paper i corregir-los automàticament a partir dels fulls escanejats:

| Programa | Què fa |
|---|---|
| `plantilla-examens-escanejats.py` | Genera el PDF amb els fulls de respostes, una pàgina per permutació. |
| `corregir-examens-escanejats.py` | Llegeix els fulls escanejats (JPEG), detecta el DNI, la permutació i les respostes marcades, i genera el fitxer de notes `correccio.csv` i una imatge corregida de cada examen. |

Cada pregunta té 4 respostes (A, B, C, D) i només una és correcta.

## Instal·lació

Cal Python 3 amb OpenCV, NumPy i ReportLab. A Debian/Ubuntu:

```bash
sudo apt install python3-opencv python3-numpy python3-reportlab
```

O bé amb `pip`, dins d'un entorn virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install opencv-python-headless numpy reportlab
```

Per comprovar-ho: `python3 -c "import cv2; print(cv2.__version__)"`.

## Flux de treball

1. Genera els fulls de respostes amb `plantilla-examens-escanejats.py`.
2. Imprimeix-los a **mida real (100 %)**, no amb "ajusta a la pàgina".
3. Els estudiants omplen el DNI i les respostes.
4. Escaneja els fulls en JPEG (en gris, a 300 o 600 ppp) i desa'ls en un directori.
5. Prepara el fitxer amb les respostes correctes de cada permutació.
6. Executa `corregir-examens-escanejats.py`.
7. Revisa els avisos que mostra el programa i les imatges `-cor.jpg`.

## Generar els fulls de respostes

```bash
python3 plantilla-examens-escanejats.py NUM_PREGUNTES NUM_PERMUTACIONS [-o plantilla.pdf]
```

Exemple: 30 preguntes i 6 permutacions:

```bash
python3 plantilla-examens-escanejats.py 30 6
```

Es genera `plantilla.pdf`, en A4, amb una pàgina per permutació. Cada pàgina té:

- **4 cercles negres a les cantonades.** El corrector els fa servir per redreçar el full.
- **Requadre de dades** (Nom, Cognoms, Grup, DNI, CODI), amb el número de permutació ja escrit al camp CODI.
- **Graella del DNI:** 8 columnes amb els dígits 1, 2, …, 9, 0. L'estudiant marca un dígit per columna.
- **Columna CODI** amb la casella de la permutació ja marcada.
- **Les preguntes**, amb 4 caselles A, B, C, D cadascuna. Hi caben fins a 30 preguntes per columna; si n'hi ha més, es reparteixen en 2 o 3 columnes i es numeren de dalt a baix i d'esquerra a dreta.

Límits: com a màxim **90 preguntes** i **9 permutacions** (la columna CODI té els dígits 1 a 9).

## Fitxer de respostes correctes

Fitxer de text (per defecte `respostes.csv`) amb una línia per permutació. El
primer camp és el número de permutació i després van les lletres correctes,
separades per `;` o `,`:

```
1;C;D;C;D;A;A;D;A;D;C;B;D;D;B;C;D;A;A;B;C;B;B;B;A;A;D;A;A;A;B
2;D;D;D;C;A;C;C;D;B;C;D;D;B;B;B;C;D;D;B;D;C;B;B;B;D;D;A;A;B;A
3;C;C;A;D;A;C;C;B;D;A;A;A;B;C;A;C;D;B;A;B;D;A;B;A;B;B;C;D;A;C
```

També s'accepten les lletres juntes: `2;DDDCACCDBC...`.

**Preguntes eliminades.** Si una pregunta s'ha d'anul·lar (per exemple, perquè
l'enunciat tenia un error), **substitueix** la seva lletra correcta per una
`X`. La línia ha de continuar tenint una lletra o una `X` per a cada pregunta.
A l'exemple següent, la pregunta 1 de la permutació 2 està eliminada:

```
abans:   2;D;D;D;C;A;C;C;D;B;C;...
després: 2;X;D;D;C;A;C;C;D;B;C;...
```

Vigila de no esborrar cap lletra en posar la `X`. Si a una línia li falta una
resposta, totes les preguntes següents es compararien amb la resposta de la
pregunta següent. Per evitar-ho, el programa no corregeix cap examen d'aquella
permutació i mostra un error (vegeu *Avisos i errors*).

Una pregunta eliminada no es corregeix i no compta ni com a correcta, ni com a
errònia, ni com a sense resposta. Recorda que, si la pregunta surt en una
posició diferent a cada permutació, cal posar la `X` a la posició
corresponent de cada línia.

## Corregir els exàmens

```bash
python3 corregir-examens-escanejats.py [IMATGES_O_DIRECTORIS ...] [opcions]
```

Sense arguments, corregeix tots els `.jpg` del directori `test` amb
`respostes.csv`. Exemples:

```bash
python3 corregir-examens-escanejats.py                     # directori test
python3 corregir-examens-escanejats.py escanejos/ -v       # un altre directori, mostrant les respostes llegides
python3 corregir-examens-escanejats.py full1.jpg full2.jpg -r claus.csv -o notes.csv
```

| Opció | Significat |
|---|---|
| `-r`, `--respostes FITXER` | Fitxer de respostes correctes (per defecte `respostes.csv`). |
| `-o`, `--sortida FITXER` | Fitxer de resultats (per defecte `correccio.csv`). |
| `-u`, `--llindar VALOR` | Llindar per considerar marcada una casella (per defecte 0,06). Vegeu més avall. |
| `-v`, `--detall` | Mostra les respostes llegides a cada examen. |

### Resultats

**`correccio.csv`** té una capçalera i una línia per examen, separades per `;`:

```
DNI;permutacio;correctes;erronies;sense_resposta;avaluades;eliminades;fitxer
12856003;5;14;3;12;29;1;A6E01-20261104101917864_0001-0.jpg
48047507;6;12;6;11;29;1;A6E01-20261104101917864_0002-1.jpg
```

| Columna | Significat |
|---|---|
| `DNI` | DNI llegit de la graella (`?` als dígits que no s'han pogut llegir). |
| `permutacio` | Número de permutació (columna CODI del full). |
| `correctes` | Preguntes contestades correctament. |
| `erronies` | Preguntes contestades malament o amb més d'una marca. |
| `sense_resposta` | Preguntes avaluades sense cap casella marcada. |
| `avaluades` | Preguntes no eliminades (= correctes + erronies + sense_resposta). |
| `eliminades` | Preguntes marcades amb `X` al fitxer de respostes. |
| `fitxer` | Nom de la imatge corregida. |

Per exemple, la nota sobre 10 sense penalització és `10 * correctes / avaluades`.

**Imatge corregida.** Per a cada examen `X.jpg` es crea `X-cor.jpg` al mateix
directori: un cercle **verd** a cada resposta correcta i un cercle **vermell**
a cada resposta errònia. Les preguntes eliminades es tatxen amb una ratlla
**blava**. Les preguntes en blanc no es marquen. Si es torna a
executar el programa, aquestes imatges no es corregeixen com si fossin exàmens.

**Criteris de correcció:**

- **Correcta:** s'ha marcat només la lletra correcta.
- **Errònia:** s'ha marcat una lletra incorrecta, o més d'una lletra.
- **Sense resposta:** no s'ha marcat cap casella.
- **Eliminada:** la pregunta té una `X` al fitxer de respostes. No compta enlloc, de manera que correctes + errònies + sense resposta és el nombre de preguntes no eliminades.
- **Casella anul·lada amb una creu (X):** si l'estudiant ha omplert una casella i després l'ha ratllat amb una creu, aquesta no compta i es pren l'altra marca. Funciona igual a la graella del DNI.

El fitxer només conté els recomptes. Si cal aplicar penalització per les
errònies, es pot calcular després a partir de les columnes.

### Avisos i errors

El programa mostra per pantalla els casos que convé revisar a mà.

Els missatges que comencen per `AVÍS` indiquen casos que convé revisar, però
l'examen es corregeix. Els que comencen per `ERROR` indiquen que l'examen
**no s'ha corregit** i no apareix a `correccio.csv`.

| Missatge | Què vol dir |
|---|---|
| `DNI no llegit correctament (538??071)` | Hi ha columnes del DNI sense cap marca o amb més d'una. Els dígits dubtosos surten com a `?`. Passa, per exemple, quan l'estudiant no omple la graella o escriu un NIE. |
| `pregunta 4 amb diverses marques (CD), compta com a errònia` | Doble marca a la pregunta. |
| `pregunta 8: B anul·lada, es pren A` | S'ha detectat una casella anul·lada amb una creu. |
| `permutació (CODI) '…' no llegida o no és a respostes.csv` | No es pot saber quina permutació és. L'examen **no es corregeix**. |
| `ERROR …: 30 preguntes al full però 29 a la permutació 1 de respostes.csv; examen no corregit` | El nombre de preguntes del full no coincideix amb el nombre de respostes d'aquella permutació a `respostes.csv`. Normalment és que a la línia hi falta o hi sobra una lletra. L'examen **no es corregeix** fins que s'arregli el fitxer. |
| `no es troben els 4 cercles de les cantonades` | El full s'ha escanejat retallat o tapat. Es corregeix sense redreçar-lo. |

## Com funciona el corrector

1. **Càrrega.** La imatge es redueix a uns 300 ppp, es binaritza (llindar d'Otsu) i es corregeix la perspectiva amb els 4 cercles de les cantonades. Això corregeix el gir, la inclinació i la deformació en trapezi, com la d'una foto feta amb el mòbil.
2. **Caselles.** Es localitzen les caselles buides: components amb forma de rectangle i interior blanc. A partir d'aquestes es dedueixen les files i les columnes de les graelles, de manera que també se sap on són les caselles que l'estudiant ha omplert. Les caselles del DNI, més allargades, se separen de les de les preguntes per la forma.
3. **Marques.** Es mesura la foscor (nivell de gris) de l'interior de cada casella i se li resta el fons de les caselles buides amb la mateixa lletra o dígit. Una casella està marcada si supera el llindar de 0,06. Així es detecten també les marques fluixes fetes amb llapis.
4. **Creus.** Si una pregunta té diverses marques i una sobresurt clarament per sobre i per sota de la casella (la creu), es considera anul·lada.

### Ajustar el llindar

Amb els exàmens de prova, les caselles buides queden com a màxim 0,035 per
sobre del fons i la marca més fluixa està a 0,084, de manera que el valor per
defecte (0,06) deixa marge per les dues bandes. Si amb altres escàners o
bolígrafs es perden marques fluixes, es pot baixar (per exemple `-u 0.05`). Si
apareixen marques que no hi són, es pot pujar (per exemple `-u 0.08`).

## Recomanacions

- Abans d'un examen real, imprimeix uns quants fulls, omple'ls a mà, escaneja'ls i comprova que es corregeixen bé.
- Demana als estudiants que omplin bé les caselles amb bolígraf o llapis fosc i que, per anul·lar una resposta, la ratllin amb una creu que sobresurti de la casella.
- Revisa sempre els avisos i, si hi ha dubtes, la imatge `-cor.jpg` de l'examen.
