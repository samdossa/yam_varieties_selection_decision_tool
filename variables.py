"""
Dictionnaire des variables phénotypiques de YamHub — SOURCE UNIQUE de métadonnées.

Ce fichier documente les 16 traits de la table `phenotypage` de la base defidb :
type, libellés, groupe thématique, sens ("plus c'est haut, mieux c'est" ou non),
et pour les variables ordinales/binaires l'ordre des classes -> score.

Il est utilisé à la fois par build_dataset.py (nettoyage/typage) et par app.py
(interface + moteur de recommandation).

NOTE : les unités marquées "?" restent à confirmer avec l'équipe DEFI.
La dimension multi-environnements (Roujol/Godet) n'existe PAS dans la base
actuelle : ces valeurs sont déjà agrégées par variété.
"""

# direction : "max" = valeur élevée souhaitable ; "min" = valeur basse souhaitable ;
#             "neutre" = préférence/filtre, pas de "mieux" intrinsèque.
# type      : "numeric" | "ordinal" | "binary" | "categorical"
# groupe    : Agronomie | Sanitaire | Qualité | Morphologie | Phénologie | Biologie

TRAITS = {
    "YIELD": {
        "label_fr": "Rendement", "label_en": "Yield",
        "groupe": "Agronomie", "type": "numeric", "unite": "t/ha (?)",
        "direction": "max",
    },
    "TW": {
        "label_fr": "Poids des tubercules", "label_en": "Tuber weight",
        "groupe": "Agronomie", "type": "numeric", "unite": "kg (?)",
        "direction": "max",
    },
    "TN": {
        "label_fr": "Nombre de tubercules", "label_en": "Tuber number",
        "groupe": "Agronomie", "type": "numeric", "unite": "nb (?)",
        "direction": "max",
    },
    "TDM": {
        "label_fr": "Matière sèche du tubercule", "label_en": "Tuber dry matter",
        "groupe": "Qualité", "type": "numeric", "unite": "proportion (?)",
        "direction": "max",
    },
    "LA": {
        "label_fr": "Surface foliaire", "label_en": "Leaf area",
        "groupe": "Agronomie", "type": "numeric", "unite": "? ",
        "direction": "neutre",
    },
    "FT": {
        "label_fr": "Date de tubérisation", "label_en": "Tuberisation time",
        "groupe": "Phénologie", "type": "numeric", "unite": "jours (?)",
        "direction": "neutre",
    },
    "SEN": {
        "label_fr": "Sénescence", "label_en": "Senescence",
        "groupe": "Phénologie", "type": "numeric", "unite": "jours (?)",
        "direction": "neutre",
    },
    "EMERGENCE": {
        "label_fr": "Levée", "label_en": "Emergence",
        "groupe": "Phénologie", "type": "numeric", "unite": "jours (?)",
        "direction": "neutre",
    },
    "BOILED_Q": {
        "label_fr": "Qualité culinaire (bouilli)", "label_en": "Boiled quality",
        "groupe": "Qualité", "type": "ordinal", "direction": "max",
        "classes": ["Low", "Medium", "High"],
    },
    "FARMER_A": {
        "label_fr": "Acceptation paysanne", "label_en": "Farmer acceptance",
        "groupe": "Qualité", "type": "ordinal", "direction": "max",
        "classes": ["Low", "Medium", "High"],
    },
    "ANTHRACNOSE": {
        "label_fr": "Résistance à l'anthracnose", "label_en": "Anthracnose resistance",
        "groupe": "Sanitaire", "type": "ordinal", "direction": "max",
        "classes": ["Sensitive", "Moderately sensitive", "Resistant"],
    },
    "RUST": {
        "label_fr": "Résistance à la rouille", "label_en": "Rust resistance",
        "groupe": "Sanitaire", "type": "ordinal", "direction": "max",
        "classes": ["Sensitive", "Moderately sensitive", "Resistant"],
    },
    "TUBER_COLOR": {
        "label_fr": "Couleur de la chair", "label_en": "Tuber flesh color",
        "groupe": "Morphologie", "type": "categorical", "direction": "neutre",
    },
    "TUBER_SHAPE": {
        "label_fr": "Forme du tubercule", "label_en": "Tuber shape",
        "groupe": "Morphologie", "type": "categorical", "direction": "neutre",
    },
    "FLOWERING": {
        "label_fr": "Floraison", "label_en": "Flowering",
        "groupe": "Biologie", "type": "binary", "direction": "neutre",
        "classes": ["no", "yes"],
    },
    "SEX": {
        "label_fr": "Sexe", "label_en": "Sex",
        "groupe": "Biologie", "type": "categorical", "direction": "neutre",
    },
}

# Normalisations de valeurs brutes (casse / synonymes) rencontrées dans la base.
VALUE_FIXES = {
    "SEX": {"f": "F", "m": "M"},
    "FLOWERING": {"oui": "yes", "non": "no", "no": "no", "yes": "yes"},
}

MISSING_TOKENS = {"na", "n/a", "", "nan", "null", "-"}

# Pondérations par profil utilisateur (étape 3 de la fiche de stage).
# Un poids > 0 sur un trait = ce trait compte dans le score de ce profil.
PROFILS = {
    "Producteur": {
        "YIELD": 0.40, "ANTHRACNOSE": 0.25, "RUST": 0.15, "TN": 0.10, "TW": 0.10,
    },
    "Consommateur / Transformateur": {
        "BOILED_Q": 0.45, "FARMER_A": 0.25, "TDM": 0.15, "TUBER_COLOR": 0.15,
    },
    "Technicien": {
        "YIELD": 0.25, "ANTHRACNOSE": 0.20, "RUST": 0.10,
        "BOILED_Q": 0.20, "FARMER_A": 0.10, "TDM": 0.15,
    },
}
