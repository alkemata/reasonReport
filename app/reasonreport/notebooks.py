import json
from nbformat import v4 as nbf

def create_blank_notebook(filename):
    # Create a new notebook object
        notebook = nbf.new_notebook()

            # Add metadata to the notebook
                notebook.metadata = {
                        "kernelspec": {
                                    "name": "python3",
                                                "display_name": "Python 3"
                                                        },
                                                                "language_info": {
                                                                            "name": "python",
                                                                                        "version": "3.x"
                                                                                                }
                                                                                                    }

                                                                                                        # Add the first cell with a tag
                        cell1 = nbf.new_code_cell("# This is the first cell with a tag")
                                                                                                                cell1.metadata['tags'] = ['first_cell']

                                                                                                                    # Add the second cell with a tag
                                                                                                                        cell2 = nbf.new_code_cell("# This is the second cell with a tag")
                                                                                                                            cell2.metadata['tags'] = ['second_cell']

                                                                                                                                # Add the third cell with a tag
                                                                                                                                    cell3 = nbf.new_code_cell("# This is the third cell with a tag")
                                                                                                                                        cell3.metadata['tags'] = ['third_cell']

                                                                                                                                            # Add the cells to the notebook
                                                                                                                                                notebook.cells = [cell1, cell2, cell3]

                                                                                                                                                    # Save the notebook as a .ipynb file
                                                                                                                                                        with open(filename, 'w') as f:
                                                                                                                                                                json.dump(notebook, f, indent=4)

                                                                                                                                                                # Example usage
                                                                                                                                                                create_blank_notebook('blank_notebook.ipynb')