"""
Shared Flask extension instances.

These are created UNBOUND here (no app passed in) and attached to the
real app later with .init_app(app) inside create_app() in app.py.
This is what lets every blueprint do `from extensions import csrf`
etc. without needing to import app.py itself (which would cause a
circular import, since app.py imports the blueprints).
"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)
