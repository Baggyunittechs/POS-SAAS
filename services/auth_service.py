from extensions import db
from models import User

DEFAULT_SHOP_ID = 1


def get_user_by_username(username):
    return User.query.filter_by(username=username).first()


def get_user_by_email(email):
    return User.query.filter_by(email=email).first()


def get_user_by_id(user_id):
    return User.query.get(user_id)


def create_user(username, email, password_hash, shop_id=DEFAULT_SHOP_ID, role="owner"):
    user = User(
        username=username,
        email=email,
        password_hash=password_hash,
        shop_id=shop_id,
        role=role,
    )
    db.session.add(user)
    db.session.commit()
    return user