from flask import Blueprint, jsonify, request, session, redirect, url_for
from services.products import load_products
products_bp = Blueprint("products", __name__)


@products_bp.route("/api/products", methods=["GET"])
def get_products():
    shop_id = session.get("shop_id")
    if not shop_id:
        return jsonify({"message": "Not authenticated"}), 401
    products = load_products(shop_id)
    search = request.args.get("search")
    if search:
        search = search.lower().strip()
        def matches_search(p):
            name = p.get("name", "").lower()
            tags = " ".join(p.get("tags", [])).lower()
            return search in name or search in tags

        filtered_products = [p for p in products if matches_search(p) and p.get("instock", 0) > 0]
        return jsonify(filtered_products)

    instock_products = [p for p in products if p.get("instock", 0) > 0]
    return jsonify(instock_products)