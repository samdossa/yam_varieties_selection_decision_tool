"""
build_master.py — Consolidation du jeu de données de recherche DEFI.

Fusionne les fichiers "éparpillés" fournis par l'équipe en UN socle unifié,
clé = Code Plantation (CIRADn) :

  - base de données vitrothèque DEFI 1.xlsx (feuille Panda2) -> identité (référentiel)
  - contitaif.csv   -> traits QUANTITATIFS multi-environnements (Roujol/Godet x années)
  - qualitatif.csv  -> descripteurs QUALITATIFS (morphologie)
  - vision.csv      -> traits issus de l'ANALYSE D'IMAGE
  - traits_descripteursv_final.csv -> dictionnaire des codes de traits

Sorties (data/) :
  - master_varietes.csv        : 1 ligne par accession, toutes les variables
  - dictionnaire_complet.csv   : chaque colonne documentée (libellé, catégorie,
                                 site, année, BLUP, complétude)
  - (rapport de qualité imprimé)
"""

import os
import re
import pandas as pd

SRC = os.path.join(os.path.dirname(__file__), "data", "sources")
OUT = os.path.join(os.path.dirname(__file__), "data")
KEY = "code_plantation"


def load():
    vitro = pd.read_excel(os.path.join(SRC, "base de données vitrothèque DEFI 1.xlsx"),
                          sheet_name="Panda2")
    cont = pd.read_csv(os.path.join(SRC, "contitaif.csv"))
    qual = pd.read_csv(os.path.join(SRC, "qualitatif.csv"))
    vis = pd.read_csv(os.path.join(SRC, "vision.csv"))
    dic = pd.read_csv(os.path.join(SRC, "traits_descripteursv_final.csv"))
    return vitro, cont, qual, vis, dic


# --- Dictionnaire : code de trait -> libellé -------------------------------- #
def build_desc(dic):
    d = {str(r["TRAIT"]).strip(): str(r["DESCRIPTION"]).strip()
         for _, r in dic.iterrows()}
    return d


def label_for(base, desc):
    for cand in (base, base + "_BLUP", re.sub(r"_\d+$", "", base)):
        if cand in desc:
            # pour un libellé "famille", on coupe la modalité "- 1 Lisse"
            return desc[cand].split(" - ")[0]
    return None


def decode_value(col, v, desc):
    """Traduit un code qualitatif en libellé via le dictionnaire (ex: FF=2 -> 'Cordée')."""
    if pd.isna(v):
        return None
    try:
        iv = int(float(v))
    except (ValueError, TypeError):
        return str(v)
    for base in (col, re.sub(r"_\d+$", "", col)):
        key = f"{base}_{iv}"
        if key in desc:
            part = desc[key].split(" - ", 1)
            lab = part[1] if len(part) > 1 else part[0]
            return re.sub(r"^\d+\s*", "", lab).strip()   # retire le "2 " de tête
    return str(iv)   # code brut si modalité inconnue


# --- Analyse d'un nom de colonne quantitatif (site / année / BLUP) ---------- #
def parse_quant(col):
    site = year = None
    blup = "BLUP" in col
    m = re.search(r"\d{2}_\d{2}", col)
    if m:
        year = m.group(0)
    for s in ("ROU", "GOD"):
        if re.search(rf"(^|_){s}(_|$)", col):
            site = s
    base = col
    if year:
        base = base.replace(year, "")
    for s in ("ROU", "GOD"):
        base = re.sub(rf"(^|_){s}(_|$)", "_", base)
    base = base.replace("BLUP", "")
    base = re.sub(r"_+", "_", base).strip("_")
    return base, site, year, blup


def main():
    vitro, cont, qual, vis, dic = load()
    desc = build_desc(dic)

    # Identité depuis la vitrothèque
    idcols = {
        "Code Plantation": KEY, "Code CIRAD": "code_cirad", "Nom": "nom",
        "Espèce": "espece", "Pays origine": "pays_origine",
        "Polyploidie": "polyploidie", "Sexe": "sexe",
        "Date d'obtention/creation": "annee_creation", "Centre d'origine": "centre_origine",
    }
    idcols = {k: v for k, v in idcols.items() if k in vitro.columns}
    ident = vitro[list(idcols)].rename(columns=idcols)
    ident[KEY] = ident[KEY].astype(str).str.strip()
    ident = ident[ident[KEY].str.match(r"^CIRAD\d+$", na=False)].drop_duplicates(KEY)

    # Traits : renommer la clé Taxa -> code_plantation
    for d in (cont, qual, vis):
        d.rename(columns={"Taxa": KEY}, inplace=True)
        d[KEY] = d[KEY].astype(str).str.strip()

    # Index maître = union de toutes les accessions rencontrées
    allkeys = sorted(set(ident[KEY]) | set(cont[KEY]) | set(qual[KEY]) | set(vis[KEY]),
                     key=lambda x: (len(x), x))
    master = pd.DataFrame({KEY: allkeys})
    master = master.merge(ident, on=KEY, how="left")
    master = master.merge(cont, on=KEY, how="left")
    master = master.merge(qual, on=KEY, how="left", suffixes=("", "_qual"))
    master = master.merge(vis, on=KEY, how="left")

    # Décodage des descripteurs qualitatifs : codes -> libellés lisibles
    qual_cols = [c for c in qual.columns if c != KEY]
    for col in qual_cols:
        if col in master.columns:
            master[col] = master[col].map(lambda v: decode_value(col, v, desc))

    master.to_csv(os.path.join(OUT, "master_varietes.csv"), index=False)

    # --- Dictionnaire complet des colonnes du master ----------------------- #
    id_set = set(idcols.values())
    cont_set = set(cont.columns) - {KEY}
    qual_set = set(qual.columns) - {KEY}
    vis_set = set(vis.columns) - {KEY}
    rows = []
    for col in master.columns:
        if col == KEY:
            continue
        if col in id_set:
            cat, base, site, year, blup = "identité", col, None, None, False
            lib = col
        elif col in cont_set:
            cat = "quantitatif (multi-env)"
            base, site, year, blup = parse_quant(col)
            lib = label_for(base, desc) or base
        elif col in qual_set:
            cat, base, site, year, blup = "qualitatif", col, None, None, False
            lib = label_for(col, desc) or col
        elif col in vis_set:
            cat, base, site, year, blup = "analyse d'image", col, None, None, False
            lib = col
        else:
            cat, base, site, year, blup = "?", col, None, None, False
            lib = col
        rows.append({
            "colonne": col, "categorie": cat, "trait_base": base,
            "site": site or "", "annee": year or "", "blup": "oui" if blup else "",
            "libelle": lib,
            "completude": f"{master[col].notna().mean()*100:.0f}%",
        })
    dico = pd.DataFrame(rows)
    dico.to_csv(os.path.join(OUT, "dictionnaire_complet.csv"), index=False)

    # --- Rapport de qualité ------------------------------------------------ #
    n = len(master)
    with_ident = master["nom"].notna().sum() if "nom" in master else 0
    multi_env = dico[dico["site"] != ""]
    sites = sorted(multi_env["site"].unique())
    years = sorted([y for y in dico["annee"].unique() if y])
    undoc = dico[(dico["categorie"].str.startswith("quantitatif")) &
                 (dico["libelle"] == dico["trait_base"])]
    n_ident = int((dico["categorie"] == "identité").sum())
    n_quant = int(dico["categorie"].str.startswith("quantitatif").sum())
    n_qual = int((dico["categorie"] == "qualitatif").sum())
    n_vis = int((dico["categorie"] == "analyse d'image").sum())
    print("=== SOCLE UNIFIÉ ===")
    print(f"Accessions (Code Plantation)      : {n}")
    print(f"  avec identité (vitrothèque)     : {with_ident}")
    print(f"Colonnes de variables            : {len(dico)}")
    print(f"  identité                        : {n_ident}")
    print(f"  quantitatif (multi-env)         : {n_quant}")
    print(f"  qualitatif                      : {n_qual}")
    print(f"  analyse d'image                 : {n_vis}")
    print(f"Sites détectés                   : {sites}")
    print(f"Années détectées                 : {years}")
    print(f"Quantitatifs non documentés (dict): {len(undoc)}")
    print(f"\n-> data/master_varietes.csv  +  data/dictionnaire_complet.csv")


if __name__ == "__main__":
    main()
