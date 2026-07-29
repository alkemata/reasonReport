import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path('app/reasonreport').resolve()))
import database_init  # noqa: E402


class DatabaseInitializationTest(unittest.TestCase):
    def test_initialization_creates_all_collections_and_indexes(self):
        db = MagicMock()
        db.list_collection_names.return_value = []
        collections = {name: MagicMock() for name in database_init.INDEXES}
        db.__getitem__.side_effect = collections.__getitem__
        database_init.initialize_database(db)

        created = {call.args[0] for call in db.create_collection.call_args_list}
        self.assertEqual(created, set(database_init.COLLECTION_VALIDATORS))
        self.assertEqual(db.command.call_count, len(database_init.COLLECTION_VALIDATORS))
        for name, indexes in database_init.INDEXES.items():
            self.assertEqual(collections[name].create_index.call_count, len(indexes))

    def test_notebook_validator_defaults_visibility_to_an_explicit_enum(self):
        schema = database_init.COLLECTION_VALIDATORS['notebooks']['$jsonSchema']
        self.assertIn('visibility', schema['required'])
        self.assertEqual(
            schema['properties']['visibility']['enum'],
            ['private', 'restricted', 'public'],
        )


if __name__ == '__main__':
    unittest.main()
