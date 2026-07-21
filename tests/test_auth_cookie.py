import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path('app/reasonreport').resolve()))
import app as reasonreport_app  # noqa: E402
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
                'password': 'secret',
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

    def test_registration_logs_user_in_before_opening_editor(self):
        with (
            patch.object(reasonreport_app, 'get_user_by_username', return_value=None),
            patch.object(reasonreport_app, 'create_user', return_value='user-id'),
            patch.object(reasonreport_app, 'create_notebook', return_value='notebook-id'),
            patch.object(reasonreport_app, 'generate_token', return_value='register-token'),
        ):
            response = self.client.post('/register', data={
                'username': 'alice',
                'password': 'secret',
            })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, '/edit/notebook-id')
        self.assertIn('jwt_token1=register-token', response.headers['Set-Cookie'])

    def test_external_next_url_is_rejected(self):
        with patch.object(reasonreport_app, 'authenticate_user', return_value='token'):
            response = self.client.post('/login?next=https://attacker.example', data={
                'username': 'alice',
                'password': 'secret',
            })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, '/')


if __name__ == '__main__':
    unittest.main()
