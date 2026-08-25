from flask import Blueprint, jsonify, make_response, request, session

from extensions import csrf
from services.cart import get_user_key, load_cart, save_cart
from services.products import load_products

cart_bp = Blueprint("cart", __name__)


def _require_shop():
    """Returns shop_id or None. Callers check for None and 401."""
    return session.get("shop_id")


def _cart_key(shop_id, user_key):
    return f"{shop_id}:{user_key}"


@cart_bp.route("/api/cart", methods=["GET"])
def get_cart():
    shop_id = _require_shop()
    if not shop_id:
        return jsonify({"message": "Not authenticated"}), 401

    user_key = get_user_key()
    carts = load_cart()
    cart = carts.get(_cart_key(shop_id, user_key), [])
    products = load_products(shop_id)

    enriched = []
    total = 0

    for item in cart:
        product = next(
            (p for p in products if str(p.get("barcode")) == str(item["product_id"])), None
        )
        if product:
            line_total = product["price"] * item["quantity"]
            total += line_total
            enriched.append({
                "product_id": item["product_id"],
                "quantity": item["quantity"],
                "product": product,
                "line_total": line_total,
            })

    response = jsonify({"items": enriched, "total": total, "count": len(cart)})
    response.set_cookie("user_key", user_key, max_age=60 * 60 * 24 * 365)
    return response


@cart_bp.route("/api/cart/add", methods=["POST"])
@csrf.exempt
def add_to_cart():
    shop_id = _require_shop()
    if not shop_id:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    data = request.json
    product_id = data.get("product_id")
    quantity = int(data.get("quantity", 1))

    if not product_id:
        return jsonify({"success": False, "message": "Product ID required"}), 400

    user_key = get_user_key()
    carts = load_cart()
    key = _cart_key(shop_id, user_key)
    cart = carts.get(key, [])

    found = False
    for item in cart:
        if str(item["product_id"]) == str(product_id):
            item["quantity"] += quantity
            found = True
            break

    if not found:
        cart.append({"product_id": product_id, "quantity": quantity})

    carts[key] = cart
    save_cart(carts)

    response = make_response(jsonify({
        "success": True,
        "cart_count": len(cart),
        "message": "Product added to cart",
    }))
    response.set_cookie("user_key", user_key, max_age=60 * 60 * 24 * 365)
    return response


@cart_bp.route("/api/cart/update", methods=["POST"])
@csrf.exempt
def update_cart():
    shop_id = _require_shop()
    if not shop_id:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    data = request.json
    product_id = data.get("product_id")
    quantity = int(data.get("quantity", 1))

    if not product_id:
        return jsonify({"success": False, "message": "Product ID required"}), 400

    user_key = get_user_key()
    carts = load_cart()
    key = _cart_key(shop_id, user_key)
    cart = carts.get(key, [])

    for item in cart:
        if str(item["product_id"]) == str(product_id):
            if quantity <= 0:
                cart.remove(item)
            else:
                item["quantity"] = quantity
            break

    carts[key] = cart
    save_cart(carts)

    response = make_response(jsonify({"success": True, "message": "Cart updated"}))
    response.set_cookie("user_key", user_key, max_age=60 * 60 * 24 * 365)
    return response


@cart_bp.route("/api/cart/remove", methods=["POST"])
@csrf.exempt
def remove_from_cart():
    shop_id = _require_shop()
    if not shop_id:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    data = request.json
    product_id = data.get("product_id")

    if not product_id:
        return jsonify({"success": False, "message": "Product ID required"}), 400

    user_key = get_user_key()
    carts = load_cart()
    key = _cart_key(shop_id, user_key)
    cart = carts.get(key, [])

    cart = [item for item in cart if str(item["product_id"]) != str(product_id)]

    carts[key] = cart
    save_cart(carts)

    response = make_response(jsonify({"success": True, "message": "Item removed from cart"}))
    response.set_cookie("user_key", user_key, max_age=60 * 60 * 24 * 365)
    return response