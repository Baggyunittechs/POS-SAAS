from extensions import db

class Shop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    subscription_tier = db.Column(db.String, default='free')
    created_at = db.Column(db.DateTime, server_default=db.func.now())


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False)
    username = db.Column(db.String, nullable=False)
    email = db.Column(db.String, nullable=False)
    password_hash = db.Column(db.String, nullable=False)
    role = db.Column(db.String, nullable=False, default='owner')

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False)
    barcode = db.Column(db.String, nullable=False)
    name = db.Column(db.String, nullable=False)
    price = db.Column(db.Float, nullable=False)
    buying_price = db.Column(db.Float)
    tags = db.Column(db.String)
    instock = db.Column(db.Integer, default=0)
    sell_count = db.Column(db.Integer, default=0)
    image_url = db.Column(db.String)
    __table_args__ = (db.UniqueConstraint('shop_id', 'barcode'),)

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False)
    cashier_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    status = db.Column(db.String, default='pending')
    total = db.Column(db.Float)
    profit = db.Column(db.Float)
    payment_method = db.Column(db.String)
    mpesa_receipt = db.Column(db.String)
    checkout_request_id = db.Column(db.String)
    transaction_date = db.Column(db.String)
    payment_details = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    items = db.relationship('SaleItem', backref='sale', cascade='all, delete-orphan')

class SaleItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sale.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    barcode = db.Column(db.String)
    name = db.Column(db.String)
    price = db.Column(db.Float)
    quantity = db.Column(db.Integer)
    item_total = db.Column(db.Float)