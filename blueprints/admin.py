import os
from datetime import date, timedelta

from flask import Blueprint, current_app, jsonify, request, session
from werkzeug.utils import secure_filename

from extensions import csrf
from services.products import load_products, save_products
from services.sales import list_sales, sale_to_dict

admin_bp = Blueprint("admin", __name__)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _require_shop():
    return session.get("shop_id")


@admin_bp.route("/api/admin/sales/summary", methods=["GET"])
@csrf.exempt
def get_daily_orders():
    shop_id = _require_shop()
    if not shop_id:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    today = date.today()
    yesterday = today - timedelta(days=1)
    sales = [sale_to_dict(s) for s in list_sales(shop_id)]

    revenue = sales_count = 0
    monthly_revenue = monthly_sales_count = monthly_profit = 0
    yesterday_revenue = yesterday_sales = 0
    last_month_revenue = last_month_sales = last_month_profit = 0

    start_of_month = today.replace(day=1)
    if today.month == 12:
        start_of_next_month = today.replace(year=today.year + 1, month=1, day=1)
    else:
        start_of_next_month = today.replace(month=today.month + 1, day=1)
    end_of_month = start_of_next_month - timedelta(days=1)
    end_of_last_month = start_of_month - timedelta(days=1)
    start_of_last_month = end_of_last_month.replace(day=1)

    from datetime import datetime as dt

    for sale in sales:
        if sale.get("status") != "paid":
            continue

        created_at = sale.get("created_at")
        if not created_at:
            continue
        sale_date = dt.strptime(created_at, "%Y-%m-%d %H:%M:%S").date()
        total = sale.get("total", 0)
        profit = sale.get("profit", 0)

        if sale_date == today:
            revenue += total
            sales_count += 1
        if sale_date == yesterday:
            yesterday_revenue += total
            yesterday_sales += 1
        if start_of_month <= sale_date <= end_of_month:
            monthly_revenue += total
            monthly_sales_count += 1
            monthly_profit += profit
        if start_of_last_month <= sale_date <= end_of_last_month:
            last_month_revenue += total
            last_month_sales += 1
            last_month_profit += profit

    return jsonify({
        "status": "success",
        "today": {"revenue": revenue, "sales_total": sales_count},
        "yesterday": {"revenue": yesterday_revenue, "sales_total": yesterday_sales},
        "today_vs_yesterday": {
            "revenue_difference": revenue - yesterday_revenue,
            "sales_difference": sales_count - yesterday_sales,
        },
        "this_month": {
            "revenue": monthly_revenue,
            "sales_total": monthly_sales_count,
            "monthly_profit": monthly_profit,
        },
        "last_month": {
            "revenue": last_month_revenue,
            "sales_total": last_month_sales,
            "last_month_profit": last_month_profit,
        },
        "this_month_vs_last_month": {
            "revenue_difference": monthly_revenue - last_month_revenue,
        },
    }), 200


@admin_bp.route("/api/admin/sales/history")
@csrf.exempt
def sales_history():
    shop_id = _require_shop()
    if not shop_id:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    from datetime import datetime as dt

    sales = [sale_to_dict(s) for s in list_sales(shop_id)]
    month_param = request.args.get("month")
    year_param = request.args.get("year")
    today = date.today()

    if month_param and year_param:
        try:
            start_of_month = date(int(year_param), int(month_param), 1)
        except ValueError:
            start_of_month = today.replace(day=1)
    else:
        start_of_month = today.replace(day=1)

    if start_of_month.month == 12:
        start_of_next_month = start_of_month.replace(year=start_of_month.year + 1, month=1, day=1)
    else:
        start_of_next_month = start_of_month.replace(month=start_of_month.month + 1, day=1)
    end_of_month = start_of_next_month - timedelta(days=1)

    paid_sales = []
    for sale in sales:
        if sale.get("status") != "paid":
            continue

        created_at = sale.get("created_at")
        if not created_at:
            continue

        try:
            sale_date = dt.strptime(created_at, "%Y-%m-%d %H:%M:%S").date()
        except ValueError:
            continue

        if start_of_month <= sale_date <= end_of_month:
            paid_sales.append({
                "sales_id": sale.get("sales_id"),
                "sales_status": sale.get("status"),
                "total": sale.get("total"),
                "transaction_id": sale.get("mpesa_receipt"),
                "date": sale.get("created_at"),
                "profit": sale.get("profit"),
            })

    return jsonify({
        "month": start_of_month.strftime("%B %Y"),
        "month_start": start_of_month.isoformat(),
        "month_end": end_of_month.isoformat(),
        "total_sales": len(paid_sales),
        "sales": paid_sales,
    }), 200


@admin_bp.route("/api/admin/sales/history/all")
@csrf.exempt
def sales_history_all():
    shop_id = _require_shop()
    if not shop_id:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    paid_sales = [
        {
            "sales_id": sale.get("sales_id"),
            "sales_status": sale.get("status"),
            "total": sale.get("total"),
            "transaction_id": sale.get("mpesa_receipt"),
            "date": sale.get("created_at"),
            "profit": sale.get("profit"),
        }
        for sale in (sale_to_dict(s) for s in list_sales(shop_id))
        if sale.get("status") == "paid"
    ]
    return jsonify(paid_sales), 200


@admin_bp.route("/api/admin/sales/weekly", methods=["GET"])
@csrf.exempt
def weekly_sales():
    shop_id = _require_shop()
    if not shop_id:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    from datetime import datetime as dt

    today = date.today()
    days_since_sunday = (today.weekday() + 1) % 7
    sunday = today - timedelta(days=days_since_sunday)
    saturday = sunday + timedelta(days=6)

    days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    weekly_revenue = {d: 0 for d in days}
    weekly_sales_count = {d: 0 for d in days}

    for sale in (sale_to_dict(s) for s in list_sales(shop_id)):
        if sale.get("status") != "paid":
            continue
        created_at = sale.get("created_at")
        if not created_at:
            continue
        sale_date = dt.strptime(created_at, "%Y-%m-%d %H:%M:%S").date()
        if sunday <= sale_date <= saturday:
            day_name = sale_date.strftime("%A")
            weekly_revenue[day_name] += sale.get("total", 0)
            weekly_sales_count[day_name] += 1

    return jsonify({
        "status": "success",
        "week": {"sunday": sunday.isoformat(), "saturday": saturday.isoformat()},
        "revenue": weekly_revenue,
        "sales": weekly_sales_count,
    }), 200


@admin_bp.route("/api/admin/items/stock", methods=["GET"])
@csrf.exempt
def load_outofstock_products():
    shop_id = _require_shop()
    if not shop_id:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    filtered_products = [p for p in load_products(shop_id) if p.get("instock") == 0]
    return jsonify({"status": "success", "out_of_stock_items": filtered_products}), 200


@admin_bp.route("/api/admin/items/stock/edit", methods=["POST"])
@csrf.exempt
def edit_stock():
    shop_id = _require_shop()
    if not shop_id:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "missing fields"}), 400

    barcode = data.get("barcode")
    stock_quantity = data.get("stock_quantity")

    products = load_products(shop_id)
    for product in products:
        if product.get("barcode") == barcode:
            product["instock"] = stock_quantity
            break

    try:
        save_products(shop_id, products)
        return jsonify({"status": "success"}), 200
    except Exception as e:
        print(f"Failed to update stock: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@admin_bp.route("/api/admin/items/upload", methods=["POST"])
@csrf.exempt
def admin_add_product():
    shop_id = _require_shop()
    if not shop_id:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    name = request.form.get("name", "").strip()
    price = request.form.get("price")
    barcode = request.form.get("barcode")
    tags_raw = request.form.get("tags", "").strip()
    buying_price = request.form.get("buying price")
    stock_amount = request.form.get("stock_amount", "1").strip()

    if not all([name, buying_price, price, stock_amount]):
        return jsonify({
            "error": "Missing required fields:name, buying price, price, stock amount"
        }), 400

    try:
        price = float(price)
    except ValueError:
        return jsonify({"error": "Price must be a number"}), 400

    if buying_price:
        try:
            buying_price = float(buying_price)
        except ValueError:
            return jsonify({"error": "old_price must be a number"}), 400
    else:
        buying_price = None

    tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []

    main_image_file = request.files.get("main_image")
    if not main_image_file or main_image_file.filename == "":
        return jsonify({"error": "main_image is required"}), 400

    if not allowed_file(main_image_file.filename):
        return jsonify({"error": "Invalid file type for main_image"}), 400

    main_filename = secure_filename(f"{shop_id}_{barcode}_main_{main_image_file.filename}")
    main_path = os.path.join(current_app.root_path, "static", "images", main_filename)
    main_image_file.save(main_path)

    image_files = request.files.getlist("images")
    for img_file in image_files:
        if img_file and img_file.filename and allowed_file(img_file.filename):
            img_filename = secure_filename(f"{shop_id}_{barcode}_{img_file.filename}")
            img_path = os.path.join(current_app.root_path, "static", "images", img_filename)
            img_file.save(img_path)

    main_image_url = "/static/images/" + main_filename
    new_product = {
        "barcode": barcode,
        "name": name,
        "price": price,
        "buying_price": buying_price,
        "tags": tags,
        "instock": int(stock_amount),
        "image": main_image_url,
    }

    products = load_products(shop_id)
    if any(p.get("barcode") == barcode for p in products):
        return jsonify({"error": "Product with this barcode already exists"}), 409

    products.append(new_product)
    try:
        save_products(shop_id, products)
    except Exception as e:
        return jsonify({"error": f"Failed to save product data: {str(e)}"}), 500

    return jsonify({"success": True, "product": new_product}), 201


@admin_bp.route("/api/admin/stock/value", methods=["GET"])
@csrf.exempt
def stock_value():
    shop_id = _require_shop()
    if not shop_id:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    total_value = sum(p.get("price") * p.get("instock") for p in load_products(shop_id))
    return jsonify({"status": "success", "stock_value": total_value}), 200