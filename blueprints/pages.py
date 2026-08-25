from flask import Blueprint, redirect, render_template, url_for

from blueprints.auth import get_current_user

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def dashboard():
    user = get_current_user()
    if not user:
        return redirect(url_for("auth.login"))
    return render_template("index.html")


@pages_bp.route("/cart")
def cart_page():
    user = get_current_user()
    if not user:
        return redirect(url_for("auth.login"))
    return render_template("cart.html")


@pages_bp.route("/shop")
def shop_page():
    user = get_current_user()
    if not user:
        return redirect(url_for("auth.login"))
    return render_template("shop.html")


@pages_bp.route("/sales")
def sales_page():
    user = get_current_user()
    if not user:
        return redirect(url_for("auth.login"))
    return render_template("sales.html")


@pages_bp.route("/checkout")
def checkout_page():
    user = get_current_user()
    if not user:
        return redirect(url_for("auth.login"))
    return render_template("checkout.html")
