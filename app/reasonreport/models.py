# models.py
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
from slugify import slugify
import nbformat
from nbconvert import HTMLExporter
from datetime import datetime
import json

mongo = PyMongo()
USER_ROLES = frozenset({'admin', 'editor', 'user'})

# User Operations
def create_user(username, password, landing_page=None, role='user', additional_fields=None):
    username = username.strip()
    if len(username) < 3:
        raise ValueError('Username must be at least 3 characters')
    if len(password) < 8:
        raise ValueError('Password must be at least 8 characters')
    if role not in USER_ROLES:
        raise ValueError(f"Role must be one of: {', '.join(sorted(USER_ROLES))}")
    if mongo.db.users.find_one({'username': username}):
        return None
    
    user = {
        'username': username,
        'password': generate_password_hash(password),
        'landing_page': landing_page or None,
        'role': role,
    }
    
    if additional_fields:
        user.update(additional_fields)
    if user.get('role') not in USER_ROLES:
        raise ValueError(f"Role must be one of: {', '.join(sorted(USER_ROLES))}")
    
    result = mongo.db.users.insert_one(user)
    return str(result.inserted_id)

def get_user_by_username(username):
    return mongo.db.users.find_one({'username': username})

def get_user_by_id(user_id):
    if not ObjectId.is_valid(str(user_id)):
        return None
    return mongo.db.users.find_one({'_id': ObjectId(user_id)})

def update_user(user_id, update_fields):
    if not ObjectId.is_valid(str(user_id)):
        return False
    if 'role' in update_fields and update_fields['role'] not in USER_ROLES:
        raise ValueError(f"Role must be one of: {', '.join(sorted(USER_ROLES))}")
    result = mongo.db.users.update_one({'_id': ObjectId(user_id)}, {'$set': update_fields})
    return result.matched_count > 0

def delete_user(user_id):
    if not ObjectId.is_valid(str(user_id)):
        return False
    result = mongo.db.users.delete_one({'_id': ObjectId(user_id)})
    mongo.db.notebooks.delete_many({'author': str(user_id)})
    return result.deleted_count > 0


# Notebook Operations
DEFAULT_TITLE = "Please enter the title here"


def create_notebook(author_id, author_name=None):
    nb = create_notebook_content(author_id, author_name)
    notebook = {
        'notebook': nb,
        'author': author_id,
        'date': datetime.utcnow(),
        'title': "",
        'slug': "",
        'is_public': False
    }
    result = mongo.db.notebooks.insert_one(notebook)
    return str(result.inserted_id)


def create_notebook_content(author_id, author_name=None):
    if not author_name:
        author = get_user_by_id(author_id)
        author_name = author['username'] if author else str(author_id)
    nb = nbformat.v4.new_notebook()
    
    # Pre-processing: Add three cells with tags author, date, and title
    cells = []
    
    # Author Cell
    cells.append(nbformat.v4.new_markdown_cell("Author:"))
    cells.append(nbformat.v4.new_markdown_cell(author_name))
    cells[-1].metadata['type']="author"
    
    # Date Cell
    cells.append(nbformat.v4.new_markdown_cell("Date of creation:"))
    cells.append(nbformat.v4.new_markdown_cell(f"{datetime.utcnow().isoformat()}"))
    cells[-1].metadata['type']="date"
    # Title Cell
    cells.append(nbformat.v4.new_markdown_cell(f"# Please enter the title here #"))
    cells[-1].metadata['type']="title"

    # Summary
    cells.append(nbformat.v4.new_markdown_cell("Summary:"))
    cells.append(nbformat.v4.new_markdown_cell(f" Please enter here a short introduction for your article "))
    cells[-1].metadata['type']="summary"
    
    nb['cells'] = cells
    
    return nb

def create_new_notebook(author_id, author_name, notebook_json):
    notebook = build_notebook_document(author_id, author_name, notebook_json)
    result = mongo.db.notebooks.insert_one(notebook)
    return str(result.inserted_id), notebook['slug']

def save_notebook(notebook_id, author_id, author_name, notebook_json):
    existing = mongo.db.notebooks.find_one({'_id': ObjectId(notebook_id)})
    if not existing:
        return "not_found"
    update_fields = build_notebook_document(
        author_id,
        author_name,
        notebook_json,
        notebook_id=notebook_id,
        created_at=existing.get('date')
    )
    mongo.db.notebooks.update_one({'_id': ObjectId(notebook_id)}, {'$set': update_fields})
    return update_fields['slug']


def build_notebook_document(author_id, author_name, notebook_json,
                            notebook_id=None, created_at=None):
    """Validate notebook JSON and derive safe server-side publication fields."""
    raw_notebook = notebook_json.get('notebook', notebook_json)
    try:
        nb = nbformat.from_dict(raw_notebook)
        nbformat.validate(nb)
    except Exception as error:
        raise ValueError(f"Invalid notebook: {error}") from error
    metadata = find_metadata_cells(nb)
    if metadata == "error":
        raise ValueError("Notebook requires non-empty title and date metadata cells")

    title = metadata['title'].strip().strip('#').strip()
    if title.casefold() == DEFAULT_TITLE.casefold():
        raise ValueError(f'Title must be different from "{DEFAULT_TITLE}"')
    initial_slug = slugify(title)
    if not initial_slug:
        raise ValueError("Notebook title must produce a valid slug")
    slug = ensure_unique_slug(initial_slug, notebook_id)
    set_author_cell(nb, author_name)
    return {
        'notebook': nb,
        'author': str(author_id),
        'slug': slug,
        'title': title,
        'date': created_at or datetime.utcnow(),
        'is_public': True
    }


def set_author_cell(notebook, author_name):
    """Set the visible author metadata cell from the authenticated user."""
    for cell in notebook.cells:
        if cell.metadata.get('type') == 'author':
            cell.source = author_name
            return
    notebook.cells.insert(
        0, nbformat.v4.new_markdown_cell(author_name, metadata={'type': 'author'})
    )

def get_notebook(query, user_id):
    if isinstance(query, str) and ObjectId.is_valid(query):
        notebook = mongo.db.notebooks.find_one({'_id': ObjectId(query)})
    else:
        notebook = mongo.db.notebooks.find_one({'slug': query})
    
    if notebook:
        if check_authorization(notebook, user_id):
            return notebook
        else:
            return {'message': 'not_authorized'}
    else:
        return {'message':'not found'}

def check_authorization(notebook, user_id):
    """
    Check if a user is authorized to access a notebook.
    The user must either be the author or the notebook must be public.
    """
    return notebook['author'] == str(user_id) or notebook.get('is_public', True) #TODO Check

def delete_notebook(notebook_id):
    mongo.db.notebooks.delete_one({'_id': ObjectId(notebook_id)})

def notebook_html(notebook):
    notebook_content = nbformat.from_dict(notebook)
    html_exporter = HTMLExporter(template_name="classic")
    (body, resources) = html_exporter.from_notebook_node(notebook_content)
    return body


def ensure_unique_slug(initial_slug, notebook_id=None):
    """
    Ensure the generated slug is unique in the database by appending a number if necessary.

    :param initial_slug: The initial slug generated from the title.
    :return: A unique slug that doesn't already exist in the MongoDB collection.
    """
    slug = initial_slug
    counter = 1
    
    # Keep checking if the slug exists in the database
    query = {'slug': slug}
    if notebook_id:
        query['_id'] = {'$ne': ObjectId(notebook_id)}
    while mongo.db.notebooks.find_one(query):
        # If it exists, append or increment the counter to make it unique
        slug = f"{initial_slug}-{counter}"
        query['slug'] = slug
        counter += 1
    
    return slug


def find_cells_by_metadata(notebook_json, key, value):
    """
    Find cells in a Jupyter Notebook file with a given metadata key and value.

    :param nb_path: Path to the Jupyter Notebook file (e.g., "notebook.ipynb").
    :param key: Metadata key to search for (e.g., "tags").
    :param value: Metadata value to match.
    :return: List of cells that match the given metadata key and value.
    """
    matching_cells = []
    for cell in notebook_json.get('cells', []):
        metadata = cell.get('metadata', {})
        
        # Check if metadata contains the key and value
        if key in metadata:
            # If the key holds a list (like tags), check if the value is in the list
            if isinstance(metadata[key], list) and value in metadata[key]:
                matching_cells.append(cell)
            # Otherwise, match directly to the value
            elif metadata[key] == value:
                matching_cells.append(cell)
    return matching_cells

def find_metadata_cells(notebook_data):
    """
    Find cells with metadata "type" values of "title", "author", "date", or "summary".
    Check that they are not empty and return required information if all are present.

    :param nb_path: Path to the Jupyter Notebook file (e.g., "notebook.ipynb").
    :return: A dictionary containing author, slug, and date if successful. Otherwise, raises an error.
    """
    required_types = ["title", "date"]
    metadata_values = {key: None for key in required_types}

    # Iterate through the notebook cells to find required metadata
    for cell in notebook_data.cells:
        metadata = cell.metadata
        if 'type' in metadata and metadata['type'] in required_types:
            # Store the cell's content if it matches one of the required types
            if cell.cell_type == 'markdown' or cell.cell_type == 'raw':
                metadata_values[metadata['type']] = ''.join(cell.source).strip()

    # Check if any of the required metadata is missing or empty
    missing_or_empty = [key for key, value in metadata_values.items() if not value]
    if missing_or_empty:
        return "error"

    # Create and return the resulting structure
    result = {
        'date': metadata_values['date'],
        'title':metadata_values['title']
    }

    return result
