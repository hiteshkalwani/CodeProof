FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
# Runs as root only because it talks to the Docker socket to start sandboxes; see docs/ARCHITECTURE.md.
# Long timeout: a repair loop is several model calls plus sandbox runs in one request.
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn config.wsgi --bind 0.0.0.0:8000 --workers 3 --timeout 180 --access-logfile -"]
