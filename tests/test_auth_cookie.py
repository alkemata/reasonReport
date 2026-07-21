import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path('app/reasonreport').resolve()))
import app as reasonreport_app  # noqa: E402
import resources  # noqa: E402
import utils  # noqa: E402
from utils import decode_token, generate_token  # noqa: E402


class AuthenticationCookieTest(unittest.TestCase):
    def setUp(self):
        reasonreport_app.app.config.update(
            TESTING=True,
            JWT_COOKIE_SECURE=True,
            JWT_ACCESS_TOKEN_EXPIRES=86400,
        )
        self.client = reasonreport_app.app.test_client()

    def test_generated_token_uses_configured_jwt_secret(self):
        token = generate_token('user-id')
        self.assertEqual(decode_token(token), 'user-id')

    def test_login_sets_api_cookie(self):
        with patch.object(reasonreport_app, 'authenticate_user', return_value='login-token'):
            response = self.client.post('/login?next=/create', data={
                'username': 'alice',
                'password': 'secret12',
            })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, '/create')
        cookie = response.headers['Set-Cookie']
        self.assertIn('jwt_token1=login-token', cookie)
        self.assertIn('Max-Age=86400', cookie)
        self.assertIn('Secure', cookie)
        self.assertIn('HttpOnly', cookie)
        self.assertIn('SameSite=Strict', cookie)
        self.assertIn('Path=/', cookie)

    def test_login_form_preserves_requested_destination(self):
        response = self.client.get('/login?next=/create')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'action="/login?next=/create"', response.data)

    def test_editor_redirects_anonymous_user_to_login(self):
        response = self.client.get('/edit/notebook-id')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, '/login?next=/edit/notebook-id')

    def test_registration_logs_user_in_before_opening_editor(self):
        with (
            patch.object(reasonreport_app, 'get_user_by_username', return_value=None),
            patch.object(reasonreport_app, 'create_user', return_value='user-id'),
            patch.object(reasonreport_app, 'create_notebook', return_value='notebook-id'),
            patch.object(reasonreport_app, 'generate_token', return_value='register-token'),
        ):
            response = self.client.post('/register', data={
                'username': 'alice',
                'password': 'secret12',
            })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, '/edit/notebook-id')
        self.assertIn('jwt_token1=register-token', response.headers['Set-Cookie'])

    def test_external_next_url_is_rejected(self):
        with patch.object(reasonreport_app, 'authenticate_user', return_value='token'):
            response = self.client.post('/login?next=https://attacker.example', data={
                'username': 'alice',
                'password': 'secret12',
            })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, '/')

    def test_logout_clears_only_authentication_cookie(self):
        self.client.set_cookie('jwt_token1', 'token')
        response = self.client.get('/logout')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, '/login')
        cookie = response.headers['Set-Cookie']
        self.assertIn('jwt_token1=', cookie)
        self.assertIn('Expires=Thu, 01 Jan 1970 00:00:00 GMT', cookie)

    def test_json_login_sets_cookie_without_exposing_password(self):
        user = {'_id': 'user-id', 'username': 'alice', 'password': 'hash'}
        with (
            patch.object(resources, 'authenticate_user', return_value='api-token'),
            patch.object(resources, 'get_user_by_username', return_value=user),
        ):
            response = self.client.post('/api/login', json={
                'username': 'alice',
                'password': 'secret12',
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['user']['username'], 'alice')
        self.assertNotIn('password', response.json['user'])
        self.assertIn('jwt_token1=api-token', response.headers['Set-Cookie'])

    def test_bearer_token_authenticates_current_user(self):
        user = {'_id': 'user-id', 'username': 'alice', 'password': 'hash'}
        token = generate_token('user-id')
        with (
            patch.object(utils, 'get_user_by_id', return_value=user),
            patch.object(resources, 'get_user_by_id', return_value=user),
        ):
            response = self.client.get(
                '/api/me',
                headers={'Authorization': f'Bearer {token}'},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['user']['username'], 'alice')
        self.assertNotIn('password', response.json['user'])


if __name__ == '__main__':
    unittest.main()
