# Image de l'outil d'aide au choix variétal YamHub.
#
# Construite en deux temps : les dépendances système de WeasyPrint (pango,
# cairo) puis les paquets Python. Séparer les deux garde le cache Docker utile
# quand seul le code change.
FROM python:3.11-slim

# WeasyPrint génère les fiches PDF : sans ces bibliothèques il échoue au
# rendu, pas à l'import — l'erreur n'apparaîtrait qu'au premier téléchargement.
# La liste reprend packages.txt, utilisé par Streamlit Cloud.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libpangoft2-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        libcairo2 \
        libffi-dev \
        libjpeg-dev \
        shared-mime-info \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Les dépendances d'abord : cette couche n'est refaite que si requirements
# change, pas à chaque modification du code.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Utilisateur non privilégié : rien ici n'a besoin de root.
RUN useradd -m -u 1000 yamhub && chown -R yamhub:yamhub /app
USER yamhub

EXPOSE 8501

# Streamlit répond sur /_stcore/health : Docker peut donc distinguer un
# conteneur démarré d'une app réellement prête, et le relancer sinon.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
