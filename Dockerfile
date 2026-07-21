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
RUN npm ci --no-audit --no-fund
RUN npm run build:prod
RUN extension_dir="$(python -c 'import sysconfig; print(sysconfig.get_path("data"))')/share/jupyter/labextensions/jupyter_flask_extension" \
    && mkdir -p "$extension_dir" \
    && cp -a jupyter_flask_extension_py/labextension/. "$extension_dir/"
RUN jupyter lite build --output-dir=/opt/jupyterlite
COPY scripts/externalize_inline_scripts.py /usr/local/bin/externalize-inline-scripts
RUN externalize-inline-scripts /opt/jupyterlite

WORKDIR /app/reasonreport
ENV JUPYTERLITE_PATH=/opt/jupyterlite
CMD flask run -h 0.0.0.0 -p 5000
