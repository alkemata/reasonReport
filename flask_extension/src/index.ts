import { JupyterFrontEnd, JupyterFrontEndPlugin } from '@jupyterlab/application';
import { IDocumentManager } from '@jupyterlab/docmanager';
import { INotebookTracker } from '@jupyterlab/notebook';

type ParentCommand =
  | { msgtype: 'create'; documentId: string; editorNonce: string }
  | { msgtype: 'publish'; documentId: string; requestId?: string };

interface BridgeResponse {
  source: 'reasonreport-jupyterlite';
  msgtype: 'ready' | 'loaded' | 'publish-result' | 'error';
  requestId?: string;
  documentId?: string;
  slug?: string;
  message?: string;
}

interface NotebookPayload {
  cells: unknown[];
  metadata: Record<string, unknown>;
  nbformat: number;
  nbformat_minor: number;
}

const SOURCE = 'reasonreport-parent';

function parentOrigin(): string {
  if (!document.referrer) {
    return window.location.origin;
  }
  return new URL(document.referrer).origin;
}

function sendToParent(message: BridgeResponse): void {
  window.parent.postMessage(message, parentOrigin());
}

function isCommand(value: unknown): value is ParentCommand {
  if (!value || typeof value !== 'object') {
    return false;
  }
  const command = value as Record<string, unknown>;
  const validType = command.msgtype === 'create' || command.msgtype === 'publish';
  const validNonce = command.msgtype !== 'create' || typeof command.editorNonce === 'string';
  return (
    command.source === SOURCE &&
    typeof command.documentId === 'string' &&
    validType &&
    validNonce
  );
}

async function requestJSON(url: string, init: RequestInit = {}): Promise<any> {
  const response = await fetch(url, {
    ...init,
    credentials: 'include',
    headers: {
      Accept: 'application/json',
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...init.headers
    }
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.message || `ReasonReport request failed (${response.status})`);
  }
  return payload;
}

async function provisionPythonClient(
  documentManager: IDocumentManager,
  editorNonce: string
): Promise<void> {
  const session = await requestJSON('/api/editor/session', {
    method: 'POST',
    headers: { 'X-ReasonReport-Editor': 'jupyterlite' },
    body: JSON.stringify({ launch_nonce: editorNonce })
  });
  const moduleResponse = await fetch('/static/python/reasonreport.py', {
    credentials: 'include'
  });
  if (!moduleResponse.ok) {
    throw new Error('ReasonReport Python client could not be loaded.');
  }
  const contents = documentManager.services.contents;
  await contents.save('reasonreport.py', {
    type: 'file',
    format: 'text',
    content: await moduleResponse.text()
  });
  await contents.save('.reasonreport-session.json', {
    type: 'file',
    format: 'text',
    content: JSON.stringify(session)
  });
}

async function openNotebook(
  documentId: string,
  documentManager: IDocumentManager
): Promise<void> {
  const payload = await requestJSON(`/api/notebooks/query/${encodeURIComponent(documentId)}`);
  const notebook = payload.notebook as NotebookPayload;
  const filename = `reasonreport-${documentId === '-1' ? 'new' : documentId}.ipynb`;
  const contents = documentManager.services.contents;

  await contents.save(filename, {
    type: 'notebook',
    format: 'json',
    content: notebook
  });
  documentManager.openOrReveal(filename, 'Notebook');
  sendToParent({
    source: 'reasonreport-jupyterlite',
    msgtype: 'loaded',
    documentId
  });
}

async function publishNotebook(
  documentId: string,
  requestId: string | undefined,
  tracker: INotebookTracker
): Promise<void> {
  const panel = tracker.currentWidget;
  if (!panel) {
    throw new Error('No notebook is currently open.');
  }

  await panel.context.save();
  const notebook = panel.content.model?.toJSON();
  if (!notebook) {
    throw new Error('The active notebook could not be serialized.');
  }

  const isNew = documentId === '-1';
  const url = isNew
    ? '/api/notebooks/create'
    : `/api/notebooks/save/${encodeURIComponent(documentId)}`;
  const payload = await requestJSON(url, {
    method: isNew ? 'POST' : 'PUT',
    body: JSON.stringify({ notebook })
  });
  if (typeof payload.slug !== 'string' || !payload.slug) {
    throw new Error(
      'The server did not return a valid page slug. Correct the page and publish again.'
    );
  }
  sendToParent({
    source: 'reasonreport-jupyterlite',
    msgtype: 'publish-result',
    requestId,
    documentId: payload.notebook_id || documentId,
    slug: payload.slug
  });
}

const plugin: JupyterFrontEndPlugin<void> = {
  id: '@reasonreport/jupyterlite-extension:plugin',
  description: 'Bridge between JupyterLite and the ReasonReport Flask application.',
  autoStart: true,
  requires: [IDocumentManager, INotebookTracker],
  activate: (
    app: JupyterFrontEnd,
    documentManager: IDocumentManager,
    tracker: INotebookTracker
  ): void => {
    void app.restored.then(async () => {
      window.addEventListener('message', event => {
        if (
          event.source !== window.parent ||
          event.origin !== parentOrigin() ||
          !isCommand(event.data)
        ) {
          return;
        }

        const command = event.data;
        const operation =
          command.msgtype === 'create'
            ? provisionPythonClient(documentManager, command.editorNonce).then(() =>
                openNotebook(command.documentId, documentManager)
              )
            : publishNotebook(command.documentId, command.requestId, tracker);

        void operation.catch(error => {
          sendToParent({
            source: 'reasonreport-jupyterlite',
            msgtype: 'error',
            requestId: command.msgtype === 'publish' ? command.requestId : undefined,
            documentId: command.documentId,
            message: error instanceof Error ? error.message : String(error)
          });
        });
      });

      sendToParent({ source: 'reasonreport-jupyterlite', msgtype: 'ready' });
    });
  }
};

export default plugin;
