#!/usr/bin/env python3
"""
sync_photos.py — Publie les photos recadrées (feuilles, recouvrement) sur yamhub.fr.

Fait le pont entre la sortie des outils de recadrage et l'arborescence attendue
par les fiches variétales sur le serveur :

    data/feuilles/CIRADn.jpg                  ->  photos/feuilles/CIRADn.jpg
    data/recouvrement_1mois/CIRADn_1mois.jpg  ->  photos/recouvrement/1mois/CIRADn_1mois.jpg
    data/recouvrement_3mois/CIRADn_3mois.jpg  ->  photos/recouvrement/3mois/CIRADn_3mois.jpg

Ces dossiers sont exclus de git (volumineux) : ils passent donc par FTPS, pas par
le dépôt. Les URL correspondantes sont lues par fiche_html.py via LEAF_URL et
RECOUV_URL (secrets Streamlit Cloud).

Le transfert est INCRÉMENTAL : un fichier déjà présent sur le serveur avec la même
taille n'est pas renvoyé. Relancer le script après chaque session de recadrage
n'envoie donc que les nouveautés.

Identifiants (jamais versionnés) : ftp_credentials.txt — voir le modèle
ftp_credentials.txt.example. Ou variables d'environnement YAMHUB_FTP_HOST,
YAMHUB_FTP_USER, YAMHUB_FTP_PASS.

Usage :
  python sync_photos.py                  # feuilles + tous les stades de recouvrement
  python sync_photos.py --only 1mois     # un seul jeu (1mois, 3mois, feuilles)
  python sync_photos.py --dry-run        # liste ce qui partirait, n'envoie rien
  python sync_photos.py --force          # renvoie tout, même l'identique
"""
import argparse
import ftplib
import glob
import os
import re
import socket
import ssl
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
CRED_FILE = os.path.join(HERE, "ftp_credentials.txt")

# Racine distante, relative au dossier où atterrit le compte FTP. Chez
# Hostinger, ce compte ouvre sur / et non sur public_html : le site vit donc
# sous domains/<domaine>/public_html. Surchargeable par ROOT= dans
# ftp_credentials.txt, ou par YAMHUB_FTP_ROOT.
REMOTE_ROOT = os.environ.get("YAMHUB_FTP_ROOT",
                             "domains/yamhub.fr/public_html/photos")


# --------------------------------------------------------------------------
# Identifiants
# --------------------------------------------------------------------------
def load_credentials():
    """Lit ftp_credentials.txt (clé = valeur) puis complète par l'environnement."""
    cred = {}
    if os.path.exists(CRED_FILE):
        with open(CRED_FILE) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                cred[k.strip().upper()] = v.strip().strip('"').strip("'")
    for k in ("HOST", "USER", "PASS"):
        cred.setdefault(k, os.environ.get(f"YAMHUB_FTP_{k}", ""))
    if cred.get("ROOT"):                   # ROOT= dans le fichier a le dernier mot
        globals()["REMOTE_ROOT"] = cred["ROOT"].rstrip("/")
    missing = [k for k in ("HOST", "USER", "PASS") if not cred[k]]
    if missing:
        sys.exit(
            f"Identifiants FTP manquants : {', '.join(missing)}.\n"
            f"Crée {os.path.basename(CRED_FILE)} à partir du modèle "
            f"{os.path.basename(CRED_FILE)}.example, ou exporte YAMHUB_FTP_HOST / "
            f"_USER / _PASS."
        )
    return cred


def _ouvrir(cred, contexte):
    """Ouvre une session FTPS avec le contexte TLS donné. Lève telle quelle."""
    ftp = ftplib.FTP_TLS(context=contexte)
    ftp.connect(cred["HOST"], int(cred.get("PORT") or 21), timeout=30)
    ftp.login(cred["USER"], cred["PASS"])
    ftp.prot_p()                           # chiffre aussi le canal de données
    return ftp


def connect(cred):
    """Connexion FTPS explicite : le mot de passe ne circule jamais en clair.

    Le FTP simple transmet les identifiants en clair — inacceptable sur un
    réseau partagé. On reste donc en FTPS et on diagnostique précisément les
    trois échecs courants plutôt que de tout renvoyer sous « connexion
    impossible ».
    """
    hote = cred["HOST"]
    try:
        ftp = _ouvrir(cred, ssl.create_default_context())
    except socket.gaierror:
        sys.exit(f"Hôte introuvable : « {hote} ».\n"
                 f"Ce n'est pas un problème de mot de passe : le nom ne se "
                 f"résout pas.\nVérifie la ligne HOST de "
                 f"{os.path.basename(CRED_FILE)} — un « @ » ou un « ftp:// » "
                 f"collé devant l'adresse suffit à provoquer cette erreur.")
    except ssl.SSLCertVerificationError:
        # Cas Hostinger : le certificat est un wildcard mutualisé, valide pour
        # *.hstgr.io / *.main-hosting.eu mais PAS pour une adresse IP. On garde
        # le chiffrement (le mot de passe reste protégé) en renonçant à vérifier
        # l'identité du serveur, et on le dit franchement à chaque exécution.
        print(f"⚠  Le certificat TLS ne couvre pas « {hote} » (normal avec une "
              f"adresse IP chez Hostinger).\n"
              f"   La connexion reste chiffrée, mais l'identité du serveur "
              f"n'est pas vérifiée.\n"
              f"   Pour l'éviter, mets dans HOST le nom d'hôte FTP indiqué par "
              f"hPanel (Fichiers → Comptes FTP)\n"
              f"   plutôt que son adresse IP.\n")
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            ftp = _ouvrir(cred, ctx)
        except ftplib.error_perm as e:
            sys.exit(f"Identifiants refusés par le serveur ({e}).\n"
                     f"Vérifie USER et PASS dans {os.path.basename(CRED_FILE)}.")
    except ftplib.error_perm as e:
        sys.exit(f"Identifiants refusés par le serveur ({e}).\n"
                 f"Vérifie USER et PASS dans {os.path.basename(CRED_FILE)}.")
    except (ssl.SSLError, OSError) as e:
        sys.exit(f"Connexion à {hote} impossible ({e}).\n"
                 f"Serveur injoignable, port 21 fermé, ou FTPS non supporté.")
    ftp.set_pasv(True)
    ftp.voidcmd("TYPE I")                  # binaire : requis pour SIZE
    return ftp


# --------------------------------------------------------------------------
# Opérations distantes
# --------------------------------------------------------------------------
def ensure_dir(ftp, path):
    """Crée l'arborescence distante segment par segment (mkdir -p)."""
    cur = ""
    for part in path.strip("/").split("/"):
        cur = f"{cur}/{part}" if cur else part
        try:
            ftp.mkd(cur)
        except ftplib.error_perm:
            pass                            # existe déjà : cas normal


def remote_sizes(ftp, path):
    """{nom_fichier: taille} du dossier distant. {} s'il n'existe pas encore."""
    sizes = {}
    try:
        for name, facts in ftp.mlsd(path):
            if facts.get("type") == "file":
                sizes[name] = int(facts.get("size", -1))
        return sizes
    except ftplib.error_temp:
        return {}                           # dossier absent : il sera créé
    except (ftplib.error_perm, ftplib.error_proto):
        pass                                # serveur sans MLSD : repli ci-dessous
    try:
        for entry in ftp.nlst(path):
            name = entry.rsplit("/", 1)[-1]
            try:
                sizes[name] = ftp.size(f"{path}/{name}") or -1
            except ftplib.all_errors:
                sizes[name] = -1
    except (ftplib.error_perm, ftplib.error_temp):
        return {}                           # dossier absent
    return sizes


def sync_dir(ftp, local_dir, remote_dir, force=False, dry_run=False):
    """Envoie les .jpg de local_dir vers remote_dir. Retourne (envoyés, ignorés)."""
    files = sorted(
        f for f in os.listdir(local_dir)
        if f.lower().endswith((".jpg", ".jpeg")) and not f.startswith(".")
    )
    if not files:
        print(f"  (aucune photo dans {os.path.relpath(local_dir, HERE)})")
        return 0, 0

    existing = {} if force else remote_sizes(ftp, remote_dir)
    todo = [
        f for f in files
        if force or existing.get(f, -1) != os.path.getsize(os.path.join(local_dir, f))
    ]
    skipped = len(files) - len(todo)

    if not todo:
        print(f"  {len(files)} photos, déjà toutes à jour.")
        return 0, skipped

    total_mo = sum(os.path.getsize(os.path.join(local_dir, f)) for f in todo) / 1e6
    print(f"  {len(todo)} à envoyer ({total_mo:.0f} Mo), {skipped} déjà à jour.")
    if dry_run:
        for f in todo[:10]:
            print(f"    [simulation] {f}")
        if len(todo) > 10:
            print(f"    … et {len(todo) - 10} autres")
        return 0, skipped

    ensure_dir(ftp, remote_dir)
    sent = 0
    for i, f in enumerate(todo, 1):
        local = os.path.join(local_dir, f)
        try:
            with open(local, "rb") as fh:
                ftp.storbinary(f"STOR {remote_dir}/{f}", fh, blocksize=65536)
            sent += 1
        except ftplib.all_errors as e:      # inclut déjà OSError
            print(f"    ÉCHEC {f} : {e}")
            continue
        print(f"\r    {i}/{len(todo)}  {f}", end="", flush=True)
    print()
    return sent, skipped


# --------------------------------------------------------------------------
# Publication unitaire (utilisée par crop_tool.py)
# --------------------------------------------------------------------------
def credentials_available():
    """True si des identifiants FTP sont configurés — sans les lire ni les valider."""
    if os.path.exists(CRED_FILE):
        return True
    return all(os.environ.get(f"YAMHUB_FTP_{k}") for k in ("HOST", "USER", "PASS"))


def publish_file(local_path, stage):
    """Envoie UNE photo recadrée dans photos/recouvrement/<stage>/.

    Ouvre puis referme sa propre connexion : appelé au coup par coup depuis
    l'outil de recadrage, où les enregistrements sont espacés de plusieurs
    secondes (une connexion maintenue expirerait entre deux).
    Retourne (True, url) ou (False, message_d_erreur).
    """
    remote_dir = f"{REMOTE_ROOT}/recouvrement/{stage}"
    name = os.path.basename(local_path)
    try:
        ftp = connect(load_credentials())
    except SystemExit as e:
        return False, str(e)
    try:
        ensure_dir(ftp, remote_dir)
        with open(local_path, "rb") as fh:
            ftp.storbinary(f"STOR {remote_dir}/{name}", fh, blocksize=65536)
    except ftplib.all_errors as e:
        return False, f"Envoi FTP impossible : {e}"
    finally:
        try:
            ftp.quit()
        except ftplib.all_errors:
            ftp.close()
    public = REMOTE_ROOT.split("public_html/", 1)[-1]
    return True, f"https://yamhub.fr/{public}/recouvrement/{stage}/{name}"


# --------------------------------------------------------------------------
# Plan de synchronisation
# --------------------------------------------------------------------------
def build_plan(only=None):
    """[(étiquette, dossier_local, dossier_distant)] pour ce qui existe en local."""
    plan = []
    for nom in ("feuilles", "tubercules"):
        d = os.path.join(DATA, nom)
        if os.path.isdir(d):
            plan.append((nom, d, f"{REMOTE_ROOT}/{nom}"))
    for d in sorted(glob.glob(os.path.join(DATA, "recouvrement_*mois"))):
        stage = re.sub(r"^recouvrement_", "", os.path.basename(d))
        plan.append((stage, d, f"{REMOTE_ROOT}/recouvrement/{stage}"))
    if only:
        plan = [p for p in plan if p[0] == only]
        if not plan:
            sys.exit(f"Rien à synchroniser pour « {only} ». "
                     f"Valeurs possibles : feuilles, tubercules, 1mois, 3mois…")
    return plan


def main():
    ap = argparse.ArgumentParser(
        description="Publie les photos recadrées sur yamhub.fr (FTPS, incrémental).")
    ap.add_argument("--only", help="un seul jeu : feuilles, 1mois, 3mois…")
    ap.add_argument("--dry-run", action="store_true",
                    help="liste ce qui partirait sans rien envoyer")
    ap.add_argument("--force", action="store_true",
                    help="renvoie même les fichiers déjà identiques sur le serveur")
    args = ap.parse_args()

    plan = build_plan(args.only)
    if not plan:
        sys.exit("Aucun dossier de photos trouvé dans data/. "
                 "Lance d'abord crop_drone.py ou crop_tool.py.")

    ftp = connect(load_credentials())
    print(f"Connecté — racine distante : {REMOTE_ROOT}\n")

    total_sent = total_skip = 0
    try:
        for label, local_dir, remote_dir in plan:
            print(f"{label} -> {remote_dir}")
            sent, skipped = sync_dir(ftp, local_dir, remote_dir,
                                     args.force, args.dry_run)
            total_sent += sent
            total_skip += skipped
    finally:
        try:
            ftp.quit()
        except ftplib.all_errors:
            ftp.close()

    print(f"\nTerminé : {total_sent} envoyées, {total_skip} déjà à jour.")
    if total_sent and not args.dry_run:
        print("Vérifie une URL au hasard, par exemple :")
        print(f"  https://yamhub.fr/photos/recouvrement/1mois/CIRAD102_1mois.jpg")


if __name__ == "__main__":
    main()
