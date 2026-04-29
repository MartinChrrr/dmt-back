# Dockerfile
FROM python:3.11-slim

# Variables d'environnement
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Répertoire de travail
WORKDIR /app

# Installation des dépendances système (+ WeasyPrint)
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    libcairo2 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copie et installation des dépendances Python
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copie du projet
COPY . /app/

# Expose le port
EXPOSE 8000

# Lance le script de démarrage par défaut (utilisé en prod sur Render)
CMD ["./start.sh"]