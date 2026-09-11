"""
fiche_html.py — Fiche variétale au format  Guadeloupe, rendue en PDF.

Reproduit le modèle officiel (2 pages : DESCRIPTION / QUALITE puis PERFORMANCES)
via HTML+CSS rendu par WeasyPrint. Chaque variété se remplit à partir de tool_data,
le graphe de rendement par site (Roujol/Godet) est généré automatiquement.

Champs indisponibles en base -> "n.d." (et listés dans "Données manquantes").
"""

import base64
import functools
import io
import math
import os

import pandas as pd

import i18n

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


def _v(row, code, suffix="", lang=i18n.DEFAUT):
    """Valeur formatée d'un descripteur, traduite si c'est du texte.

    Les valeurs de la base sont saisies en français (« Granuleux », « Violet
    clair »…) : sans ce passage par i18n.val, la fiche anglaise afficherait des
    libellés anglais avec des valeurs françaises.
    """
    v = row.get(code)
    if pd.isna(v):
        return ND
    if isinstance(v, float):
        return f"{round(v, 1):g}{suffix}"
    return f"{i18n.val(str(v), lang)}{suffix}"


def _photo_url(photos, acc, desc):
    if pd.isna(acc):
        return None
    r = photos[(photos["variete_name"] == acc) & (photos["description"] == desc)]
    return UPLOADS_URL + str(r.iloc[0]["photo_bytea"]) if len(r) else None


def _points_forts(row, lang=i18n.DEFAUT):
    """Points forts déduits des données mesurées (min 2, max 5)."""
    T = lambda k: i18n.t(k, lang)
    pts = []
    cls = str(row.get("classe_rendement")).lower() if pd.notna(row.get("classe_rendement")) else ""
    rp = row.get("rendement_perf")
    if pd.notna(rp) and float(rp) >= 35:
        pts.append(T("pf_rendement_eleve"))
    elif pd.notna(rp) and float(rp) >= 25:
        pts.append(T("pf_bon_rendement"))
    elif "performante" in cls:
        pts.append(T("pf_bon_rendement"))
    if "stable" in cls:
        pts.append(T("pf_rendement_stable"))
    au, rv = row.get("anthracnose_perf"), row.get("R_AUDPC_GOD_25_26")
    res = []
    if pd.notna(au) and float(au) < 35:
        res.append(T("a_anthracnose"))
    if pd.notna(rv) and float(rv) < 35:
        res.append(T("a_rouille"))
    if res:
        pts.append(T("tolerance") + f' {T("et")} '.join(res))
    bq = row.get("BOILED_Q")
    if bq == "High":
        pts.append(T("pf_bonne_cuisson"))
    elif bq == "Medium":
        pts.append(T("pf_cuisson_correcte"))
    pt = row.get("PTS1M")
    if pt == "Absent":
        pts.append(T("pf_pas_pourriture"))
    elif pt == "Faible":
        pts.append(T("pf_faible_pourriture"))
    if row.get("FARMER_A") == "High":
        pts.append(T("pf_appreciee"))
    tms = row.get("TMS_BLUP")
    if pd.notna(tms):
        v = float(tms); v = v * 100 if v <= 1 else v
        if v >= 32:
            pts.append(T("pf_ms_elevee"))
    pm = row.get("poids_moyen_g")
    if pd.notna(pm) and float(pm) >= 1500:
        pts.append(T("pf_gros_tubercules"))
    for extra in [T("pf_adaptee"), T("evaluee_stations")]:
        if len(pts) >= 2:
            break
        pts.append(extra)
    return pts[:4]


def _chart_sites(row, lang=i18n.DEFAUT):
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
    ax.set_title(i18n.t("graph_titre", lang), fontsize=10, color=PURPLE)
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


def _tuber_local(code):
    """Photo de tubercule de complément : data/tubercules/CIRADn.jpg.

    Issue du fonds PANDA2 (build_tubercules.py), elle n'existe QUE pour les
    variétés sans photo dans YamHub : aucun risque de doublon. Même mécanique
    que les feuilles — fichier local, sinon TUBER_URL sur yamhub.fr.
    """
    if not code or str(code) in ("nan", ""):
        return ""
    pth = os.path.join(os.path.dirname(__file__), "data", "tubercules", f"{code}.jpg")
    if os.path.exists(pth):
        return _img_uri(pth, 560, "JPEG")
    url = os.environ.get("TUBER_URL")
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


@functools.lru_cache(maxsize=4096)
def _url_existe(url):
    """La photo distante existe-t-elle ?

    Sans cette verification, toute variete affichait un emplacement « 3 mois »
    des que RECOUV_URL etait defini, photo ou pas : le bloc listait les stades
    configures au lieu des stades disponibles, et la fiche sortait avec une
    image cassee au lieu du message « a venir ».

    En cas de panne reseau on repond True : mieux vaut une image manquante
    qu'une fiche qui nierait des photos bel et bien publiees. Le cache evite
    de redemander le meme fichier a chaque variete d'un lot.
    """
    import urllib.error
    import urllib.request
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=4) as r:
            return r.status < 400
    except urllib.error.HTTPError:
        return False                       # reponse claire du serveur : absente
    except Exception:
        return True                        # panne reseau : on ne conclut pas


def _cases_regularite(niveau, lang=i18n.DEFAUT):
    """Profil de régularité : le seul niveau mesuré, pas la liste des trois.

    Afficher les trois avec une seule cochée obligeait le lecteur à chercher
    la croix. Moins de trois essais : la variabilité n'est pas conclue, et
    cocher quoi que ce soit laisserait croire à une mesure, d'où le message.
    """
    if niveau is None:
        return f'<span style="color:{GREY}">{i18n.t("eval_insuffisante", lang)}</span>'
    return (f'<span style="border:1px solid #333;padding:0 5px">X</span> '
            f'{i18n.t("var_" + niveau, lang)}')


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
    if url and _url_existe(f"{url.rstrip('/')}/{stage}/{fn}"):
        return f'<img src="{url.rstrip("/")}/{stage}/{fn}" style="{style}">'
    return ""


def _recouv_block(code, lang=i18n.DEFAUT):
    """Bloc HTML des photos de recouvrement disponibles (1 mois, 3 mois)."""
    avail = [(s, l) for s, l in [("1mois", i18n.t("mois_1", lang)),
                                 ("3mois", i18n.t("mois_3", lang))]
             if _recouv_tag(code, s)]
    if not avail:
        return f'<div class="expl">{i18n.t("recouvrement_a_venir", lang)}</div>'
    h = 205 if len(avail) == 1 else 150    # grande si seule, réduite si deux
    parts = []
    for stage, label in avail:
        parts.append(
            f'<div style="display:inline-block;text-align:center;margin:0 8px;vertical-align:top">'
            f'<div style="font-size:9pt;color:{GREY};margin-bottom:3px">'
            f'{i18n.t("recouvrement_a", lang)} {label}</div>'
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


def build_html(row, photos, all_df=None, lang=i18n.DEFAUT):
    T = lambda k: i18n.t(k, lang)          # libellé traduit, clé si non traduit
    acc = row.get("nom_accession")
    nom = row.get("nom") if pd.notna(row.get("nom")) else (acc if pd.notna(acc) else row.get("code_plantation"))
    _cp = str(row.get("code_plantation", "")).strip()
    _nm = row.get("nom") if pd.notna(row.get("nom")) else (acc if pd.notna(acc) else "")
    titre = f"{_cp} ({_nm})" if (_cp and str(_nm).strip()) else (_cp or str(nom))
    # Nouvelle feuille (2024/2023) en priorité ; sinon repli sur l'ancienne photo
    leaf = (_leaf_local(row.get("code_plantation"))
            or _photo_url(photos, acc, "Feuille adaxiale")
            or _photo_url(photos, acc, "Feuille abaxiale"))
    tuber = (_photo_url(photos, acc, "Tubercule forme")
             or _tuber_local(row.get("code_plantation")))
    flesh = _photo_url(photos, acc, "Tubercule chair")
    chart = _chart_sites(row, lang)
    calibre_pie = _chart_calibre(row)
    pm = row.get("poids_moyen_g")
    poids_moyen = f"{pm / 1000:.1f} kg" if pd.notna(pm) else ND

    pf = "".join(f"<li>{p}</li>" for p in _points_forts(row, lang))

    # Champs suivis pour la liste "données manquantes"
    suivi = [("Couleur de la chair", "CCCTCT"), ("Texture feuille", "TF"),
             ("Couleur pétiole", "CP"), ("Bulbilles", "APB"),
             ("Épaisseur peau", "EPT"), (i18n.t("rendement_unite", lang), "rendement_perf"),
             ("Nb tubercules/plant", "NTMP_BLUP"), ("Taux de germination", "TG_BLUP"),
             ("Qualité bouillie", "BOILED_Q")]
    manquantes = _missing(row, suivi)
    manq_html = ("".join(f"<li>{m}</li>" for m in manquantes)
                 if manquantes else "<li>aucune donnée clé manquante</li>")

    def cell(v):
        return v if v not in (None, "nan") else ND

    # anthracnose : indice AUDPC -> niveau
    au = row.get("anthracnose_perf")
    anthra = (i18n.val("Sensible" if au >= 50 else
                       "Modérément sensible" if au >= 35 else "Tolérante", lang)
              if pd.notna(au) else ND)
    rv = row.get("R_AUDPC_GOD_25_26")
    rouille = (i18n.val("Sensible" if rv >= 50 else
                        "Modérément sensible" if rv >= 35 else "Tolérante", lang)
               if pd.notna(rv) else ND)
    afm = row.get("AFM")
    afm_oui = pd.notna(afm) and str(afm) not in ("Absent", "Absence")
    pays = row.get("pays_origine")
    pays_html = f" ({pays})" if pd.notna(pays) else ""
    sen = row.get("S_BLUP")   # sénescence (BLUP) -> durée du cycle levée->sénescence
    if pd.notna(sen):
        _m = sen / 30.0
        _c = T("cycle_court_txt") if _m < 6 else T("cycle_long_txt") if _m <= 9 else T("cycle_tres_long_txt")
        cycle_txt = f'{_m:.1f} {T("mois")} - {_c}'
    else:
        cycle_txt = ND
    pts = row.get("PTS1M")    # pourriture tubercule au stockage, test à 1 mois
    # PTS1M mesure la pourriture ; on l'exprime en niveau de conservation.
    conserv = (i18n.val({"Absent": "Absente", "Faible": "Faible",
                         "Fort": "Forte"}.get(pts, ND), lang)
               if pd.notna(pts) else ND)
    # Profil de régularité -> cases de variabilité.
    # Les classes disaient autrefois « stable » / « spécialisée » ; la refonte
    # de la stabilité (CV + pente de Finlay-Wilkinson) les a remplacées par
    # trois niveaux de variabilité. Les anciens tests ne trouvaient donc plus
    # jamais leur mot-clé et AUCUNE case n'était cochée, sur aucune fiche.
    _clr = str(row.get("classe_rendement")).lower() if pd.notna(row.get("classe_rendement")) else ""
    niveau_var = next((n for n in ("faible", "moyenne", "forte")
                       if f"variabilité {n}" in _clr), None)
    bq = row.get("BOILED_Q")  # qualité bouillie -> français
    qbouillie = i18n.val(bq, lang) if pd.notna(bq) else ND
    de = row.get("DE_BLUP")   # durée d'émergence -> jours (arrondi au supérieur)
    emergence = f'{math.ceil(de)} {T("jours")}' if pd.notna(de) else ND
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
      <div class="sidebar"><span>{T("plateforme")}</span></div>
      <div style="display:flex; justify-content:space-between; align-items:flex-start;">
        <div class="brand">{logos_tag}</div>
      </div>
      <div class="banner">{cell(titre)}</div>
      <div style="text-align:right; font-size:8pt; color:{GREY}; margin-top:2px;">{T("edition")}</div>

      <div class="sec">{T("carte_identite")}</div>
      <div class="grid2">
        <div class="col">
          <table class="fields">
            <tr><td class="attr">{T("espece")}</td><td class="val"><i>{cell(_v(row,'espece',lang=lang))}</i></td></tr>
            <tr><td class="attr">{T("origine")}</td><td class="val">{cell(_v(row,'pays_origine',lang=lang))}</td></tr>
            <tr><td class="attr">{T("code_centre")}</td><td class="val">{cell(_panda2(row,'centre_code') or _v(row,'centre_origine',lang=lang))}</td></tr>
            <tr><td class="attr">{T("fournisseur")}</td><td class="val">{cell(_panda2(row,'fournisseur'))}</td></tr>
            <tr><td class="attr">{T("code_cirad")}</td><td class="val">{cell(_v(row,'code_cirad',lang=lang))}</td></tr>
            <tr><td class="attr">DOI</td><td class="val" style="font-size:8.5pt">{cell(_panda2(row,'doi') or _doi_of(row))}</td></tr>
            <tr><td class="attr" style="padding-top:8px">{T("annee_introduction")}</td><td class="val" style="padding-top:8px">{cell(_v(row,'annee_creation',lang=lang))}</td></tr>
            <tr><td class="attr">{T("periode_evaluation")}</td><td class="val">2022-2025</td></tr>
          </table>
        </div>
        <div class="col pf"><b>{T("points_forts")}</b><ul>{pf}</ul></div>
      </div>

      <div class="sec">{T("description")}</div>
      <div class="grid2">
        <div class="col">
          <div class="sub">{T("partie_aerienne")}</div>
          <table class="fields">
            <tr><td class="org">{T("tige")}</td><td class="attr">{T("bulbilles")}</td><td class="val">{cell(_v(row,'APB',lang=lang))}</td></tr>
            <tr><td></td><td class="attr">{T("couleur")}</td><td class="val">{cell(_v(row,'CTP',lang=lang))}</td></tr>
            <tr><td class="org">{T("feuille")}</td><td class="attr">{T("forme")}</td><td class="val">{cell(_v(row,'FF',lang=lang))}</td></tr>
            <tr><td></td><td class="attr">{T("texture")}</td><td class="val">{cell(_v(row,'TF',lang=lang))}</td></tr>
            <tr><td class="org">{T("petiole")}</td><td class="attr">{T("couleur")}</td><td class="val">{cell(_v(row,'CP',lang=lang))}</td></tr>
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
          <div class="sub">{T("partie_souterraine")}</div>
          <table class="fields">
            <tr><td class="org">{T("tubercule")}</td><td class="attr">{T("aspect_chair")}</td><td class="val">{cell(_v(row,'ACT',lang=lang))}</td></tr>
            <tr><td></td><td class="attr">{T("couleur_chair")}</td><td class="val">{cell(_v(row,'CCCTCT',lang=lang))}</td></tr>
            <tr><td></td><td class="attr">{T("racines")}</td><td class="val">{cell(_v(row,'PRT',lang=lang))}</td></tr>
            <tr><td class="org">{T("peau")}</td><td class="attr">{T("epaisseur")}</td><td class="val">{cell(_v(row,'EPT',lang=lang))}</td></tr>
            <tr><td></td><td class="attr">{T("phelloderme")}</td><td class="val">{cell(_v(row,'CPT',lang=lang))}</td></tr>
          </table>
        </div>
      </div>

      <div class="sec">{T("qualite")}</div>
      <div class="grid2">
        <div class="col">
          <table class="fields">
            <tr><td class="attr">{T("pourriture_stockage")}</td><td class="val">{conserv}</td></tr>
            <tr><td class="attr" style="padding-top:6px">{T("couleur_chair_l")}</td><td class="val" style="padding-top:6px">{cell(_v(row,'CCCTCT',lang=lang))}</td></tr>
            <tr><td class="attr">{T("oxydation_cuisson")}</td><td class="val">{cell(_v(row,'POT',lang=lang))}</td></tr>
            <tr><td class="attr">{T("qualite_bouillie")}</td><td class="val">{qbouillie}</td></tr>
          </table>
        </div>
        <div class="col" style="text-align:center">
          <div style="color:#7d2e78; font-style:italic; font-size:9pt; margin-bottom:3px">{T("sites_guadeloupe")}</div>
          {carte_tag if carte_tag else '<div class="expl">{T("carte_indispo")}</div>'}
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
      <div class="sidebar"><span>{T("plateforme")}</span></div>
      <div class="sec">{T("performances")}</div>
      <div class="note">{T("note_stations")}</div>

      <div class="sub">{T("maladies")}</div>
      <div class="grid2">
        <div class="col box"><b>{T("anthracnose")}</b>
          <table class="fields"><tr><td class="attr">{T("niveau")}</td><td class="val">{anthra}</td></tr></table></div>
        <div class="col box"><b>{T("rouille")}</b>
          <table class="fields"><tr><td class="attr">{T("niveau")}</td><td class="val">{rouille}</td></tr></table></div>
      </div>
      <div style="margin-top:6px; font-size:9.5pt;">{T("attaque_fourmi")}
        &nbsp; <span style="border:1px solid #333;padding:0 5px">{'X' if afm_oui else '&nbsp;'}</span> {T("oui")}
        &nbsp; <span style="border:1px solid #333;padding:0 5px">{'X' if (pd.notna(afm) and not afm_oui) else '&nbsp;'}</span> {T("non")}</div>

      <div class="sub">{T("levee_recouvrement")}</div>
      <div class="grid2">
        <div class="col">
          <div class="box">
            <table class="fields">
              <tr><td class="attr">{T("taux_germination")}</td><td class="val">{germ}</td></tr>
              <tr><td class="attr">{T("duree_emergence")}</td><td class="val">{emergence}</td></tr>
              <tr><td class="attr">{T("duree_cycle")}</td><td class="val">{cycle_txt}</td></tr>
            </table>
          </div>
        </div>
        <div class="col" style="text-align:center">{_recouv_block(row.get('code_plantation'), lang)}</div>
      </div>

      <div class="sub">{T("rendement_maj")}</div>
      <div class="box" style="width:62%">
        <table class="fields">
          <tr><td class="attr">{T("rendement_potentiel")}</td><td class="val">{cell(_v(row,'rendement_perf',' t/ha',lang=lang))}</td></tr>
          <tr><td class="attr">{T("nb_tubercules")}</td><td class="val">{cell(_v(row,'NTMP_BLUP',lang=lang))}</td></tr>
          <tr><td class="attr">{T("profil_regularite")}</td><td class="val">
            {_cases_regularite(niveau_var, lang)}
          </td></tr>
        </table>
      </div>

      <div style="margin-top:8px; text-align:center;">
        {'<img src="'+chart+'" style="width:60%">' if chart else '<div class="expl">{T("rendement_site_indispo")}</div>'}
      </div>

      <div class="sub">{T("calibre_maj")}</div>
      <div class="grid2">
        <div class="col" style="text-align:center">
          {'<img src="'+calibre_pie+'" style="width:74%">' if calibre_pie else '<div class="expl">{T("calibre_indispo")}</div>'}
        </div>
        <div class="col" style="text-align:center; padding-top:10px">
          <table class="fields" style="margin-bottom:10px">
            <tr><td class="attr">{T("poids_moyen")}</td><td class="val">{poids_moyen}</td></tr>
          </table>
          {('<div style="margin-top:60px"><div style="font-size:8pt;color:'+GREY+';margin-bottom:3px">'+T("fiche_en_ligne")+'</div>'+qr_tag+'</div>') if qr_tag else ''}
        </div>
      </div>
      {partner_row}
    </div>
    """
    return f"<html><head><meta charset='utf-8'><style>{css}</style></head><body>{p1}{p2}</body></html>"

def generate(row, photos, all_df=None, lang=i18n.DEFAUT):
    from weasyprint import HTML
    html = build_html(row, photos, all_df, lang)
    return HTML(string=html).write_pdf()
