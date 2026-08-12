"""
Génération de la fiche variétale au format officiel "Plateforme d'Évaluation
Variétale Igname et Tubercules" (charte CIRAD).

Reproduit fidèlement la structure du modèle de référence (fiche Roujol), en 2 pages :

  Page 1 : CARTE D'IDENTITE | DESCRIPTION (Partie aérienne / Partie souterraine) | QUALITE
  Page 2 : CARACTERES CULTURAUX (Conditions d'évaluation, Lutte mauvaises herbes,
           Tolérance aux maladies, Production) + bande de logos officielle

Les champs présents en base sont remplis ; les descripteurs absents sont marqués
"n.d." pour préserver la structure officielle et rendre visibles les manques.

- Rendu : fpdf2 (aucune dépendance système).
- Photos : chargées depuis le site YamHub, REDIMENSIONNÉES avant intégration
  (sinon le PDF pèse des dizaines de Mo).
"""

import io
import os
import ssl
import tempfile
import urllib.parse
import urllib.request

import pandas as pd
from fpdf import FPDF

try:
    from PIL import Image
    HAS_PIL = True
except Exception:
    HAS_PIL = False

try:
    import requests
    HAS_REQUESTS = True
except Exception:
    HAS_REQUESTS = False

UPLOADS_URL = "https://yamhub.fr/adminPanel/uploads/"
IMG_DIR = os.path.join(os.path.dirname(__file__), "..", "public_html", "images")
ASSETS = os.path.join(os.path.dirname(__file__), "assets")

PURPLE = (125, 46, 120)
GREEN = (39, 137, 60)
ORANGE = (222, 120, 30)
DARK = (45, 45, 45)

ND = "n.d."

CONDITIONS_TXT = (
    "Les variétés sont évaluées sur plusieurs années dans des conditions optimales "
    "de culture en station de recherche (Guadeloupe : Roujol / Godet), sur billons "
    "irrigués, avec gestion manuelle de l'enherbement."
)


# --------------------------------------------------------------------------- #
# Téléchargement + redimensionnement des photos                               #
# --------------------------------------------------------------------------- #
def _download(url):
    """Télécharge des octets. Gère le souci de certificat SSL sous macOS.
    Ne bloque pas : une image manquante (404) renvoie None immédiatement."""
    headers = {"User-Agent": "Mozilla/5.0"}
    # 1) requests (embarque ses propres certificats -> fiable sous macOS)
    if HAS_REQUESTS:
        try:
            r = requests.get(url, timeout=8, headers=headers)
            return r.content if r.status_code == 200 else None
        except Exception:
            pass  # on ne bascule sur urllib QUE si requests a planté (pas un 404)
    # 2) urllib : vérifié, puis repli sans vérification (souci de certif macOS)
    for ctx in (ssl.create_default_context(), ssl._create_unverified_context()):
        try:
            req = urllib.request.Request(url, headers=headers)
            return urllib.request.urlopen(req, timeout=8, context=ctx).read()
        except ssl.SSLError:
            continue          # certificat -> on retente sans vérification
        except Exception:
            return None       # 404, timeout, etc. -> abandon immédiat
    return None


def _fetch(filename, max_px=900, quality=75):
    """Télécharge une photo YamHub (nom encodé) et la redimensionne. -> chemin ou None."""
    url = UPLOADS_URL + urllib.parse.quote(str(filename))
    data = _download(url)
    if not data:
        return None
    try:
        fd, path = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        if HAS_PIL:
            im = Image.open(io.BytesIO(data)).convert("RGB")
            im.thumbnail((max_px, max_px))
            im.save(path, "JPEG", quality=quality, optimize=True)
        else:
            with open(path, "wb") as fh:
                fh.write(data)     # repli : image brute (PDF plus lourd)
        return path
    except Exception:
        return None


def _latin(s):
    return str(s).encode("latin-1", "replace").decode("latin-1")


def _val(row, code):
    v = row.get(code)
    return str(v) if pd.notna(v) else ND


def _points_forts(row):
    pts = []
    cls = row.get("classe_rendement")
    if pd.notna(cls) and "performante" in str(cls):
        pts.append("Bon rendement")
    if pd.notna(cls) and "stable" in str(cls):
        pts.append("Rendement régulier (stable)")
    if row.get("BOILED_Q") == "High":
        pts.append("Bonne qualité culinaire")
    if row.get("FARMER_A") == "High":
        pts.append("Bien accepté par les producteurs")
    return pts[:4] if pts else ["Données en cours de consolidation"]


def _photo(photos, accession, desc):
    r = photos[(photos["variete_name"] == accession) & (photos["description"] == desc)]
    return r.iloc[0]["photo_bytea"] if len(r) else None


class Fiche(FPDF):
    def sidebar(self, texte):
        self.set_fill_color(*PURPLE)
        self.rect(0, 0, 14, 297, "F")
        with self.rotation(90, 7, 285):
            self.set_xy(7, 285)
            self.set_text_color(255, 255, 255)
            self.set_font("Helvetica", "B", 12)
            self.cell(270, 6, _latin(texte))

    def header_band(self, nom):
        self.set_fill_color(*PURPLE)
        self.rect(14, 0, 196, 40, "F")
        self.set_text_color(255, 255, 255)
        self.set_xy(20, 6)
        self.set_font("Helvetica", "", 14)
        self.cell(184, 8, "Fiche Variétale Igname", align="C")
        self.set_xy(20, 15)
        self.set_font("Helvetica", "B", 30)
        self.cell(184, 16, _latin(nom), align="C")

    def section(self, titre, y):
        self.set_xy(110, y)
        self.set_text_color(*GREEN)
        self.set_font("Helvetica", "B", 15)
        self.cell(94, 8, _latin(titre), align="R")
        self.set_draw_color(*GREEN)
        self.set_line_width(0.6)
        self.line(20, y + 8.5, 204, y + 8.5)

    def subsection(self, titre, x, y):
        self.set_xy(x, y)
        self.set_text_color(*ORANGE)
        self.set_font("Helvetica", "BI", 12)
        self.cell(85, 6, _latin(titre))

    def field(self, label, value, x, y, w_label=52):
        self.set_xy(x, y)
        self.set_text_color(*DARK)
        self.set_font("Helvetica", "B", 9)
        self.cell(w_label, 5, _latin(label))
        self.set_font("Helvetica", "", 9)
        self.cell(30, 5, _latin(str(value)))

    def paragraph(self, txt, x, y, w=90):
        self.set_xy(x, y)
        self.set_text_color(*DARK)
        self.set_font("Helvetica", "", 9)
        self.multi_cell(w, 4.5, _latin(txt))


def generate(row, photos, extra=None):
    """row : Series d'une variété ; photos : DataFrame ; -> bytes PDF."""
    acc = str(row["nom_accession"]) if pd.notna(row.get("nom_accession")) else ""
    titre = row.get("nom") if pd.notna(row.get("nom")) else (acc or str(row.get("code_plantation", "")))
    pdf = Fiche(format="A4")
    pdf.set_auto_page_break(False)

    # ========================= PAGE 1 ========================= #
    pdf.add_page()
    pdf.sidebar("Plateforme d'Evaluation Variétale Igname et Tubercules")
    pdf.header_band(titre)

    # --- CARTE D'IDENTITE ---
    pdf.section("CARTE D'IDENTITE", 46)
    y = 58
    origine = row.get("pays_origine")
    pdf.field("Espèce", row.get("espece", ND), 20, y); y += 6
    pdf.field("Origine", origine if pd.notna(origine) else ND, 20, y); y += 6
    pdf.field("Sélectionneur", "Cirad", 20, y); y += 6
    pdf.field("Mainteneur", "CRB - Plantes Tropicales", 20, y, 52); y += 6
    pdf.field("Année d'introduction", _val(row, "annee_creation"), 20, y, 52); y += 6
    pdf.field("Période d'évaluation", ND, 20, y, 52)

    # Encadré points forts
    pdf.set_draw_color(*PURPLE); pdf.set_line_width(0.4)
    pdf.rect(118, 56, 86, 34)
    pdf.set_xy(121, 58); pdf.set_text_color(*PURPLE); pdf.set_font("Helvetica", "BI", 11)
    pdf.cell(80, 6, _latin("Points forts de la variété :"))
    yy = 65
    pdf.set_font("Helvetica", "", 10); pdf.set_text_color(*DARK)
    for p in _points_forts(row):
        pdf.set_xy(121, yy); pdf.cell(80, 5, _latin("- " + p)); yy += 5.5

    # --- DESCRIPTION ---
    pdf.section("DESCRIPTION", 96)

    # Partie aérienne (fields à gauche, photo feuille à droite)
    pdf.subsection("PARTIE AERIENNE", 20, 108)
    ya = 116
    for lab, code in [("Tige - couleur", "CTP"), ("Tige - bulbilles", "APB"),
                      ("Feuille - forme", "FF"), ("Feuille - texture", "TF"),
                      ("Pétiole - couleur", "CP")]:
        pdf.field(lab, _val(row, code), 20, ya); ya += 6
    pf = _photo(photos, acc, "Feuille adaxiale")
    if pf:
        p = _fetch(pf)
        if p:
            try: pdf.image(p, x=120, y=108, w=84, h=46)
            except Exception: pass

    # Partie souterraine (fields à droite, photo tubercule à gauche)
    pdf.subsection("PARTIE SOUTERRAINE", 118, 160)
    ys = 168
    pdf.field("Tubercule - aspect chair", _val(row, "ACT"), 118, ys); ys += 6
    pdf.field("Tubercule - couleur chair", _val(row, "CCCTCT"), 118, ys); ys += 6
    pdf.field("Phelloderme", _val(row, "CPT"), 118, ys); ys += 6
    pdf.field("Peau - épaisseur", _val(row, "EPT"), 118, ys); ys += 6
    pdf.field("Racines sur tubercule", _val(row, "PRT"), 118, ys)
    pt = _photo(photos, acc, "Tubercule forme")
    if pt:
        p = _fetch(pt)
        if p:
            try: pdf.image(p, x=20, y=150, w=84, h=54)
            except Exception: pass

    # --- QUALITE ---
    pdf.section("QUALITE", 210)
    yq = 220
    sen, emg = row.get("SEN"), row.get("EMERGENCE")
    duree = f"{sen - emg:.0f} j" if pd.notna(sen) and pd.notna(emg) else ND
    recolte = f"{sen:.0f} j" if pd.notna(sen) else ND
    pdf.field("Durée du cycle", duree, 20, yq, 62); yq += 6
    pdf.field("Récolte", recolte, 20, yq, 62); yq += 6
    pdf.field("Conservation", ND, 20, yq, 62); yq += 6
    pdf.field("Couleur de la chair", _val(row, "CCCTCT"), 20, yq, 62); yq += 6
    pdf.field("Oxydation à la cuisson", _val(row, "POT"), 20, yq, 62); yq += 6
    pdf.field("Fermeté après cuisson", _val(row, "BOILED_Q"), 20, yq, 62)
    pc = _photo(photos, acc, "Tubercule chair")
    if pc:
        p = _fetch(pc)
        if p:
            try: pdf.image(p, x=152, y=214, w=44, h=44)
            except Exception: pass

    # ========================= PAGE 2 ========================= #
    pdf.add_page()
    pdf.sidebar("Evaluation Variétale GUADELOUPE")

    pdf.section("CARACTERES CULTURAUX", 20)

    pdf.subsection("CONDITIONS D'EVALUATION", 20, 34)
    pdf.paragraph(CONDITIONS_TXT, 20, 42, w=180)

    pdf.subsection("LUTTE CONTRE LES MAUVAISES HERBES", 20, 66)
    pdf.paragraph("Information non disponible pour cette variété (à compléter).", 20, 74, w=180)

    pdf.subsection("TOLERANCE AUX MALADIES", 20, 90)
    au = row.get("anthracnose_perf")
    pdf.paragraph("Anthracnose (indice AUDPC, plus bas = plus résistant) : "
                  + (f"{au:.0f}" if pd.notna(au) else ND), 20, 98, w=180)

    pdf.subsection("PRODUCTION", 20, 116)
    yp = 124
    rp = row.get("rendement_perf")
    cls = row.get("classe_rendement")
    cv = row.get("rendement_cv")
    pdf.field("Rendement (indice multi-env)", f"{rp:.0f}" if pd.notna(rp) else ND, 20, yp, 58); yp += 6
    pdf.field("Profil de régularité", str(cls) if pd.notna(cls) else ND, 20, yp, 58); yp += 6
    pdf.field("Variabilité entre milieux (CV)", f"{cv:.0f} %" if pd.notna(cv) else ND, 20, yp, 58)

    # Bande de logos officielle
    footer = os.path.join(ASSETS, "footer_logos.png")
    if os.path.exists(footer):
        try: pdf.image(footer, x=17, y=273, w=176)
        except Exception: pass

    return bytes(pdf.output())
