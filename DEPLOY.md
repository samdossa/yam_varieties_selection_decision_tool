# Mise en production — Outil d'aide au choix variétal

L'app Streamlit tourne sur **Streamlit Community Cloud** (gratuit). Elle embarque son
jeu de données (`data/*.csv`) ; les photos viennent de yamhub.fr. YamHub l'affiche via
la page `aide-decision.php` (iframe) + une entrée de menu.

> Ces étapes se font depuis TES comptes (GitHub, Streamlit Cloud, Hostinger, Mapbox).

---

## A. Déployer l'app sur Streamlit Cloud

1. **Pousser `decision-tool/` sur un dépôt GitHub PRIVÉ** (le `.gitignore` exclut le token,
   le venv et les sources ; les `data/*.csv` nécessaires sont bien inclus).
   > **Protection du code (concurrence).** Le dépôt doit être **privé** : Streamlit Cloud
   > déploie sans problème depuis un repo privé, et le code n'est jamais servi à
   > l'utilisateur (seule l'app rendue est visible). La licence propriétaire (`LICENSE`,
   > « Tous droits réservés » CIRAD) protège juridiquement contre toute réutilisation.
   ```bash
   cd ~/YamHub/yamhub.fr/decision-tool
   git init && git add -A && git commit -m "Outil aide au choix variétal igname"
   git branch -M main
   git remote add origin https://github.com/<toi>/yamhub-decision-tool.git
   git push -u origin main
   ```
2. Sur **https://share.streamlit.io** → *New app* → choisir le dépôt, branche `main`,
   fichier principal `app.py`.
3. Dans *Advanced settings → Secrets*, coller :
   ```toml
   MAPBOX_TOKEN = "pk.eyJ1IjoiYWx4MTgi..."
   ```
4. *Deploy*. Le fichier `packages.txt` installe automatiquement les librairies système
   de WeasyPrint. Tu obtiens une URL type `https://<app>.streamlit.app`.

## B. Brancher YamHub sur l'app

1. Dans `public_html/aide-decision.php`, mettre `$APP_URL` = l'URL Streamlit obtenue.
2. Dans `public_html/api/varietes.php`, restreindre le CORS :
   remplacer `Access-Control-Allow-Origin: *` par ton origine
   (`https://<app>.streamlit.app`).
3. **Uploader sur Hostinger** (gestionnaire de fichiers ou FTP) le contenu de
   `public_html/` modifié :
   - `api/`, `aide-decision.php`
   - les 6 pages avec le menu « Aide au choix » : `index.php`, `search.php`,
     `galerie.php`, `passport.php`, `contact.php`, `publication.php`
   - `includes/db.php`, `includes/db_credentials.php`, `config.php`,
     `adminPanel/db_config.php`, `adminPanel/includes/db_config.php`
   - les pages sécurisées : `login.php`, `forgot-password.php`, `reset-password.php`
   - `migrations/001_create_lot.sql` (et l'exécuter en prod si pas déjà fait)

## C. Sécurité (à faire absolument)

1. **Régénérer le mot de passe MySQL** de `defidb` dans Hostinger (il a circulé au
   début). Déposer le nouveau dans un `config.local.php` sur le serveur (modèle :
   `config.local.php.example`), non versionné.
2. **Restreindre le token Mapbox** par URL dans ton compte Mapbox (ton app + yamhub.fr).
3. Vérifier login admin / upload en prod (requêtes préparées déjà en place).

## D. Vérification post-déploiement

- Ouvrir **https://yamhub.fr/aide-decision.php** → l'outil s'affiche dans le site.
- Choisir un profil, filtrer, cliquer « Voir la fiche » → télécharger la fiche PDF
  (photos + carte Mapbox visibles).

---

### Note données
L'app est **autonome** : elle embarque `data/tool_data.csv` (socle consolidé : 200+
variables, stabilité GxE, calibre) et charge les photos en direct depuis yamhub.fr.
Pour la mettre à jour quand de nouvelles données arrivent : relancer le pipeline
(`build_master → analyse_stabilite → build_calibre → build_tool_data`), committer les
`data/*.csv`, pousser → Streamlit Cloud redéploie tout seul.
