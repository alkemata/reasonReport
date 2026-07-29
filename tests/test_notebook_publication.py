import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import nbformat

sys.path.insert(0, str(Path('app/reasonreport').resolve()))
import models  # noqa: E402


def publication_notebook(title):
    notebook = nbformat.v4.new_notebook()
    notebook.metadata['title'] = title
    notebook.cells = [
        nbformat.v4.new_markdown_cell('Ordinary user content'),
    ]
    return notebook


class NotebookPublicationTest(unittest.TestCase):
    def test_default_title_is_rejected_with_editor_message(self):
        with self.assertRaisesRegex(
            ValueError, 'Title must be different from "Please enter the title here"'
        ):
            models.build_notebook_document(
                '507f1f77bcf86cd799439011',
                'Alice',
                {'notebook': publication_notebook('# Please enter the title here #')},
            )

    def test_publication_sets_owner_and_slug_from_title(self):
        notebooks = MagicMock()
        notebooks.find_one.return_value = None
        with patch.object(
            models, 'mongo', SimpleNamespace(db=SimpleNamespace(notebooks=notebooks))
        ):
            document = models.build_notebook_document(
                '507f1f77bcf86cd799439011',
                'Alice',
                {'notebook': publication_notebook('# A Better Page #')},
            )

        self.assertEqual(document['owner_id'], '507f1f77bcf86cd799439011')
        self.assertEqual(document['title'], 'A Better Page')
        self.assertEqual(document['slug'], 'a-better-page')
        server_metadata_cells = [
            cell for cell in document['notebook'].cells
            if cell.metadata.get('type') in {'author', 'date'}
        ]
        self.assertEqual(server_metadata_cells, [])
        self.assertIn('created_at', document)
        self.assertIn('updated_at', document)

    def test_title_change_recalculates_existing_page_slug(self):
        notebooks = MagicMock()
        notebooks.find_one.return_value = None
        with patch.object(
            models, 'mongo', SimpleNamespace(db=SimpleNamespace(notebooks=notebooks))
        ):
            document = models.build_notebook_document(
                '507f1f77bcf86cd799439011',
                'Alice',
                {'notebook': publication_notebook('Renamed Page')},
                notebook_id='507f1f77bcf86cd799439011',
            )

        self.assertEqual(document['slug'], 'renamed-page')
        query = notebooks.find_one.call_args.args[0]
        self.assertEqual(query['slug'], 'renamed-page')
        self.assertIn('$ne', query['_id'])

    def test_publication_uses_only_first_line_as_title(self):
        notebooks = MagicMock()
        notebooks.find_one.return_value = None
        with patch.object(
            models, 'mongo', SimpleNamespace(db=SimpleNamespace(notebooks=notebooks))
        ):
            document = models.build_notebook_document(
                'user-id', 'Alice',
                {'notebook': publication_notebook('# First Line #\nSecond line')},
            )

        self.assertEqual(document['title'], 'First Line')
        self.assertEqual(document['slug'], 'first-line')

    def test_publication_limits_slug_source_to_fifty_title_characters(self):
        title = 'A' * 45 + ' five words after the limit'
        notebooks = MagicMock()
        notebooks.find_one.return_value = None
        with patch.object(
            models, 'mongo', SimpleNamespace(db=SimpleNamespace(notebooks=notebooks))
        ):
            document = models.build_notebook_document(
                'user-id', 'Alice', {'notebook': publication_notebook(title)}
            )

        self.assertEqual(document['title'], title)
        self.assertEqual(document['slug'], models.slugify(title[:50]))

    def test_new_notebook_uses_standard_title_metadata_only(self):
        notebook = models.create_notebook_content('user-id', 'Alice')

        self.assertEqual(notebook.metadata['title'], models.DEFAULT_TITLE)
        self.assertFalse(any(
            cell.metadata.get('type') in {'author', 'date', 'title'}
            for cell in notebook.cells
        ))

    def test_create_notebook_generates_id_before_building_document(self):
        notebooks = MagicMock()
        with patch.object(
            models, 'mongo', SimpleNamespace(db=SimpleNamespace(notebooks=notebooks))
        ):
            notebook_id = models.create_notebook('user-id', 'Alice')

        document = notebooks.insert_one.call_args.args[0]
        self.assertEqual(notebook_id, str(document['_id']))
        self.assertEqual(document['slug'], f"notebook-{notebook_id}")

    def test_legacy_author_and_date_cells_are_removed_without_user_content_loss(self):
        notebook = nbformat.v4.new_notebook(metadata={'title': 'Migrated Page'})
        notebook.cells = [
            nbformat.v4.new_markdown_cell('Author:'),
            nbformat.v4.new_markdown_cell('Old Author', metadata={'type': 'author'}),
            nbformat.v4.new_markdown_cell('Date of creation:'),
            nbformat.v4.new_markdown_cell('2020-01-01', metadata={'type': 'date'}),
            nbformat.v4.new_markdown_cell('Keep this user-authored paragraph.'),
        ]
        notebooks = MagicMock()
        notebooks.find_one.return_value = None
        with patch.object(
            models, 'mongo', SimpleNamespace(db=SimpleNamespace(notebooks=notebooks))
        ):
            document = models.build_notebook_document(
                'user-id', 'Alice', {'notebook': notebook}
            )

        self.assertEqual(
            [cell.source for cell in document['notebook'].cells],
            ['Keep this user-authored paragraph.'],
        )

    def test_forged_author_metadata_is_discarded(self):
        notebook = publication_notebook('Safe Page')
        notebook.cells.insert(0, nbformat.v4.new_markdown_cell(
            'Administrator', metadata={'type': 'author'}
        ))
        notebooks = MagicMock()
        notebooks.find_one.return_value = None
        with patch.object(
            models, 'mongo', SimpleNamespace(db=SimpleNamespace(notebooks=notebooks))
        ):
            document = models.build_notebook_document(
                'real-owner', 'Alice', {
                    'owner_id': 'forged-owner',
                    'author': 'Administrator',
                    'created_at': '1900-01-01',
                    'notebook': notebook,
                }
            )

        self.assertEqual(document['owner_id'], 'real-owner')
        self.assertFalse(any(
            cell.metadata.get('type') == 'author'
            for cell in document['notebook'].cells
        ))

    def test_save_preserves_creation_time_and_advances_update_time(self):
        notebook_id = '507f1f77bcf86cd799439011'
        created_at = models.datetime(2020, 1, 2, 3, 4, 5, tzinfo=models.timezone.utc)
        old_updated_at = models.datetime(2020, 1, 3, 3, 4, 5, tzinfo=models.timezone.utc)
        notebooks = MagicMock()
        notebooks.find_one.side_effect = [
            {'created_at': created_at, 'updated_at': old_updated_at},
            None,
        ]
        with patch.object(
            models, 'mongo', SimpleNamespace(db=SimpleNamespace(notebooks=notebooks))
        ):
            models.save_notebook(
                notebook_id, 'user-id', 'Alice',
                {'notebook': publication_notebook('Updated Page')},
            )

        update = notebooks.update_one.call_args.args[1]
        self.assertEqual(update['$set']['created_at'], created_at)
        self.assertGreater(update['$set']['updated_at'], old_updated_at)
        self.assertEqual(update['$unset'], {'author': '', 'date': ''})


if __name__ == '__main__':
    unittest.main()
