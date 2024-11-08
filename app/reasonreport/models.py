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

# User Operations
def create_user(username, password, landing_page=None, role="normal", additional_fields=None):
    """Create a new user with a role."""
    if mongo.db.users.find_one({'username': username}):
        return None

    # Add validation to ensure the role is valid
    if role not in ["admin", "normal", "editor", "advanced"]:
        raise ValueError("Invalid role. Must be one of: admin, normal, editor, advanced")

    user = {
        'username': username,
        'password': generate_password_hash(password),
        'landing_page': landing_page or None,
        'role': role  # Add role to the user document
    }
    
    if additional_fields:
        user.update(additional_fields)
    
    result = mongo.db.users.insert_one(user)
    return str(result.inserted_id)

def get_user_by_username(username):
    return mongo.db.users.find_one({'username': username})

def get_user_by_id(user_id):
    return mongo.db.users.find_one({'_id': ObjectId(user_id)})

def update_user(user_id, update_fields):
    mongo.db.users.update_one({'_id': ObjectId(user_id)}, {'$set': update_fields})

def delete_user(user_id):
    mongo.db.users.delete_one({'_id': ObjectId(user_id)})   


# Notebook Operations
def create_notebook(author_id):
    nb = nbformat.v4.new_notebook()
    
    # Pre-processing: Add three cells with tags author, date, and title
    cells = []
    
    # Author Cell
    cells.append(nbformat.v4.new_markdown_cell("Author:"))
    cells.append(nbformat.v4.new_markdown_cell(f"{author_id}"))
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
    
    notebook_json = nb
    
    # Slug based on username will be set in the frontend after registration
    notebook = {
        'notebook': notebook_json,
        'author': author_id,
        'date': datetime.utcnow(),
        'title': "",
        'slug': "",  # To be updated after registration
    }
    
    result = mongo.db.notebooks.insert_one(notebook)
    return str(result.inserted_id)

def save_notebook(notebook_id, notebook_json):
    #notebook_json = notebook_json.replace("'", '"')
    nb = nbformat.from_dict(notebook_json['notebook'])

    result=find_metadata_cells(nb)
    if result=="error":
        return "error"
    update_fields = {
        'notebook': nb,
        'author': result['author'],
        'slug':result['slug'],
        'title':result['title'],
        'date':result['date']
    }
    
    mongo.db.notebooks.update_one({'_id': ObjectId(notebook_id)}, {'$set': update_fields})
    
    # Ensure indexes
    #mongo.db.notebooks.create_index([('slug', 1)], unique=True)
    #mongo.db.notebooks.create_index([('author', 1)])
    return 'ok'

def get_notebook(query):
    if isinstance(query, str) and ObjectId.is_valid(query):
        notebook = mongo.db.notebooks.find_one({'_id': ObjectId(query)})
    else:
        notebook = mongo.db.notebooks.find_one({'slug': query})
    return notebook

def delete_notebook(notebook_id):
    mongo.db.notebooks.delete_one({'_id': ObjectId(notebook_id)})

def notebook_html(notebook):
    notebook_content = nbformat.from_dict(notebook)
    html_exporter = HTMLExporter(template_name="classic")
    (body, resources) = html_exporter.from_notebook_node(notebook_content)
    return body


def ensure_unique_slug(initial_slug):
    """
    Ensure the generated slug is unique in the database by appending a number if necessary.

    :param initial_slug: The initial slug generated from the title.
    :return: A unique slug that doesn't already exist in the MongoDB collection.
    """
    slug = initial_slug
    counter = 1
    
    # Keep checking if the slug exists in the database
    while mongo.db.notebooks.find_one({'slug': slug}):
        # If it exists, append or increment the counter to make it unique
        slug = f"{initial_slug}-{counter}"
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
    for cell in notebook_data.get('cells', []):
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
    required_types = ["title", "author", "date"]
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

    # Generate slug from title
    slug = slugify(metadata_values['title'])
    slug = ensure_unique_slug(slug)

    # Create and return the resulting structure
    result = {
        'author': metadata_values['author'],
        'slug': slug,
        'date': metadata_values['date'],
        'title':metadata_values['title']
    }

    return result