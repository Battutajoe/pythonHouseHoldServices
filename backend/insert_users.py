from app import app, db, User
from flask_bcrypt import generate_password_hash

# Push an application context
with app.app_context():
    # Create an admin user
    admin = User(
        username='admin',
        password=generate_password_hash('adminpassword').decode('utf-8'),
        role='admin'
    )

    # Create a regular user
    user = User(
        username='user',
        password=generate_password_hash('userpassword').decode('utf-8'),
        role='user'
    )

    # Add users to the session and commit
    db.session.add(admin)
    db.session.add(user)
    db.session.commit()

    print("Admin and user created successfully.")