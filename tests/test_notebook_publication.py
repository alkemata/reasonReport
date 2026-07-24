import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import nbformat

sys.path.insert(0, str(Path('app/reasonreport').resolve()))
import models  # noqa: E402


def publication_notebook(title, author=''):
    notebook = nbformat.v4.new_notebook()
    notebook.cells = [
        nbformat.v4.new_markdown_cell(author, metadata={'type': 'author'}),
        nbformat.v4.new_markdown_cell(title, metadata={'type': 'title'}),
        nbformat.v4.new_markdown_cell('2026-07-23', metadata={'type': 'date'}),
    ]
    return notebook


class NotebookPublicationTest(unittest.TestCase):
    def test_default_title_is_rejected_with_editor_message(self):
        with self.assertRaisesRegex(
            ValueError, 'Title must be different from "Please enter the title here"'
        ):
            models.build_notebook_document(
                'user-id',
                'Alice',
                {'notebook': publication_notebook('# Please enter the title here #')},
            )

    def test_publication_sets_author_and_slug_from_title(self):
        notebooks = MagicMock()
        notebooks.find_one.return_value = None
        with patch.object(
            models, 'mongo', SimpleNamespace(db=SimpleNamespace(notebooks=notebooks))
        ):
            document = models.build_notebook_document(
                'user-id',
                'Alice',
                {'notebook': publication_notebook('# A Better Page #')},
            )

        self.assertEqual(document['author'], 'user-id')
        self.assertEqual(document['title'], 'A Better Page')
        self.assertEqual(document['slug'], 'a-better-page')
        author_cells = [
            cell for cell in document['notebook'].cells
            if cell.metadata.get('type') == 'author'
        ]
        self.assertEqual(author_cells[0].source, 'Alice')

    def test_title_change_recalculates_existing_page_slug(self):
        notebooks = MagicMock()
        notebooks.find_one.return_value = None
        with patch.object(
            models, 'mongo', SimpleNamespace(db=SimpleNamespace(notebooks=notebooks))
        ):
            document = models.build_notebook_document(
                'user-id',
                'Alice',
                {'notebook': publication_notebook('Renamed Page')},
                notebook_id='507f1f77bcf86cd799439011',
            )

        self.assertEqual(document['slug'], 'renamed-page')
        query = notebooks.find_one.call_args.args[0]
        self.assertEqual(query['slug'], 'renamed-page')
        self.assertIn('$ne', query['_id'])


if __name__ == '__main__':
    unittest.main()
