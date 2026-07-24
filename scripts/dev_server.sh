#!/bin/sh
set -eu

extension_signature() {
    find /build/flask_extension/src -type f -print0 \
        | sort -z \
        | xargs -0 sha256sum \
        | sha256sum \
        | cut -d ' ' -f 1
}

rebuild_extension() {
    echo "JupyterLite extension changed; rebuilding..."
    cd /build/flask_extension
    npm run build:prod
    extension_dir="$(python -c 'import sysconfig; print(sysconfig.get_path("data"))')/share/jupyter/labextensions/jupyter_flask_extension"
    mkdir -p "$extension_dir"
    rm -rf "$extension_dir"/*
    cp -a jupyter_flask_extension_py/labextension/. "$extension_dir/"
    jupyter lite build \
        --contents=/build/jupyterlite-content \
        --output-dir=/opt/jupyterlite
    externalize-inline-scripts /opt/jupyterlite
    echo "JupyterLite extension rebuild complete; reload the editor page."
}

watch_extension() {
    previous="$(extension_signature)"
    while sleep 2; do
        current="$(extension_signature)"
        if [ "$current" != "$previous" ]; then
            if rebuild_extension; then
                previous="$current"
            else
                echo "JupyterLite extension rebuild failed; waiting for another change." >&2
            fi
        fi
    done
}

watch_extension &
cd /app/reasonreport
exec flask run --debug -h 0.0.0.0 -p 5000
