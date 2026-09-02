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
    env_index = sub[rc].mean().values          
    fw = {}
    for _, r in sub.iterrows():
        y = r[rc].values.astype(float)
        m = ~np.isnan(y)
        if m.sum() >= 3:
            fw[r[KEY]] = round(float(np.polyfit(env_index[m], y[m], 1)[0]), 2)
    stab["rendement_pente_FW"] = stab[KEY].map(fw)

    # --- Classement rendement : performance × variabilité ---
    #
    # L'ancienne version comparait le CV a sa mediane et appelait « stable »
    # tout ce qui passait dessous. Trompeur : la mediane du CV vaut 48 % sur
    # cette collection, si bien qu'une variete allant de 30 a 82 t/ha etait
    # etiquetee « reguliere ». Trois corrections :
    #
    #  1. minimum de 3 environnements. Les varietes testees sur 2 essais
    #     affichent un CV median de 17 % — artefact : avec deux points on ne
    #     VOIT pas la variabilite. On ne conclut plus a partir de si peu.
    #  2. le CV seul ne suffit pas. On lui adjoint l'ecart a 1 de la pente de
    #     Finlay-Wilkinson : une pente eloignee de 1 signale une variete qui
    #     reagit de facon atypique au milieu. CIRAD244 (CV 33 %, pente -2,4)
    #     passe ainsi de « reguliere » a « forte variabilite ».
    #  3. vocabulaire comparatif. On classe en variabilite faible/moyenne/forte
    #     PAR RAPPORT A LA COLLECTION, sans jamais affirmer qu'une variete est
    #     « stable » dans l'absolu — aucune ne l'est vraiment ici.
    N_ENV_MIN = 3
    perf = stab["rendement_perf"]
    med_p = perf.median()

    ok = (stab["rendement_n_env"] >= N_ENV_MIN) & stab["rendement_cv"].notna() \
        & stab["rendement_pente_FW"].notna()
    ind = pd.Series(index=stab.index, dtype=float)
    if ok.sum():
        sub = stab[ok]
        r_cv = sub["rendement_cv"].rank(pct=True)
        r_pente = (sub["rendement_pente_FW"] - 1).abs().rank(pct=True)
        ind[ok] = (r_cv + r_pente) / 2
    stab["indice_variabilite"] = ind
    t33, t66 = (ind.quantile([1 / 3, 2 / 3]) if ok.sum() else (0.33, 0.66))

    def classe(row):
        p, i = row["rendement_perf"], row["indice_variabilite"]
        if pd.isna(p) or pd.isna(i):
            return "données insuffisantes"
        haut = "performante" if p >= med_p else "modeste"
        var = "variabilité faible" if i <= t33 else \
              "variabilité moyenne" if i <= t66 else "variabilité forte"
        return f"{haut} & {var}"

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
    print("\nTop 8 'performante & variabilité faible' (rendement élevé, le moins irrégulier) :")
    top = stab[stab["classe_rendement"] == "performante & variabilité faible"] \
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
        # Vert -> rouge : plus la variabilité est forte, plus la couleur alerte.
        colors = {"performante & variabilité faible": "#278a3c",
                  "performante & variabilité moyenne": "#8bbf3d",
                  "performante & variabilité forte": "#e0a200",
                  "modeste & variabilité faible": "#6fa8dc",
                  "modeste & variabilité moyenne": "#b07aa1",
                  "modeste & variabilité forte": "#cc4125"}
        plt.figure(figsize=(8, 6))
        for cl, col in colors.items():
            g = d[d["classe_rendement"] == cl]
            plt.scatter(g["rendement_perf"], g["rendement_cv"], c=col, label=cl, alpha=0.7, s=30)
        plt.axvline(med_p, color="grey", ls="--", lw=0.8)
        plt.axhline(d["rendement_cv"].median(), color="grey", ls="--", lw=0.8)
        plt.gca().invert_yaxis()  # haut = plus stable
        # Un PNG par langue : l'app affiche celui qui correspond au sélecteur.
        import i18n
        for lg, suffixe in (("fr", ""), ("en", "_en")):
            plt.xlabel(i18n.t("stab_x", lg))
            plt.ylabel(i18n.t("stab_y", lg))
            plt.title(i18n.t("stab_titre", lg))
            plt.legend([i18n.badge(cl, lg) for cl in colors], fontsize=8)
            plt.tight_layout()
            plt.savefig(os.path.join(OUT, f"stabilite_rendement{suffixe}.png"), dpi=120)
            print(f"Graphique [{lg}] -> data/stabilite_rendement{suffixe}.png")
    except Exception as e:
        print(f"\n(graphique non généré : {e})")


if __name__ == "__main__":
    main()
