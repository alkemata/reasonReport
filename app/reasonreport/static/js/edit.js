(() => {
    'use strict';

    const iframe = document.getElementById('jupyterlite-iframe');
    if (!iframe) {
        return;
    }

    const documentId = iframe.dataset.documentId;
    const editorUrl = iframe.dataset.editorUrl;
    const editorNonce = iframe.dataset.editorNonce;
    const expectedOrigin = window.location.origin;
    let editorReady = false;
    let publishing = false;
    let closing = false;

    if (!documentId || !editorUrl || !editorNonce) {
        window.alert('The notebook editor configuration is incomplete.');
        return;
    }

    function send(command) {
        if (!iframe.contentWindow) {
            return;
        }
        iframe.contentWindow.postMessage(
            { source: 'reasonreport-parent', ...command },
            expectedOrigin
        );
    }

    function requestId() {
        if (window.crypto && typeof window.crypto.randomUUID === 'function') {
            return window.crypto.randomUUID();
        }
        return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    }

    function finishPublishing() {
        publishing = false;
        const publishButton = document.getElementById('publish-button');
        if (publishButton) {
            publishButton.disabled = false;
            publishButton.textContent = 'Publish';
        }
    }

    async function publishedSlug(message) {
        if (message.slug) {
            return message.slug;
        }
        if (!message.documentId) {
            return '';
        }
        const response = await fetch(
            `/api/notebooks/query/${encodeURIComponent(message.documentId)}`,
            { credentials: 'include' }
        );
        if (!response.ok) {
            return '';
        }
        const payload = await response.json();
        return typeof payload.slug === 'string' ? payload.slug : '';
    }

    function installEditorButtons() {
        const createControl = document.querySelector('.dropdown');
        if (createControl) {
            createControl.hidden = true;
        }

        const authButtons = document.getElementById('auth-buttons');
        if (!authButtons || document.getElementById('publish-button')) {
            return;
        }

        const publishButton = document.createElement('button');
        publishButton.id = 'publish-button';
        publishButton.textContent = 'Publish';
        publishButton.addEventListener('click', () => {
            if (!editorReady || publishing) {
                return;
            }
            publishing = true;
            publishButton.disabled = true;
            publishButton.textContent = 'Publishing…';
            send({
                msgtype: 'publish',
                documentId,
                requestId: requestId()
            });
        });

        const closeButton = document.createElement('button');
        closeButton.id = 'quit-editing-button';
        closeButton.textContent = 'Close editor';
        closeButton.addEventListener('click', () => {
            if (!editorReady || publishing || closing) {
                return;
            }
            closing = true;
            closeButton.disabled = true;
            closeButton.textContent = 'Closing…';
            send({ msgtype: 'cleanup', documentId });
        });

        authButtons.append(publishButton, closeButton);
    }

    window.addEventListener('message', async event => {
        if (
            event.origin !== expectedOrigin ||
            event.source !== iframe.contentWindow ||
            !event.data ||
            event.data.source !== 'reasonreport-jupyterlite'
        ) {
            return;
        }

        const message = event.data;
        if (message.msgtype === 'ready') {
            installEditorButtons();
            send({ msgtype: 'create', documentId, editorNonce });
        } else if (message.msgtype === 'loaded') {
            editorReady = true;
        } else if (message.msgtype === 'publish-result') {
            finishPublishing();
            const slug = await publishedSlug(message);
            if (!slug) {
                window.alert('The published page did not return a valid slug.');
                return;
            }
            window.location.assign(`/slug/${encodeURIComponent(slug)}`);
        } else if (message.msgtype === 'cleanup-result') {
            window.location.assign(documentId === '-1' ? '/' : `/id/${documentId}`);
        } else if (message.msgtype === 'error') {
            finishPublishing();
            closing = false;
            const closeButton = document.getElementById('quit-editing-button');
            if (closeButton) {
                closeButton.disabled = false;
                closeButton.textContent = 'Close editor';
            }
            window.alert(message.message || 'The notebook operation failed.');
        }
    });

    // Start JupyterLite only after the parent listener is installed, so its
    // one-time ready message cannot race the parent page initialization.
    iframe.src = editorUrl;
})();
