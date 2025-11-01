FROM python:3.12-slim

RUN apt-get update && apt-get install -y build-essential libffi-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

# Collect static files for WhiteNoise or for serving via CDN later
RUN mkdir -p /app/staticfiles && python manage.py collectstatic --noinput
ENV DJANGO_SETTINGS_MODULE=voiceguard_project.settings
ENV DEBUG=False


# Cloud Run listens on $PORT
ENV PORT=8080
CMD ["gunicorn","-k","uvicorn.workers.UvicornWorker","voiceguard_project.asgi:application","--bind","0.0.0.0:8080","--workers","2","--timeout","120"]
