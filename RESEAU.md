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
