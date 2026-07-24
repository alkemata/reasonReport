import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path('app/reasonreport').resolve()))
import models  # noqa: E402


class UserRoleTest(unittest.TestCase):
    def test_create_user_stores_selected_role(self):
        users = MagicMock()
        users.find_one.return_value = None
        users.insert_one.return_value = SimpleNamespace(inserted_id='user-id')

        with patch.object(models.mongo, 'db', SimpleNamespace(users=users)):
            user_id = models.create_user('alice', 'secret12', role='editor')

        self.assertEqual(user_id, 'user-id')
        stored_user = users.insert_one.call_args.args[0]
        self.assertEqual(stored_user['role'], 'editor')

    def test_create_user_rejects_unknown_role(self):
        with self.assertRaisesRegex(ValueError, 'Role must be one of'):
            models.create_user('alice', 'secret12', role='owner')


if __name__ == '__main__':
    unittest.main()
