import base64
from datetime import datetime

import requests
from flask import Blueprint, jsonify, request, session

from extensions import csrf, db
from services.products import update_sell_count
from services.sales import get_sale, get_sale_by_checkout_request_id, get_total, sale_to_dict, update_sale_status

payments_bp = Blueprint("payments", __name__)

# TODO: move to environment variables before adding real data
MPESA_CONSUMER_KEY = "IfQIojwCKZWj2KF5egPYiWi1fBNxMyJNUFGf1JRETcEFvPjS"
MPESA_CONSUMER_SECRET = "56NGUdD2OyAgbdK6JpsXAOEspHXoYg7XApM0mQZtAdj0AWwg2w9xoxTcSRKzpuYQ"
MPESA_SHORTCODE = "174379"
MPESA_PASSKEY = "bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919"
MPESA_CALLBACK_URL = "https://thats-persons-terrorist-james.trycloudflare.com/api/payment/mpesa/callback"


def get_access_token(consumer_key, consumer_secret):
    url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    response = requests.get(url, auth=(consumer_key, consumer_secret), timeout=40)
    if response.status_code == 200:
        return response.json()["access_token"]
    raise Exception(f"Failed to get access token: {response.text}")


def generate_password(shortcode, passkey):
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    data_to_encode = shortcode + passkey + timestamp
    encoded = base64.b64encode(data_to_encode.encode())
    return encoded.decode(), timestamp


def initiate_stk_prompt(phone, amount, callback_url, sales_id):
    try:
        access_token = get_access_token(MPESA_CONSUMER_KEY, MPESA_CONSUMER_SECRET)
        password, timestamp = generate_password(MPESA_SHORTCODE, MPESA_PASSKEY)
        url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "BusinessShortCode": MPESA_SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount,
            "PartyA": phone,
            "PartyB": MPESA_SHORTCODE,
            "PhoneNumber": phone,
            "CallBackURL": callback_url,
            "AccountReference": str(sales_id),
            "TransactionDesc": "Your purchased goods payments",
        }
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        return response.json()
    except Exception as e:
        print(f"STK Error: {str(e)}")
        return {"error": str(e)}


def _parse_sales_id(raw):
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


@payments_bp.route("/api/sales/payments/mpesa", methods=["POST"])
@csrf.exempt
def mpesa_payment():
    shop_id = session.get("shop_id")
    if not shop_id:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "data not provided"}), 400

    sales_id = _parse_sales_id(data.get("sales_id"))
    mpesa_phone = data.get("phone")
    if not mpesa_phone or sales_id is None:
        return jsonify({"status": "error", "message": "data not provided"}), 400

    total = get_total(shop_id, sales_id)
    if total is None:
        return jsonify({"status": "error", "message": "sales_id not found"}), 404

    try:
        response = initiate_stk_prompt(mpesa_phone, total, MPESA_CALLBACK_URL, sales_id)
        checkout_request_id = response.get("CheckoutRequestID")

        if checkout_request_id:
            update_sale_status(shop_id, sales_id, "pending", checkout_request_id=checkout_request_id)

        return jsonify(response), 200

    except Exception as e:
        print(f"STK Error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@payments_bp.route("/api/payment/mpesa/callback", methods=["POST"])
@csrf.exempt
def mpesa_callback():
    # Webhook from Safaricom — no user session, so no shop_id scoping here.
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "data not provided"}), 200

    stk_callback = data.get("Body", {}).get("stkCallback", {})
    result_code = stk_callback.get("ResultCode")
    result_desc = stk_callback.get("ResultDesc")
    checkout_request_id = stk_callback.get("CheckoutRequestID")

    if not checkout_request_id:
        return jsonify({
            "status": "error",
            "message": "checkout_request_id missing from callback",
        }), 200

    matched_sale = get_sale_by_checkout_request_id(checkout_request_id)

    if not matched_sale:
        print(f"No matching sale for CheckoutRequestID: {checkout_request_id}")
        return jsonify({
            "status": "error",
            "message": "sales_id not found",
            "checkout_request_id": checkout_request_id,
        }), 200

    shop_id = matched_sale.shop_id
    sales_id = matched_sale.id

    if result_code == 0:
        callback_metadata = stk_callback.get("CallbackMetadata", {})
        items = callback_metadata.get("Item", [])

        mpesa_receipt = amount_paid = phone_number = transaction_date = None
        for item in items:
            name = item.get("Name")
            if name == "MpesaReceiptNumber":
                mpesa_receipt = item.get("Value")
            elif name == "Amount":
                amount_paid = item.get("Value")
            elif name == "PhoneNumber":
                phone_number = item.get("Value")
            elif name == "TransactionDate":
                transaction_date = item.get("Value")

        updated = update_sale_status(
            shop_id,
            sales_id,
            "paid",
            mpesa_receipt=mpesa_receipt,
            transaction_date=transaction_date,
            payment_method="M-pesa",
        )

        if not updated:
            return jsonify({
                "status": "error",
                "message": "sale could not be updated",
                "sales_id": sales_id,
            }), 200

        update_sell_count(shop_id, sale_to_dict(matched_sale))
        return jsonify({
            "status": "success",
            "message": "payment successful",
            "sales_id": sales_id,
            "checkout_request_id": checkout_request_id,
            "receipt": mpesa_receipt,
            "amount": amount_paid,
            "phone": phone_number,
            "transaction_date": transaction_date,
        }), 200

    print(f"Payment failed: {result_code} - {result_desc}")
    update_sale_status(shop_id, sales_id, "failed")
    return jsonify({
        "status": "failed",
        "message": result_desc,
        "sales_id": sales_id,
        "checkout_request_id": checkout_request_id,
    }), 200


@payments_bp.route("/api/payment/mpesa/callback/status", methods=["POST"])
@csrf.exempt
def mpesa_callback_status():
    shop_id = session.get("shop_id")
    if not shop_id:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "data not provided"}), 400

    sales_id = _parse_sales_id(data.get("sales_id"))
    if sales_id is None:
        return jsonify({"status": "error", "message": "sales_id required"}), 400

    sale = get_sale(shop_id, sales_id)
    if not sale:
        return jsonify({"status": "error", "message": "sale not found"}), 404

    status = sale.status or "pending"

    if status == "paid":
        return jsonify({
            "status": "success",
            "message": "Payment successful",
            "sales_id": sales_id,
            "receipt": sale.mpesa_receipt,
            "amount": sale.total,
            "transaction_date": sale.transaction_date,
        }), 200
    elif status == "failed":
        return jsonify({
            "status": "failed",
            "message": "Payment failed",
            "sales_id": sales_id,
        }), 200
    else:
        return jsonify({
            "status": "pending",
            "message": "Payment still processing",
            "sales_id": sales_id,
        }), 200


@payments_bp.route("/api/payment/cash", methods=["POST"])
@csrf.exempt
def cash_payment():
    shop_id = session.get("shop_id")
    if not shop_id:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "missing data"}), 404

    sales_id = _parse_sales_id(data.get("sales_id"))
    if sales_id is None:
        return jsonify({"status": "error", "message": "sales_id required"}), 400

    matched_sale = get_sale(shop_id, sales_id)
    if not matched_sale:
        return jsonify({"status": "error", "message": "sales_id not found"}), 404

    if matched_sale.status == "paid":
        return jsonify({"status": "error", "message": "This sale has already been paid"}), 400

    updated = update_sale_status(
        shop_id,
        sales_id,
        "paid",
        transaction_date=matched_sale.created_at.strftime("%Y-%m-%d %H:%M:%S") if matched_sale.created_at else None,
        payment_method="Cash",
        mpesa_receipt="No transactionID",
    )
    if not updated:
        return jsonify({
            "status": "error",
            "message": "sale could not be updated",
            "sales_id": sales_id,
        }), 200

    update_sell_count(shop_id, sale_to_dict(matched_sale))
    return jsonify({
        "status": "success",
        "message": "payment successful",
        "sales_id": sales_id,
    }), 200


@payments_bp.route("/api/sales/payments/hybrid", methods=["POST"])
@csrf.exempt
def hybrid_payment():
    shop_id = session.get("shop_id")
    if not shop_id:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "data not provided"}), 400

    sales_id = _parse_sales_id(data.get("sales_id"))
    phone = data.get("phone")
    cash_amount = data.get("cash_amount", 0)
    mpesa_amount = data.get("mpesa_amount", 0)

    if sales_id is None:
        return jsonify({"status": "error", "message": "sales_id required"}), 400
    if not phone:
        return jsonify({"status": "error", "message": "phone required"}), 400

    try:
        cash_amount = float(cash_amount)
        mpesa_amount = float(mpesa_amount)
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "Invalid payment amounts"}), 400

    sale = get_sale(shop_id, sales_id)
    if not sale:
        return jsonify({"status": "error", "message": "Sale not found"}), 404

    if sale.status == "paid":
        return jsonify({"status": "error", "message": "This sale has already been paid"}), 400

    sale_total = float(sale.total or 0)
    total_payment = cash_amount + mpesa_amount

    if total_payment != sale_total:
        return jsonify({
            "status": "error",
            "message": "Payment amounts do not match sale total",
            "sale_total": sale_total,
            "cash_amount": cash_amount,
            "mpesa_amount": mpesa_amount,
            "total_payment": total_payment,
        }), 400

    if cash_amount <= 0 or mpesa_amount <= 0:
        return jsonify({
            "status": "error",
            "message": "Hybrid payment must contain both cash and M-PESA",
        }), 400

    sale.payment_method = "hybrid"
    sale.payment_details = {
        "cash": {"amount": cash_amount, "status": "received"},
        "mpesa": {"amount": mpesa_amount, "status": "pending", "phone": phone},
    }
    sale.status = "pending"
    db.session.commit()

    try:
        response = initiate_stk_prompt(phone, mpesa_amount, MPESA_CALLBACK_URL, sales_id)
    except Exception as e:
        sale.payment_details["mpesa"]["status"] = "failed"
        db.session.commit()
        return jsonify({"status": "error", "message": str(e)}), 500

    checkout_request_id = response.get("CheckoutRequestID")

    if not checkout_request_id:
        sale.payment_details = {**sale.payment_details, "mpesa": {**sale.payment_details["mpesa"], "status": "failed"}}
        db.session.commit()
        return jsonify({
            "status": "error",
            "message": "M-PESA STK Push failed",
            "mpesa_response": response,
        }), 400

    sale.checkout_request_id = checkout_request_id
    sale.payment_details = {**sale.payment_details, "mpesa": {**sale.payment_details["mpesa"], "checkout_request_id": checkout_request_id}}
    db.session.commit()
    update_sell_count(shop_id, sale_to_dict(sale))

    return jsonify({
        "status": "pending",
        "message": "Cash received. Waiting for M-PESA payment.",
        "sales_id": sales_id,
        "sale_total": sale_total,
        "cash_amount": cash_amount,
        "mpesa_amount": mpesa_amount,
        "checkout_request_id": checkout_request_id,
    }), 200