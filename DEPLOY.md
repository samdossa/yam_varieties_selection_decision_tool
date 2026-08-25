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

## B bis. Publier les photos (feuilles + recouvrement)

Les tubercules et anciennes feuilles viennent déjà de `yamhub.fr/adminPanel/uploads/`
(via `data/varietes_photos.csv`) : rien à faire pour elles.

En revanche `data/feuilles/` et `data/recouvrement_*mois/` sont **exclus de git**
(volumineux). Ils n'arrivent donc jamais sur Streamlit Cloud. `fiche_html.py` prévoit
un repli par URL : on héberge ces photos sur yamhub.fr et on déclare les adresses.

**1. Arborescence serveur** (sous `public_html/`) :

```
photos/
├── feuilles/            CIRADn.jpg
└── recouvrement/
    ├── 1mois/           CIRADn_1mois.jpg
    └── 3mois/           CIRADn_3mois.jpg
```

> Attention : le stade est un **sous-dossier** distant (`recouvrement/1mois/`), alors
> qu'en local c'est un préfixe (`data/recouvrement_1mois/`). `sync_photos.py` fait
> la conversion tout seul.

**2. Identifiants** : copier `ftp_credentials.txt.example` en `ftp_credentials.txt`
et le remplir (valeurs du profil FileZilla). Le fichier est gitignoré.

**3. Envoi** — incrémental, seuls les fichiers nouveaux ou modifiés partent :

```bash
python sync_photos.py --dry-run     # vérifier ce qui partirait
python sync_photos.py               # envoyer
python sync_photos.py --only 3mois  # une seule campagne
```

**4. Secrets Streamlit Cloud** (Settings -> Secrets), à ajouter à `MAPBOX_TOKEN` :

```toml
LEAF_URL = "https://yamhub.fr/photos/feuilles"
RECOUV_URL = "https://yamhub.fr/photos/recouvrement"
```

### Chaîne complète pour une nouvelle campagne drone

1. Décharger les photos drone (nommées par numéro : `174.JPG`, `213(1).JPG`…).
2. Recadrer — au choix :
   - `streamlit run crop_tool.py` (manuel, une variété à la fois). Coche
     **« Publier sur yamhub.fr à l'enregistrement »** : chaque photo validée part
     en ligne immédiatement, plus rien à faire ensuite.
   - `python crop_drone.py --src <dossier> --out data/recouvrement_3mois --stage 3mois`
     (automatique, par lot), puis `python sync_photos.py`.
3. Rien à redéployer côté Streamlit : les fiches vont chercher les images à l'URL.

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
