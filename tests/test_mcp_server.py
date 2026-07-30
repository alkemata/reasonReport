import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path('app').resolve()))

from reasonreport_mcp.tokens import token_digest  # noqa: E402
from reasonreport_mcp.service import KnowledgeService  # noqa: E402


class McpSecurityTest(unittest.TestCase):
    def test_token_hash_is_peppered_and_deterministic(self):
        digest = token_digest('rrmcp_secret', 'pepper-one')
        self.assertEqual(digest, token_digest('rrmcp_secret', 'pepper-one'))
        self.assertNotEqual(digest, token_digest('rrmcp_secret', 'pepper-two'))
        self.assertNotIn('secret', digest)

    def test_tags_are_normalized_deduplicated_and_bounded(self):
        self.assertEqual(KnowledgeService._validate_tags([' AI ', 'ai', 'Notes']), ['ai', 'notes'])
        with self.assertRaisesRegex(ValueError, 'at most 30'):
            KnowledgeService._validate_tags([str(value) for value in range(31)])

    def test_owner_query_supports_current_and_legacy_schema(self):
        user_id = '507f1f77bcf86cd799439011'
        values = KnowledgeService._owner_query(user_id)['$in']
        self.assertIn(user_id, values)
        self.assertIn('507f1f77bcf86cd799439011', [str(value) for value in values])


if __name__ == '__main__':
    unittest.main()
