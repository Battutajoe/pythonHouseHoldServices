from setuptools import setup

setup(
    name="HouseHoldServices",  # Matches your app name in .buildozer.spec
    version="0.1",             # Matches version in .buildozer.spec
    packages=["householdservices"],  # Adjust if your package structure differs
    install_requires=[
        "kivy",                # Core UI framework
        "kivymd"
        "flask",               # Web framework (ensure it runs locally in app)
        "flask-sqlalchemy",    # Flask ORM
        "flask-bcrypt",        # Password hashing
        "flask-jwt-extended",  # JWT authentication
        "flask-cors",          # CORS support
        "flask-socketio",      # WebSocket support
        "requests",            # HTTP requests
        "socketio",            # Socket.IO client (may need clarification)
        "python-socketio",     # Socket.IO server
        "pyjnius"
        "python-engineio",
        "bidict",
        "pyjwt",               # JWT handling
        "python-dotenv",       # Environment variable loading
        "sqlalchemy",          # Database ORM
        "marshmallow",         # Serialization
        "python-dateutil",     # Date utilities
        "logging",             # Logging utilities
        "pillow",             # Image processing
        "eventlet",
        "gunicorn"
    ],
)