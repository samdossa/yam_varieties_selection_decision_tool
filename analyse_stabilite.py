"""
analyse_stabilite.py — Analyse de stabilité génotype × environnement (GxE).

Objectif secondaire n°1 du stage : identifier les variétés performantes, stables
ou spécialisées, à partir des données multi-environnements (Roujol / Godet, années).

Pour chaque variété et chaque trait clé :
  - performance   : valeur BLUP (estimation génétique inter-env) sinon moyenne
  - stabilité     : coefficient de variation (CV) entre environnements
                    (CV bas = variété régulière ; CV haut = spécialisée/variable)
  - pente Finlay-Wilkinson (rendement) : sensibilité à la qualité du milieu
      b ~ 1 : réactivité moyenne ; b < 1 : régulière/rustique ; b > 1 : exigeante

Classement (rendement) croisant performance × stabilité en 4 profils.

Sortie : data/stabilite.csv (+ graphique si matplotlib dispo)
"""

import os
import re
import numpy as np
import pandas as pd

SRC = os.path.join(os.path.dirname(__file__), "data", "sources")
OUT = os.path.join(os.path.dirname(__file__), "data")
KEY = "code_plantation"


def num(s):
    return pd.to_numeric(s, errors="coerce")


def main():
    cont = pd.read_csv(os.path.join(SRC, "contitaif.csv")).rename(columns={"Taxa": KEY})
    master = pd.read_csv(os.path.join(OUT, "master_varietes.csv"))

    # Traits clés : colonnes par environnement (hors BLUP) + sens + BLUP
    def envcols(pat):
        return [c for c in cont.columns if re.search(pat, c) and "BLUP" not in c]

    # Rendement = RT (t/ha), mesuré par site (Roujol/Godet) ; RE = épluchage (%) écarté.
    TRAITS = {
        "rendement":     {"cols": envcols(r"^RT_.*(ROU|GOD)"),     "dir": "max", "blup": "RT_BLUP"},
        "anthracnose":   {"cols": envcols(r"^A_AUDPC_"),           "dir": "min", "blup": "A_AUDPC_BLUP"},
        "matiere_seche": {"cols": envcols(r"^TMS_\d\d_\d\d$"),     "dir": "max", "blup": "TMS_BLUP"},
    }
    rou_cols = [c for c in TRAITS["rendement"]["cols"] if "ROU" in c]
    god_cols = [c for c in TRAITS["rendement"]["cols"] if "GOD" in c]

    rows = []
    for _, r in cont.iterrows():
        rec = {KEY: r[KEY]}
        for t, cfg in TRAITS.items():
            vals = num(r[cfg["cols"]]).dropna() if cfg["cols"] else pd.Series(dtype=float)
            rec[f"{t}_n_env"] = int(len(vals))
            rec[f"{t}_moy"] = round(vals.mean(), 2) if len(vals) else np.nan
            rec[f"{t}_cv"] = (round(vals.std(ddof=0) / vals.mean() * 100, 1)
                             if len(vals) >= 2 and vals.mean() else np.nan)
            b = cfg.get("blup")
            rec[f"{t}_perf"] = round(num(pd.Series([r[b]]))[0], 2) if b in cont.columns else rec[f"{t}_moy"]
        # Rendement par site (moyenne des parcelles/répétitions du site)
        rec["rendement_roujol"] = round(num(r[rou_cols]).mean(), 2) if rou_cols else np.nan
        rec["rendement_godet"] = round(num(r[god_cols]).mean(), 2) if god_cols else np.nan
        rows.append(rec)
    stab = pd.DataFrame(rows)

    # --- Finlay-Wilkinson sur le rendement (>= 3 environnements) ---
    rc = TRAITS["rendement"]["cols"]
    sub = cont[[KEY] + rc].copy()
    for c in rc:
        sub[c] = num(sub[c])
    env_index = sub[rc].mean().values          # indice environnemental (moy. des génotypes)
    fw = {}
    for _, r in sub.iterrows():
        y = r[rc].values.astype(float)
        m = ~np.isnan(y)
        if m.sum() >= 3:
            fw[r[KEY]] = round(float(np.polyfit(env_index[m], y[m], 1)[0]), 2)
    stab["rendement_pente_FW"] = stab[KEY].map(fw)

    # --- Classement rendement : performance × stabilité ---
    perf = stab["rendement_perf"]
    cv = stab["rendement_cv"]
    med_p, med_cv = perf.median(), cv.median()

    def classe(row):
        p, c = row["rendement_perf"], row["rendement_cv"]
        if pd.isna(p) or pd.isna(c):
            return "données insuffisantes"
        haut = "performante" if p >= med_p else "modeste"
        reg = "stable" if c <= med_cv else "spécialisée"
        return f"{haut} & {reg}"

    stab["classe_rendement"] = stab.apply(classe, axis=1)

    # Identité pour lecture humaine
    ident = master[[c for c in [KEY, "nom", "espece"] if c in master.columns]]
    stab = ident.merge(stab, on=KEY, how="right")
    stab.to_csv(os.path.join(OUT, "stabilite.csv"), index=False)

    # --- Rapport ---
    print("=== ANALYSE DE STABILITÉ (GxE) ===")
    print(f"Variétés analysées : {len(stab)}")
    print(f"Rendement : {stab['rendement_n_env'].gt(0).sum()} variétés avec données, "
          f"{stab['rendement_cv'].notna().sum()} avec >=2 environnements (stabilité calculable)")
    print(f"Pente Finlay-Wilkinson calculée (>=3 env) : {stab['rendement_pente_FW'].notna().sum()} variétés")
    print("\nRépartition des profils (rendement) :")
    print(stab["classe_rendement"].value_counts().to_string())
    print("\nTop 8 'performante & stable' (rendement élevé + régulier) :")
    top = stab[stab["classe_rendement"] == "performante & stable"] \
        .sort_values("rendement_perf", ascending=False)
    cols = [c for c in ["nom", "espece", "rendement_perf", "rendement_cv",
                        "rendement_n_env", "rendement_pente_FW"] if c in top.columns]
    print(top[cols].head(8).to_string(index=False))

    # --- Graphique performance vs stabilité (optionnel) ---
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        d = stab.dropna(subset=["rendement_perf", "rendement_cv"])
        colors = {"performante & stable": "#278a3c", "performante & spécialisée": "#e0a200",
                  "modeste & stable": "#6fa8dc", "modeste & spécialisée": "#cc4125"}
        plt.figure(figsize=(8, 6))
        for cl, col in colors.items():
            g = d[d["classe_rendement"] == cl]
            plt.scatter(g["rendement_perf"], g["rendement_cv"], c=col, label=cl, alpha=0.7, s=30)
        plt.axvline(med_p, color="grey", ls="--", lw=0.8)
        plt.axhline(med_cv, color="grey", ls="--", lw=0.8)
        plt.xlabel("Rendement (t/ha, BLUP)")
        plt.ylabel("Instabilité — CV entre environnements (%)")
        plt.title("Rendement : performance vs stabilité des variétés d'igname")
        plt.legend(fontsize=8)
        plt.gca().invert_yaxis()  # haut = plus stable
        plt.tight_layout()
        plt.savefig(os.path.join(OUT, "stabilite_rendement.png"), dpi=120)
        print("\nGraphique -> data/stabilite_rendement.png")
    except Exception as e:
        print(f"\n(graphique non généré : {e})")


if __name__ == "__main__":
    main()
