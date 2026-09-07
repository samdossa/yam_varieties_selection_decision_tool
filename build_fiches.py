#!/usr/bin/env python3
"""
build_fiches.py — Pré-génère les fiches variétales en PDF.

Les fiches sont normalement produites à la volée par l'app Streamlit. Les
pré-générer permet de les servir en fichiers statiques depuis yamhub.fr :
téléchargement immédiat, lien partageable, et surtout AUCUNE dépendance à
l'app — elles restent disponibles même si celle-ci est arrêtée.

Sortie : data/fiches/<langue>/<code>.pdf
         data/fiches/index.csv   (versionné : dit quelles fiches existent)

Le rendu est identique à celui du bouton de téléchargement de l'app : même
build_html, mêmes données, mêmes photos.

Usage :
  python build_fiches.py                      # variétés avec données, fr + en
  python build_fiches.py --toutes             # les 330, y compris les vides
  python build_fiches.py --langues fr         # une seule langue
  python build_fiches.py --procs 8            # plus de parallélisme
  python build_fiches.py --force              # regénère même l'existant

À publier ensuite : python sync_photos.py --only fiches
"""
import argparse
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import pandas as pd

ICI = os.path.dirname(os.path.abspath(__file__))
DEF_OUT = os.path.join(ICI, "data", "fiches")


def _une_fiche(args):
    """Génère une fiche. Exécuté dans un processus séparé : WeasyPrint est lent
    et mono-thread, le parallélisme divise le temps total d'autant."""
    code, langue, sortie = args
    try:
        import fiche_html
        d = _donnees()
        row = d[0][d[0]["code_plantation"] == code].iloc[0]
        pdf = fiche_html.generate(row, d[1], d[0], lang=langue)
        chemin = os.path.join(sortie, langue, f"{code}.pdf")
        with open(chemin, "wb") as f:
            f.write(pdf)
        return (code, langue, len(pdf), None)
    except Exception as e:
        return (code, langue, 0, str(e)[:120])


_CACHE = None


def _donnees():
    """Jeu de données chargé une fois par processus."""
    global _CACHE
    if _CACHE is None:
        _CACHE = (pd.read_csv(os.path.join(ICI, "data", "tool_data.csv")),
                  pd.read_csv(os.path.join(ICI, "data", "varietes_photos.csv")))
    return _CACHE


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--out", default=DEF_OUT)
    ap.add_argument("--langues", nargs="+", default=["fr", "en"])
    ap.add_argument("--toutes", action="store_true",
                    help="inclure les variétés sans données de rendement")
    ap.add_argument("--procs", type=int, default=max(1, (os.cpu_count() or 4) - 1))
    ap.add_argument("--force", action="store_true",
                    help="regénérer les fiches déjà présentes")
    args = ap.parse_args()

    d, _ = _donnees()
    src = d if args.toutes else d[d["rendement_perf"].notna()]
    # dédoublonné : tool_data peut porter plusieurs lignes pour un même code,
    # qui produiraient le même PDF deux fois.
    codes = sorted(set(src["code_plantation"].dropna().astype(str)),
                   key=lambda c: (len(c), c))

    for lg in args.langues:
        os.makedirs(os.path.join(args.out, lg), exist_ok=True)

    taches = [(c, lg, args.out) for lg in args.langues for c in codes
              if args.force or not os.path.exists(
                  os.path.join(args.out, lg, f"{c}.pdf"))]

    print(f"{len(codes)} variétés x {len(args.langues)} langue(s) "
          f"= {len(codes)*len(args.langues)} fiches")
    print(f"{len(taches)} à générer ({args.procs} processus)")
    if not taches:
        print("Tout est déjà à jour.")
        return

    t0, faits, octets, erreurs = time.time(), 0, 0, []
    with ProcessPoolExecutor(max_workers=args.procs) as ex:
        futures = [ex.submit(_une_fiche, t) for t in taches]
        for fut in as_completed(futures):
            code, lg, n, err = fut.result()
            faits += 1
            if err:
                erreurs.append(f"{code} [{lg}] : {err}")
            else:
                octets += n
            if faits % 25 == 0 or faits == len(taches):
                reste = (time.time() - t0) / faits * (len(taches) - faits)
                print(f"\r  {faits}/{len(taches)}  "
                      f"({octets/1e6:.0f} Mo, ~{reste/60:.0f} min restantes)",
                      end="", flush=True)
    print()

    # Index versionné : les PDF sont volumineux et exclus de git, mais le site
    # doit savoir quelles fiches existent pour n'afficher que les liens valides.
    index = []
    for lg in args.langues:
        dossier = os.path.join(args.out, lg)
        for f in sorted(os.listdir(dossier)):
            if f.endswith(".pdf"):
                index.append({"code": f[:-4], "langue": lg,
                              "octets": os.path.getsize(os.path.join(dossier, f))})
    pd.DataFrame(index).to_csv(os.path.join(args.out, "index.csv"), index=False)

    print(f"\n{faits - len(erreurs)} fiches écrites ({octets/1e6:.0f} Mo) "
          f"en {(time.time()-t0)/60:.1f} min")
    print(f"Index -> {os.path.relpath(args.out, ICI)}/index.csv ({len(index)} entrées)")
    if erreurs:
        print(f"\n{len(erreurs)} échecs :")
        for e in erreurs[:10]:
            print("   ", e)
    print("\nPublication : python sync_photos.py --only fiches")


if __name__ == "__main__":
    main()
