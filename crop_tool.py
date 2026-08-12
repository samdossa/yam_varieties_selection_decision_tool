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

Réglages en haut de la barre latérale (dossiers source / sortie / stade).
"""
import os
import re
import glob

import streamlit as st
from PIL import Image, ImageOps
from streamlit_cropper import st_cropper

Image.MAX_IMAGE_PIXELS = None

st.set_page_config(page_title="Recadrage recouvrement", layout="wide")

# --- Chemins par défaut (modifiables dans la barre latérale) ---
HOME = os.path.expanduser("~")
DEF_SRC = os.path.join(HOME, "Downloads", "recouvrement_1mois")
DEF_OUT = os.path.join(os.path.dirname(__file__), "data", "recouvrement_1mois")
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


# ----------------------------- Barre latérale -----------------------------
st.sidebar.header("Réglages")
src = st.sidebar.text_input("Dossier des photos drone", DEF_SRC)
out = st.sidebar.text_input("Dossier de sortie", DEF_OUT)
stage = st.sidebar.text_input("Stade", "1mois")
free = st.sidebar.checkbox("Proportions libres", value=False,
                           help="Décoché = format portrait fixe (recommandé pour la fiche).")
aspect = None if free else (3, 4)

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
        oc.save(os.path.join(out, f"{code}_{stage}.jpg"), quality=90)
        st.success(f"Enregistré : {code}_{stage}.jpg")
        if st.session_state.idx < len(view) - 1:
            st.session_state.idx += 1
        st.rerun()
