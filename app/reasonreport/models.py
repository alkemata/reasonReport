# models.py
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash
from bson.objectid import ObjectId
from slugify import slugify
import nbformat
from nbconvert import HTMLExporter
from datetime import datetime, timezone

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
        'username_normalized': username.casefold(),
        'password': generate_password_hash(password),
        'landing_page': landing_page or None,
        'role': role,
        'status': 'active',
        'created_at': datetime.now(timezone.utc),
    }
    
    if additional_fields:
        user.update(additional_fields)
    if user.get('role') not in USER_ROLES:
        raise ValueError(f"Role must be one of: {', '.join(sorted(USER_ROLES))}")
    
    result = mongo.db.users.insert_one(user)
    return str(result.inserted_id)

def get_user_by_username(username):
    return mongo.db.users.find_one({'username_normalized': username.strip().casefold()})

def get_user_by_id(user_id):
    if not ObjectId.is_valid(str(user_id)):
        return None
    return mongo.db.users.find_one({'_id': ObjectId(user_id)})

def update_user(user_id, update_fields):
    if not ObjectId.is_valid(str(user_id)):
        return False
    if 'role' in update_fields and update_fields['role'] not in USER_ROLES:
        raise ValueError(f"Role must be one of: {', '.join(sorted(USER_ROLES))}")
    if 'username' in update_fields:
        update_fields['username_normalized'] = update_fields['username'].strip().casefold()
    result = mongo.db.users.update_one({'_id': ObjectId(user_id)}, {'$set': update_fields})
    return result.matched_count > 0

def delete_user(user_id):
    if not ObjectId.is_valid(str(user_id)):
        return False
    result = mongo.db.users.delete_one({'_id': ObjectId(user_id)})
    mongo.db.notebooks.delete_many({'$or': [
        {'owner_id': str(user_id)}, {'author': str(user_id)}
    ]})
    return result.deleted_count > 0


# Notebook Operations
DEFAULT_TITLE = "Please enter the title here"


def create_notebook(author_id, author_name=None):
    nb = create_notebook_content(author_id, author_name)
    now = datetime.now(timezone.utc)
    notebook_id = ObjectId()
    notebook = {
        '_id': notebook_id,
        'notebook': nb,
        'owner_id': str(author_id),
        'created_at': now,
        'updated_at': now,
        'title': "",
        'slug': f"notebook-{notebook_id}",
        'visibility': 'private',
        'allowed_user_ids': [],
        'topic_ids': [],
        'revision': 1,
    }
    mongo.db.notebooks.insert_one(notebook)
    return str(notebook_id)


def create_notebook_content(author_id, author_name=None):
    nb = nbformat.v4.new_notebook()
    # The editor owns the title. Identity and timestamps are deliberately absent
    # from the client-editable notebook and are stored on the Mongo document.
    nb.metadata['title'] = DEFAULT_TITLE
    cells = []

    # Summary
    cells.append(nbformat.v4.new_markdown_cell("Summary:"))
    cells.append(nbformat.v4.new_markdown_cell(" Please enter here a short introduction for your article "))
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
        created_at=existing.get('created_at', existing.get('date'))
    )
    mongo.db.notebooks.update_one(
        {'_id': ObjectId(notebook_id)},
        {'$set': update_fields, '$unset': {'author': '', 'date': ''}}
    )
    return update_fields['slug']


def build_notebook_document(author_id, author_name, notebook_json,
                            notebook_id=None, created_at=None, revision=1):
    """Validate notebook JSON and derive safe server-side publication fields."""
    raw_notebook = notebook_json.get('notebook', notebook_json)
    try:
        nb = nbformat.from_dict(raw_notebook)
        nbformat.validate(nb)
    except Exception as error:
        raise ValueError(f"Invalid notebook: {error}") from error
    metadata = find_metadata_cells(nb)
    if metadata == "error":
        raise ValueError("Notebook requires a non-empty title in notebook metadata")

    title = metadata['title'].strip().strip('#').strip()
    if title.casefold() == DEFAULT_TITLE.casefold():
        raise ValueError(f'Title must be different from "{DEFAULT_TITLE}"')
    initial_slug = slugify(title)
    if not initial_slug:
        raise ValueError("Notebook title must produce a valid slug")
    slug = ensure_unique_slug(initial_slug, notebook_id)
    nb.metadata['title'] = title
    set_author_cell(nb, author_name)
    now = datetime.now(timezone.utc)
    return {
        'notebook': nb,
        'owner_id': str(author_id),
        'slug': slug,
        'title': title,
        'created_at': created_at or now,
        'updated_at': now,
        'is_public': True
    }


def set_author_cell(notebook, author_name):
    """Remove client-editable legacy identity and timestamp cells.

    ``author_name`` remains in the signature for callers using the old API, but
    is intentionally ignored.  An author is resolved from ``owner_id`` when a
    document is read, never copied into notebook content.
    """
    legacy_types = {'author', 'date'}
    cleaned = []
    for cell in notebook.cells:
        cell_type = cell.metadata.get('type')
        if cell_type in legacy_types:
            label = 'Author:' if cell_type == 'author' else 'Date of creation:'
            if cleaned and cleaned[-1].cell_type == 'markdown' \
                    and cleaned[-1].source.strip() == label:
                cleaned.pop()
            continue
        cleaned.append(cell)
    notebook.cells = cleaned

def get_notebook(query, user_id):
    if isinstance(query, str) and ObjectId.is_valid(query):
        notebook = mongo.db.notebooks.find_one({'_id': ObjectId(query)})
    else:
        notebook = mongo.db.notebooks.find_one({'slug': query})
    
    if notebook:
        if check_authorization(notebook, user_id):
            owner_id = str(notebook.get('owner_id', notebook.get('author', '')))
            notebook['owner_id'] = owner_id
            owner = get_user_by_id(owner_id)
            notebook['author'] = owner.get('username', 'Unknown') if owner else 'Unknown'
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
    owner_id = notebook.get('owner_id', notebook.get('author'))
    return str(owner_id) == str(user_id) or notebook.get('is_public', True) #TODO Check

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
    Read the title from standard notebook metadata.

    A legacy ``type=title`` cell is accepted as a one-way migration path. Author
    and date cells are never read because those values are server-owned.

    :param notebook_data: A parsed Jupyter notebook.
    :return: A dictionary containing the title, or ``"error"`` when absent.
    """
    title = notebook_data.metadata.get('title', '')
    if not isinstance(title, str):
        return "error"
    title = title.strip()
    if not title:
        for cell in notebook_data.cells:
            if (cell.metadata.get('type') == 'title'
                    and cell.cell_type in {'markdown', 'raw'}):
                title = ''.join(cell.source).strip()
                if title:
                    break
    return {'title': title} if title else "error"
