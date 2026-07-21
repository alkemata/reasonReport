import { JupyterFrontEnd, JupyterFrontEndPlugin } from '@jupyterlab/application';
import { IDocumentManager } from '@jupyterlab/docmanager';
import { INotebookTracker } from '@jupyterlab/notebook';

type ParentCommand =
  | { msgtype: 'create'; documentId: string }
  | { msgtype: 'publish'; documentId: string; requestId?: string };

interface BridgeResponse {
  source: 'reasonreport-jupyterlite';
  msgtype: 'ready' | 'loaded' | 'publish-result' | 'error';
  requestId?: string;
  documentId?: string;
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
  return (
    command.source === SOURCE &&
    typeof command.documentId === 'string' &&
    (command.msgtype === 'create' || command.msgtype === 'publish')
  );
}

async function requestJSON(url: string, init: RequestInit = {}): Promise<any> {
  const response = await fetch(url, {
    ...init,
    credentials: 'same-origin',
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
  sendToParent({
    source: 'reasonreport-jupyterlite',
    msgtype: 'publish-result',
    requestId,
    documentId: payload.notebook_id || documentId
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
    void app.restored.then(() => {
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
            ? openNotebook(command.documentId, documentManager)
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
