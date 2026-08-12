"""
build_tool_data.py — Jeu de données consommé par l'outil (rebranchement sur le socle).

Fusionne, clé = Code Plantation :
  - master_varietes.csv   : identité + descripteurs qualitatifs DÉCODÉS + quantitatif
  - stabilite.csv         : performance + stabilité (rendement, anthracnose, MS) + profil GxE
  - pont defidb           : nom_accession (pour les photos) + traits culinaires existants
                            (BOILED_Q, FARMER_A) + couleur/forme (les données de recherche
                            n'ont pas de trait culinaire)

Sortie : data/tool_data.csv  (1 ligne par variété, prête pour app.py et fiche_pdf.py)
"""

import os
import pandas as pd

from build_dataset import parse_insert  # réutilise le tokenizer SQL

BASE = os.path.dirname(__file__)
OUT = os.path.join(BASE, "data")
DUMP = os.path.join(BASE, "..", "public_html", "docker", "initdb", "defidb.sql")
KEY = "code_plantation"


def defidb_bridge():
    """Renvoie code_plantation -> nom_accession + traits culinaires/morpho de defidb."""
    sql = open(DUMP, encoding="utf-8", errors="replace").read()
    var = parse_insert(sql, "variete",
                       ["id", "centre_origine", "champ", "code_cirad", "code_origine",
                        "code_plantation_id", "concentration_adn", "datemisajour",
                        "date_creation", "date_diffusion", "doi", "espece_id",
                        "nom_accession", "pays_origine", "polyploidie", "serre"])
    ph = parse_insert(sql, "phenotypage",
                      ["id", "variete_id", "SEX", "FLOWERING", "TDM", "FT", "SEN",
                       "EMERGENCE", "LA", "TN", "TW", "YIELD", "BOILED_Q", "FARMER_A",
                       "ANTHRACNOSE", "RUST", "TUBER_SHAPE", "TUBER_COLOR"])
    b = var[["id", "code_plantation_id", "nom_accession"]].merge(
        ph[["variete_id", "BOILED_Q", "FARMER_A", "TUBER_COLOR", "TUBER_SHAPE"]],
        left_on="id", right_on="variete_id", how="left")
    b = b.rename(columns={"code_plantation_id": KEY})
    b = b[b[KEY].astype(str).str.match(r"^CIRAD\d+$", na=False)]
    return b[[KEY, "nom_accession", "BOILED_Q", "FARMER_A", "TUBER_COLOR", "TUBER_SHAPE"]]


def main():
    master = pd.read_csv(os.path.join(OUT, "master_varietes.csv"))
    stab = pd.read_csv(os.path.join(OUT, "stabilite.csv"))
    bridge = defidb_bridge()

    stab_cols = [KEY, "rendement_perf", "rendement_cv", "rendement_pente_FW",
                 "classe_rendement", "anthracnose_perf", "matiere_seche_perf",
                 "rendement_roujol", "rendement_godet"]
    stab_cols = [c for c in stab_cols if c in stab.columns]

    tool = master.merge(stab[stab_cols], on=KEY, how="left")
    tool = tool.merge(bridge, on=KEY, how="left")

    cal_path = os.path.join(OUT, "calibre.csv")
    if os.path.exists(cal_path):
        tool = tool.merge(pd.read_csv(cal_path), on=KEY, how="left")

    tool.to_csv(os.path.join(OUT, "tool_data.csv"), index=False)
    print(f"OK : tool_data.csv — {len(tool)} variétés, {tool.shape[1]} colonnes")
    print(f"  avec nom_accession (photos) : {tool['nom_accession'].notna().sum()}")
    print(f"  avec rendement (stabilité)  : {tool['rendement_perf'].notna().sum()}")
    print(f"  avec profil GxE             : {tool['classe_rendement'].notna().sum()}")


if __name__ == "__main__":
    main()
