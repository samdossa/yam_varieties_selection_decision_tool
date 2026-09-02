#!/usr/bin/env python3
"""
crop_tool.py — Outil de recadrage MANUEL des photos drone de recouvrement.

Pour chaque variété : affiche la photo drone, tu ajustes la boîte de recadrage
(serrée sur le billon central, sans les variétés voisines), tu enregistres.
Le résultat est écrit CIRAD{n}_<stade>.jpg dans le dossier de sortie, prêt pour
la fiche variétale.

"""
import os
import re
import glob
import subprocess
import sys

import streamlit as st
from PIL import Image, ImageOps
from streamlit_cropper import st_cropper

import sync_photos

Image.MAX_IMAGE_PIXELS = None

st.set_page_config(page_title="Recadrage recouvrement", layout="wide")

# Cet outil lit et ecrit des dossiers de TA machine. Sur Streamlit Cloud le
# script tourne dans un conteneur Linux distant : les photos drone n'y sont pas,
# et tout fichier ecrit disparait au redemarrage. Autant le dire franchement
# plutot que d'afficher un selecteur de dossiers qui ne trouvera jamais rien.
SUR_LE_CLOUD = os.path.isdir("/mount/src")
if SUR_LE_CLOUD:
    st.error(
        "**Cet outil doit tourner en local, pas sur Streamlit Cloud.**\n\n"
        "Il recadre des photos qui sont sur ton ordinateur et ecrit le resultat "
        "dans un dossier local. Ici le script s'execute sur un serveur distant : "
        "il n'a acces ni a tes photos, ni a tes dossiers, et ce qu'il ecrirait "
        "serait efface au prochain redemarrage.\n\n"
        "Lance-le depuis ton Mac :\n"
        "```\ncd ~/YamHub/yamhub.fr/decision-tool\nstreamlit run crop_tool.py\n```\n"
        "Tu peux supprimer cette app dans Streamlit Cloud — seule celle qui "
        "pointe sur `app.py` (l'outil d'aide au choix) doit y rester."
    )
    st.stop()

# --- Chemins par défaut (modifiables dans la barre latérale) ---
HOME = os.path.expanduser("~")
# abspath : lancé via « streamlit run crop_tool.py », dirname(__file__) est vide.
# Un chemin relatif casserait la navigation vers le dossier parent.
ICI = os.path.dirname(os.path.abspath(__file__))
DEF_SRC = os.path.join(HOME, "Downloads", "recouvrement_1mois")
OUT_SIZE = 2048
STADES = ["1mois", "3mois"]


def defaut_sortie(stade):
    """Dossier de sortie attendu pour un stade — celui que lit sync_photos.py."""
    return os.path.join(ICI, "data", f"recouvrement_{stade}")


def code_of(fn):
    s = os.path.splitext(fn)[0]
    if s.startswith("CIRAD"):
        return None
    m = re.match(r"^\s*(\d+)", s)
    return f"CIRAD{int(m.group(1))}" if m else None


@st.cache_data(show_spinner="Lecture des photos…")
def scan_sources(src):
    """code CIRAD -> meilleure photo source (vert le plus central)."""
    import numpy as np
    files = glob.glob(os.path.join(src, "**", "*.jpg"), recursive=True) \
        + glob.glob(os.path.join(src, "**", "*.JPG"), recursive=True)
    cand = {}
    for fp in files:
        c = code_of(os.path.basename(fp))
        if not c:
            continue
        try:
            im = Image.open(fp)
            im.draft("RGB", (200, 150))
            a = np.asarray(ImageOps.exif_transpose(im).convert("RGB").resize((200, 150)), float)
            R, G, B = a[..., 0], a[..., 1], a[..., 2]
            mask = (G > R + 8) & (G > B + 6) & (G > 50)
            area = mask.sum()
            dx = 0.0
            if area:
                cols = mask.sum(axis=0).astype(float)
                dx = ((np.arange(200) * cols).sum() / cols.sum() - 100) / 100
            score = area * (1 - 0.5 * abs(dx))
        except Exception:
            score = -1
        if c not in cand or score > cand[c][0]:
            cand[c] = (score, fp)
    return {c: fp for c, (s, fp) in sorted(cand.items(), key=lambda kv: int(kv[0].replace("CIRAD", "")))}


def _dialogue_possible():
    """Un sélecteur de fichiers natif exige un environnement graphique.

    Sur un serveur Linux sans écran — le cas d'un déploiement réseau où chacun
    se connecte par le navigateur — tkinter ne peut pas s'ouvrir. On bascule
    alors sur la navigation par liste, qui, elle, marche à distance.
    """
    if sys.platform == "darwin":
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _dialogue_dossier(titre, depart):
    """Ouvre le sélecteur de dossiers du système (Finder sur macOS).

    Passe par un sous-processus : tkinter exige le thread principal, or
    Streamlit exécute le script dans un thread de travail — l'appeler
    directement fige l'app sur macOS. Renvoie "" si l'utilisateur annule.
    """
    bout = (
        "import tkinter as tk\n"
        "from tkinter import filedialog\n"
        "r = tk.Tk(); r.withdraw(); r.attributes('-topmost', True)\n"
        f"print(filedialog.askdirectory(title={titre!r}, initialdir={depart!r}) or '')\n"
    )
    try:
        res = subprocess.run([sys.executable, "-c", bout],
                             capture_output=True, text=True, timeout=300)
        return res.stdout.strip()
    except Exception:
        return ""


def _navigation_liste(cle, cur):
    """Navigation par liste : remonter d'un cran, ou entrer dans un sous-dossier.

    Les clés des widgets incluent le chemin courant : elles changent à chaque
    déplacement, ce qui réinitialise la liste au lieu de garder l'ancien choix.
    """
    try:
        subs = sorted(d for d in os.listdir(cur)
                      if os.path.isdir(os.path.join(cur, d)) and not d.startswith("."))
    except OSError:
        subs = []

    c1, c2 = st.sidebar.columns([1, 4])
    if c1.button("⬆", key=f"{cle}_up_{cur}", help="Dossier parent"):
        st.session_state[cle] = os.path.dirname(cur.rstrip(os.sep)) or os.sep
        st.rerun()
    sel = c2.selectbox("Sous-dossiers", ["— entrer dans…"] + subs,
                       key=f"{cle}_sub_{cur}", label_visibility="collapsed",
                       disabled=not subs)
    if sel != "— entrer dans…":
        st.session_state[cle] = os.path.join(cur, sel)
        st.rerun()


def dossier_picker(label, cle, defaut):
    """Choix d'un dossier, adapté à l'endroit où l'outil tourne.

    En local : le Finder, qui sait déjà naviguer et créer un dossier.
    Sur un serveur sans écran : navigation par liste, utilisable à distance.
    Dans les deux cas, une saisie manuelle reste disponible en secours.
    """
    st.session_state.setdefault(cle, defaut)
    cur = st.session_state[cle]

    st.sidebar.markdown(f"**{label}**")
    st.sidebar.caption(cur.replace(HOME, "~"))

    if _dialogue_possible():
        if st.sidebar.button("📁 Parcourir…", key=f"{cle}_browse", width="stretch"):
            choisi = _dialogue_dossier(label, cur if os.path.isdir(cur) else HOME)
            if choisi:
                st.session_state[cle] = choisi
                st.rerun()
    else:
        _navigation_liste(cle, cur)

    with st.sidebar.expander("…ou coller un chemin", expanded=False):
        saisi = st.text_input("Chemin", value="", key=f"{cle}_txt_{cur}",
                              placeholder=cur, label_visibility="collapsed")
        if saisi:
            cible = os.path.abspath(os.path.expanduser(saisi.strip()))
            # dossier inexistant accepté si son parent existe : il sera créé.
            if os.path.isdir(cible) or os.path.isdir(os.path.dirname(cible)):
                st.session_state[cle] = cible
                st.rerun()
            else:
                st.warning("Dossier introuvable.")

    return st.session_state[cle]


# ----------------------------- Barre latérale -----------------------------
st.sidebar.header("Réglages")

stage = st.sidebar.radio(
    "Stade", STADES, horizontal=True,
    help="Sert au nom du fichier (CIRADn_<stade>.jpg) et au dossier de "
         "publication sur yamhub.fr.")

# Le dossier de sortie suit le stade tant que tu n'en as pas choisi un toi-même :
# sans ça, passer en 3 mois écrirait dans le dossier des 1 mois sans rien dire.
_prec = st.session_state.get("_stade_precedent")
if _prec != stage:
    if _prec is None or st.session_state.get("out_dir") == defaut_sortie(_prec):
        st.session_state["out_dir"] = defaut_sortie(stage)
    st.session_state["_stade_precedent"] = stage

src = dossier_picker("📂 Photos drone (entrée)", "src_dir", DEF_SRC)
out = dossier_picker("💾 Dossier de sortie", "out_dir", defaut_sortie(stage))

if stage not in os.path.basename(out):
    st.sidebar.caption(f"⚠️ Le dossier de sortie ne mentionne pas « {stage} » — "
                       "vérifie qu'il correspond bien au stade.")
free = st.sidebar.checkbox("Proportions libres", value=False,
                           help="Décoché = format portrait fixe (recommandé pour la fiche).")
aspect = None if free else (3, 4)

# Publication directe sur yamhub.fr : évite d'avoir à relancer sync_photos.py.
_can_publish = sync_photos.credentials_available()
publish = st.sidebar.checkbox(
    "Publier sur yamhub.fr à l'enregistrement", value=_can_publish,
    disabled=not _can_publish,
    help=("Envoie la photo recadrée dans photos/recouvrement/<stade>/ dès "
          "l'enregistrement." if _can_publish else
          "Crée ftp_credentials.txt (modèle : ftp_credentials.txt.example) "
          "pour activer la publication directe."))
if not _can_publish:
    st.sidebar.caption("Publication hors ligne — les photos restent en local. "
                       "`python sync_photos.py` les enverra plus tard.")

if not os.path.isdir(src):
    st.error(f"Dossier introuvable : {src}")
    st.stop()
os.makedirs(out, exist_ok=True)

sources = scan_sources(src)
codes = list(sources.keys())
if not codes:
    st.error("Aucune photo numérotée trouvée dans le dossier source.")
    st.stop()


def is_done(code):
    return os.path.exists(os.path.join(out, f"{code}_{stage}.jpg"))


# Filtre
filt = st.sidebar.radio("Afficher", ["Toutes", "À faire (non enregistrées)", "Déjà faites"])
if filt == "À faire (non enregistrées)":
    view = [c for c in codes if not is_done(c)]
elif filt == "Déjà faites":
    view = [c for c in codes if is_done(c)]
else:
    view = codes
if not view:
    st.success("Rien à afficher dans ce filtre.")
    st.stop()

done = sum(is_done(c) for c in codes)
st.sidebar.progress(done / len(codes), text=f"{done}/{len(codes)} enregistrées")

# Navigation
if "idx" not in st.session_state:
    st.session_state.idx = 0
st.session_state.idx = max(0, min(st.session_state.idx, len(view) - 1))
c1, c2, c3 = st.sidebar.columns(3)
if c1.button("◀ Préc."):
    st.session_state.idx = max(0, st.session_state.idx - 1)
if c3.button("Suiv. ▶"):
    st.session_state.idx = min(len(view) - 1, st.session_state.idx + 1)
sel = st.sidebar.selectbox("Variété", view, index=st.session_state.idx,
                           format_func=lambda c: f"{'✅ ' if is_done(c) else ''}{c}")
st.session_state.idx = view.index(sel)

# ----------------------------- Zone principale -----------------------------
code = view[st.session_state.idx]
st.subheader(f"{code}  —  {st.session_state.idx + 1}/{len(view)}   {'✅ déjà enregistrée' if is_done(code) else ''}")
st.caption("Ajuste la boîte : serrée sur le billon central, sans variété voisine. Puis « Enregistrer ».")

full = ImageOps.exif_transpose(Image.open(sources[code])).convert("RGB")
FILL = (245, 245, 245)

# Curseur de redressement (billon en biais)
rot = st.slider("Redresser l'image (°)", -20.0, 20.0, 0.0, 0.5,
                help="Fais pivoter pour que le billon soit bien vertical, puis recadre.")

# Image d'affichage (petite = rapide), pivotée pour l'aperçu et le recadrage
DISP_W = 900
disp0 = full.resize((DISP_W, round(full.size[1] * DISP_W / full.size[0])))
disp = disp0 if rot == 0 else disp0.rotate(rot, resample=Image.BICUBIC,
                                           expand=True, fillcolor=FILL)

# boîte par défaut : bande centrale étroite
dw, dh = disp.size
bw = int(dw * 0.38)
default = (int((dw - bw) / 2), int((dw + bw) / 2), 0, dh)   # (x1, x2, y1, y2)

colL, colR = st.columns([3, 2])
with colL:
    try:
        box = st_cropper(disp, realtime_update=True, box_color="#00b3ff",
                         aspect_ratio=aspect, return_type="box", default_coords=default,
                         key=f"crop_{code}_{rot}")
    except TypeError:
        box = st_cropper(disp, realtime_update=True, box_color="#00b3ff",
                         aspect_ratio=aspect, return_type="box", key=f"crop_{code}_{rot}")

# Aperçu (sur l'image d'affichage pivotée)
bx, by = int(box["left"]), int(box["top"])
bw2, bh2 = int(box["width"]), int(box["height"])
prev = disp.crop((max(0, bx), max(0, by), bx + bw2, by + bh2))
prev.thumbnail((400, 700))
with colR:
    st.image(prev, caption="Aperçu du recadrage")
    if st.button("💾 Enregistrer", type="primary", width="stretch"):
        # plein résolution : on pivote l'original du même angle, puis on mappe la boîte
        full_r = full if rot == 0 else full.rotate(rot, resample=Image.BICUBIC,
                                                    expand=True, fillcolor=FILL)
        r = full_r.size[0] / disp.size[0]
        x = max(0, int(bx * r)); y = max(0, int(by * r))
        w = max(10, min(int(bw2 * r), full_r.size[0] - x))
        h = max(10, min(int(bh2 * r), full_r.size[1] - y))
        oc = full_r.crop((x, y, x + w, y + h))
        long = max(oc.size)
        if long > OUT_SIZE:
            s = OUT_SIZE / long
            oc = oc.resize((round(oc.size[0] * s), round(oc.size[1] * s)))
        dest = os.path.join(out, f"{code}_{stage}.jpg")
        oc.save(dest, quality=90)
        st.success(f"Enregistré : {code}_{stage}.jpg")
        if publish:
            with st.spinner("Publication sur yamhub.fr…"):
                ok, info = sync_photos.publish_file(dest, stage)
            # Un échec d'envoi ne fait pas perdre le recadrage : le fichier est
            # déjà sur le disque, sync_photos.py le rattrapera.
            st.success(f"En ligne : {info}") if ok else st.warning(
                f"{info}\nLa photo reste en local ; relance `python sync_photos.py`.")
        if st.session_state.idx < len(view) - 1:
            st.session_state.idx += 1
        st.rerun()
