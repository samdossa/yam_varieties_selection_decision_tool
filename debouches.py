"""
debouches.py — Débouchés / usages recommandés par variété d'igname.

Déduit, à partir des traits déjà présents dans le socle de données, ce que l'on peut
faire de chaque variété (pâte alimentaire, chips, farine, consommation fraîche...).

⚠️ Ce sont des recommandations HEURISTIQUES basées sur trois traits mesurés :
  - matière sèche (TMS_BLUP)      → aptitude à la transformation sèche (farine, chips)
  - qualité à la cuisson (BOILED_Q) → aptitude à la consommation bouillie / pâte
  - poids moyen du tubercule       → segment (marché de frais vs transformation)
Les seuils sont regroupés ci-dessous pour être ajustés facilement par l'équipe.
"""

# --- Seuils ajustables ---------------------------------------------------------
MS_ELEVEE = 32.0   # % matière sèche : au-dessus → farine + chips/frites
MS_MOYENNE = 29.0  # % matière sèche : au-dessus → farine / séché
PM_GROS = 1500.0   # g : gros tubercules → transformation / marché
PM_PETIT = 250.0   # g : petits tubercules → semences / consommation ménagère


def _ms_pct(row):
    v = row.get("TMS_BLUP")
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v * 100 if v <= 1 else v  # stocké en fraction (0.30) → 30 %


def _boiled(row):
    v = str(row.get("BOILED_Q", "")).strip().lower()
    return {"high": "High", "medium": "Medium", "low": "Low"}.get(v)


def _poids(row):
    try:
        return float(row.get("poids_moyen_g"))
    except (TypeError, ValueError):
        return None


def usages(row, limit=3):
    """Retourne une liste ordonnée (max `limit`) de débouchés recommandés."""
    ms, bq, pm = _ms_pct(row), _boiled(row), _poids(row)
    out = []

    # Transformation sèche selon la matière sèche
    if ms is not None and ms >= MS_ELEVEE:
        out += ["Farine et produits séchés", "Chips et frites (croustilles)"]
    elif ms is not None and ms >= MS_MOYENNE:
        out += ["Farine et produits séchés"]

    # Consommation cuite selon la qualité à la cuisson
    if bq == "High":
        out += ["Consommation bouillie, purée et igname pilée (pâte)"]
    elif bq == "Medium":
        out += ["Consommation bouillie et cuisine familiale"]

    # Segment de marché selon le calibre
    if pm is not None and pm >= PM_GROS:
        out += ["Transformation et marché de gros"]
    elif pm is not None and pm <= PM_PETIT:
        out += ["Consommation ménagère et semences"]

    # Par défaut : marché de frais
    out += ["Consommation fraîche (marché de frais)"]

    # Dédoublonnage en conservant l'ordre
    seen, ranked = set(), []
    for u in out:
        if u not in seen:
            seen.add(u)
            ranked.append(u)
    return ranked[:limit]


def phrase(row):
    """Petite phrase de synthèse des débouchés (façon fiche variétale)."""
    ms, bq = _ms_pct(row), _boiled(row)
    if ms is None and bq is None:
        return "Débouchés à préciser (données de qualité incomplètes)."
    u = usages(row)
    if len(u) == 1:
        liste = u[0].lower()
    else:
        liste = ", ".join(x.lower() for x in u[:-1]) + " et " + u[-1].lower()
    return f"Variété adaptée à : {liste}."
