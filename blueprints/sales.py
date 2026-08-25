from flask import Blueprint, jsonify, request, session

from extensions import csrf
from services.products import load_products
from services.sales import create_sale, get_sale, sale_to_dict

sales_bp = Blueprint("sales", __name__)


@sales_bp.route("/api/save/sales", methods=["POST"])
@csrf.exempt
def create_sale_route():
    shop_id = session.get("shop_id")
    if not shop_id:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    data = request.get_json()
    items = data.get("items", [])

    products = load_products(shop_id)
    sales_items = []
    total = 0
    overal_profit = 0

    for item in items:
        barcode = item.get("barcode")
        quantity = item.get("quantity", 1)

        found_product = next((p for p in products if p.get("barcode") == barcode), None)

        if found_product:
            price = found_product.get("price", 0)
            buying_price = found_product.get("buying_price") or 0
            item_total = price * quantity
            total += item_total
            profit = price - buying_price
            overal_profit += profit * quantity

            sales_items.append({
                "barcode": barcode,
                "product_id": found_product.get("id"),
                "name": found_product.get("name"),
                "price": price,
                "quantity": quantity,
                "item_total": item_total,
            })

    cashier_id = session.get("user_id")
    sale = create_sale(shop_id, cashier_id, sales_items, total, overal_profit)

    return jsonify({
        "status": "success",
        "message": "Sale created successfully",
        "sales_id": sale.id,
        "total": total,
        "created_at": sale.created_at.strftime("%Y-%m-%d %H:%M:%S") if sale.created_at else None,
    })


@sales_bp.route("/api/checkout", methods=["GET"])
def checkout():
    shop_id = session.get("shop_id")
    if not shop_id:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    sales_id = request.args.get("sales_id")
    if not sales_id:
        return jsonify({"status": "error", "message": "sales id not provided"}), 400

    sale = get_sale(shop_id, sales_id)
    if sale and sale.status != "paid":
        return jsonify({"status": "success", "sale": sale_to_dict(sale)}), 200

    return jsonify({
        "status": "error",
        "message": "sale not found or has already been closed",
    }), 400