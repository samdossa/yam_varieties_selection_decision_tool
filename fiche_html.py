"""
fiche_html.py — Fiche variétale au format RITA Guadeloupe, rendue en PDF.

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
    pts = []
    cls = row.get("classe_rendement")
    if pd.notna(cls) and "performante" in str(cls):
        pts.append("Rendement")
    if row.get("BOILED_Q") == "High":
        pts.append("Goût")
    if pd.notna(cls) and "stable" in str(cls):
        pts.append("Régularité")
    return pts or ["À confirmer"]


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


def _recouv_tag(code, stage, h=150):
    """Image de recouvrement pour une variété à un stade (1mois, 3mois...).
    Cherche data/recouvrement_<stage>/CIRADn_<stage>.jpg en local, sinon RECOUV_URL."""
    if not code or str(code) in ("nan", ""):
        return ""
    fn = f"{code}_{stage}.jpg"
    local = os.path.join(os.path.dirname(__file__), "data", f"recouvrement_{stage}", fn)
    style = f"height:{h}px;border-radius:5px;box-shadow:0 0 3px #999"
    if os.path.exists(local):
        return f'<img src="file://{local}" style="{style}">'
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
    h = 240 if len(avail) == 1 else 175    # grande si seule, réduite si deux
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
    leaf = _photo_url(photos, acc, "Feuille adaxiale")
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
    pts = row.get("PTS1M")    # pourritures en stockage -> conservation
    conserv = ({"Absent": "Bonne", "Faible": "Moyenne", "Fort": "Faible"}.get(pts, ND)
               if pd.notna(pts) else ND)
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
        carte_src = (f"https://api.mapbox.com/styles/v1/mapbox/outdoors-v12/static/"
                     f"{markers}/auto/900x520?padding=60&access_token={tok}")
    elif os.path.exists(carte_local):
        carte_src = f"file://{carte_local}"
    else:
        carte_src = ""
    carte_tag = (f'<img src="{carte_src}" style="width:74%;border-radius:8px;'
                 f'box-shadow:0 0 4px #999">' if carte_src else "")

    css = f"""
    @page {{ size: A4; margin: 0; }}
    * {{ font-family: 'Helvetica','Arial',sans-serif; box-sizing: border-box; }}
    body {{ margin:0; color:#222; }}
    .page {{ position: relative; width:210mm; height:297mm; page-break-after: always;
             padding: 8mm 8mm 8mm 20mm; }}
    .sidebar {{ position:absolute; left:0; top:0; width:14mm; height:100%; background:{PURPLE}; }}
    .sidebar span {{ position:absolute; transform: rotate(-90deg); transform-origin:left top;
                     left:4mm; bottom:6mm; white-space:nowrap; color:#fff; font-weight:bold;
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
    .miss {{ font-size:8pt; color:{GREY}; border-top:1px dashed #bbb; margin-top:6px; padding-top:3px; }}
    table.cmp {{ width:100%; border-collapse:collapse; font-size:9.5pt; margin-top:4px; }}
    table.cmp th {{ background:{GREEN}; color:#fff; padding:5px 8px; text-align:left; }}
    table.cmp td {{ padding:5px 8px; border-bottom:1px solid #ddd; }}
    """

    # ---------- Débouchés / usages (déduits des traits, indicatifs) ----------
    deb_phrase = _deb.phrase(row)
    deb_items = "".join(f"<li>{u}</li>" for u in _deb.usages(row))

    # ---------- Logo CIRAD (en-tête haut-gauche) ----------
    cirad_path = os.path.join(ASSETS, "cirad_logo.png")
    cirad_tag = (f'<img src="file://{cirad_path}" style="height:40px">'
                 if os.path.exists(cirad_path) else "CIRAD")

    # ---------- PAGE 1 ----------
    p1 = f"""
    <div class="page">
      <div class="sidebar"><span>Plateforme d'Évaluation Variétale : Ignames</span></div>
      <div style="display:flex; justify-content:space-between; align-items:flex-start;">
        <div class="brand">{cirad_tag}</div>
      </div>
      <div class="banner">{cell(titre)}</div>
      <div style="text-align:right; font-size:8pt; color:{GREY}; margin-top:2px;">Édition : 2025</div>

      <div class="sec">CARTE D'IDENTITÉ</div>
      <div class="grid2">
        <div class="col">
          <table class="fields">
            <tr><td class="attr">Espèce</td><td class="val"><i>{cell(_v(row,'espece'))}</i></td></tr>
            <tr><td class="attr">Origine</td><td class="val">{cell(_v(row,'pays_origine'))}</td></tr>
            <tr><td class="attr">Sélectionneur</td><td class="val">Cirad</td></tr>
            <tr><td class="attr">Code CIRAD</td><td class="val">{cell(_v(row,'code_cirad'))}</td></tr>
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
            <tr><td class="attr">Durée du cycle</td><td class="val">{cycle_txt}</td></tr>
            <tr><td class="attr">Récolte</td><td class="val">Sénescence feuillage</td></tr>
            <tr><td class="attr">Conservation</td><td class="val">{conserv}</td></tr>
            <tr><td class="attr" style="padding-top:6px">Couleur de la chair</td><td class="val" style="padding-top:6px">{cell(_v(row,'CCCTCT'))}</td></tr>
            <tr><td class="attr">Oxydation à la cuisson</td><td class="val">{cell(_v(row,'POT'))}</td></tr>
            <tr><td class="attr">Qualité bouillie</td><td class="val">{qbouillie}</td></tr>
          </table>
        </div>
        <div class="col">{'<img class="photo" src="'+flesh+'">' if flesh else ''}</div>
      </div>

      <div class="sec">USAGES / DÉBOUCHÉS</div>
      <div style="font-size:9.5pt; font-style:italic; margin-bottom:3px;">{deb_phrase}</div>
      <ul style="margin:2px 0 0 16px; font-size:9pt;">{deb_items}</ul>
      <div class="expl" style="margin-top:3px; font-size:7.5pt;">Usages indicatifs, déduits
        des caractéristiques mesurées (matière sèche, qualité à la cuisson, calibre).</div>
    </div>
    """

    # ---------- PAGE 2 ----------
    p2 = f"""
    <div class="page">
      <div class="sidebar"><span>Évaluation Variétale GUADELOUPE</span></div>
      <div class="sec">PERFORMANCES</div>
      <div class="note">NOTE : à l'exception du rendement, les données présentées ci-après ont été
        obtenues en stations expérimentales (Roujol, Godet). Elles traduisent les performances
        de la variété dans les conditions de culture des stations.</div>

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
          <tr><td class="attr">Profil de régularité</td><td class="val">{cell(row.get('classe_rendement'))}</td></tr>
          <tr><td class="attr">Note standard de performance</td><td class="val">à définir</td></tr>
        </table>
      </div>

      <div style="margin-top:8px; text-align:center;">
        {'<img src="'+chart+'" style="width:70%">' if chart else '<div class="expl">Rendement par site indisponible.</div>'}
      </div>

      <div class="sub">CALIBRE</div>
      <div class="grid2">
        <div class="col" style="text-align:center">
          {'<img src="'+calibre_pie+'" style="width:82%">' if calibre_pie else '<div class="expl">Calibre indisponible.</div>'}
        </div>
        <div class="col" style="padding-top:20px">
          <table class="fields">
            <tr><td class="attr">Poids moyen par tubercule</td><td class="val">{poids_moyen}</td></tr>
          </table>
        </div>
      </div>
    </div>
    """

    # ---------- PAGE 3 : SYNTHÈSE ----------
    cmp_phrase, cmp_tbl = _comparison(row, all_df)
    p3 = f"""
    <div class="page">
      <div class="sidebar"><span>Évaluation Variétale GUADELOUPE</span></div>

      <div class="sec">COMPARAISON AVEC LES MEILLEURES VARIÉTÉS</div>
      <div style="font-size:10pt; margin-bottom:4px;">{cmp_phrase}</div>
      <div class="expl" style="margin-bottom:4px">« Meilleures » = variétés au rendement
        le plus élevé (◀ = variété de cette fiche, ligne surlignée).</div>
      {cmp_tbl if cmp_tbl else '<div class="expl">Comparaison indisponible.</div>'}

      <div class="sec">SITES D'ÉVALUATION</div>
      <div style="text-align:center; margin-top:6px">
        {carte_tag if carte_tag else '<div class="expl">Carte indisponible.</div>'}
        <div style="margin-top:6px; font-size:9pt;">
          <span style="color:#c0392b; font-weight:bold;">●</span> Roujol (Petit-Bourg) &nbsp;&nbsp;
          <span style="color:#2e7d32; font-weight:bold;">●</span> Godet (Le Moule)
        </div>
      </div>
    </div>
    """
    return f"<html><head><meta charset='utf-8'><style>{css}</style></head><body>{p1}{p2}{p3}</body></html>"

def generate(row, photos, all_df=None):
    from weasyprint import HTML
    html = build_html(row, photos, all_df)
    return HTML(string=html).write_pdf()
