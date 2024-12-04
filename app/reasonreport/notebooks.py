import nbformat as nbf

def create_blank_notebook():
    nb = nbf.v4.new_notebook()
    return nb

def create_notebook_with_labels(cell_labels):
    # Create a new notebook
    nb = nbf.v4.new_notebook()
    
    # Metadata for the notebook
    nb.metadata = {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3"
        },
        "language_info": {
            "name": "python",
            "version": "3.8"
        }
    }
    
    # Create text cells with the provided labels
    for idx, label in enumerate(cell_labels):
        cell_content = f"## Cell {idx+1}\nThis is text cell labeled: {label}."
        cell_metadata = {"tags": [f"custom-tag-{idx+1}"]}
        
        # Add the cell to the notebook
        nb.cells.append(nbf.v4.new_markdown_cell(cell_content, metadata=cell_metadata))
    
    return nb

def create_rr_notebook():
    return create_notebook_with_labels({'title','author','summary'})

# Usage example
#cell_labels = ["Label 1", "Label 2", "Label 3"]
#notebook = create_notebook_with_labels(cell_labels)
