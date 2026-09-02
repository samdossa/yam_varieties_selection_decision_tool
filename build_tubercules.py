#!/usr/bin/env python3
"""
build_tubercules.py — Complète les photos de tubercules manquantes.

157 variétés ont une photo de tubercule dans YamHub (servie depuis
adminPanel/uploads/ via data/varietes_photos.csv). Les autres n'en ont pas.
Ce script pioche dans le fonds PANDA2 pour combler les trous, et LUI SEUL :
une variété qui a déjà une photo dans YamHub n'est jamais touchée.

Source (3 campagnes, 3 conventions de nommage) :
    2023-2024/CIRAD_107.jpg
    2024-2025/CIRAD239.JPG
    2025-2026/Images_Tubercule_CIRAD_2026/cirad204.JPG

Sortie : data/tubercules/CIRADn.jpg — même logique que data/feuilles/, lue par
fiche_html.py en local et publiée sur yamhub.fr par sync_photos.py.

Choix quand plusieurs fichiers existent pour un code : jamais de HEIC si un JPG
est disponible (HEIC ne s'affiche ni dans les navigateurs ni dans WeasyPrint),
puis la campagne la plus récente, puis le fichier le plus lourd.

Usage :
  python build_tubercules.py --src "/chemin/PANDA2-photo-tubercule"
  python build_tubercules.py --src ... --dry-run
"""
import argparse
import collections
import os
import re
import sys

import pandas as pd
from PIL import Image, ImageOps

Image.MAX_IMAGE_PIXELS = None

ICI = os.path.dirname(os.path.abspath(__file__))
DEF_OUT = os.path.join(ICI, "data", "tubercules")
LARGEUR = 1200          # au-delà, inutile : la fiche l'affiche sur ~200px
QUALITE = 85
ANNEES = {"2025-2026": 3, "2024-2025": 2, "2023-2024": 1}
CODE = re.compile(r"cirad[_\s-]*0*(\d+)", re.I)


def inventaire(src):
    """{code CIRAD: [chemins]} — tolère les trois conventions de nommage."""
    inv = collections.defaultdict(list)
    for root, _, files in os.walk(src):
        for f in files:
            if f.startswith(".") or not f.lower().endswith((".jpg", ".jpeg", ".png", ".heic")):
                continue
            m = CODE.search(os.path.splitext(f)[0])
            if m:
                inv[f"CIRAD{int(m.group(1))}"].append(os.path.join(root, f))
    return inv


def manquantes():
    """Codes CIRAD des variétés sans photo de tubercule dans YamHub."""
    d = pd.read_csv(os.path.join(ICI, "data", "tool_data.csv"))
    p = pd.read_csv(os.path.join(ICI, "data", "varietes_photos.csv"))
    avec = set(p[p["description"].isin(["Tubercule forme", "Tubercule chair"])]
               ["variete_name"].dropna())
    sans = d[~d["nom_accession"].isin(avec)]
    return set(sans["code_plantation"].dropna().astype(str))


def meilleur(chemins, src):
    """Le fichier à retenir : JPG avant HEIC, campagne récente, puis le plus lourd."""
    def cle(p):
        annee = ANNEES.get(os.path.relpath(p, src).split(os.sep)[0], 0)
        return (0 if p.lower().endswith(".heic") else 1, annee, os.path.getsize(p))
    return max(chemins, key=cle)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--src", required=True, help="dossier PANDA2-photo-tubercule")
    ap.add_argument("--out", default=DEF_OUT)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not os.path.isdir(args.src):
        sys.exit(f"Dossier source introuvable : {args.src}")

    inv = inventaire(args.src)
    sans = manquantes()
    a_faire = sorted(set(inv) & sans, key=lambda c: int(c[5:]))

    print(f"{len(inv)} codes photographiés, {len(sans)} variétés sans photo")
    print(f"-> {len(a_faire)} comblables ; "
          f"{len(sans - set(inv))} resteront sans photo ; "
          f"{len(set(inv) - sans)} photos ignorées (variété déjà illustrée)")

    if args.dry_run:
        for c in a_faire[:15]:
            print(f"   {c} <- {os.path.relpath(meilleur(inv[c], args.src), args.src)}")
        if len(a_faire) > 15:
            print(f"   … et {len(a_faire) - 15} autres")
        return

    os.makedirs(args.out, exist_ok=True)
    ecrits = octets = 0
    for c in a_faire:
        source = meilleur(inv[c], args.src)
        try:
            im = ImageOps.exif_transpose(Image.open(source)).convert("RGB")
        except Exception as e:                       # HEIC sans décodeur, fichier corrompu
            print(f"   ÉCHEC {c} ({os.path.basename(source)}) : {e}")
            continue
        if im.width > LARGEUR:
            im = im.resize((LARGEUR, round(im.height * LARGEUR / im.width)))
        dest = os.path.join(args.out, f"{c}.jpg")
        im.save(dest, quality=QUALITE)
        ecrits += 1
        octets += os.path.getsize(dest)

    # Index versionné : les JPEG sont exclus de git, mais l'app doit savoir
    # QUELLES variétés ont une photo pour ne pas pointer vers une URL morte.
    index = os.path.join(ICI, "data", "tubercules_index.txt")
    with open(index, "w") as f:
        f.write("\n".join(sorted(
            (c for c in a_faire
             if os.path.exists(os.path.join(args.out, f"{c}.jpg"))),
            key=lambda c: int(c[5:]))) + "\n")

    print(f"\n{ecrits} photos écrites dans {os.path.relpath(args.out, ICI)} "
          f"({octets/1e6:.1f} Mo)")
    print(f"Index -> data/tubercules_index.txt ({ecrits} codes)")
    print("Publication : python sync_photos.py --only tubercules")


if __name__ == "__main__":
    main()
