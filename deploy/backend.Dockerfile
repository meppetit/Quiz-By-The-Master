FROM python:3.11-slim

WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

COPY requirements.txt .
RUN pip install -r requirements.txt gunicorn

COPY . .

ENV BACKEND_WORKERS=4
CMD gunicorn server:app -k uvicorn.workers.UvicornWorker \
    -w ${BACKEND_WORKERS} -b 0.0.0.0:8001 \
    --timeout 60 --graceful-timeout 30 --backlog 2048 --access-logfile -
