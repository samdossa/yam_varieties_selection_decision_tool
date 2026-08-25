"""
fiche_html.py — Fiche variétale au format  Guadeloupe, rendue en PDF.

Reproduit le modèle officiel (2 pages : DESCRIPTION / QUALITE puis PERFORMANCES)
via HTML+CSS rendu par WeasyPrint. Chaque variété se remplit à partir de tool_data,
le graphe de rendement par site (Roujol/Godet) est généré automatiquement.

Champs indisponibles en base -> "n.d." (et listés dans "Données manquantes").
"""

import base64
import io
import math
import os

import pandas as pd

import debouches as _deb

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MPL = True
except Exception:
    HAS_MPL = False

UPLOADS_URL = "https://yamhub.fr/adminPanel/uploads/"
ASSETS = os.path.join(os.path.dirname(__file__), "assets")
ND = "n.d."

PURPLE = "#7d2e78"
GREEN = "#4e9a2f"
ORANGE = "#c0622a"
PINK = "#efdcec"
GREY = "#555"


QUAL_FR = {"Low": "Faible", "Medium": "Moyenne", "High": "Bonne"}


def _mapbox_token():
    p = os.path.join(os.path.dirname(__file__), "mapbox_token.txt")
    if os.path.exists(p):
        return open(p).read().strip()
    return os.environ.get("MAPBOX_TOKEN", "")


def _v(row, code, suffix=""):
    v = row.get(code)
    if pd.isna(v):
        return ND
    if isinstance(v, float):
        return f"{round(v, 1):g}{suffix}"
    return f"{v}{suffix}"


def _photo_url(photos, acc, desc):
    if pd.isna(acc):
        return None
    r = photos[(photos["variete_name"] == acc) & (photos["description"] == desc)]
    return UPLOADS_URL + str(r.iloc[0]["photo_bytea"]) if len(r) else None


def _points_forts(row):
    """Points forts déduits des données mesurées (min 2, max 5)."""
    pts = []
    cls = str(row.get("classe_rendement")).lower() if pd.notna(row.get("classe_rendement")) else ""
    rp = row.get("rendement_perf")
    if pd.notna(rp) and float(rp) >= 35:
        pts.append("Rendement élevé")
    elif pd.notna(rp) and float(rp) >= 25:
        pts.append("Bon rendement")
    elif "performante" in cls:
        pts.append("Bon rendement")
    if "stable" in cls:
        pts.append("Rendement stable")
    au, rv = row.get("anthracnose_perf"), row.get("R_AUDPC_GOD_25_26")
    res = []
    if pd.notna(au) and float(au) < 35:
        res.append("à l'anthracnose")
    if pd.notna(rv) and float(rv) < 35:
        res.append("à la rouille")
    if res:
        pts.append("Tolérance " + " et ".join(res))
    bq = row.get("BOILED_Q")
    if bq == "High":
        pts.append("Bonne qualité à la cuisson")
    elif bq == "Medium":
        pts.append("Qualité à la cuisson correcte")
    pt = row.get("PTS1M")
    if pt == "Absent":
        pts.append("Pas de pourriture au stockage (1 mois)")
    elif pt == "Faible":
        pts.append("Faible pourriture au stockage (1 mois)")
    if row.get("FARMER_A") == "High":
        pts.append("Appréciée des agriculteurs")
    tms = row.get("TMS_BLUP")
    if pd.notna(tms):
        v = float(tms); v = v * 100 if v <= 1 else v
        if v >= 32:
            pts.append("Matière sèche élevée")
    pm = row.get("poids_moyen_g")
    if pd.notna(pm) and float(pm) >= 1500:
        pts.append("Gros tubercules")
    for extra in ["Adaptée aux conditions de la Guadeloupe",
                  "Évaluée en stations expérimentales (Roujol, Godet)"]:
        if len(pts) >= 2:
            break
        pts.append(extra)
    return pts[:4]


def _chart_sites(row):
    """Barres du rendement par site x année (les données ne couvrent que Roujol/Godet)."""
    if not HAS_MPL:
        return None

    def moy(cols):
        vals = [row.get(c) for c in cols]
        vals = [float(v) for v in vals if pd.notna(v)]
        return sum(vals) / len(vals) if vals else None

    barres = [
        ("Roujol\n23-24", moy(["RT_ROU_23_24"]), PURPLE),
        ("Roujol\n24-25", moy(["RT_A_ROU_24_25", "RT_D_ROU_24_25"]), PURPLE),
        ("Godet\n24-25", moy(["RT_RP1_GOD_24_25", "RT_RP2_GOD_24_25"]), GREEN),
        ("Godet\n25-26", moy(["RT_RP1_GOD_25_26", "RT_RP2_GOD_25_26"]), GREEN),
    ]
    barres = [b for b in barres if b[1] is not None]
    if not barres:
        return None
    labels = [b[0] for b in barres]
    vals = [b[1] for b in barres]
    colors = [b[2] for b in barres]
    fig, ax = plt.subplots(figsize=(6, 2.6))
    ax.bar(labels, vals, color=colors, width=0.6)
    ax.set_ylabel("t/ha", fontsize=9)
    ax.set_title("Rendement potentiel par site et année", fontsize=10, color=PURPLE)
    for i, v in enumerate(vals):
        ax.text(i, v + 0.5, f"{v:.0f}", ha="center", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120)
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _chart_calibre(row):
    """Camembert du calibre (classes de poids) -> data URI base64."""
    if not HAS_MPL:
        return None
    parts = [("> 2 kg", "cal_sup2kg", "#d9382c"),
             ("300 g - 2 kg", "cal_300_2000", "#e0a200"),
             ("80 - 300 g", "cal_80_300", "#4e9a2f"),
             ("0 - 80 g", "cal_0_80", "#7d2e78")]
    labels, vals, colors = [], [], []
    for lbl, col, c in parts:
        v = row.get(col)
        labels.append(lbl)                       # toutes les classes affichées, même à 0 %
        vals.append(float(v) if pd.notna(v) else 0.0)
        colors.append(c)
    if sum(vals) == 0:                            # aucune donnée calibre
        return None
    fig, ax = plt.subplots(figsize=(3.4, 3.0))
    ax.pie(vals, colors=colors, autopct="%1.0f%%", startangle=90,
           textprops={"fontsize": 8, "color": "white"})
    ax.legend(labels, loc="center left", bbox_to_anchor=(0.95, 0.5),
              fontsize=8, frameon=False)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120)
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _missing(row, mapping):
    return [label for label, code in mapping if pd.isna(row.get(code))]


def _img_uri(path, max_px=160, fmt="PNG"):
    """Image locale -> data-URI base64 (embarquée, robuste sur tous les WeasyPrint,
    aucune dépendance file://). Redimensionne pour limiter le poids."""
    import base64
    import io
    from PIL import Image, ImageOps
    try:
        im = ImageOps.exif_transpose(Image.open(path))
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            bg = Image.new("RGB", im.size, (255, 255, 255))
            bg.paste(im, mask=im.split()[-1])
            im = bg
        else:
            im = im.convert("RGB")
        if max(im.size) > max_px:
            im.thumbnail((max_px, max_px))
        buf = io.BytesIO()
        if fmt.upper() == "JPEG":
            im.save(buf, format="JPEG", quality=85)
            mime = "jpeg"
        else:
            im.save(buf, format="PNG")
            mime = "png"
        return f"data:image/{mime};base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""


def _leaf_local(code):
    """Photo de feuille (nouveau jeu 2024/2023) : data/feuilles/CIRADn.jpg.
    Recherche insensible à la casse. Vide si la variété n'en a pas."""
    if not code or str(code) in ("nan", ""):
        return ""
    d = os.path.join(os.path.dirname(__file__), "data", "feuilles")
    for name in (f"{code}.jpg", f"{str(code).upper()}.jpg", f"{str(code).lower()}.jpg"):
        pth = os.path.join(d, name)
        if os.path.exists(pth):
            return _img_uri(pth, 560, "JPEG")
    url = os.environ.get("LEAF_URL")
    if url:
        return f"{url.rstrip('/')}/{str(code).upper()}.jpg"
    return ""


_PANDA2 = {}

def _panda2(row, field):
    """Champ de la feuille Panda2 (data/panda2.csv) : fournisseur, centre_code, doi.
    Clé = code_plantation (insensible à la casse). '' si absent."""
    p = os.path.join(os.path.dirname(__file__), "data", "panda2.csv")
    if not _PANDA2 and os.path.exists(p):
        import csv
        with open(p, newline="") as f:
            for r in csv.DictReader(f):
                cp = str(r.get("code_plantation", "")).strip().lower()
                if cp:
                    _PANDA2[cp] = r
    rec = _PANDA2.get(str(row.get("code_plantation", "")).strip().lower())
    return (rec.get(field, "").strip() if rec else "")


_DOI_MAP = {}


def _doi_of(row):
    """DOI de la variété (depuis data/doi.csv, issu de defidb). None si absent."""
    if not _DOI_MAP and os.path.exists(os.path.join(os.path.dirname(__file__), "data", "doi.csv")):
        import csv
        with open(os.path.join(os.path.dirname(__file__), "data", "doi.csv"), newline="") as f:
            for r in csv.DictReader(f):
                d = (r.get("doi") or "").strip()
                if not d:
                    continue
                for k in (r.get("nom_accession"), r.get("code_plantation_id")):
                    if k:
                        _DOI_MAP[str(k).strip().lower()] = d
    for k in (row.get("nom_accession"), row.get("code_plantation")):
        if k and str(k).strip().lower() in _DOI_MAP:
            return _DOI_MAP[str(k).strip().lower()]
    return None


def _recouv_tag(code, stage, h=150):
    """Image de recouvrement pour une variété à un stade (1mois, 3mois...).
    Cherche data/recouvrement_<stage>/CIRADn_<stage>.jpg en local, sinon RECOUV_URL."""
    if not code or str(code) in ("nan", ""):
        return ""
    fn = f"{code}_{stage}.jpg"
    local = os.path.join(os.path.dirname(__file__), "data", f"recouvrement_{stage}", fn)
    style = f"height:{h}px;border-radius:5px;box-shadow:0 0 3px #999"
    if os.path.exists(local):
        return f'<img src="{_img_uri(local, 620, "JPEG")}" style="{style}">'
    url = os.environ.get("RECOUV_URL")
    if url:
        return f'<img src="{url.rstrip("/")}/{stage}/{fn}" style="{style}">'
    return ""


def _recouv_block(code):
    """Bloc HTML des photos de recouvrement disponibles (1 mois, 3 mois)."""
    avail = [(s, l) for s, l in [("1mois", "1 mois"), ("3mois", "3 mois")]
             if _recouv_tag(code, s)]
    if not avail:
        return '<div class="expl">Photo de recouvrement à venir.</div>'
    h = 205 if len(avail) == 1 else 150    # grande si seule, réduite si deux
    parts = []
    for stage, label in avail:
        parts.append(
            f'<div style="display:inline-block;text-align:center;margin:0 8px;vertical-align:top">'
            f'<div style="font-size:9pt;color:{GREY};margin-bottom:3px">Recouvrement à {label}</div>'
            f'{_recouv_tag(code, stage, h)}</div>')
    return "".join(parts)


def _vname(r):
    cc = r.get("code_cirad")
    na = r.get("nom_accession")
    cc = None if (cc is None or str(cc) in ("nan", "")) else str(cc)
    na = None if (na is None or str(na) in ("nan", "")) else str(na)
    if cc and na:
        return f"{cc} ({na})"
    return cc or na or "—"


def _fr_boiled(v):
    return {"High": "Bonne", "Medium": "Moyenne", "Low": "Faible"}.get(str(v).strip(), ND)


def _ms_pct(r):
    v = r.get("TMS_BLUP")
    try:
        v = float(v)
    except (TypeError, ValueError):
        return ND
    return f"{round((v * 100 if v <= 1 else v)):g} %"


def _comparison(row, all_df, n=5):
    """Rubrique : variété cible vs meilleures variétés (rendement le plus élevé).

    Retourne (phrase_positionnement, tableau_html).
    """
    if all_df is None or "rendement_perf" not in all_df.columns:
        return "", ""
    d = all_df[all_df["rendement_perf"].notna()].copy()
    if not len(d):
        return "", ""
    d = d.sort_values("rendement_perf", ascending=False).reset_index(drop=True)
    tgt_cp = row.get("code_plantation")
    

    # Positionnement de la variété (rang par rendement)
    phrase = ""
    idx = d.index[d["code_plantation"] == tgt_cp]
    if len(idx):
        rang = int(idx[0]) + 1
        rdt_t = round(float(d.iloc[idx[0]]["rendement_perf"]), 1)
        phrase = (f"Cette variété se classe <b>{rang}<sup>e</sup> sur {len(d)}</b> "
                  f"pour le rendement ({rdt_t:g} t/ha).")

    top = d.head(n)
    sel = top if tgt_cp in list(top["code_plantation"]) else pd.concat(
        [top, all_df[all_df["code_plantation"] == tgt_cp]])
    sel = sel.drop_duplicates("code_plantation").sort_values(
        "rendement_perf", ascending=False)

    trs = ""
    for _, r in sel.iterrows():
        is_tgt = r.get("code_plantation") == tgt_cp
        rdt = r.get("rendement_perf")
        rdt = f"{round(float(rdt), 1):g}" if pd.notna(rdt) else ND
        reg = r.get("classe_rendement")
        reg = reg if pd.notna(reg) else ND
        try:
            usage = _deb.usages(r)[0]
        except Exception:
            usage = ND
        style = (f' style="background:{PINK}; font-weight:bold;"' if is_tgt else "")
        flag = " ◀" if is_tgt else ""
        trs += (f'<tr{style}><td>{_vname(r)}{flag}</td>'
                f'<td style="text-align:center">{rdt}</td>'
                f'<td style="text-align:center">{reg}</td>'
                f'<td style="text-align:center">{_ms_pct(r)}</td>'
                f'<td style="text-align:center">{_fr_boiled(r.get("BOILED_Q"))}</td>'
                f'<td>{usage}</td></tr>')
    table = (
        '<table class="cmp"><thead><tr><th>Variété</th>'
        '<th>Rendement<br>(t/ha)</th><th>Régularité</th><th>Matière<br>sèche</th>'
        '<th>Qualité<br>cuisson</th><th>Usage principal</th>'
        f'</tr></thead><tbody>{trs}</tbody></table>')
    return phrase, table


def build_html(row, photos, all_df=None):
    acc = row.get("nom_accession")
    nom = row.get("nom") if pd.notna(row.get("nom")) else (acc if pd.notna(acc) else row.get("code_plantation"))
    _cp = str(row.get("code_plantation", "")).strip()
    _nm = row.get("nom") if pd.notna(row.get("nom")) else (acc if pd.notna(acc) else "")
    titre = f"{_cp} ({_nm})" if (_cp and str(_nm).strip()) else (_cp or str(nom))
    # Nouvelle feuille (2024/2023) en priorité ; sinon repli sur l'ancienne photo
    leaf = (_leaf_local(row.get("code_plantation"))
            or _photo_url(photos, acc, "Feuille adaxiale")
            or _photo_url(photos, acc, "Feuille abaxiale"))
    tuber = _photo_url(photos, acc, "Tubercule forme")
    flesh = _photo_url(photos, acc, "Tubercule chair")
    chart = _chart_sites(row)
    calibre_pie = _chart_calibre(row)
    pm = row.get("poids_moyen_g")
    poids_moyen = f"{pm / 1000:.1f} kg" if pd.notna(pm) else ND

    pf = "".join(f"<li>{p}</li>" for p in _points_forts(row))

    # Champs suivis pour la liste "données manquantes"
    suivi = [("Couleur de la chair", "CCCTCT"), ("Texture feuille", "TF"),
             ("Couleur pétiole", "CP"), ("Bulbilles", "APB"),
             ("Épaisseur peau", "EPT"), ("Rendement (t/ha)", "rendement_perf"),
             ("Nb tubercules/plant", "NTMP_BLUP"), ("Taux de germination", "TG_BLUP"),
             ("Qualité bouillie", "BOILED_Q")]
    manquantes = _missing(row, suivi)
    manq_html = ("".join(f"<li>{m}</li>" for m in manquantes)
                 if manquantes else "<li>aucune donnée clé manquante</li>")

    def cell(v):
        return v if v not in (None, "nan") else ND

    # anthracnose : indice AUDPC -> niveau
    au = row.get("anthracnose_perf")
    anthra = (("Sensible" if au >= 50 else "Modérément sensible" if au >= 35 else "Tolérante")
              if pd.notna(au) else ND)
    rv = row.get("R_AUDPC_GOD_25_26")
    rouille = (("Sensible" if rv >= 50 else "Modérément sensible" if rv >= 35 else "Tolérante")
               if pd.notna(rv) else ND)
    afm = row.get("AFM")
    afm_oui = pd.notna(afm) and str(afm) not in ("Absent", "Absence")
    pays = row.get("pays_origine")
    pays_html = f" ({pays})" if pd.notna(pays) else ""
    sen = row.get("S_BLUP")   # sénescence (BLUP) -> durée du cycle levée->sénescence
    if pd.notna(sen):
        _m = sen / 30.0
        _c = "court (<6 mois)" if _m < 6 else "long (6-9 mois)" if _m <= 9 else "très long (>9 mois)"
        cycle_txt = f"{_m:.1f} mois - {_c}"
    else:
        cycle_txt = ND
    pts = row.get("PTS1M")    # pourriture tubercule au stockage, test à 1 mois
    conserv = ({"Absent": "Absente", "Faible": "Faible", "Fort": "Forte"}.get(pts, ND)
               if pd.notna(pts) else ND)
    # Profil de régularité -> cases Stable / Non stable
    _clr = str(row.get("classe_rendement")).lower() if pd.notna(row.get("classe_rendement")) else ""
    stable_oui = "stable" in _clr
    nonstable_oui = ("spécialis" in _clr) or ("specialis" in _clr)
    bq = row.get("BOILED_Q")  # qualité bouillie -> français
    qbouillie = QUAL_FR.get(bq, ND) if pd.notna(bq) else ND
    de = row.get("DE_BLUP")   # durée d'émergence -> jours (arrondi au supérieur)
    emergence = f"{math.ceil(de)} jours" if pd.notna(de) else ND
    tg = row.get("TG_BLUP")
    germ = f"{round(tg)} %" if pd.notna(tg) else ND
    tok = _mapbox_token()
    carte_local = os.path.join(ASSETS, "carte_guadeloupe.png")
    if tok:
        markers = "pin-l+c0392b(-61.585,16.19),pin-l+2e7d32(-61.44,16.36)"
        bbox = "[-61.85,15.90,-61.15,16.55]"   # toute l'île principale (Basse-Terre + Grande-Terre)
        carte_src = (f"https://api.mapbox.com/styles/v1/mapbox/outdoors-v12/static/"
                     f"{markers}/{bbox}/660x580?padding=25&access_token={tok}")
    elif os.path.exists(carte_local):
        carte_src = _img_uri(carte_local, 900, "PNG")
    else:
        carte_src = ""
    carte_tag = (f'<img src="{carte_src}" style="max-width:100%;max-height:185px;'
                 f'border-radius:8px;box-shadow:0 0 4px #999">' if carte_src else "")

    css = f"""
    @page {{ size: A4; margin: 0; }}
    * {{ font-family: 'Helvetica','Arial',sans-serif; box-sizing: border-box; }}
    body {{ margin:0; color:#222; }}
    .page {{ position: relative; width:210mm; height:297mm; page-break-after: always;
             padding: 8mm 8mm 8mm 20mm; }}
    .sidebar {{ position:absolute; left:0; top:0; width:14mm; height:100%; background:{PURPLE};
                display:flex; align-items:center; justify-content:center; overflow:hidden; }}
    .sidebar span {{ transform: rotate(-90deg); white-space:nowrap; color:#fff; font-weight:bold;
                     font-size:12pt; letter-spacing:.5px; }}
    .banner {{ background:{PURPLE}; color:#fff; padding:6px 14px; font-size:30pt;
               font-weight:bold; text-align:center; letter-spacing:1px; }}
    .brand {{ color:{ORANGE}; font-weight:bold; font-size:16pt; }}
    .brand small {{ display:block; color:#333; font-size:8pt; font-weight:normal; }}
    .sec {{ color:{GREEN}; font-size:16pt; font-weight:bold; text-align:right;
            border-bottom:2px solid {GREEN}; margin:10px 0 6px; padding-bottom:2px; }}
    .sub {{ color:{ORANGE}; font-style:italic; font-weight:bold; font-size:11pt;
            border-bottom:1px solid #ccc; margin:8px 0 4px; }}
    table.fields {{ width:100%; border-collapse:collapse; font-size:9.5pt; }}
    table.fields td {{ padding:2px 4px; vertical-align:top; }}
    .org {{ color:#333; }} .attr {{ color:{GREY}; }} .val {{ font-weight:bold; }}
    .pf {{ border:1px solid {PURPLE}; border-radius:4px; padding:6px 10px; }}
    .pf b {{ color:{PURPLE}; font-style:italic; }}
    .pf ul {{ margin:4px 0 0 0; padding-left:16px; color:{PURPLE}; }}
    .box {{ background:{PINK}; padding:6px 10px; font-size:9.5pt; }}
    .note {{ background:{PINK}; padding:8px 12px; font-size:9pt; font-style:italic; }}
    .expl {{ color:{GREY}; font-style:italic; font-size:9pt; }}
    img.photo {{ max-width:100%; max-height:200px; display:block; margin:auto;
                 border-radius:2px; }}
    .grid2 {{ display:flex; gap:10px; }}
    .col {{ flex:1; }}
    .logo-row {{
        display: flex;
        align-items: center;
        gap: 10px;
        width: 100%;
        min-height: 55px;
        overflow: visible;
    }}
    .logo-row img {{
        display: block;
        width: auto !important;
        height: auto !important;
        max-width: 23%;
        max-height: 52px;
        object-fit: contain;
        flex: 0 1 auto;
    }}
    .bottom-logos {{
        margin-top: 14px;
        justify-content: flex-start;
    }}
    /* NB : PAS de display:flex ici — WeasyPrint ne calcule pas la largeur
       intrinsèque des <img width:auto> en flex et les fait disparaître.
       inline-block + margin (gap inopérant en inline-block) => tous les logos s'affichent. */
    .partner-row {{ margin-top:12px; }}
    .partner-row img {{ height:38px; width:auto; display:inline-block; vertical-align:middle; margin-right:16px; }}
    .header-logos {{ }}
    .header-logos img {{ height:30px; width:auto; display:inline-block; vertical-align:middle; margin-right:12px; }}

    table.cmp {{ width:100%; border-collapse:collapse; font-size:9.5pt; margin-top:4px; }}
    table.cmp th {{ background:{GREEN}; color:#fff; padding:5px 8px; text-align:left; }}
    table.cmp td {{ padding:5px 8px; border-bottom:1px solid #ddd; }}
    """

    # ---------- Logo CIRAD (en-tête haut-gauche) + QR code YamHub ----------
    from pathlib import Path

    def local_img(path):
        return Path(path).resolve().as_uri()

    cirad_path = os.path.join(ASSETS, "cirad_logo.png")
    cirad_tag = (
        f'<img src="{_img_uri(cirad_path, 200, "PNG")}" alt="CIRAD">'
        if os.path.exists(cirad_path) else ""
    )

    qr_path = os.path.join(ASSETS, "qr_yamhub.png")
    qr_tag = (
        f'<img src="{_img_uri(qr_path, 320, "PNG")}" style="width:110px" alt="YamHub">'
        if os.path.exists(qr_path) else ""
    )

    # Tous les logos depuis assets/logos_entete/ — affichés en HAUT (en-tête) et en BAS (page 2)
    logos_dir = os.path.join(ASSETS, "logos_entete")
    all_logos = ""
    if os.path.isdir(logos_dir):
        for fn in sorted(os.listdir(logos_dir)):
            if fn.lower().endswith((".png", ".jpg", ".jpeg", ".gif")):
                uri = _img_uri(os.path.join(logos_dir, fn), 200, "PNG")
                if uri:
                    all_logos += f'<img src="{uri}" alt="">'
    logos_tag = f'<div class="header-logos">{all_logos}</div>'
    partner_row = f'<div class="partner-row">{all_logos}</div>' if all_logos else ""

    # ---------- PAGE 1 ----------
    p1 = f"""
    <div class="page">
      <div class="sidebar"><span>Plateforme d'Évaluation Variétale d'Ignames</span></div>
      <div style="display:flex; justify-content:space-between; align-items:flex-start;">
        <div class="brand">{logos_tag}</div>
      </div>
      <div class="banner">{cell(titre)}</div>
      <div style="text-align:right; font-size:8pt; color:{GREY}; margin-top:2px;">Édition : 2026</div>

      <div class="sec">CARTE D'IDENTITÉ</div>
      <div class="grid2">
        <div class="col">
          <table class="fields">
            <tr><td class="attr">Espèce</td><td class="val"><i>{cell(_v(row,'espece'))}</i></td></tr>
            <tr><td class="attr">Origine</td><td class="val">{cell(_v(row,'pays_origine'))}</td></tr>
            <tr><td class="attr">Centre d'origine</td><td class="val">{cell(_panda2(row,'centre_code') or _v(row,'centre_origine'))}</td></tr>
            <tr><td class="attr">Fournisseur</td><td class="val">{cell(_panda2(row,'fournisseur'))}</td></tr>
            <tr><td class="attr">Code CIRAD</td><td class="val">{cell(_v(row,'code_cirad'))}</td></tr>
            <tr><td class="attr">DOI</td><td class="val" style="font-size:8.5pt">{cell(_panda2(row,'doi') or _doi_of(row))}</td></tr>
            <tr><td class="attr" style="padding-top:8px">Année d'introduction</td><td class="val" style="padding-top:8px">{cell(_v(row,'annee_creation'))}</td></tr>
            <tr><td class="attr">Période d'évaluation</td><td class="val">2022-2025</td></tr>
          </table>
        </div>
        <div class="col pf"><b>Points forts de la variété :</b><ul>{pf}</ul></div>
      </div>

      <div class="sec">DESCRIPTION</div>
      <div class="grid2">
        <div class="col">
          <div class="sub">PARTIE AÉRIENNE</div>
          <table class="fields">
            <tr><td class="org">Tige</td><td class="attr">Bulbilles</td><td class="val">{cell(_v(row,'APB'))}</td></tr>
            <tr><td></td><td class="attr">Couleur</td><td class="val">{cell(_v(row,'CTP'))}</td></tr>
            <tr><td class="org">Feuille</td><td class="attr">Forme</td><td class="val">{cell(_v(row,'FF'))}</td></tr>
            <tr><td></td><td class="attr">Texture</td><td class="val">{cell(_v(row,'TF'))}</td></tr>
            <tr><td class="org">Pétiole</td><td class="attr">Couleur</td><td class="val">{cell(_v(row,'CP'))}</td></tr>
          </table>
        </div>
        <div class="col" style="text-align:center">
          {'<img class="photo" src="'+leaf+'">' if leaf else ''}
        </div>
      </div>
      <div class="grid2" style="margin-top:4px">
        <div class="col" style="text-align:center">
          {'<img class="photo" src="'+tuber+'">' if tuber else ''}
        </div>
        <div class="col">
          <div class="sub">PARTIE SOUTERRAINE</div>
          <table class="fields">
            <tr><td class="org">Tubercule</td><td class="attr">Aspect chair</td><td class="val">{cell(_v(row,'ACT'))}</td></tr>
            <tr><td></td><td class="attr">Couleur chair</td><td class="val">{cell(_v(row,'CCCTCT'))}</td></tr>
            <tr><td></td><td class="attr">Racines</td><td class="val">{cell(_v(row,'PRT'))}</td></tr>
            <tr><td class="org">Peau</td><td class="attr">Épaisseur</td><td class="val">{cell(_v(row,'EPT'))}</td></tr>
            <tr><td></td><td class="attr">Phelloderme</td><td class="val">{cell(_v(row,'CPT'))}</td></tr>
          </table>
        </div>
      </div>

      <div class="sec">QUALITÉ</div>
      <div class="grid2">
        <div class="col">
          <table class="fields">
            <tr><td class="attr">Pourriture au stockage (1 mois)</td><td class="val">{conserv}</td></tr>
            <tr><td class="attr" style="padding-top:6px">Couleur de la chair</td><td class="val" style="padding-top:6px">{cell(_v(row,'CCCTCT'))}</td></tr>
            <tr><td class="attr">Oxydation à la cuisson</td><td class="val">{cell(_v(row,'POT'))}</td></tr>
            <tr><td class="attr">Qualité bouillie</td><td class="val">{qbouillie}</td></tr>
          </table>
        </div>
        <div class="col" style="text-align:center">
          <div style="color:#7d2e78; font-style:italic; font-size:9pt; margin-bottom:3px">Sites d'évaluation en Guadeloupe</div>
          {carte_tag if carte_tag else '<div class="expl">Carte indisponible.</div>'}
          <div style="margin-top:5px; font-size:9pt;">
            <span style="color:#c0392b; font-weight:bold;">●</span> Roujol (Petit-Bourg) &nbsp;&nbsp;
            <span style="color:#2e7d32; font-weight:bold;">●</span> Godet (Petit-Canal)
          </div>
        </div>
      </div>
    </div>
    """

    # ---------- PAGE 2 ----------
    p2 = f"""
    <div class="page">
      <div class="sidebar"><span>Plateforme d'Évaluation Variétale d'Ignames</span></div>
      <div class="sec">PERFORMANCES</div>
      <div class="note">NOTE : Toutes les données présentées ci-après ont été obtenues en stations
        expérimentales (Roujol, Godet). Elles traduisent les performances de la variété dans les
        conditions de culture des stations.</div>

      <div class="sub">MALADIES</div>
      <div class="grid2">
        <div class="col box"><b>Anthracnose</b>
          <table class="fields"><tr><td class="attr">Niveau</td><td class="val">{anthra}</td></tr></table></div>
        <div class="col box"><b>Rouille</b>
          <table class="fields"><tr><td class="attr">Niveau</td><td class="val">{rouille}</td></tr></table></div>
      </div>
      <div style="margin-top:6px; font-size:9.5pt;">Attaque fourmi manioc dangereuse pour cette variété ?
        &nbsp; <span style="border:1px solid #333;padding:0 5px">{'X' if afm_oui else '&nbsp;'}</span> Oui
        &nbsp; <span style="border:1px solid #333;padding:0 5px">{'X' if (pd.notna(afm) and not afm_oui) else '&nbsp;'}</span> Non</div>

      <div class="sub">LEVÉE ET RECOUVREMENT</div>
      <div class="grid2">
        <div class="col">
          <div class="box">
            <table class="fields">
              <tr><td class="attr">Taux de germination</td><td class="val">{germ}</td></tr>
              <tr><td class="attr">Durée d'émergence</td><td class="val">{emergence}</td></tr>
              <tr><td class="attr">Durée du cycle</td><td class="val">{cycle_txt}</td></tr>
            </table>
          </div>
        </div>
        <div class="col" style="text-align:center">{_recouv_block(row.get('code_plantation'))}</div>
      </div>

      <div class="sub">RENDEMENT</div>
      <div class="box" style="width:62%">
        <table class="fields">
          <tr><td class="attr">Rendement potentiel</td><td class="val">{cell(_v(row,'rendement_perf',' t/ha'))}</td></tr>
          <tr><td class="attr">Nb moyen de tubercules/plant</td><td class="val">{cell(_v(row,'NTMP_BLUP'))}</td></tr>
          <tr><td class="attr">Profil de régularité</td><td class="val">
            <span style="border:1px solid #333;padding:0 5px">{'X' if stable_oui else '&nbsp;'}</span> Stable
            &nbsp; <span style="border:1px solid #333;padding:0 5px">{'X' if nonstable_oui else '&nbsp;'}</span> Non stable
          </td></tr>
        </table>
      </div>

      <div style="margin-top:8px; text-align:center;">
        {'<img src="'+chart+'" style="width:60%">' if chart else '<div class="expl">Rendement par site indisponible.</div>'}
      </div>

      <div class="sub">CALIBRE</div>
      <div class="grid2">
        <div class="col" style="text-align:center">
          {'<img src="'+calibre_pie+'" style="width:74%">' if calibre_pie else '<div class="expl">Calibre indisponible.</div>'}
        </div>
        <div class="col" style="text-align:center; padding-top:10px">
          <table class="fields" style="margin-bottom:10px">
            <tr><td class="attr">Poids moyen par tubercule</td><td class="val">{poids_moyen}</td></tr>
          </table>
          {('<div style="margin-top:60px"><div style="font-size:8pt;color:'+GREY+';margin-bottom:3px">Fiche en ligne sur YamHub</div>'+qr_tag+'</div>') if qr_tag else ''}
        </div>
      </div>
      {partner_row}
    </div>
    """
    return f"<html><head><meta charset='utf-8'><style>{css}</style></head><body>{p1}{p2}</body></html>"

def generate(row, photos, all_df=None):
    from weasyprint import HTML
    html = build_html(row, photos, all_df)
    return HTML(string=html).write_pdf()
