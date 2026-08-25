import cv2
import numpy as np
from flask import Blueprint, jsonify, request, session

from extensions import csrf
from services.cart import cart_key, get_user_key, load_cart, save_cart
from services.products import load_products

barcode_bp = Blueprint("barcode", __name__)

detector = cv2.barcode.BarcodeDetector()


@barcode_bp.route("/api/barcode/scan", methods=["POST"])
@csrf.exempt
def scan():
    shop_id = session.get("shop_id")
    if not shop_id:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    if "image" not in request.files:
        return jsonify({"status": "error", "message": "No image uploaded"}), 400

    file = request.files["image"]
    image_bytes = file.read()

    array = np.frombuffer(image_bytes, dtype=np.uint8)
    frame = cv2.imdecode(array, cv2.IMREAD_COLOR)

    if frame is None:
        return jsonify({"status": "error", "message": "Invalid image data"}), 400

    barcode_data, barcode_type, bbox = detector.detectAndDecode(frame)

    if not barcode_data:
        return jsonify({"status": "error", "message": "No barcode detected in image"}), 404

    if barcode_data == session.get("last_scanned_barcode"):
        return jsonify({
            "status": "duplicate",
            "message": "Product already scanned",
            "barcode": barcode_data,
        }), 404

    products = load_products(shop_id)
    found_product = next((p for p in products if p.get("barcode") == barcode_data), None)

    if found_product:
        session["last_scanned_barcode"] = barcode_data
        try:
            user_key = get_user_key()
            carts = load_cart()
            key = cart_key(shop_id, user_key)
            cart = carts.get(key, [])
            found = False
            for item in cart:
                if str(item["product_id"]) == str(barcode_data):
                    item["quantity"] += 1
                    found = True
                    break

            if not found:
                cart.append({"product_id": barcode_data, "quantity": 1})

            carts[key] = cart
            save_cart(carts)

        except Exception as e:
            print(f"Error adding to cart: {e}")

        return jsonify({
            "status": "success",
            "message": "Product found and added to cart",
            "product": found_product,
        }), 200
    else:
        return jsonify({
            "status": "not_found",
            "message": "Product not in database",
            "barcode": barcode_data,
        }), 200