from flask_bcrypt import Bcrypt
from pymongo import MongoClient

bcrypt = Bcrypt()

client = MongoClient('mongodb://localhost:27017/')
db = client.flask_auth_db
users_collection = db.users


def register_user(username, password, invitation_code):
    # Check if the invitation code is valid
        if invitation_code not in Config.INVITATION_CODES:
                return False, "Invalid invitation code"

                    # Check if username is already taken
                        existing_user = users_collection.find_one({"username": username})
                            if existing_user:
                                    return False, "Username already exists"

                                        # Hash the password and create the user
                                            hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
                                                users_collection.insert_one({
                                                        "username": username,
                                                                "password": hashed_password
                                                                    })

                                                                        return True, "User registered successfully"


                                                                        def authenticate_user(username, password):
                                                                            # Find the user in the database
                                                                                user = users_collection.find_one({"username": username})
                                                                                    if user and bcrypt.check_password_hash(user['password'], password):
                                                                                            return True, user
                                                                                                return False, None I'm