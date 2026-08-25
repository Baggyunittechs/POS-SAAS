import json
import os
import uuid

from flask import current_app, request


def _cart_path():
    return os.path.join(current_app.root_path, "data", "cart.json")


def load_json_file(filepath):
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_json_file(filepath, data):
    try:
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
    except (FileNotFoundError, json.JSONDecodeError):
        print("cart file not found")


def get_user_key():
    return request.cookies.get("user_key") or str(uuid.uuid4())


def load_cart():
    return load_json_file(_cart_path())


def save_cart(carts):
    save_json_file(_cart_path(), carts)

def cart_key(shop_id, user_key):
    return f"{shop_id}:{user_key}"