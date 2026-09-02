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
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components

import fiche_html
import i18n
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
def stab_png(lang_code):
    """Graphique de stabilité dans la langue voulue ; repli sur le français si
    la version anglaise n'a pas encore été générée (analyse_stabilite.py)."""
    base = os.path.join(os.path.dirname(__file__), "data", "stabilite_rendement")
    p_en = f"{base}_en.png"
    if lang_code == "en" and os.path.exists(p_en):
        return p_en
    return f"{base}.png"
UPLOADS_URL = "https://yamhub.fr/adminPanel/uploads/"

st.set_page_config(page_title="YamHub — Choix variétal",
                   page_icon="https://yamhub.fr/images/favicon.png", layout="wide")


@st.cache_data
def load():
    d = pd.read_csv(DATA).drop_duplicates("code_plantation").reset_index(drop=True)
    # Position d'origine, conservée à travers les filtres et les reset_index :
    # les rangs des critères sont calculés une fois sur la collection entière.
    d["_idx"] = range(len(d))
    return d


@st.cache_data
def load_photos():
    if os.path.exists(PHOTOS):
        return pd.read_csv(PHOTOS)
    return pd.DataFrame(columns=["variete_name", "description", "photo_bytea"])


df = load()
photos = load_photos()


def lang():
    """Langue courante. Lue dans la session : les fonctions ci-dessous sont
    définies avant que le sélecteur ne soit affiché."""
    return st.session_state.get("lang", i18n.DEFAUT)


@st.cache_data(show_spinner="…")
def make_fiche(code_plantation, lang_code):
    """lang_code fait partie de la signature : sans lui, le cache renverrait la
    fiche française après un passage en anglais."""
    r = df[df["code_plantation"] == code_plantation].iloc[0]
    return fiche_html.generate(r, photos, df, lang=lang_code)


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

# Profil GxE -> couleur du badge ; le libellé, lui, vient de i18n.badge().
# Vert -> rouge selon la variabilité, bleu/violet pour les rendements modérés.
BADGE_COULEUR = {
    "performante & variabilité faible": "#278a3c",
    "performante & variabilité moyenne": "#8bbf3d",
    "performante & variabilité forte": "#e0a200",
    "modeste & variabilité faible": "#6fa8dc",
    "modeste & variabilité moyenne": "#b07aa1",
    "modeste & variabilité forte": "#cc4125",
    "données insuffisantes": "#8a8a8a",
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


@st.cache_data
def _rangs_criteres():
    """Rang centile de chaque variété, pour chaque critère.

    Les étoiles étaient calculées sur l'ÉTENDUE (min-max) : une seule variété à
    62 t/ha écrasait l'échelle, si bien que 4 variétés sur 330 obtenaient trois
    étoiles en récolte et 164 une seule. Sur les rangs, les trois niveaux se
    remplissent par tiers et comparent réellement les variétés entre elles.
    Les ex æquo (ex. les 180 variétés sans pourriture) partagent le même rang :
    c'est voulu, la donnée ne les distingue pas.
    """
    out = {}
    for nom, f in CRIT.items():
        v = df.apply(f, axis=1)
        # method="max" : les ex æquo prennent le rang le PLUS HAUT du groupe.
        # Sans cela, les 173 variétés sans pourriture — le meilleur groupe —
        # se retrouvaient au rang moyen, donc à deux étoiles.
        out[nom] = v.rank(pct=True, method="max")
    return out


def stars(valeur, critere=None, idx=None):
    """Trois niveaux par tiers de rang. Sans rang exploitable, on le dit."""
    if critere is not None and idx is not None:
        r = _rangs_criteres().get(critere)
        p = r.iloc[idx] if r is not None and idx < len(r) else None
        if p is None or pd.isna(p):
            return "☆☆☆"
        n = 1 if p <= 1 / 3 else 2 if p <= 2 / 3 else 3
        return "★" * n + "☆" * (3 - n)
    if valeur is None:
        return "☆☆☆"
    n = max(0, min(3, round(valeur * 3)))
    return "★" * n + "☆" * (3 - n)


def vname(r):
    """Affichage : code CIRAD en premier, nom entre parenthèses. Ex : CIRAD231 (14M)."""
    cp = str(r.get("code_plantation", "")).strip()
    nm = r.get("nom") if pd.notna(r.get("nom")) else r.get("nom_accession")
    if cp and pd.notna(nm) and str(nm).strip():
        return f"{cp} ({nm})"
    return cp or (str(nm) if pd.notna(nm) else "?")


@st.cache_data
def _codes_tubercules():
    """Codes ayant une photo PANDA2 (index versionné, cf. build_tubercules.py).

    Les JPEG sont exclus de git : sans cet index, l'app en ligne pointerait vers
    une URL inexistante pour les variétés dépourvues de photo.
    """
    p = os.path.join(os.path.dirname(__file__), "data", "tubercules_index.txt")
    if not os.path.exists(p):
        return set()
    with open(p) as f:
        return {l.strip() for l in f if l.strip()}


def tuber_photo(code):
    """Photo de tubercule de complément (fonds PANDA2, build_tubercules.py).

    N'existe que pour les variétés absentes de varietes_photos.csv — jamais en
    doublon de YamHub. Le fichier local sert en développement ; en ligne le
    dossier data/tubercules/ est exclu de git, d'où le repli sur TUBER_URL,
    la même variable que celle utilisée par fiche_html.
    Renvoie un chemin local, une URL, ou None.
    """
    if not code or pd.isna(code):
        return None
    p = os.path.join(os.path.dirname(__file__), "data", "tubercules", f"{code}.jpg")
    if os.path.exists(p):
        return p
    url = os.environ.get("TUBER_URL")
    if url and str(code) in _codes_tubercules():
        return f"{url.rstrip('/')}/{str(code).upper()}.jpg"
    return None


def first_photo(row):
    """Vignette d'une variété : YamHub d'abord, fonds PANDA2 en complément."""
    nom = row.get("nom_accession")
    if pd.notna(nom):
        sub = photos[photos["variete_name"] == nom]
        for d in ("Tubercule forme", "Tubercule chair", "Feuille adaxiale"):
            m = sub[sub["description"] == d]
            if len(m):
                return UPLOADS_URL + str(m.iloc[0]["photo_bytea"])
        if len(sub):
            return UPLOADS_URL + str(sub.iloc[0]["photo_bytea"])
    # Pas de photo YamHub : soit une URL directement utilisable, soit un
    # fichier local converti en data-URI (Streamlit ne sert pas le disque).
    p = tuber_photo(row.get("code_plantation"))
    if not p:
        return None
    return p if p.startswith("http") else fiche_html._img_uri(p, 400, "JPEG")


def badge(row):
    """Badge de variabilité, suivi des chiffres qui le justifient.

    Le badge seul induisait en erreur (« régulière » pour une variété allant de
    30 à 82 t/ha) : on affiche donc systématiquement le CV et le nombre
    d'essais, pour que le lecteur puisse juger par lui-même.
    """
    cl = row.get("classe_rendement")
    if pd.isna(cl) or cl not in BADGE_COULEUR:
        return
    lg = lang()
    label, color = i18n.badge(cl, lg), BADGE_COULEUR[cl]
    cv, n = row.get("rendement_cv"), row.get("rendement_n_env")
    detail = ""
    if pd.notna(cv) and pd.notna(n):
        detail = (f" <span style='color:#666;font-size:0.78em'>"
                  f"CV {cv:.0f} % · {int(n)} {i18n.t('essais', lg)}</span>")
    st.markdown(f"<span style='background:{color};color:#fff;padding:2px 8px;"
                f"border-radius:10px;font-size:0.8em'>{label}</span>{detail}",
                unsafe_allow_html=True)


def fiche_btn(code_plantation, label=None):
    lg = lang()
    try:
        st.download_button(label or i18n.t("telecharger_fiche", lg),
                           data=make_fiche(code_plantation, lg),
                           file_name=f"fiche_{code_plantation}_{lg}.pdf",
                           mime="application/pdf", key=f"dl_{code_plantation}")
    except Exception as e:
        st.error(f'{i18n.t("erreur_fiche", lg)} {e}')


# =========================================================================== #
# Langue : bouton visible en haut à droite, mémorisé pour toute la session.
st.session_state.setdefault("lang", i18n.DEFAUT)
_ct, _cl = st.columns([5, 1])
with _cl:
    st.session_state["lang"] = st.segmented_control(
        i18n.t("langue", st.session_state["lang"]),
        list(i18n.LANGUES), format_func=lambda c: i18n.LANGUES[c],
        default=st.session_state["lang"], label_visibility="collapsed") or st.session_state["lang"]
LANG = st.session_state["lang"]

with _ct:
    st.title(i18n.t("titre_app", LANG))
mode_detaille = st.toggle(i18n.t("mode_detaille", LANG), value=False)
st.divider()

# =========================================================================== #
# MODE SIMPLE                                                                  #
# =========================================================================== #
if not mode_detaille:
    st.subheader(i18n.t("etape1", LANG))
    # Les clés restent en français : elles indexent PROFILS et CARTE_CRIT.
    profil = st.radio("profil", list(PROFILS.keys()), horizontal=True,
                      format_func=lambda k: i18n.profil(k, LANG),
                      label_visibility="collapsed")
    weights = PROFILS[profil]

    with st.expander(i18n.t("sites_carte", LANG), expanded=False):
        _sites = pd.DataFrame({"lat": [16.19, 16.36], "lon": [-61.585, -61.44]})
        st.map(_sites, latitude="lat", longitude="lon", size=500, color="#c0392b", zoom=9.3)

    st.subheader(i18n.t("etape2", LANG))
    data = df.copy()
    c1, c2 = st.columns(2)

    if profil == "Producteur":
        with c1:
            rmax = float(df["rendement_perf"].max())
            rmin = st.slider(i18n.t("rendement_min", LANG), 0.0, round(rmax, 0), 0.0, 1.0)
            anthr_only = st.toggle(i18n.t("res_anthracnose", LANG))
            rouille_only = st.toggle(i18n.t("res_rouille", LANG))
            fourmi_only = st.toggle(i18n.t("pas_fourmis", LANG))
        with c2:
            # Clés stables : le test plus bas ne doit pas dépendre de la langue.
            cycle_choix = st.selectbox(
                i18n.t("duree_cycle", LANG),
                ["peu_importe", "cycle_court", "cycle_long", "cycle_tres_long"],
                format_func=lambda k: i18n.t(k, LANG))
            formes = sorted(df["FT"].dropna().unique()) if "FT" in df.columns else []
            f_forme = st.multiselect(i18n.t("forme_tubercule", LANG), formes)
            conserv_only = st.toggle(i18n.t("bonne_conservation", LANG))
        if rmin > 0:
            data = data[data["rendement_perf"].fillna(-1) >= rmin]
        if anthr_only:
            data = data[data["anthracnose_perf"] <= df["anthracnose_perf"].median()]
        if rouille_only and ROU_COL in data.columns:
            data = data[data[ROU_COL] <= df[ROU_COL].median()]
        if fourmi_only:                              # pas d'attaque = AFM absent
            data = data[data["AFM"].isin(["Absent", "Absence"])]
        if cycle_choix != "peu_importe" and "S_BLUP" in data.columns:
            _m = data["S_BLUP"] / 30            # sénescence BLUP -> mois
            if cycle_choix == "cycle_court":
                data = data[_m < 6]
            elif cycle_choix == "cycle_long":
                data = data[(_m >= 6) & (_m <= 9)]
            else:
                data = data[_m > 9]
        if conserv_only:
            data = data[data["PTS1M"] == "Absent"]
        if f_forme:
            data = data[data["FT"].isin(f_forme)]

    elif profil == "Agrotransformateur":
        with c1:
            # None = « peu importe » : une valeur neutre, jamais traduite.
            couleurs = [None] + [c for c in sorted(df["CCCTCT"].dropna().unique())
                                 if not str(c).replace(".", "").isdigit()]
            col = st.selectbox(i18n.t("couleur_chair", LANG), couleurs,
                               format_func=lambda c: i18n.t("peu_importe", LANG)
                               if c is None else i18n.val(c, LANG))
            gout_only = st.toggle(i18n.t("bonne_qualite_bouillie", LANG))
        with c2:
            ms_only = st.toggle(i18n.t("ms_elevee", LANG))
            gros_only = st.toggle(i18n.t("gros_calibre", LANG))
            formes = sorted(df["FT"].dropna().unique()) if "FT" in df.columns else []
            f_forme = st.multiselect(i18n.t("forme_tubercule", LANG), formes, key="forme_agro")
        if col is not None:
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
            rmin = st.slider(i18n.t("rendement_min", LANG), 0.0, round(rmax, 0), 0.0, 1.0)
            resist_only = st.toggle(i18n.t("res_maladies", LANG))
            gout_only = st.toggle(i18n.t("bon_gout", LANG))
        with c2:
            ms_only = st.toggle(i18n.t("ms_elevee", LANG))
            conserv_only = st.toggle(i18n.t("bonne_conservation", LANG))
        st.caption(i18n.t("astuce_detaille", LANG))
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

    st.subheader(i18n.t("etape3", LANG))
    nshow = st.slider(i18n.t("nb_varietes", LANG), 4, 40, 12, 2)
    if not len(data):
        st.info(i18n.t("aucune_variete", LANG))
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
                        ph = first_photo(r)
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
                            st.write(f"{i18n.crit(k, LANG)} : "
                                     f"{stars(None, k, r['_idx'])}")
                        if st.button(i18n.t("voir_fiche", LANG), key=f"f_{i + j}",
                                     width="stretch"):
                            st.session_state["fiche_sel"] = r["code_plantation"]
                        if st.session_state.get("fiche_sel") == r["code_plantation"]:
                            fiche_btn(r["code_plantation"],
                                      i18n.t("telecharger_fiche", LANG))

    st.divider()
    st.caption(i18n.t("legende_etoiles", LANG))

# =========================================================================== #
# MODE DÉTAILLÉ                                                                #
# =========================================================================== #
else:
    # ===================== MODE TECHNICIEN =====================
    # Filtres groupés par thème, nuage interactif (survol + clic), tableau
    # configurable, export CSV et fiche téléchargeable.

    def _plage(col, label, pas=1.0, unite=""):
        """Curseur min/max sur une colonne numérique. None si la colonne manque."""
        if col not in df.columns or df[col].dropna().empty:
            return None
        lo, hi = float(df[col].min()), float(df[col].max())
        if lo == hi:
            return None
        return st.slider(label, lo, hi, (lo, hi), pas)

    with st.sidebar:
        st.header(i18n.t("filtres", LANG))
        recherche = st.text_input(i18n.t("recherche", LANG), "",
                                  placeholder="CIRAD244, NERON…")

        with st.expander(i18n.t("filtres_identite", LANG), expanded=True):
            f_esp = st.multiselect(i18n.t("espece", LANG),
                                   sorted(df["espece"].dropna().unique()))
            f_pays = st.multiselect(
                i18n.t("pays_origine", LANG),
                sorted(df["pays_origine"].dropna().unique())
                if "pays_origine" in df.columns else [])

        with st.expander(i18n.t("filtres_rendement", LANG), expanded=True):
            f_cls = st.multiselect(i18n.t("profil_gxe", LANG),
                                   sorted(df["classe_rendement"].dropna().unique()),
                                   format_func=lambda c: i18n.badge(c, LANG))
            p_rdt = _plage("rendement_perf", i18n.t("rendement_plage", LANG))
            p_cv = _plage("rendement_cv", i18n.t("cv_plage", LANG))
            n_min = 0
            if "rendement_n_env" in df.columns and df["rendement_n_env"].notna().any():
                n_min = st.slider(i18n.t("n_env_min", LANG), 0,
                                  int(df["rendement_n_env"].max()), 0)

        with st.expander(i18n.t("filtres_sanitaire", LANG), expanded=False):
            p_anthr = _plage("anthracnose_perf", i18n.t("anthracnose_max", LANG))
            f_afm = st.multiselect("AFM", sorted(df["AFM"].dropna().unique())
                                   if "AFM" in df.columns else [],
                                   format_func=lambda v: i18n.val(v, LANG))

        with st.expander(i18n.t("filtres_qualite", LANG), expanded=False):
            f_col = st.multiselect(i18n.t("couleur_chair", LANG),
                                   sorted(df["CCCTCT"].dropna().unique()),
                                   format_func=lambda c: i18n.val(c, LANG))
            f_forme = st.multiselect(i18n.t("forme_tubercule", LANG),
                                     sorted(df["FT"].dropna().unique())
                                     if "FT" in df.columns else [],
                                     format_func=lambda c: i18n.val(c, LANG))
            f_tf = st.multiselect(i18n.t("texture_feuille", LANG),
                                  sorted(df["TF"].dropna().unique())
                                  if "TF" in df.columns else [],
                                  format_func=lambda c: i18n.val(c, LANG))
            f_bq = st.multiselect(i18n.t("qualite_bouillie_f", LANG),
                                  [v for v in ["High", "Medium", "Low"]
                                   if "BOILED_Q" in df.columns
                                   and v in set(df["BOILED_Q"].dropna())],
                                  format_func=lambda c: i18n.val(c, LANG))
            p_ms = _plage("TMS_BLUP", i18n.t("ms_min", LANG))

    # ---------------------------- filtrage ----------------------------
    res = df.copy()
    if recherche.strip():
        q = recherche.strip().lower()
        champs = [c for c in ("nom", "nom_accession", "code_plantation", "code_cirad")
                  if c in res.columns]
        masque = False
        for c in champs:
            masque = masque | res[c].astype(str).str.lower().str.contains(q, na=False)
        res = res[masque]
    for col, sel in (("espece", f_esp), ("pays_origine", f_pays),
                     ("classe_rendement", f_cls), ("CCCTCT", f_col),
                     ("FT", f_forme), ("TF", f_tf), ("BOILED_Q", f_bq),
                     ("AFM", f_afm)):
        if sel and col in res.columns:
            res = res[res[col].isin(sel)]
    for col, plage in (("rendement_perf", p_rdt), ("rendement_cv", p_cv),
                       ("anthracnose_perf", p_anthr), ("TMS_BLUP", p_ms)):
        if plage and col in res.columns:
            lo, hi = plage
            res = res[res[col].isna() | res[col].between(lo, hi)]
    if n_min and "rendement_n_env" in res.columns:
        res = res[res["rendement_n_env"].fillna(0) >= n_min]

    st.caption(f"{len(res)} {i18n.t('resultats', LANG)} / {len(df)}")

    # ------------------------- nuage interactif -------------------------
    st.subheader(i18n.t("analyse_stabilite", LANG))
    st.caption(i18n.t("nuage_aide", LANG))
    nuage = res.dropna(subset=["rendement_perf", "rendement_cv"]).copy()
    if len(nuage):
        nuage["variete"] = nuage.apply(vname, axis=1)
        nuage["profil"] = nuage["classe_rendement"].map(
            lambda c: i18n.badge(c, LANG) if pd.notna(c) else "—")
        fig = px.scatter(
            nuage, x="rendement_perf", y="rendement_cv", color="profil",
            custom_data=["code_plantation"],
            color_discrete_map={i18n.badge(k, LANG): v
                                for k, v in BADGE_COULEUR.items()},
            hover_name="variete",
            hover_data={"rendement_perf": ":.1f", "rendement_cv": ":.0f",
                        "rendement_n_env": True, "profil": False},
            labels={"rendement_perf": i18n.t("axe_rendement", LANG),
                    "rendement_cv": i18n.t("axe_cv", LANG),
                    "rendement_n_env": i18n.t("essais_col", LANG),
                    "profil": i18n.t("profil_gxe", LANG)})
        # CV faible en haut : un point haut = une variété plus régulière.
        fig.update_yaxes(autorange="reversed")
        fig.update_traces(marker=dict(size=9, opacity=0.75))
        fig.update_layout(height=520, legend_title_text="",
                          margin=dict(l=10, r=10, t=10, b=10))
        # use_container_width, pas width= : cette version transmet les kwargs
        # inconnus à la config Plotly et affiche un avertissement.
        evt = st.plotly_chart(fig, use_container_width=True, key="nuage",
                              on_select="rerun", selection_mode="points")
        pts = (evt.get("selection", {}) or {}).get("points", []) if evt else []
        if pts:
            # On ne réécrit qu'au changement : sinon le clic reprendrait la main
            # sur le menu déroulant à chaque réexécution.
            choisi = pts[0]["customdata"][0]
            if choisi != st.session_state.get("tech_sel"):
                st.session_state["tech_sel"] = choisi
                st.session_state["_aller_au_detail"] = True
    else:
        st.info(i18n.t("aucune_variete_filtres", LANG))

    # ----------------------------- tableau -----------------------------
    st.subheader(i18n.t("tableau", LANG))
    dispo = [c for c in ["code_plantation", "nom", "nom_accession", "espece",
                         "pays_origine", "rendement_perf", "rendement_cv",
                         "rendement_n_env", "classe_rendement", "anthracnose_perf",
                         "TMS_BLUP", "BOILED_Q", "CCCTCT", "FT", "FF", "TF"]
             if c in res.columns]
    cols_show = st.multiselect(i18n.t("colonnes", LANG), dispo,
                               default=dispo[:10])
    if cols_show:
        st.dataframe(res[cols_show].reset_index(drop=True),
                     width="stretch", height=340)
        st.download_button(i18n.t("exporter_csv", LANG),
                           data=res[cols_show].to_csv(index=False).encode("utf-8"),
                           file_name="varietes_selection.csv", mime="text/csv")

    # ------------------------ détail + fiche ------------------------
    st.divider()
    st.markdown('<div id="detail-variete"></div>', unsafe_allow_html=True)
    st.subheader(i18n.t("detail_variete", LANG))
    if st.session_state.pop("_aller_au_detail", False):
        # Le composant vit dans une iframe : on remonte au document parent pour
        # faire défiler la page jusqu'à l'ancre posée juste au-dessus.
        components.html(
            "<script>const a = window.parent.document.getElementById"
            "('detail-variete'); if (a) a.scrollIntoView({behavior:'smooth',"
            "block:'start'});</script>", height=0)
    if len(res):
        options = res["code_plantation"].tolist()
        prec = st.session_state.get("tech_sel")
        idx = options.index(prec) if prec in options else 0
        choix = st.selectbox(
            i18n.t("choisir_variete", LANG), options, index=idx,
            format_func=lambda cp: vname(res[res["code_plantation"] == cp].iloc[0]))
        st.session_state["tech_sel"] = choix
        row = res[res["code_plantation"] == choix].iloc[0]

        c1, c2 = st.columns([2, 3])
        with c1:
            st.markdown(f"### {vname(row)}")
            st.caption(f"_{row['espece']}_" +
                       (f" · {row['pays_origine']}"
                        if pd.notna(row.get("pays_origine")) else ""))
            badge(row)
        with c2:
            for k in CRIT:
                st.write(f"{i18n.crit(k, LANG)} : {stars(None, k, row['_idx'])}")

        nacc = row.get("nom_accession")
        subph = photos[photos["variete_name"] == nacc] if pd.notna(nacc) else photos.iloc[0:0]
        if len(subph):
            pcols = st.columns(min(4, len(subph)))
            for i, (_, pr) in enumerate(subph.head(4).iterrows()):
                with pcols[i]:
                    st.image(UPLOADS_URL + str(pr["photo_bytea"]),
                             caption=i18n.val(pr["description"], LANG),
                             width="stretch")
        elif tuber_photo(row.get("code_plantation")):
            st.image(tuber_photo(row.get("code_plantation")),
                     caption=i18n.t("tubercule", LANG), width=320)

        fiche_btn(choix, i18n.t("telecharger_fiche_off", LANG))
    else:
        st.info(i18n.t("aucune_variete_filtres", LANG))
