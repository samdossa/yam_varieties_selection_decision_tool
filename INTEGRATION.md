# Plan d'intégration de l'outil d'aide à la décision à YamHub

Document de conception (étape 7 du stage). Décrit comment connecter le prototype
Streamlit à la plateforme YamHub, les options envisagées, l'architecture retenue,
et les étapes de mise en production.

## 1. Contrainte de départ

- **YamHub** : site PHP + base MariaDB (`defidb`), hébergé sur mutualisé (Hostinger).
  Un hébergement PHP mutualisé **ne peut pas exécuter** une application Python/Streamlit.
- **L'outil** : application Streamlit (Python). Elle doit tourner sur un hébergement
  qui supporte Python, tout en utilisant les **données de YamHub**.

Il faut donc découpler *où tourne l'outil* de *où vivent les données*.

## 2. Options envisagées

| Option | Principe | Avantages | Limites |
|---|---|---|---|
| **A. Réécriture PHP native** | Refaire l'outil en PHP dans YamHub | Intégration totale, un seul hébergement | Abandonne Python/Streamlit ; gros travail ; perd l'agilité data science |
| **B. Streamlit + accès DB direct** | L'app se connecte en direct à MariaDB | Données toujours à jour | Hostinger restreint l'accès MySQL distant (IP whitelist) ; expose les identifiants DB à l'app |
| **C. Streamlit + API JSON (retenue)** | YamHub expose une API lecture seule ; l'app la consomme | Données à jour, YamHub reste source unique, pas de credentials DB côté app, découplé | Une petite API à maintenir |

**Architecture retenue : option C.** C'est la « maquette connectée aux APIs existantes »
mentionnée dans la fiche de stage.

## 3. Architecture retenue

```
   Utilisateur (smartphone / navigateur)
              │
              ▼
   ┌───────────────────────┐        lien / iframe depuis le menu YamHub
   │  App Streamlit         │◀───────────────────────────────────────┐
   │  (Streamlit Cloud)     │                                         │
   └───────────┬───────────┘                                         │
               │  HTTPS GET (JSON)                                    │
               ▼                                                      │
   ┌───────────────────────┐        ┌───────────────────────┐        │
   │  API  /api/varietes.php│───────▶│  Base defidb (MariaDB) │        │
   │  (lecture seule, JSON) │        └───────────────────────┘        │
   └───────────────────────┘                                          │
               ▲                                                      │
   ┌───────────┴───────────────────────────────────────────┐         │
   │  YamHub (PHP, Hostinger)  ── menu "Aide au choix" ──────┘         │
   └──────────────────────────────────────────────────────────────────┘
```

- **Source unique de données** : la base `defidb` de YamHub. L'outil ne duplique rien.
- **API** : `https://yamhub.fr/api/varietes.php` — déjà développée (`public_html/api/`).
  Renvoie en JSON les données jointes (variété + espèce + pays + phénotypage) et la
  liste des photos. Lecture seule, aucune donnée sensible.
- **Photos** : servies telles quelles depuis `yamhub.fr/adminPanel/uploads/`.

## 4. Côté outil : consommation de l'API

`build_dataset.py` accepte désormais deux sources, avec le **même nettoyage** :

```bash
python build_dataset.py            # hors-ligne, depuis le dump (dév)
python build_dataset.py --api      # EN DIRECT depuis https://yamhub.fr/api/varietes.php
```

En production, l'app régénère son jeu de données depuis l'API (au démarrage ou via une
tâche planifiée quotidienne), garantissant des recommandations toujours alignées sur
les données de YamHub.

## 5. Déploiement de l'app

Options d'hébergement Python (gratuites/légères) :

1. **Streamlit Community Cloud** (recommandé pour un prototype) — déploiement direct
   depuis un dépôt GitHub, gratuit, HTTPS fourni.
2. Hugging Face Spaces, Render, Railway, ou un petit VPS.

Étapes (Streamlit Cloud) :

1. Pousser le dossier `decision-tool/` sur un dépôt GitHub.
2. Connecter le dépôt à Streamlit Cloud, pointer sur `app.py`.
3. Configurer une régénération des données via l'API (`--api`).

## 6. Lien depuis YamHub

Ajouter une entrée de menu dans la navigation de YamHub (fichier `includes/header.php`
ou les pages), pointant vers l'app déployée :

```html
<li class="nav-item">
  <a class="nav-link" href="https://<app-deployee>.streamlit.app" target="_blank">
    Aide au choix variétal
  </a>
</li>
```

Alternative : intégrer l'app dans une page YamHub via une `<iframe>` pour une expérience
« dans le site ».

## 7. Sécurité

- API **lecture seule**, requête fixe (aucune entrée utilisateur → pas d'injection),
  n'expose aucune table sensible (`adminusers` exclue).
- `Access-Control-Allow-Origin` à **restreindre** en production au domaine de l'app
  (au lieu de `*`).
- Aucun identifiant de base n'est partagé avec l'app (contrairement à l'option B).

## 8. Ce qui est déjà fait / reste à faire

**Fait**
- API `/api/varietes.php` développée et sécurisée.
- `build_dataset.py` capable de consommer l'API (`--api`), testé (résultat identique au dump).

**Reste à faire**
- Déployer l'API en prod (upload de `public_html/api/`) et la tester en ligne.
- Déployer l'app (Streamlit Cloud) + planifier la régénération via l'API.
- Ajouter l'entrée de menu dans YamHub.
- Restreindre le CORS au domaine de l'app.


