"""
YamHub — Outil d'aide à la décision pour le choix variétal de l'igname.

Rebranché sur le SOCLE UNIFIÉ (data/tool_data.csv) : identité + descripteurs
décodés + performance/stabilité GxE (Roujol/Godet) + traits culinaires.

Deux modes :
- SIMPLE (défaut, agriculteurs) : cartes visuelles, étoiles, badge de stabilité.
- DÉTAILLÉ (techniciens) : filtres, tableau riche, graphique de stabilité.

Lancer :  streamlit run app.py
"""

import os
import pandas as pd
import streamlit as st

import fiche_html
import debouches as _deb


def mapbox_token():
    p = os.path.join(os.path.dirname(__file__), "mapbox_token.txt")
    if os.path.exists(p):
        return open(p).read().strip()
    try:
        if "MAPBOX_TOKEN" in st.secrets:
            return st.secrets["MAPBOX_TOKEN"]
    except Exception:
        pass
    return os.environ.get("MAPBOX_TOKEN", "")


# Propage le token à l'environnement pour que fiche_html (hors Streamlit) le voie
_MB = mapbox_token()
if _MB:
    os.environ["MAPBOX_TOKEN"] = _MB

DATA = os.path.join(os.path.dirname(__file__), "data", "tool_data.csv")
PHOTOS = os.path.join(os.path.dirname(__file__), "data", "varietes_photos.csv")
STAB_PNG = os.path.join(os.path.dirname(__file__), "data", "stabilite_rendement.png")
UPLOADS_URL = "https://yamhub.fr/adminPanel/uploads/"

st.set_page_config(page_title="YamHub — Choix variétal",
                   page_icon="https://yamhub.fr/images/favicon.png", layout="wide")


@st.cache_data
def load():
    return pd.read_csv(DATA).drop_duplicates("code_plantation").reset_index(drop=True)


@st.cache_data
def load_photos():
    if os.path.exists(PHOTOS):
        return pd.read_csv(PHOTOS)
    return pd.DataFrame(columns=["variete_name", "description", "photo_bytea"])


df = load()
photos = load_photos()


@st.cache_data(show_spinner="Génération de la fiche…")
def make_fiche(code_plantation):
    r = df[df["code_plantation"] == code_plantation].iloc[0]
    return fiche_html.generate(r, photos, df)


# --------------------------------------------------------------------------- #
# Critères de décision (normalisés 0..1)                                      #
# --------------------------------------------------------------------------- #
R_RANGE = (df["rendement_perf"].min(), df["rendement_perf"].max())
A_RANGE = (df["anthracnose_perf"].min(), df["anthracnose_perf"].max())
ROU_COL = "R_AUDPC_GOD_25_26"
ROU_RANGE = (df[ROU_COL].min(), df[ROU_COL].max()) if ROU_COL in df.columns else (0, 1)
TMS_RANGE = (df["TMS_BLUP"].min(), df["TMS_BLUP"].max()) if "TMS_BLUP" in df.columns else (0, 1)
ORD = {"Low": 0.0, "Medium": 0.5, "High": 1.0}
CONSERV = {"Absent": 1.0, "Faible": 0.5, "Fort": 0.0}   # PTS1M : pourriture -> conservation


def _mm(v, rng, invert=False):
    if pd.isna(v) or rng[1] == rng[0]:
        return None
    n = (v - rng[0]) / (rng[1] - rng[0])
    return 1 - n if invert else n


def n_recolte(r):
    return _mm(r.get("rendement_perf"), R_RANGE)


def n_resistance(r):                               # anthracnose + rouille (AUDPC bas = résistant)
    parts = [x for x in (_mm(r.get("anthracnose_perf"), A_RANGE, invert=True),
                         _mm(r.get(ROU_COL), ROU_RANGE, invert=True)) if x is not None]
    return sum(parts) / len(parts) if parts else None


def n_gout(r):
    for c in ("BOILED_Q", "FARMER_A"):
        v = r.get(c)
        if pd.notna(v) and v in ORD:
            return ORD[v]
    return None


def n_matiere(r):
    return _mm(r.get("TMS_BLUP"), TMS_RANGE)


def n_conservation(r):
    v = r.get("PTS1M")
    return CONSERV.get(v) if pd.notna(v) else None


CRIT = {"Récolte": n_recolte, "Résistance": n_resistance, "Goût": n_gout,
        "Matière sèche": n_matiere, "Conservation": n_conservation}

# Pondérations du score par profil
PROFILS = {
    "Producteur": {"Récolte": 0.4, "Résistance": 0.4, "Conservation": 0.2},
    "Agrotransformateur": {"Goût": 0.35, "Matière sèche": 0.35, "Récolte": 0.30},
    "Technicien": {"Récolte": 0.25, "Résistance": 0.25, "Goût": 0.20,
                   "Matière sèche": 0.15, "Conservation": 0.15},
}

# Critères affichés en étoiles sur les cartes, selon le profil
CARTE_CRIT = {
    "Producteur": ["Récolte", "Résistance", "Conservation"],
    "Agrotransformateur": ["Goût", "Matière sèche", "Récolte"],
    "Technicien": ["Récolte", "Résistance", "Goût"],
}

# Profil GxE -> libellé court + couleur (badge)
BADGE = {
    "performante & stable": ("Productive et régulière", "#278a3c"),
    "performante & spécialisée": ("Productive mais variable", "#e0a200"),
    "modeste & stable": ("Régulière, rendement modéré", "#6fa8dc"),
    "modeste & spécialisée": ("Rendement modéré et variable", "#cc4125"),
}


def score(r, weights):
    num = den = 0.0
    for k, w in weights.items():
        v = CRIT[k](r)
        if v is None:
            continue
        num += w * v
        den += w
    if den == 0:
        return None, 0.0
    return round(100 * num / den, 1), round(den / sum(weights.values()), 2)


def stars(x):
    if x is None:
        return "☆☆☆ (pas d'info)"
    n = max(0, min(3, round(x * 3)))
    return "★" * n + "☆" * (3 - n)


def vname(r):
    """Affichage : code CIRAD en premier, nom entre parenthèses. Ex : CIRAD231 (14M)."""
    cp = str(r.get("code_plantation", "")).strip()
    nm = r.get("nom") if pd.notna(r.get("nom")) else r.get("nom_accession")
    if cp and pd.notna(nm) and str(nm).strip():
        return f"{cp} ({nm})"
    return cp or (str(nm) if pd.notna(nm) else "?")


def first_photo(nom_accession):
    if pd.isna(nom_accession):
        return None
    sub = photos[photos["variete_name"] == nom_accession]
    for d in ("Tubercule forme", "Tubercule chair", "Feuille adaxiale"):
        m = sub[sub["description"] == d]
        if len(m):
            return UPLOADS_URL + str(m.iloc[0]["photo_bytea"])
    return UPLOADS_URL + str(sub.iloc[0]["photo_bytea"]) if len(sub) else None


def badge(row):
    cl = row.get("classe_rendement")
    if pd.notna(cl) and cl in BADGE:
        label, color = BADGE[cl]
        st.markdown(f"<span style='background:{color};color:#fff;padding:2px 8px;"
                    f"border-radius:10px;font-size:0.8em'>{label}</span>",
                    unsafe_allow_html=True)


def fiche_btn(code_plantation, label="Télécharger la fiche"):
    try:
        st.download_button(label, data=make_fiche(code_plantation),
                           file_name=f"fiche_{code_plantation}.pdf",
                           mime="application/pdf", key=f"dl_{code_plantation}")
    except Exception as e:
        st.error(f"Erreur génération de la fiche : {e}")


# =========================================================================== #
st.title("Quelle variété d'igname choisir ?")
mode_detaille = st.toggle("Mode détaillé (pour techniciens)", value=False)
st.divider()

# =========================================================================== #
# MODE SIMPLE                                                                  #
# =========================================================================== #
if not mode_detaille:
    st.subheader("1. Vous êtes :")
    profil = st.radio("Vous êtes :", list(PROFILS.keys()),
                      horizontal=True, label_visibility="collapsed")
    weights = PROFILS[profil]

    with st.expander("Sites d'évaluation en Guadeloupe (Roujol, Godet)", expanded=False):
        _sites = pd.DataFrame({"lat": [16.19, 16.36], "lon": [-61.585, -61.44]})
        st.map(_sites, latitude="lat", longitude="lon", size=500, color="#c0392b", zoom=9.3)

    st.subheader("2. Ce que vous cherchez (facultatif) :")
    data = df.copy()
    c1, c2 = st.columns(2)

    if profil == "Producteur":
        with c1:
            rmax = float(df["rendement_perf"].max())
            rmin = st.slider("Rendement minimum (t/ha)", 0.0, round(rmax, 0), 0.0, 1.0)
            anthr_only = st.toggle("Résistante à l'anthracnose")
            rouille_only = st.toggle("Résistante à la rouille")
            fourmi_only = st.toggle("Pas d'attaque de fourmis")
        with c2:
            cycle_choix = st.selectbox("Durée du cycle (levée → sénescence)",
                ["Peu importe", "Court (< 6 mois)", "Long (6-9 mois)", "Très long (> 9 mois)"])
            formes = sorted(df["FT"].dropna().unique()) if "FT" in df.columns else []
            f_forme = st.multiselect("Forme du tubercule", formes)
            conserv_only = st.toggle("Bonne conservation")
        if rmin > 0:
            data = data[data["rendement_perf"].fillna(-1) >= rmin]
        if anthr_only:
            data = data[data["anthracnose_perf"] <= df["anthracnose_perf"].median()]
        if rouille_only and ROU_COL in data.columns:
            data = data[data[ROU_COL] <= df[ROU_COL].median()]
        if fourmi_only:                              # pas d'attaque = AFM absent
            data = data[data["AFM"].isin(["Absent", "Absence"])]
        if cycle_choix != "Peu importe" and "S_BLUP" in data.columns:
            _m = data["S_BLUP"] / 30            # sénescence BLUP -> mois
            if cycle_choix.startswith("Court"):
                data = data[_m < 6]
            elif cycle_choix.startswith("Long"):
                data = data[(_m >= 6) & (_m <= 9)]
            else:
                data = data[_m > 9]
        if conserv_only:
            data = data[data["PTS1M"] == "Absent"]
        if f_forme:
            data = data[data["FT"].isin(f_forme)]

    elif profil == "Agrotransformateur":
        with c1:
            couleurs = ["Peu importe"] + [c for c in sorted(df["CCCTCT"].dropna().unique())
                                          if not str(c).replace(".", "").isdigit()]
            col = st.selectbox("Couleur de la chair", couleurs)
            gout_only = st.toggle("Bonne qualité bouillie")
        with c2:
            ms_only = st.toggle("Matière sèche élevée")
            gros_only = st.toggle("Gros calibre (>2 kg fréquent)")
            formes = sorted(df["FT"].dropna().unique()) if "FT" in df.columns else []
            f_forme = st.multiselect("Forme du tubercule", formes, key="forme_agro")
        if col != "Peu importe":
            data = data[data["CCCTCT"] == col]
        if gout_only:
            data = data[data["BOILED_Q"].isin(["High", "Medium"])]
        if ms_only and "TMS_BLUP" in data.columns:
            data = data[data["TMS_BLUP"] >= df["TMS_BLUP"].median()]
        if gros_only and "cal_sup2kg" in data.columns:
            data = data[data["cal_sup2kg"].fillna(0) >= 20]
        if f_forme:
            data = data[data["FT"].isin(f_forme)]

    else:  # Technicien : accès à tous les critères
        with c1:
            rmax = float(df["rendement_perf"].max())
            rmin = st.slider("Rendement minimum (t/ha)", 0.0, round(rmax, 0), 0.0, 1.0)
            resist_only = st.toggle("Résistante aux maladies")
            gout_only = st.toggle("Bon goût")
        with c2:
            ms_only = st.toggle("Matière sèche élevée")
            conserv_only = st.toggle("Bonne conservation")
        st.caption("Pour l'analyse complète (tous les traits, tableau, graphe de "
                   "stabilité), utilise le **mode détaillé** en haut de page.")
        if rmin > 0:
            data = data[data["rendement_perf"].fillna(-1) >= rmin]
        if resist_only:
            data = data[data["anthracnose_perf"] <= df["anthracnose_perf"].median()]
        if gout_only:
            data = data[data["BOILED_Q"].isin(["High", "Medium"])]
        if ms_only and "TMS_BLUP" in data.columns:
            data = data[data["TMS_BLUP"] >= df["TMS_BLUP"].median()]
        if conserv_only:
            data = data[data["PTS1M"] == "Absent"]

    sc = data.apply(lambda r: score(r, weights), axis=1)
    data["_score"] = [s[0] for s in sc]
    data["_cov"] = [s[1] for s in sc]
    data = data[data["_score"].notna() & (data["_cov"] >= 0.5)]
    data = data.sort_values(["_score", "_cov"], ascending=False)

    st.subheader("3. Variétés conseillées pour vous :")
    nshow = st.slider("Nombre de variétés à afficher", 4, 40, 12, 2)
    if not len(data):
        st.info("Aucune variété ne correspond. Essayez d'enlever un filtre.")
    else:
        crit_cartes = CARTE_CRIT[profil]
        top = data.head(nshow).reset_index(drop=True)

        for i in range(0, len(top), 2):
            cols = st.columns(2)
            for j in range(2):
                if i + j >= len(top):
                    break
                r = top.iloc[i + j]
                with cols[j]:
                    with st.container(border=True):
                        ph = first_photo(r.get("nom_accession"))
                        if ph:
                            st.markdown(
                                f'<img src="{ph}" style="width:100%;height:auto;'
                                f'border-radius:6px;display:block">',
                                unsafe_allow_html=True)
                        st.markdown(f"### {vname(r)}")
                        st.caption(f"_{r['espece']}_" +
                                   (f" · {r['pays_origine']}" if pd.notna(r.get("pays_origine")) else ""))
                        badge(r)
                        for k in crit_cartes:
                            st.write(f"{k} : {stars(CRIT[k](r))}")
                        if st.button("Voir la fiche", key=f"f_{i + j}",
                                     width="stretch"):
                            st.session_state["fiche_sel"] = r["code_plantation"]
                        if st.session_state.get("fiche_sel") == r["code_plantation"]:
                            fiche_btn(r["code_plantation"], "Télécharger la fiche")

    st.divider()
    st.caption("★ = plus il y a d'étoiles, mieux c'est. Le badge coloré indique la "
               "régularité de la variété d'un milieu/année à l'autre (analyse Roujol/Godet).")

# =========================================================================== #
# MODE DÉTAILLÉ                                                                #
# =========================================================================== #
else:
    with st.sidebar:
        st.header("Filtres")
        f_esp = st.multiselect("Espèce", sorted(df["espece"].dropna().unique()))
        f_cls = st.multiselect("Profil GxE", sorted(df["classe_rendement"].dropna().unique()))
        f_col = st.multiselect("Couleur de la chair", sorted(df["CCCTCT"].dropna().unique()))

    res = df.copy()
    if f_esp:
        res = res[res["espece"].isin(f_esp)]
    if f_cls:
        res = res[res["classe_rendement"].isin(f_cls)]
    if f_col:
        res = res[res["CCCTCT"].isin(f_col)]

    st.subheader("Analyse de stabilité (rendement, Roujol × Godet × années)")
    if os.path.exists(STAB_PNG):
        st.image(STAB_PNG, width="stretch")

    st.subheader(f"Variétés ({len(res)})")
    cols_show = [c for c in ["nom", "nom_accession", "espece", "rendement_perf",
                             "rendement_cv", "classe_rendement", "anthracnose_perf",
                             "BOILED_Q", "CCCTCT", "FF", "TF"] if c in res.columns]
    st.dataframe(res[cols_show].reset_index(drop=True), width="stretch", height=380)

    st.divider()
    st.subheader("Fiche variétale")
    if len(res):
        options = res["code_plantation"].tolist()
        choix = st.selectbox("Choisir une variété", options,
                             format_func=lambda cp: vname(res[res["code_plantation"] == cp].iloc[0]))
        row = res[res["code_plantation"] == choix].iloc[0]
        nacc = row.get("nom_accession")
        subph = photos[photos["variete_name"] == nacc] if pd.notna(nacc) else photos.iloc[0:0]
        if len(subph):
            pcols = st.columns(min(4, len(subph)))
            for i, (_, pr) in enumerate(subph.head(4).iterrows()):
                with pcols[i]:
                    st.image(UPLOADS_URL + str(pr["photo_bytea"]),
                             caption=pr["description"], width="stretch")
        fiche_btn(choix, "Télécharger la fiche variétale (format officiel)")
    else:
        st.info("Aucune variété ne correspond aux filtres.")
