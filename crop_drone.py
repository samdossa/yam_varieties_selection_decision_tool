#!/usr/bin/env python3
"""
crop_drone.py — Recadrage uniforme des photos drone de recouvrement (igname).

Chaque photo drone est nommée par son numéro CIRAD (ex. 174, 213(1), 63-).
Le script :
  1. extrait le numéro -> code CIRAD (CIRAD{n}),
  2. si une variété a PLUSIEURS photos, n'en garde qu'UNE (la mieux cadrée),
  3. recadre une BANDE VERTICALE, centrée (ou recentrée sur la plante si elle
     est franchement hors-centre),
  4. redimensionne (côté long = --size),
  5. enregistre en CIRAD{n}_<stade>.jpg  (ex. CIRAD147_1mois.jpg).

Le stade (1mois, 3mois...) est inscrit dans le nom pour distinguer les campagnes.

Usage :
  python crop_drone.py --src "/chemin/recouvrement_1mois" --out SORTIE --stage 1mois
  python crop_drone.py --src "/chemin/recouvrement_3mois" --out SORTIE --stage 3mois

Options :
  --stage      étiquette du stade ajoutée au nom (défaut: 1mois)
  --band       fraction de largeur conservée (défaut 0.50)
  --size       côté long en px (défaut 2048)
  --shift-thr  recentre sur la plante si hors-centre au-delà de ce ratio
               (0 = jamais, toujours centré). Défaut 0.28
  --all        garde TOUTES les photos (sinon: une seule par variété)
"""
import argparse
import os
import re
import glob
import csv
import numpy as np
from PIL import Image, ImageOps

Image.MAX_IMAGE_PIXELS = None


def code_from_filename(fn):
    """'174(1).JPG'->'CIRAD174'; '63-.JPG'->'CIRAD63'; sinon None."""
    stem = os.path.splitext(fn)[0]
    if re.match(r"^CIRAD\d+", stem):        # ignore nos propres sorties
        return None
    m = re.match(r"^\s*(\d+)", stem)
    return f"CIRAD{int(m.group(1))}" if m else None


def quick_metrics(fp):
    """Décodage RAPIDE en basse résolution (JPEG draft) pour mesurer la plante.
    Retourne (fraction de vert, dx normalisé [-1..1])."""
    im = Image.open(fp)
    im.draft("RGB", (300, 225))          # décode ~1/8 : très rapide
    im = ImageOps.exif_transpose(im).convert("RGB").resize((300, 225))
    a = np.asarray(im, float)
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    mask = (G > R + 8) & (G > B + 6) & (G > 50)
    area = mask.sum()
    if area < 200:
        return 0.0, 0.0
    cols = mask.sum(axis=0).astype(float)
    cx = (np.arange(300) * cols).sum() / cols.sum()
    return area / mask.size, (cx - 150) / 150


def crop_band(im, band, cx=None):
    W, H = im.size
    bw = int(W * band)
    center = W // 2 if cx is None else cx
    x0 = max(0, min(center - bw // 2, W - bw))
    return im.crop((x0, 0, x0 + bw, H))


def resize_long(im, size):
    W, H = im.size
    if max(W, H) <= size:
        return im
    if W >= H:
        return im.resize((size, round(H * size / W)))
    return im.resize((round(W * size / H), size))


def main():
    ap = argparse.ArgumentParser(description="Recadrage uniforme des photos drone.")
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--stage", default="1mois", help="étiquette de stade (défaut 1mois)")
    ap.add_argument("--band", type=float, default=0.42)
    ap.add_argument("--size", type=int, default=2048)
    ap.add_argument("--shift-thr", type=float, default=0.0,
                    help="0 = toujours centré (fiable). >0 = tente de recentrer sur "
                         "la plante si hors-centre (peut déraper sur herbes/voisins).")
    ap.add_argument("--all", action="store_true", help="garder toutes les photos (pas 1/variété)")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    files = sorted(
        glob.glob(os.path.join(args.src, "**", "*.jpg"), recursive=True)
        + glob.glob(os.path.join(args.src, "**", "*.JPG"), recursive=True)
    )

    # --- Étape 1 : analyse rapide (basse résolution) ---
    cand = {}   # code -> liste de (score, filepath, dx)
    skipped = 0
    total = len(files)
    print(f"Analyse de {total} photos…")
    for k, fp in enumerate(files, 1):
        code = code_from_filename(os.path.basename(fp))
        if code is None:
            skipped += 1
            continue
        try:
            green, dx = quick_metrics(fp)
            score = green * (1 - 0.5 * abs(dx))   # gros plant ET centré = meilleur
            cand.setdefault(code, []).append((score, fp, dx))
        except Exception:
            skipped += 1
        if k % 40 == 0:
            print(f"  analysé {k}/{total}")

    # --- Étape 2 : recadrage pleine résolution des photos retenues ---
    rows, ok = [], 0
    codes = sorted(cand.items())
    print(f"Recadrage de {len(codes)} variété(s)…")
    for j, (code, lst) in enumerate(codes, 1):
        chosen = lst if args.all else [max(lst, key=lambda t: t[0])]
        for i, (score, fp, dx) in enumerate(chosen):
            name = f"{code}_{args.stage}" + (f"__{i}" if i else "")
            im = ImageOps.exif_transpose(Image.open(fp)).convert("RGB")
            W = im.size[0]
            cx = int((dx * 150 + 150) / 300 * W)
            use_cx = cx if (args.shift_thr > 0 and abs(dx) > args.shift_thr) else None
            out = resize_long(crop_band(im, args.band, use_cx), args.size)
            out.save(os.path.join(args.out, name + ".jpg"), quality=90)
            rows.append([code, os.path.basename(fp), name + ".jpg",
                         "décalé plante" if use_cx is not None else "centré",
                         len(lst)])
            ok += 1
        if j % 40 == 0:
            print(f"  recadré {j}/{len(codes)} variétés")

    with open(os.path.join(args.out, "_correspondance.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["code", "photo_source_retenue", "fichier_sortie", "cadrage", "nb_photos_dispo"])
        w.writerows(rows)

    print(f"Stade : {args.stage}")
    print(f"Variétés traitées : {len(cand)}  |  fichiers écrits : {ok}  |  ignorés : {skipped}")
    print(f"Sortie : {args.out}  (voir _correspondance.csv)")


if __name__ == "__main__":
    main()
