from extensions import db
from models import Product


def _to_dict(p):
    return {
        "id": p.id,
        "barcode": p.barcode,
        "name": p.name,
        "price": p.price,
        "buying_price": p.buying_price,
        "tags": p.tags.split(",") if p.tags else [],
        "instock": p.instock,
        "sell_count": p.sell_count,
        "image": p.image_url,
    }


def load_products(shop_id):
    products = Product.query.filter_by(shop_id=shop_id).all()
    return [_to_dict(p) for p in products]


def save_products(shop_id, products):
    for prod in products:
        existing = Product.query.filter_by(shop_id=shop_id, barcode=prod["barcode"]).first()
        if existing:
            existing.name = prod.get("name", existing.name)
            existing.price = prod.get("price", existing.price)
            existing.buying_price = prod.get("buying_price", existing.buying_price)
            existing.tags = ",".join(prod.get("tags", []))
            existing.instock = prod.get("instock", existing.instock)
            existing.sell_count = prod.get("sell_count", existing.sell_count)
            existing.image_url = prod.get("image", existing.image_url)
        else:
            db.session.add(Product(
                shop_id=shop_id,
                barcode=prod["barcode"],
                name=prod.get("name"),
                price=prod.get("price"),
                buying_price=prod.get("buying_price"),
                tags=",".join(prod.get("tags", [])),
                instock=prod.get("instock", 0),
                sell_count=prod.get("sell_count", 0),
                image_url=prod.get("image"),
            ))
    db.session.commit()


def update_sell_count(shop_id, sale):
    for item in sale.get("items", []):
        product = Product.query.filter_by(shop_id=shop_id, barcode=item.get("barcode")).first()
        if product:
            product.sell_count = (product.sell_count or 0) + item.get("quantity", 1)
    db.session.commit()
    return True