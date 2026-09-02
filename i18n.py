#!/usr/bin/env python3
"""
i18n.py — Traductions français / anglais de l'outil et des fiches variétales.

Principe : les clés RESTENT en français, parce qu'elles servent aussi de clés
de logique ailleurs dans le code (PROFILS, CRIT, CARTE_CRIT dans app.py, valeurs
de la base pour BADGE). Traduire les clés casserait le moteur de score. On ne
traduit donc que l'AFFICHAGE, au dernier moment.

Usage :
    import i18n
    i18n.t("titre_app", "en")           # -> "Which yam variety should I grow?"
    i18n.val("High", "en")              # valeur de la base -> libellé affiché
    i18n.crit("Récolte", "en")          # clé de logique -> libellé affiché

Une clé absente est renvoyée telle quelle : un oubli de traduction se voit à
l'écran sans jamais faire planter l'application.
"""

LANGUES = {"fr": "Français", "en": "English"}
DEFAUT = "fr"


# --------------------------------------------------------------------------
# Interface (app.py)
# --------------------------------------------------------------------------
UI = {
    "titre_app": ("Quelle variété d'igname choisir ?",
                  "Which yam variety should I grow?"),
    "mode_detaille": ("Mode détaillé (pour techniciens)",
                      "Detailed mode (for technicians)"),
    "etape1": ("1. Vous êtes :", "1. You are:"),
    "etape2": ("2. Ce que vous cherchez (facultatif) :",
               "2. What you are looking for (optional):"),
    "etape3": ("3. Variétés conseillées pour vous :",
               "3. Varieties recommended for you:"),
    "sites_carte": ("Sites d'évaluation en Guadeloupe (Roujol, Godet)",
                    "Evaluation sites in Guadeloupe (Roujol, Godet)"),
    "rendement_min": ("Rendement minimum (t/ha)", "Minimum yield (t/ha)"),
    "res_anthracnose": ("Résistante à l'anthracnose", "Anthracnose resistant"),
    "res_rouille": ("Résistante à la rouille", "Rust resistant"),
    "pas_fourmis": ("Pas d'attaque de fourmis", "No ant damage"),
    "res_maladies": ("Résistante aux maladies", "Disease resistant"),
    "duree_cycle": ("Durée du cycle (levée → sénescence)",
                    "Cycle length (emergence → senescence)"),
    "forme_tubercule": ("Forme du tubercule", "Tuber shape"),
    "bonne_conservation": ("Bonne conservation", "Good storability"),
    "couleur_chair": ("Couleur de la chair", "Flesh colour"),
    "bonne_qualite_bouillie": ("Bonne qualité bouillie", "Good boiled quality"),
    "bon_gout": ("Bon goût", "Good taste"),
    "ms_elevee": ("Matière sèche élevée", "High dry matter"),
    "gros_calibre": ("Gros calibre (>2 kg fréquent)", "Large size (>2 kg common)"),
    "nb_varietes": ("Nombre de variétés à afficher", "Number of varieties to show"),
    "aucune_variete": ("Aucune variété ne correspond. Essayez d'enlever un filtre.",
                       "No variety matches. Try removing a filter."),
    "aucune_variete_filtres": ("Aucune variété ne correspond aux filtres.",
                               "No variety matches the filters."),
    "voir_fiche": ("Voir la fiche", "View data sheet"),
    "telecharger_fiche": ("Télécharger la fiche", "Download data sheet"),
    "telecharger_fiche_off": ("Télécharger la fiche variétale (format officiel)",
                              "Download variety data sheet (official format)"),
    "erreur_fiche": ("Erreur génération de la fiche :",
                     "Data sheet generation failed:"),
    "legende_etoiles": ("★ = plus il y a d'étoiles, mieux c'est. Le badge indique la "
                        "variabilité du rendement d'un essai à l'autre, **comparée aux "
                        "autres variétés** de la collection : sur igname, toutes varient "
                        "beaucoup. Le détail (CV, nombre d'essais) est sur la fiche.",
                        "★ = the more stars, the better. The badge shows yield variability "
                        "across trials **relative to the other varieties** in the "
                        "collection: on yam, all of them vary a lot. Details (CV, number "
                        "of trials) are on the data sheet."),
    "essais": ("essais", "trials"),
    "cv_rendement": ("Variabilité du rendement (CV)", "Yield variability (CV)"),
    "nb_essais": ("Nombre d'essais", "Number of trials"),
    "eval_insuffisante": ("Moins de 3 essais : variabilité non conclue",
                          "Fewer than 3 trials: variability not assessed"),
    "astuce_detaille": ("Pour l'analyse complète (tous les traits, tableau, graphe "
                        "de stabilité), utilise le **mode détaillé** en haut de page.",
                        "For the full analysis (all traits, table, stability plot), "
                        "use **detailed mode** at the top of the page."),
    "filtres": ("Filtres", "Filters"),
    "espece": ("Espèce", "Species"),
    "profil_gxe": ("Profil GxE", "GxE profile"),
    "analyse_stabilite": ("Analyse de stabilité (rendement, Roujol × Godet × années)",
                          "Stability analysis (yield, Roujol × Godet × years)"),
    "varietes": ("Variétés", "Varieties"),
    "fiche_variétale": ("Fiche variétale", "Variety data sheet"),
    "choisir_variete": ("Choisir une variété", "Choose a variety"),
    "tubercule": ("Tubercule", "Tuber"),
    "langue": ("Langue", "Language"),
    # --- mode technicien ---
    "recherche": ("Rechercher une variété (nom ou code)",
                  "Search a variety (name or code)"),
    "filtres_identite": ("Identité", "Identity"),
    "filtres_rendement": ("Rendement et régularité", "Yield and consistency"),
    "filtres_sanitaire": ("Sanitaire", "Health"),
    "filtres_qualite": ("Qualité et morphologie", "Quality and morphology"),
    "pays_origine": ("Pays d'origine", "Country of origin"),
    "rendement_plage": ("Rendement (t/ha)", "Yield (t/ha)"),
    "cv_plage": ("Variabilité CV (%)", "Variability CV (%)"),
    "n_env_min": ("Essais minimum", "Minimum trials"),
    "anthracnose_max": ("Anthracnose : indice AUDPC maximum",
                        "Anthracnose: maximum AUDPC index"),
    "ms_min": ("Matière sèche minimum (%)", "Minimum dry matter (%)"),
    "texture_feuille": ("Texture de la feuille", "Leaf texture"),
    "qualite_bouillie_f": ("Qualité bouillie", "Boiled quality"),
    "reinit": ("Réinitialiser les filtres", "Reset filters"),
    "nuage_aide": ("Survole un point pour identifier la variété, clique dessus "
                   "pour ouvrir sa fiche plus bas.",
                   "Hover a point to identify the variety, click it to open its "
                   "data sheet below."),
    "axe_rendement": ("Rendement (t/ha)", "Yield (t/ha)"),
    "axe_cv": ("Variabilité — CV entre essais (%)",
               "Variability — CV across trials (%)"),
    "selection_vide": ("Aucune variété sélectionnée — clique un point du nuage "
                       "ou choisis-en une ci-dessous.",
                       "No variety selected — click a point on the plot or pick "
                       "one below."),
    "detail_variete": ("Détail de la variété", "Variety detail"),
    "tableau": ("Tableau", "Table"),
    "colonnes": ("Colonnes affichées", "Columns shown"),
    "exporter_csv": ("Exporter la sélection (CSV)", "Export selection (CSV)"),
    "resultats": ("résultats", "results"),
    "essais_col": ("Essais", "Trials"),
    "peu_importe": ("Peu importe", "Any"),
    "cycle_court": ("Court (< 6 mois)", "Short (< 6 months)"),
    "cycle_long": ("Long (6-9 mois)", "Long (6-9 months)"),
    "cycle_tres_long": ("Très long (> 9 mois)", "Very long (> 9 months)"),
}


# --------------------------------------------------------------------------
# Profils utilisateur et critères de score (clés = logique, ne pas traduire)
# --------------------------------------------------------------------------
PROFILS = {
    "Producteur": ("Producteur", "Grower"),
    "Agrotransformateur": ("Agrotransformateur", "Processor"),
    "Technicien": ("Technicien", "Technician"),
}

CRITERES = {
    "Récolte": ("Récolte", "Yield"),
    "Résistance": ("Résistance", "Resistance"),
    "Goût": ("Goût", "Taste"),
    "Matière sèche": ("Matière sèche", "Dry matter"),
    "Conservation": ("Conservation", "Storability"),
}

# Badges GxE. Le vocabulaire est volontairement COMPARATIF : sur cette
# collection le CV médian atteint 48 %, aucune variété n'est « régulière » dans
# l'absolu. Dire « variabilité faible » sous-entend « par rapport aux autres »,
# ce que la légende explicite.
BADGES = {
    "performante & variabilité faible":
        ("Productive, variabilité faible", "Productive, low variability"),
    "performante & variabilité moyenne":
        ("Productive, variabilité moyenne", "Productive, moderate variability"),
    "performante & variabilité forte":
        ("Productive, variabilité forte", "Productive, high variability"),
    "modeste & variabilité faible":
        ("Rendement modéré, variabilité faible", "Moderate yield, low variability"),
    "modeste & variabilité moyenne":
        ("Rendement modéré, variabilité moyenne", "Moderate yield, moderate variability"),
    "modeste & variabilité forte":
        ("Rendement modéré, variabilité forte", "Moderate yield, high variability"),
    "données insuffisantes": ("Évaluation insuffisante", "Insufficient evaluation"),
}


# --------------------------------------------------------------------------
# Valeurs venant de la base : affichées telles quelles aujourd'hui en français
# --------------------------------------------------------------------------
VALEURS = {
    "High": ("Bonne", "Good"),
    "Medium": ("Moyenne", "Medium"),
    "Low": ("Faible", "Low"),
    "Absent": ("Absent", "None"),
    "Absence": ("Absent", "None"),
    "Absente": ("Absente", "None"),
    "Faible": ("Faible", "Low"),
    "Fort": ("Fort", "High"),
    "Forte": ("Forte", "High"),
    "Moyenne": ("Moyenne", "Medium"),
    "Bonne": ("Bonne", "Good"),
    "Sensible": ("Sensible", "Susceptible"),
    "Modérément sensible": ("Modérément sensible", "Moderately susceptible"),
    "Tolérante": ("Tolérante", "Tolerant"),
    "Données manquantes": ("Données manquantes", "Missing data"),
    "Présence": ("Présence", "Present"),
    "Présente": ("Présente", "Present"),
    "na": ("n.d.", "n/a"),
    # Couleur de la chair (CCCTCT)
    "Blanc": ("Blanc", "White"),
    "Blanc avec du violet": ("Blanc avec du violet", "White with purple"),
    "Blanc jaunâtre ou blanc cassé": ("Blanc jaunâtre ou blanc cassé",
                                      "Yellowish or off-white"),
    "Jaune": ("Jaune", "Yellow"),
    "Orange": ("Orange", "Orange"),
    "Violet": ("Violet", "Purple"),
    "Violet clair": ("Violet clair", "Light purple"),
    "Violet avec du blanc": ("Violet avec du blanc", "Purple with white"),
    "Extérieur violet/intérieur jaunâtre": ("Extérieur violet/intérieur jaunâtre",
                                            "Purple outside / yellowish inside"),
    "exterieur violet/interieur blanc": ("Extérieur violet/intérieur blanc",
                                         "Purple outside / white inside"),
    "intérieur violet/exterieur jaune": ("Intérieur violet/extérieur jaune",
                                         "Purple inside / yellow outside"),
    # Forme du tubercule (FT)
    "Allongée": ("Allongée", "Elongated"),
    "Cylindrique": ("Cylindrique", "Cylindrical"),
    "Fusiforme": ("Fusiforme", "Spindle-shaped"),
    "Irrégulière": ("Irrégulière", "Irregular"),
    "Ovale": ("Ovale", "Oval"),
    "Ronde": ("Ronde", "Round"),
    # Forme de la feuille (FF)
    "Cordée": ("Cordée", "Cordate"),
    "Cordée allongée": ("Cordée allongée", "Elongated cordate"),
    "Cordée élargie": ("Cordée élargie", "Broad cordate"),
    "Hastée": ("Hastée", "Hastate"),
    "Sagittée allongée": ("Sagittée allongée", "Elongated sagittate"),
    "Sagittée élargie": ("Sagittée élargie", "Broad sagittate"),
    # Texture de la feuille (TF) et épaisseur de peau (EPT)
    "Coriace": ("Coriace", "Leathery"),
    "Souple": ("Souple", "Soft"),
    "Fine": ("Fine", "Thin"),
    "Épaisse": ("Épaisse", "Thick"),
    # Aspect de la chair
    "Granuleux": ("Granuleux", "Granular"),
    "Lisse": ("Lisse", "Smooth"),
    # Couleurs des organes aériens (tige, pétiole, nervures)
    "Vert": ("Vert", "Green"),
    "Verte": ("Verte", "Green"),
    "Vert pâle": ("Vert pâle", "Pale green"),
    "Vert foncé / Vert violacé": ("Vert foncé / Vert violacé",
                                  "Dark green / purplish green"),
    "Vert violacé": ("Vert violacé", "Purplish green"),
    "Vert brunâtre": ("Vert brunâtre", "Brownish green"),
    "Brun foncé": ("Brun foncé", "Dark brown"),
    "Jaunâtre": ("Jaunâtre", "Yellowish"),
    "Autre": ("Autre", "Other"),
    "Entièrement vert avec base violette":
        ("Entièrement vert avec base violette", "Fully green with purple base"),
    "Entièrement vert avec les deux extrémités violettes":
        ("Entièrement vert avec les deux extrémités violettes",
         "Fully green with both ends purple"),
    # Niveaux de sensibilité aux maladies (calculés depuis l'AUDPC)
    "Sensible": ("Sensible", "Susceptible"),
}


# --------------------------------------------------------------------------
# Fiche variétale (fiche_html.py)
# --------------------------------------------------------------------------
FICHE = {
    "carte_identite": ("CARTE D'IDENTITÉ", "IDENTITY"),
    "description": ("DESCRIPTION", "DESCRIPTION"),
    "partie_aerienne": ("PARTIE AÉRIENNE", "ABOVE-GROUND PARTS"),
    "partie_souterraine": ("PARTIE SOUTERRAINE", "BELOW-GROUND PARTS"),
    "maladies": ("MALADIES", "DISEASES"),
    "qualite": ("QUALITÉ", "QUALITY"),
    "rendement_maj": ("RENDEMENT", "YIELD"),
    "calibre_maj": ("CALIBRE", "SIZE GRADE"),
    "levee_recouvrement": ("LEVÉE ET RECOUVREMENT", "EMERGENCE AND GROUND COVER"),
    "variete": ("Variété", "Variety"),
    "espece": ("Espèce", "Species"),
    "origine": ("Origine", "Origin"),
    "code_cirad": ("Code CIRAD", "CIRAD code"),
    "code_centre": ("Code du centre d'origine", "Origin centre code"),
    "fournisseur": ("Fournisseur", "Supplier"),
    "annee_introduction": ("Année d'introduction", "Year of introduction"),
    "periode_evaluation": ("Période d'évaluation", "Evaluation period"),
    "usage_principal": ("Usage principal", "Main use"),
    "feuille": ("Feuille", "Leaf"),
    "tige": ("Tige", "Stem"),
    "petiole": ("Pétiole", "Petiole"),
    "bulbilles": ("Bulbilles", "Bulbils"),
    "tubercule": ("Tubercule", "Tuber"),
    "peau": ("Peau", "Skin"),
    "chair": ("Chair", "Flesh"),
    "couleur": ("Couleur", "Colour"),
    "couleur_chair": ("Couleur chair", "Flesh colour"),
    "couleur_chair_l": ("Couleur de la chair", "Flesh colour"),
    "aspect_chair": ("Aspect chair", "Flesh appearance"),
    "forme": ("Forme", "Shape"),
    "texture": ("Texture", "Texture"),
    "epaisseur": ("Épaisseur", "Thickness"),
    "epaisseur_peau": ("Épaisseur peau", "Skin thickness"),
    "phelloderme": ("Phelloderme", "Phelloderm"),
    "racines": ("Racines", "Roots"),
    "anthracnose": ("Anthracnose", "Anthracnose"),
    "rouille": ("Rouille", "Rust"),
    "niveau": ("Niveau", "Level"),
    "qualite_bouillie": ("Qualité bouillie", "Boiled quality"),
    "oxydation_cuisson": ("Oxydation à la cuisson", "Cooking oxidation"),
    "matiere_seche": ("Matière sèche", "Dry matter"),
    "pourriture_stockage": ("Pourriture au stockage (1 mois)",
                            "Storage rot (1 month)"),
    "taux_germination": ("Taux de germination", "Germination rate"),
    "duree_emergence": ("Durée d'émergence", "Emergence time"),
    "duree_cycle": ("Durée du cycle", "Cycle length"),
    "rendement": ("Rendement", "Yield"),
    "rendement_potentiel": ("Rendement potentiel", "Potential yield"),
    "rendement_unite": ("Rendement (t/ha)", "Yield (t/ha)"),
    "rendement_par_site": ("Rendement potentiel par site et année",
                           "Potential yield by site and year"),
    "poids_moyen": ("Poids moyen par tubercule", "Mean tuber weight"),
    "nb_tubercules": ("Nb moyen de tubercules/plant", "Mean tubers per plant"),
    "regularite": ("Régularité", "Consistency"),
    "profil_regularite": ("Profil de régularité", "Consistency profile"),
    "points_forts": ("Points forts de la variété :", "Variety strengths:"),
    "sites_guadeloupe": ("Sites d'évaluation en Guadeloupe",
                         "Evaluation sites in Guadeloupe"),
    "evaluee_stations": ("Évaluée en stations expérimentales (Roujol, Godet)",
                         "Evaluated at experimental stations (Roujol, Godet)"),
    "plateforme": ("Plateforme d'Évaluation Variétale d'Ignames",
                   "Yam Variety Evaluation Platform"),
    "fiche_en_ligne": ("Fiche en ligne sur YamHub", "Data sheet online on YamHub"),
    "edition": ("Édition : 2026", "Edition: 2026"),
    "recouvrement_a_venir": ("Photo de recouvrement à venir.",
                             "Ground-cover photo coming soon."),
    "calibre_indispo": ("Calibre indisponible.", "Size grade unavailable."),
    "carte_indispo": ("Carte indisponible.", "Map unavailable."),
    "rendement_site_indispo": ("Rendement par site indisponible.",
                               "Yield by site unavailable."),
    "aucune_donnee_manquante": ("aucune donnée clé manquante",
                                "no key data missing"),
    "donnees_manquantes": ("Données manquantes", "Missing data"),
    "recouvrement_a": ("Recouvrement à", "Ground cover at"),
    "mois_1": ("1 mois", "1 month"),
    "mois_3": ("3 mois", "3 months"),
    # Points forts déduits des mesures
    "pf_rendement_eleve": ("Rendement élevé", "High yield"),
    "pf_bon_rendement": ("Bon rendement", "Good yield"),
    "pf_rendement_stable": ("Rendement stable", "Stable yield"),
    "pf_gros_tubercules": ("Gros tubercules", "Large tubers"),
    "pf_bonne_cuisson": ("Bonne qualité à la cuisson", "Good cooking quality"),
    "pf_cuisson_correcte": ("Qualité à la cuisson correcte", "Fair cooking quality"),
    "pf_ms_elevee": ("Matière sèche élevée", "High dry matter"),
    "pf_pas_pourriture": ("Pas de pourriture au stockage (1 mois)",
                          "No storage rot (1 month)"),
    "pf_faible_pourriture": ("Faible pourriture au stockage (1 mois)",
                             "Low storage rot (1 month)"),
    "pf_appreciee": ("Appréciée des agriculteurs", "Appreciated by farmers"),
    "pf_adaptee": ("Adaptée aux conditions de la Guadeloupe",
                   "Suited to Guadeloupe conditions"),
    "performances": ("PERFORMANCES", "PERFORMANCE"),
    "attaque_fourmi": ("Attaque fourmi manioc dangereuse pour cette variété ?",
                       "Is the cassava ant a threat to this variety?"),
    "oui": ("Oui", "Yes"),
    "non": ("Non", "No"),
    "stable": ("Stable", "Stable"),
    "non_stable": ("Non stable", "Not stable"),
    "note_stations": ("NOTE : Toutes les données présentées ci-après ont été obtenues "
                      "en stations expérimentales (Roujol, Godet). Elles traduisent les "
                      "performances de la variété dans les conditions de culture des stations.",
                      "NOTE: all data below were obtained at experimental stations "
                      "(Roujol, Godet). They reflect the variety's performance under "
                      "station growing conditions."),
    "et": ("et", "and"),
    "graph_titre": ("Rendement potentiel par site et année",
                    "Potential yield by site and year"),
    "stab_titre": ("Rendement : performance vs stabilité des variétés d'igname",
                   "Yield: performance vs stability of yam varieties"),
    "stab_x": ("Rendement (t/ha, BLUP)", "Yield (t/ha, BLUP)"),
    "stab_y": ("Instabilité — CV entre environnements (%)",
               "Instability — CV across environments (%)"),
    "mois": ("mois", "months"),
    "jours": ("jours", "days"),
    "cycle_court_txt": ("court (<6 mois)", "short (<6 months)"),
    "cycle_long_txt": ("long (6-9 mois)", "long (6-9 months)"),
    "cycle_tres_long_txt": ("très long (>9 mois)", "very long (>9 months)"),
    "tolerance": ("Tolérance ", "Tolerance "),
    "a_anthracnose": ("à l'anthracnose", "to anthracnose"),
    "a_rouille": ("à la rouille", "to rust"),
}


# --------------------------------------------------------------------------
# Accès
# --------------------------------------------------------------------------
def _get(table, cle, lang):
    """Renvoie la traduction, ou la clé elle-même si elle manque.

    Ne lève jamais : un libellé oublié s'affiche en clair plutôt que de faire
    tomber l'app en pleine démonstration.
    """
    paire = table.get(cle)
    if paire is None:
        return cle
    return paire[1] if lang == "en" else paire[0]


def t(cle, lang=DEFAUT):
    """Libellé d'interface ou de fiche (UI puis FICHE)."""
    if cle in UI:
        return _get(UI, cle, lang)
    return _get(FICHE, cle, lang)


def val(v, lang=DEFAUT):
    """Valeur issue de la base (High, Absent, Fort…) -> libellé affiché."""
    return _get(VALEURS, v, lang) if isinstance(v, str) else v


def crit(cle, lang=DEFAUT):
    """Critère de score : clé de logique française -> libellé affiché."""
    return _get(CRITERES, cle, lang)


def profil(cle, lang=DEFAUT):
    """Profil utilisateur : clé de logique française -> libellé affiché."""
    return _get(PROFILS, cle, lang)


def badge(classe, lang=DEFAUT):
    """Classe GxE de la base -> libellé court affiché."""
    return _get(BADGES, classe, lang)
