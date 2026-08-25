# YamHub — Decision support tool (prototype)

Prototype of the yam variety selection support tool, using the phenotypic data from
YamHub (database `defidb`). DEFI/AGAP/CIRAD internship.

## Contents

| File | Role |
|---|---|
| `variables.py` | Variable dictionary (types, directions, classes, profile weights) — **single source of metadata** |
| `build_dataset.py` | Extracts + cleans the SQL dump data → `data/varietes_clean.csv` + `data/dictionnaire_variables.csv` |
| `app.py` | Streamlit interface: profiles, filters, score, ranking, PDF sheet |
| `data/` | Cleaned dataset + dictionary (generated) |

## Installation

```bash
cd decision-tool
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## 1. Generate the clean dataset

```bash
python build_dataset.py
```

Reads the dump `../public_html/docker/initdb/defidb.sql` and produces:

- `data/varietes_clean.csv` — 303 varieties, typed values (corrected decimals,
  `na` → empty, ordinal → score 0..1)
- `data/dictionnaire_variables.csv` — metadata + **completeness rate** per trait

## 2. Launch the tool

```bash
streamlit run app.py
```

Opens http://localhost:8501 (usable on smartphone).

## How the score works

Each profile (producer / processor-consumer / technician) assigns weights to a
subset of traits (see `PROFILS` in `variables.py`). For each variety:
traits are normalized to 0..1 (numeric min-max according to direction; ordinal via
their class score), then averaged using the profile weights. Missing traits are
excluded and the score is renormalized — the **Coverage** column indicates the share
of criteria that are actually available (a score based on little data is less reliable).

## Known limitations / to be addressed (next steps)

- **Low completeness**: yield 28%, resistance ~62%, culinary quality ~59%.
- **No multi-environment dimension** in the database: values are already aggregated by
  variety (no GxE stability analysis is possible in the current state).
  → locate the complete multi-environment dataset with the DEFI team.
- Units for several numerical variables still need confirmation (marked `?`).

## Already integrated from the existing database

- **Tuber photos** in the sheet (table `photosvariete`), loaded from the online
  site (`yamhub.fr/adminPanel/uploads/`) — no need for the 4 GB locally.
- **Country of origin + map** of origins (table `pays_partenaire`, 291/303 varieties).
- **Visual profile** of each variety (profile criteria normalized to 100).
- **Sort by score then coverage** to break ties.
