# Débouchés par variété — seuils à valider avant remise en service

**Statut : EN ATTENTE DE VALIDATION.** La rubrique « débouchés / usages » a été **retirée**
des cartes du decision tool et de la fiche variétale tant que ces règles ne sont pas
approuvées. Le moteur (`debouches.py`) reste en réserve : dès que les seuils ci-dessous
sont validés/corrigés, on les met à jour et on réactive l'affichage.

## Ce qui est réel vs ce qui est à valider
- **Données mesurées (base CIRAD, fiables)** : matière sèche `TMS_BLUP`, qualité à la
  cuisson `BOILED_Q`, poids moyen du tubercule `poids_moyen_g`.
- **À valider (posé par défaut, non sourcé)** : les seuils de coupure et le débouché
  attribué à chaque intervalle. Le principe agronomique général (matière sèche élevée →
  farine/friture ; bonne tenue à la cuisson → consommation bouillie) est admis, mais les
  **valeurs exactes** ci-dessous sont provisoires.

## Contexte chiffré (répartition observée dans les données)
- Matière sèche : min ~20 %, médiane ~30 %, max ~40 % (n = 219 variétés).
- Qualité à la cuisson : High 63, Medium 99, Low 16, non renseigné 97.
- Poids moyen : min 23 g, médiane 930 g, max ~3 980 g (n = 230).

## Règles actuelles (à approuver ou corriger)

| # | Condition (donnée mesurée) | Seuil actuel | Débouché attribué | Validé ? | Seuil corrigé |
|---|----------------------------|--------------|-------------------|----------|----------------|
| 1 | Matière sèche élevée | ≥ **32 %** | Farine et produits séchés **+** Chips et frites | ☐ | ______ |
| 2 | Matière sèche moyenne+ | ≥ **29 %** | Farine et produits séchés | ☐ | ______ |
| 3 | Qualité cuisson = High | — | Consommation bouillie, purée et igname pilée (pâte) | ☐ | — |
| 4 | Qualité cuisson = Medium | — | Consommation bouillie et cuisine familiale | ☐ | — |
| 5 | Gros tubercule | ≥ **1500 g** | Transformation et marché de gros | ☐ | ______ |
| 6 | Petit tubercule | ≤ **250 g** | Consommation ménagère et semences | ☐ | ______ |
| 7 | Par défaut (toujours ajouté) | — | Consommation fraîche (marché de frais) | ☐ | — |

## Questions pour le valideur (Eric / agronome)
1. Les seuils de matière sèche (29 % / 32 %) sont-ils pertinents pour distinguer
   farine / chips / consommation fraîche sur l'igname en Guadeloupe ?
2. Les libellés de débouchés sont-ils corrects et complets (manque-t-il un usage :
   amidon, semoule, transformation industrielle… ) ?
3. Faut-il tenir compte de l'espèce (D. alata vs esculenta vs cayenensis-rotundata)
   pour les débouchés, ou les traits suffisent-ils ?
4. Faut-il un seuil minimal de données (ne rien afficher si trop de valeurs manquantes) ?

## Après validation
Reporter les seuils approuvés dans les constantes en tête de `debouches.py`
(`MS_ELEVEE`, `MS_MOYENNE`, `PM_GROS`, `PM_PETIT`) et rebrancher l'affichage
(carte + fiche) — 3 lignes à réactiver, déjà écrites.
