# YamHub — Outil d'aide à la décision (prototype)

Prototype de l'outil d'aide au choix variétal de l'igname, à partir des données
phénotypiques de YamHub (base `defidb`). Stage DEFI/AGAP/CIRAD.

## Contenu

| Fichier | Rôle |
|---|---|
| `variables.py` | Dictionnaire des variables (types, sens, classes, pondérations par profil) — **source unique de métadonnées** |
| `build_dataset.py` | Extrait + nettoie les données du dump SQL → `data/varietes_clean.csv` + `data/dictionnaire_variables.csv` |
| `app.py` | Interface Streamlit : profils, filtres, score, classement, fiche PDF |
| `data/` | Jeu de données propre + dictionnaire (générés) |

## Installation

```bash
cd decision-tool
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## 1. Générer le jeu de données propre

```bash
python build_dataset.py
```

Lit le dump `../public_html/docker/initdb/defidb.sql`, produit :

- `data/varietes_clean.csv` — 303 variétés, valeurs typées (décimales corrigées,
  `na` → vide, ordinaux → score 0..1)
- `data/dictionnaire_variables.csv` — métadonnées + **taux de complétude** par trait

## 2. Lancer l'outil

```bash
streamlit run app.py
```

Ouvre http://localhost:8501 (utilisable sur smartphone).

## Fonctionnement du score

Chaque profil (producteur / consommateur-transformateur / technicien) pondère un
sous-ensemble de traits (voir `PROFILS` dans `variables.py`). Pour chaque variété :
les traits sont normalisés 0..1 (numériques min-max selon le sens ; ordinaux via
leur score de classe), puis moyennés par les poids du profil. Les traits manquants
sont exclus et le score est renormalisé — la colonne **Couverture** indique la part
des critères réellement disponibles (un score sur peu de données est moins fiable).

## Limites connues / à traiter (étapes suivantes)

- **Complétude faible** : rendement 28 %, résistances ~62 %, qualité culinaire ~59 %.
- **Pas de dimension multi-environnements** dans la base : les valeurs sont déjà
  agrégées par variété (pas d'analyse de stabilité GxE possible en l'état).
  → localiser le jeu multi-env complet auprès de l'équipe DEFI.
- Unités de plusieurs variables numériques à confirmer (marquées `?`).

## Déjà intégré depuis la base existante

- **Photos de tubercules** dans la fiche (table `photosvariete`), chargées depuis
  le site en ligne (`yamhub.fr/adminPanel/uploads/`) — pas besoin des 4 Go en local.
- **Pays d'origine + carte** des origines (table `pays_partenaire`, 291/303 variétés).
- **Profil visuel** de chaque variété (critères du profil normalisés sur 100).
- **Tri par score puis couverture** pour départager les ex æquo.
