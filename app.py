from flask import Flask, render_template


from config import Config
from extensions import csrf, db, limiter, migrate

from blueprints.admin import admin_bp
from blueprints.auth import auth_bp
from blueprints.barcode import barcode_bp
from blueprints.cart import cart_bp
from blueprints.pages import pages_bp
from blueprints.payments import payments_bp
from blueprints.products import products_bp
from blueprints.receipts import receipts_bp
from blueprints.sales import sales_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(barcode_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(cart_bp)
    app.register_blueprint(sales_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(receipts_bp)

    @app.errorhandler(404)
    def page_not_found(error):
        return render_template("404.html"), 404

    @app.errorhandler(429)
    def ratelimit_handler(e):
        return render_template("429.html"), 429

    return app


app = create_app()

if __name__ == "__main__":
    print("Starting Flask...")
    app.run(debug=True, host="0.0.0.0", port=5000)
