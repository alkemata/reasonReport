# models.py
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
from slugify import slugify
import nbformat
from nbconvert import HTMLExporter
from datetime import datetime

mongo = PyMongo()

# User Operations
def create_user(username, password, landing_page=None, additional_fields=None):
    if mongo.db.users.find_one({'username': username}):
        raise ValueError("Username already exists.")
    
    user = {
        'username': username,
        'password': generate_password_hash(password),
        'landing_page': landing_page or None
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
    cells.append(nbformat.v4.new_markdown_cell(f"<!-- author: {author_id} -->"))
    
    # Date Cell
    cells.append(nbformat.v4.new_markdown_cell(f"<!-- date: {datetime.utcnow().isoformat()} -->"))
    
    # Title Cell
    cells.append(nbformat.v4.new_markdown_cell(f"<!-- title: personal page -->"))
    
    nb['cells'] = cells
    
    notebook_json = nb
    
    # Slug based on username will be set in the frontend after registration
    notebook = {
        'notebook': notebook_json,
        'author': author_id,
        'date': datetime.utcnow(),
        'title': "personal page",
        'slug': "",  # To be updated after registration
    }
    
    result = mongo.db.notebooks.insert_one(notebook)
    return str(result.inserted_id)

def save_notebook(notebook_id, notebook_json):
    nb = nbformat.reads(notebook_json, as_version=4)
    cells = nb['cells']
    
    # Extract tagged cells
    extracted = {}
    for cell in cells:
        if cell['cell_type'] == 'markdown' and cell['source'].startswith('<!--') and cell['source'].endswith('-->'):
            content = cell['source'][4:-3].strip()  # Remove <!-- and -->
            if ':' in content:
                key, value = content.split(':', 1)
                extracted[key.strip()] = value.strip()
    
    title = extracted.get('title', 'Untitled')
    author = extracted.get('author', '')
    date = extracted.get('date', '')
    
    slug = slugify(title)
    
    update_fields = {
        'notebook': notebook_json,
        'title': title,
        'author': author,
        'date': date,
        'slug': slug
    }
    
    mongo.db.notebooks.update_one({'_id': ObjectId(notebook_id)}, {'$set': update_fields})
    
    # Ensure indexes
    mongo.db.notebooks.create_index([('slug', 1)], unique=True)
    mongo.db.notebooks.create_index([('author', 1)])

def get_notebook(query):
    if isinstance(query, str) and ObjectId.is_valid(query):
        notebook = mongo.db.notebooks.find_one({'_id': ObjectId(query)})
    else:
        notebook = mongo.db.notebooks.find_one({'slug': query})
    return notebook

def delete_notebook(notebook_id):
    mongo.db.notebooks.delete_one({'_id': ObjectId(notebook_id)})

def notebook_html(notebook):
    print(notebook)
    notebook_content = nbformat.from_dict(notebook)
    html_exporter = HTMLExporter()
    (body, resources) = html_exporter.from_notebook_node(notebook_content)
    return body