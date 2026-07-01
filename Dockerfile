FROM python:3.11-slim

WORKDIR /app

# Systemabhängigkeiten installieren
# Systemabhängigkeiten installieren
RUN apt-get update && apt-get install -y \
    build-essential \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Abhängigkeiten installieren
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Anwendungscode kopieren
COPY ./app ./app

EXPOSE 8000

# Start der App (z. B. aus app/main.py mit "app" als FastAPI-Instanz)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
