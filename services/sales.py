from extensions import db
from models import Sale, SaleItem


def create_sale(shop_id, cashier_id, sales_items, total, profit):
    sale = Sale(
        shop_id=shop_id,
        cashier_id=cashier_id,
        status="pending",
        total=total,
        profit=profit,
    )
    db.session.add(sale)
    db.session.flush()  

    for item in sales_items:
        db.session.add(SaleItem(
            sale_id=sale.id,
            product_id=item.get("product_id"),
            barcode=item.get("barcode"),
            name=item.get("name"),
            price=item.get("price"),
            quantity=item.get("quantity"),
            item_total=item.get("item_total"),
        ))

    db.session.commit()
    return sale


def get_sale(shop_id, sale_id):
    return Sale.query.filter_by(shop_id=shop_id, id=sale_id).first()


def sale_to_dict(sale):
    return {
        "sales_id": sale.id,
        "status": sale.status,
        "total": sale.total,
        "profit": sale.profit,
        "payment_method": sale.payment_method,
        "mpesa_receipt": sale.mpesa_receipt,
        "checkout_request_id": sale.checkout_request_id,
        "created_at": sale.created_at.strftime("%Y-%m-%d %H:%M:%S") if sale.created_at else None,
        "items": [
            {
                "barcode": item.barcode,
                "name": item.name,
                "price": item.price,
                "quantity": item.quantity,
                "item_total": item.item_total,
            }
            for item in sale.items
        ],
    }


def update_sale_status(shop_id, sale_id, status, **extra_fields):
    sale = Sale.query.filter_by(shop_id=shop_id, id=sale_id).first()
    if not sale:
        return False
    sale.status = status
    for key, value in extra_fields.items():
        if hasattr(sale, key):
            setattr(sale, key, value)
    db.session.commit()
    return True


def get_total(shop_id, sale_id):
    sale = Sale.query.filter_by(shop_id=shop_id, id=sale_id).first()
    return sale.total if sale else None

def get_sale_by_checkout_request_id(checkout_request_id):
    return Sale.query.filter_by(checkout_request_id=checkout_request_id).first()

def list_sales(shop_id):
    return Sale.query.filter_by(shop_id=shop_id).all()