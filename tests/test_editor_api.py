import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path('app/reasonreport').resolve()))
import app as reasonreport_app  # noqa: E402
import editor_api  # noqa: E402
import utils  # noqa: E402
from utils import generate_token  # noqa: E402


class EditorApiSecurityTest(unittest.TestCase):
    def setUp(self):
        reasonreport_app.app.config.update(TESTING=True)
        self.client = reasonreport_app.app.test_client()
        self.user = {'_id': 'user-id', 'username': 'alice'}
        self.token = generate_token('user-id')
        self.sessions = MagicMock()
        self.launches = MagicMock()
        self.launches.find_one_and_delete.return_value = None
        self.sessions.find_one.return_value = None
        self.notebooks = MagicMock()
        self.users = MagicMock()
        self.database = SimpleNamespace(
            editor_sessions=self.sessions,
            editor_launches=self.launches,
            notebooks=self.notebooks,
            users=self.users,
        )
        self.mongo_patch = patch.object(editor_api, 'mongo', SimpleNamespace(db=self.database))
        self.user_patch = patch.object(utils, 'get_user_by_id', return_value=self.user)
        self.mongo_patch.start()
        self.user_patch.start()
        self.addCleanup(self.mongo_patch.stop)
        self.addCleanup(self.user_patch.stop)

    def headers(self, editor_token='editor-token'):
        return {
            'Authorization': f'Bearer {self.token}',
            'Origin': 'https://localhost',
            'X-ReasonReport-Editor': 'jupyterlite',
            'X-ReasonReport-Editor-Token': editor_token,
        }

    def test_session_requires_authenticated_editor_context(self):
        response = self.client.post('/api/editor/session')
        self.assertEqual(response.status_code, 401)
        response = self.client.post(
            '/api/editor/session',
            headers={'Authorization': f'Bearer {self.token}'},
        )
        self.assertEqual(response.status_code, 403)

    def test_session_is_short_lived_and_stored_hashed(self):
        self.launches.find_one_and_delete.return_value = {'user_id': 'user-id'}
        response = self.client.post(
            '/api/editor/session',
            headers=self.headers(),
            json={'launch_nonce': 'launch-token'},
        )
        self.assertEqual(response.status_code, 201)
        stored = self.sessions.insert_one.call_args.args[0]
        self.assertNotEqual(stored['token_digest'], response.json['editor_token'])
        self.assertLessEqual(
            stored['expires_at'],
            datetime.now(timezone.utc) + timedelta(seconds=editor_api.SESSION_TTL_SECONDS + 1),
        )

    def test_launch_nonce_is_required_for_initial_session(self):
        response = self.client.post(
            '/api/editor/session',
            headers={
                'Authorization': f'Bearer {self.token}',
                'Origin': 'https://localhost',
                'X-ReasonReport-Editor': 'jupyterlite',
            },
            json={'launch_nonce': 'invalid'},
        )
        self.assertEqual(response.status_code, 403)

    def test_query_rejects_mongodb_operators(self):
        self.sessions.find_one.return_value = {'user_id': 'user-id'}
        response = self.client.post(
            '/api/editor/notebooks/query',
            headers=self.headers(),
            json={'filters': {'$where': 'malicious()'}},
        )
        self.assertEqual(response.status_code, 400)
        self.notebooks.find.assert_not_called()

    def test_editor_token_is_bound_to_authenticated_user(self):
        self.sessions.find_one.return_value = None
        response = self.client.get('/api/editor/notebooks', headers=self.headers())
        self.assertEqual(response.status_code, 401)
        query = self.sessions.find_one.call_args.args[0]
        self.assertEqual(query['user_id'], 'user-id')
        self.assertIn('expires_at', query)

    def test_admin_overview_is_restricted_to_admin(self):
        self.sessions.find_one.return_value = {'user_id': 'user-id'}
        response = self.client.get('/api/editor/admin/overview', headers=self.headers())

        self.assertEqual(response.status_code, 403)
        self.notebooks.find.assert_not_called()

    def test_admin_overview_returns_user_and_document_summary(self):
        self.user['username'] = 'admin'
        self.sessions.find_one.return_value = {'user_id': 'user-id'}
        cursor = MagicMock()
        cursor.sort.return_value.limit.return_value.__iter__.return_value = iter([{
            'title': 'Recent page',
            'slug': 'recent-page',
            'author': '507f1f77bcf86cd799439011',
        }])
        self.notebooks.find.return_value = cursor
        self.users.find.return_value = [{
            '_id': '507f1f77bcf86cd799439011',
            'username': 'Alice',
        }]
        self.users.count_documents.return_value = 7

        response = self.client.get('/api/editor/admin/overview', headers=self.headers())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['user_count'], 7)
        self.assertEqual(response.json['documents'], [{
            'title': 'Recent page',
            'slug': 'recent-page',
            'author': 'Alice',
        }])


if __name__ == '__main__':
    unittest.main()
