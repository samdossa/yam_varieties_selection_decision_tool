# Partager `crop_tool.py` sur le réseau

L'outil de recadrage tourne sur **une** machine ; les autres s'y connectent avec
un navigateur. Rien à installer chez eux, et les photos gardent leur pleine
résolution — contrairement à un passage par Streamlit Cloud.

## Trois conditions

1. **Les photos drone doivent être sur le serveur** (disque local ou partage
   monté). L'outil lit un dossier : il ne voit pas le disque des utilisateurs.
2. **Le serveur doit être joignable** depuis les postes : même réseau, port
   ouvert (8501 par défaut).
3. **Le dossier de sortie est celui du serveur.** C'est voulu — tout le monde
   écrit au même endroit, et `sync_photos.py` publie l'ensemble d'un coup.

## Sélection des dossiers à distance

Sur un serveur sans écran, le bouton « Parcourir » (Finder) ne peut pas
s'ouvrir. L'outil le détecte et affiche à la place une **navigation par liste**
(bouton parent + liste des sous-dossiers), utilisable depuis le navigateur.
Le champ « coller un chemin » reste disponible dans les deux cas.

Aucun réglage à faire : la bascule est automatique.

## Lancement

```bash
cd /chemin/vers/decision-tool
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m streamlit run crop_tool.py \
  --server.address 0.0.0.0 --server.port 8501 --server.headless true
```

Les collègues ouvrent `http://<ip-du-serveur>:8501`.

> `--server.address 0.0.0.0` expose l'outil à tout le réseau. À ne faire que sur
> un réseau de confiance : l'outil n'a aucune authentification, et il permet de
> parcourir les dossiers du serveur.

## Le garder allumé (systemd)

Sans ça, l'outil s'arrête à la fermeture de la session. Créer
`/etc/systemd/system/crop-tool.service` :

```ini
[Unit]
Description=YamHub — outil de recadrage des photos de recouvrement
After=network.target

[Service]
Type=simple
User=VOTRE_UTILISATEUR
WorkingDirectory=/chemin/vers/decision-tool
ExecStart=/chemin/vers/decision-tool/.venv/bin/python -m streamlit run crop_tool.py \
          --server.address 0.0.0.0 --server.port 8501 --server.headless true
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Puis :

```bash
sudo systemctl daemon-reload && sudo systemctl enable --now crop-tool
sudo systemctl status crop-tool     # vérifier
journalctl -u crop-tool -f          # suivre les logs
```

## Plusieurs personnes en même temps

Streamlit gère une session par navigateur : chacun a sa propre variété affichée
et sa propre boîte de recadrage. Le **dossier de sortie est commun**, donc si
deux personnes recadrent la même variété, la dernière écrase la première. Le
filtre « À faire (non enregistrées) » de la barre latérale permet de se répartir
le travail sans se marcher dessus.

## Publication vers yamhub.fr

Poser `ftp_credentials.txt` **sur le serveur uniquement** (voir
`ftp_credentials.txt.example`). La case « Publier sur yamhub.fr à
l'enregistrement » devient alors active pour tout le monde, sans que personne
n'ait à connaître les identifiants.

Sans ce fichier, les photos restent sur le serveur et partent plus tard avec :

```bash
.venv/bin/python sync_photos.py
```

---

# Déploiement Docker (decision-tool)

Le conteneur redémarre seul après un plantage **et** après un redémarrage de la
machine : c'est ce qui remplace la mise en veille subie sur Streamlit Community
Cloud.

## Mise en route

```bash
git clone https://github.com/ALX-18/decision-tool.git
cd decision-tool
cp .env.example .env        # puis remplir MAPBOX_TOKEN
docker compose up -d --build
```

L'outil répond sur `http://<serveur>:8501`.

## Exploitation

```bash
docker compose logs -f                 # journaux en direct
docker compose ps                      # etat et sante du conteneur
docker compose restart                 # apres modification d'un CSV de data/
docker compose up -d --build           # apres un git pull (code modifie)
docker compose down                    # arreter
```

Le `data/` est **monté** et non copié : mettre à jour un jeu de données ne
demande qu'un `restart`, pas une reconstruction d'image.

Le `HEALTHCHECK` interroge `/_stcore/health`. Docker distingue ainsi un
conteneur démarré d'une app réellement prête, et `docker compose ps` affiche
`healthy` plutôt qu'un simple `running`.

## Ce que le conteneur embarque

Les bibliothèques système de WeasyPrint (pango, cairo) sont installées dans
l'image : sans elles la génération de fiches échoue **au rendu et non à
l'import**, l'erreur n'apparaîtrait donc qu'au premier téléchargement.

Les identifiants ne sont jamais dans l'image — `.dockerignore` exclut `.env`,
`ftp_credentials.txt` et `mapbox_token.txt`.

## Accès depuis yamhub.fr

Si le serveur n'est joignable que sur le réseau interne, l'iframe de
`aide-decision.php` ne pourra pas l'afficher pour un visiteur extérieur. Les
**fiches PDF pré-générées restent accessibles**, elles, puisqu'elles sont
servies par yamhub.fr lui-même. Pour que l'outil interactif reste public, il
faut soit exposer le serveur, soit conserver un déploiement public en parallèle.

## Mettre un mot de passe (déploiement Docker)

Tant que l'outil ne faisait que recadrer, l'exposer sans filtre était sans
conséquence. Depuis qu'un enregistrement publie sur yamhub.fr, la page écrit
sur le site : qui atteint le port peut y déposer des photos. Et `0.0.0.0`
signifie l'internet entier, pas le seul réseau CIRAD.

Caddy s'interpose. L'outil cesse de publier un port et n'est plus joignable
que par lui.

1. Produire l'empreinte du mot de passe :

```bash
docker run --rm caddy:2-alpine caddy hash-password --plaintext 'le-mot-de-passe'
```

2. Dans `.env`, à côté du compose — guillemets simples obligatoires, le hash
   contient des `$` que Compose prendrait pour des variables :

```
CROP_USER=cirad-equipe
CROP_HASH='$2a$14$...'
```

3. Dans `docker-compose.yml`, retirer la section `ports:` du service
   `crop-tool` (il n'a plus à être joignable directement) et ajouter :

```yaml
  crop-auth:
    image: caddy:2-alpine
    restart: unless-stopped
    env_file:
      - .env
    ports:
      - "8502:8502"
    volumes:
      - ./decision-tool/deploy/Caddyfile:/etc/caddy/Caddyfile:ro
```

L'adresse ne change pas pour les utilisateurs : toujours le port 8502, avec
une demande de mot de passe en plus.

Sur une version de Caddy antérieure à 2.7, la directive s'écrit `basicauth`
en un mot. `docker compose logs crop-auth` le dit sans ambiguïté.

Le mot de passe doit différer de `PGPASSWORD`, de `WEBAPP_PASSWORD` et du mot
de passe SSH : trois portes, trois clés.
