from app import app, db

# Push an application context
with app.app_context():
    # Create all tables
    db.create_all()
    print("Database tables created successfully.")