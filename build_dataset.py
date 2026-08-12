"""
build_dataset.py — Étape 2 de la fiche de stage : préparation d'un jeu de données
exploitable pour l'outil d'aide à la décision.

Lit le dump SQL de la base YamHub (defidb), extrait variete + espece + phenotypage,
nettoie et type les valeurs (décimales françaises, valeurs manquantes 'na', casse),
convertit les variables ordinales en scores, puis écrit :

    data/varietes_clean.csv        -> jeu de données propre (une ligne par variété)
    data/dictionnaire_variables.csv -> métadonnées des variables (pour la doc/soutenance)

Usage :
    python build_dataset.py [chemin_du_dump.sql]
Défaut : ../public_html/docker/initdb/defidb.sql
"""

import os
import re
import sys
import csv
import pandas as pd

from variables import TRAITS, VALUE_FIXES, MISSING_TOKENS

DUMP_DEFAULT = os.path.join(
    os.path.dirname(__file__), "..", "public_html", "docker", "initdb", "defidb.sql"
)
OUT_DIR = os.path.join(os.path.dirname(__file__), "data")


# --------------------------------------------------------------------------- #
# 1. Extraction : tokenizer SQL robuste (respecte les quotes et les décimales) #
# --------------------------------------------------------------------------- #
def parse_insert(sql, table, cols):
    m = re.search(
        r"INSERT INTO `%s`[^\n]*VALUES\s*(.+?);\s*(?:\n|$)" % re.escape(table),
        sql, re.S,
    )
    if not m:
        return pd.DataFrame(columns=cols)
    body, rows, cur, field = m.group(1), [], [], ""
    i, n, inq, depth = 0, len(body), False, 0
    while i < n:
        ch = body[i]
        if inq:
            if ch == "\\" and i + 1 < n:
                field += body[i + 1]; i += 2; continue
            if ch == "'":
                inq = False
            else:
                field += ch
            i += 1; continue
        if ch == "'":
            inq = True; i += 1; continue
        if ch == "(" and depth == 0:
            depth, cur, field = 1, [], ""; i += 1; continue
        if ch == "," and depth == 1:
            cur.append(field.strip()); field = ""; i += 1; continue
        if ch == ")" and depth == 1:
            cur.append(field.strip()); rows.append(cur); depth, field = 0, ""; i += 1; continue
        if depth == 1:
            field += ch
        i += 1
    rows = [r for r in rows if len(r) == len(cols)]
    return pd.DataFrame(rows, columns=cols)


# --------------------------------------------------------------------------- #
# 2. Nettoyage / typage                                                       #
# --------------------------------------------------------------------------- #
def is_missing(v):
    return v is None or str(v).strip().lower() in MISSING_TOKENS


def to_float_fr(v):
    """Décimale française '9550,52' -> 9550.52 ; manquant -> None."""
    if is_missing(v):
        return None
    s = str(v).strip().replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def clean_ordinal(v, code):
    """Renvoie (classe_normalisée, score 0..1) pour un trait ordinal/binaire."""
    if is_missing(v):
        return None, None
    s = str(v).strip()
    s = VALUE_FIXES.get(code, {}).get(s.lower(), s)
    classes = TRAITS[code]["classes"]
    # tolérance à la casse
    match = next((c for c in classes if c.lower() == s.lower()), None)
    if match is None:
        return s, None
    idx = classes.index(match)
    score = idx / (len(classes) - 1) if len(classes) > 1 else 1.0
    return match, score


def clean_categorical(v, code):
    if is_missing(v):
        return None
    s = str(v).strip()
    return VALUE_FIXES.get(code, {}).get(s.lower(), s)


def load_from_dump(dump_path):
    """Construit (df joint, photos) à partir d'un dump SQL (hors-ligne)."""
    sql = open(dump_path, encoding="utf-8", errors="replace").read()

    var = parse_insert(sql, "variete",
                       ["id", "centre_origine", "champ", "code_cirad", "code_origine",
                        "code_plantation_id", "concentration_adn", "datemisajour",
                        "date_creation", "date_diffusion", "doi", "espece_id",
                        "nom_accession", "pays_origine", "polyploidie", "serre"])
    esp = parse_insert(sql, "espece", ["id", "nom_espece", "description_espece"])
    pays = parse_insert(sql, "pays_partenaire", ["id", "nom_pays", "latitude", "longitude"])
    pheno_cols = ["id", "variete_id", "SEX", "FLOWERING", "TDM", "FT", "SEN",
                  "EMERGENCE", "LA", "TN", "TW", "YIELD", "BOILED_Q", "FARMER_A",
                  "ANTHRACNOSE", "RUST", "TUBER_SHAPE", "TUBER_COLOR"]
    ph = parse_insert(sql, "phenotypage", pheno_cols)

    # Jointures : phenotypage -> variete -> espece -> pays d'origine
    df = ph.merge(var[["id", "nom_accession", "code_cirad", "espece_id",
                       "pays_origine", "code_plantation_id", "polyploidie",
                       "date_creation", "date_diffusion", "centre_origine"]],
                  left_on="variete_id", right_on="id", suffixes=("", "_var"))
    esp2 = esp.rename(columns={"id": "espece_id"})
    df = df.merge(esp2[["espece_id", "nom_espece"]], on="espece_id", how="left")
    pays2 = pays.rename(columns={"id": "pays_origine"})
    df = df.merge(pays2[["pays_origine", "nom_pays", "latitude", "longitude"]],
                  on="pays_origine", how="left")

    photos = parse_insert(sql, "photosvariete",
                          ["id", "photo_bytea", "description", "variete_name"])
    return df, photos


def load_from_api(url):
    """Construit (df, photos) EN DIRECT depuis l'API JSON YamHub (connecté)."""
    import json
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    data = json.loads(raw)
    df = pd.DataFrame(data.get("varietes", []))
    photos = pd.DataFrame(data.get("photos", []))
    return df, photos


def clean_and_write(df, photos):
    """Nettoie/typologie le df joint (quelle que soit la source) et écrit les sorties."""

    out = pd.DataFrame()
    out["nom_accession"] = df["nom_accession"]
    out["code_cirad"] = df["code_cirad"]
    out["espece"] = df["nom_espece"]
    out["pays_origine"] = df["nom_pays"]
    out["code_plantation_id"] = df["code_plantation_id"].replace("", pd.NA)
    out["polyploidie"] = df["polyploidie"].replace("", pd.NA)
    out["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    out["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    out["annee_creation"] = df["date_creation"].replace("", pd.NA)
    out["annee_diffusion"] = df["date_diffusion"].replace("", pd.NA)

    coverage = {}
    for code, meta in TRAITS.items():
        raw = df[code]
        if meta["type"] == "numeric":
            out[code] = raw.map(to_float_fr)
        elif meta["type"] in ("ordinal", "binary"):
            cls = raw.map(lambda v: clean_ordinal(v, code)[0])
            sc = raw.map(lambda v: clean_ordinal(v, code)[1])
            out[code] = cls
            out[code + "_score"] = sc
        else:  # categorical
            out[code] = raw.map(lambda v: clean_categorical(v, code))
        coverage[code] = out[code].notna().mean()

    os.makedirs(OUT_DIR, exist_ok=True)
    out.to_csv(os.path.join(OUT_DIR, "varietes_clean.csv"), index=False)

    # Photos (déjà chargées selon la source : dump ou API)
    if photos is not None and not photos.empty:
        photos = photos[["variete_name", "description", "photo_bytea"]]
        photos = photos[~photos["photo_bytea"].map(is_missing)]
        photos.to_csv(os.path.join(OUT_DIR, "varietes_photos.csv"), index=False)

    # Dictionnaire de variables (livrable de doc/soutenance)
    with open(os.path.join(OUT_DIR, "dictionnaire_variables.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["code", "libelle_fr", "libelle_en", "groupe", "type",
                    "unite", "sens", "classes", "taux_completude"])
        for code, m in TRAITS.items():
            w.writerow([code, m["label_fr"], m["label_en"], m["groupe"], m["type"],
                        m.get("unite", ""), m["direction"],
                        " < ".join(m.get("classes", [])),
                        f"{coverage[code]*100:.0f}%"])

    print(f"OK : {len(out)} variétés -> data/varietes_clean.csv")
    print("Complétude par trait :")
    for code in TRAITS:
        print(f"  {code:12s} {coverage[code]*100:5.0f}%")


API_DEFAULT = "https://yamhub.fr/api/varietes.php"


def main():
    """
    Sources :
      python build_dataset.py                 -> dump par défaut
      python build_dataset.py chemin.sql      -> dump précisé
      python build_dataset.py --api           -> API YamHub en ligne
      python build_dataset.py --api https://.. -> API précisée
    """
    args = sys.argv[1:]
    if args and args[0] == "--api":
        url = args[1] if len(args) > 1 else API_DEFAULT
        print(f"Source : API {url}")
        df, photos = load_from_api(url)
    else:
        dump = args[0] if args else DUMP_DEFAULT
        print(f"Source : dump {dump}")
        df, photos = load_from_dump(dump)
    clean_and_write(df, photos)


if __name__ == "__main__":
    main()
