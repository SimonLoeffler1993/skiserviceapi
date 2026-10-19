FROM python:3.11-slim

WORKDIR /app

# Systemabhängigkeiten installieren
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz-subset0 \
    libffi-dev \
    shared-mime-info \
    fontconfig \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Abhängigkeiten installieren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Anwendungscode kopieren
COPY ./app ./app
COPY alembic.ini .
COPY ./alembic ./alembic

# Entrypoint kopieren und ausführbar machen
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]