"""
build_calibre.py — Calcul du CALIBRE par variété à partir des poids de tubercules.

Lit rendement.xlsx (une ligne = un tubercule pesé, clé = Code CIRAD), agrège tous
les tubercules par variété (tous sites/années confondus) et calcule la répartition
en classes de poids (comme la fiche RITA) + le poids moyen.

Classes : >2kg | 300g-2kg | 80-300g | 0-80g
Sortie   : data/calibre.csv
"""

import os
import re
import pandas as pd

SRC = os.path.join(os.path.dirname(__file__), "data", "sources")
OUT = os.path.join(os.path.dirname(__file__), "data")


def classe(p):
    if p >= 2000:
        return "cal_sup2kg"
    if p >= 300:
        return "cal_300_2000"
    if p >= 80:
        return "cal_80_300"
    return "cal_0_80"


def main():
    xl = pd.ExcelFile(os.path.join(SRC, "rendement.xlsx"))
    frames = []
    for s in xl.sheet_names:
        d = xl.parse(s)
        d.columns = [str(c).strip() for c in d.columns]
        if "Code" in d.columns and "Poids" in d.columns:
            frames.append(d[["Code", "Poids"]])
    allt = pd.concat(frames, ignore_index=True)
    allt["Code"] = allt["Code"].astype(str).str.strip()
    allt["Poids"] = pd.to_numeric(allt["Poids"], errors="coerce")
    allt = allt.dropna(subset=["Poids"])
    allt = allt[allt["Code"].str.match(r"^CIRAD\d+$", na=False)]
    allt["cal"] = allt["Poids"].map(classe)

    rows = []
    for code, g in allt.groupby("Code"):
        vc = g["cal"].value_counts(normalize=True) * 100
        rows.append({
            "code_plantation": code,
            "cal_sup2kg": round(vc.get("cal_sup2kg", 0)),
            "cal_300_2000": round(vc.get("cal_300_2000", 0)),
            "cal_80_300": round(vc.get("cal_80_300", 0)),
            "cal_0_80": round(vc.get("cal_0_80", 0)),
            "poids_moyen_g": round(g["Poids"].mean()),
            "n_tubercules": len(g),
        })
    cal = pd.DataFrame(rows)
    cal.to_csv(os.path.join(OUT, "calibre.csv"), index=False)
    print(f"OK : calibre.csv — {len(cal)} variétés, {allt['Code'].nunique()} codes, "
          f"{len(allt)} tubercules pesés")
    print(cal.head(5).to_string(index=False))


if __name__ == "__main__":
    main()
