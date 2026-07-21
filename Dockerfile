# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt requirements.txt
RUN apt-get update \
    && apt-get install --no-install-recommends -y nodejs npm \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt

COPY flask_extension /build/flask_extension
WORKDIR /build/flask_extension
RUN jlpm install \
    && jlpm build:prod \
    && extension_dir="$(python -c 'import sysconfig; print(sysconfig.get_path("data"))')/share/jupyter/labextensions/jupyter_flask_extension" \
    && mkdir -p "$extension_dir" \
    && cp -a jupyter_flask_extension_py/labextension/. "$extension_dir/" \
    && jupyter lite build --output-dir=/opt/jupyterlite \
    && rm -rf node_modules

WORKDIR /app/reasonreport
ENV JUPYTERLITE_PATH=/opt/jupyterlite
CMD flask run --debug -h 0.0.0.0 -p 5000
