"""Async ReasonReport client for notebooks running in the JupyterLite Pyodide kernel."""

import json
from pathlib import Path
from urllib.parse import quote

from pyodide.http import pyfetch

_CONFIG_PATH = Path('.reasonreport-session.json')


def _config():
    if not _CONFIG_PATH.exists():
        raise RuntimeError('ReasonReport editor credentials are unavailable; reopen the notebook from ReasonReport.')
    return json.loads(_CONFIG_PATH.read_text(encoding='utf-8'))


async def _request(path, method='GET', payload=None, retry=True):
    config = _config()
    headers = {
        'Accept': 'application/json',
        'X-ReasonReport-Editor': 'jupyterlite',
        'X-ReasonReport-Editor-Token': config['editor_token'],
    }
    kwargs = {'method': method, 'headers': headers, 'credentials': 'include'}
    if payload is not None:
        headers['Content-Type'] = 'application/json'
        kwargs['body'] = json.dumps(payload)
    response = await pyfetch(path, **kwargs)
    if response.status == 401 and retry:
        await refresh_session()
        return await _request(path, method, payload, retry=False)
    data = await response.json()
    if not response.ok:
        raise PermissionError(data.get('message', f'ReasonReport API error {response.status}'))
    return data


async def refresh_session():
    config = _config()
    response = await pyfetch(
        '/api/editor/session',
        method='POST',
        headers={
            'Accept': 'application/json',
            'X-ReasonReport-Editor': 'jupyterlite',
            'X-ReasonReport-Editor-Token': config['editor_token'],
        },
        credentials='include',
    )
    data = await response.json()
    if not response.ok:
        raise PermissionError(data.get('message', 'Unable to renew editor credentials'))
    _CONFIG_PATH.write_text(json.dumps(data), encoding='utf-8')
    return data['expires_at']


async def list_documents(limit=50):
    """List notebooks the logged-in user may read."""
    return (await _request(f'/api/editor/notebooks?limit={int(limit)}'))['documents']


async def get_document(notebook_id):
    """Read a notebook by ID when it is public or owned by the logged-in user."""
    return (await _request(f'/api/editor/notebooks/{quote(str(notebook_id), safe="")}'))['document']


async def query_documents(filters=None, limit=50):
    """Query allowlisted metadata fields without exposing arbitrary MongoDB operators."""
    return (await _request(
        '/api/editor/notebooks/query',
        method='POST',
        payload={'filters': filters or {}, 'limit': int(limit)},
    ))['documents']


async def admin_overview():
    """Return user count and the 10 newest pages; available only to admin."""
    return await _request('/api/editor/admin/overview')
