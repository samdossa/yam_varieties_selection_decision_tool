#!/usr/bin/env python3
"""
crop_tool.py — Outil de recadrage MANUEL des photos drone de recouvrement.

Pour chaque variété : affiche la photo drone, tu ajustes la boîte de recadrage
(serrée sur le billon central, sans les variétés voisines), tu enregistres.
Le résultat est écrit CIRAD{n}_<stade>.jpg dans le dossier de sortie, prêt pour
la fiche variétale.

Lancer :
  cd ~/YamHub/yamhub.fr/decision-tool
  streamlit run crop_tool.py

Réglages en haut de la barre latérale : les dossiers d'entrée et de sortie se
choisissent par navigation (remonter, entrer dans un sous-dossier, coller un
chemin), le dossier de sortie pouvant être créé à la volée.
"""
import os
import re
import glob

import streamlit as st
from PIL import Image, ImageOps
from streamlit_cropper import st_cropper

import sync_photos

Image.MAX_IMAGE_PIXELS = None

st.set_page_config(page_title="Recadrage recouvrement", layout="wide")

# --- Chemins par défaut (modifiables dans la barre latérale) ---
HOME = os.path.expanduser("~")
# abspath : lancé via « streamlit run crop_tool.py », dirname(__file__) est vide.
# Un chemin relatif casserait la navigation vers le dossier parent.
ICI = os.path.dirname(os.path.abspath(__file__))
DEF_SRC = os.path.join(HOME, "Downloads", "recouvrement_1mois")
DEF_OUT = os.path.join(ICI, "data", "recouvrement_1mois")
OUT_SIZE = 2048


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


def dossier_picker(label, cle, defaut, creer=False):
    """Sélecteur de dossier navigable dans la barre latérale.

    Trois façons d'arriver au bon dossier, sans jamais taper un chemin complet :
    remonter d'un cran, descendre dans un sous-dossier, ou coller un chemin.
    Les clés des widgets incluent le chemin courant : elles changent à chaque
    navigation, ce qui réinitialise la liste au lieu de garder l'ancien choix.

    creer=True autorise un dossier qui n'existe pas encore (créé à la volée).
    Retourne le chemin retenu.
    """
    st.session_state.setdefault(cle, defaut)
    cur = st.session_state[cle]

    with st.sidebar.expander(label, expanded=False):
        st.caption(cur.replace(HOME, "~"))

        try:
            subs = sorted(d for d in os.listdir(cur)
                          if os.path.isdir(os.path.join(cur, d)) and not d.startswith("."))
        except OSError:
            subs = []

        c1, c2 = st.columns([1, 4])
        if c1.button("⬆", key=f"{cle}_up_{cur}", help="Dossier parent"):
            st.session_state[cle] = os.path.dirname(cur.rstrip(os.sep)) or os.sep
            st.rerun()
        sel = c2.selectbox("Sous-dossiers", ["— entrer dans…"] + subs,
                           key=f"{cle}_sub_{cur}", label_visibility="collapsed",
                           disabled=not subs)
        if sel != "— entrer dans…":
            st.session_state[cle] = os.path.join(cur, sel)
            st.rerun()

        saisi = st.text_input("ou coller un chemin", value="", key=f"{cle}_txt_{cur}",
                              placeholder=cur, label_visibility="collapsed")
        if saisi:
            cible = os.path.abspath(os.path.expanduser(saisi.strip()))
            if os.path.isdir(cible) or (creer and os.path.isdir(os.path.dirname(cible))):
                st.session_state[cle] = cible
                st.rerun()
            else:
                st.warning("Dossier introuvable.")

        if creer:
            nouveau = st.text_input("Créer un sous-dossier ici", value="",
                                    key=f"{cle}_new_{cur}", placeholder="nom du dossier")
            if nouveau:
                cible = os.path.join(cur, nouveau.strip())
                os.makedirs(cible, exist_ok=True)
                st.session_state[cle] = cible
                st.rerun()

    return st.session_state[cle]


# ----------------------------- Barre latérale -----------------------------
st.sidebar.header("Réglages")
src = dossier_picker("📂 Photos drone (entrée)", "src_dir", DEF_SRC)
out = dossier_picker("💾 Dossier de sortie", "out_dir", DEF_OUT, creer=True)
stage = st.sidebar.text_input("Stade", "1mois")

# Le stade sert au nom du fichier ET au dossier distant à la publication ; un
# dossier de sortie d'un autre stade enverrait les photos au mauvais endroit.
if stage and stage not in os.path.basename(out):
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
