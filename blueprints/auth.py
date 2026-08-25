import hashlib
import secrets
import smtplib
import time
from email.message import EmailMessage

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db, limiter
from services.auth_service import get_user_by_username, get_user_by_email, get_user_by_id, create_user

auth_bp = Blueprint("auth", __name__)

# TODO: move to environment variables before adding real data
RESET_EMAIL_ADDRESS = "unitbaggy3@gmail.com"
RESET_EMAIL_PASSWORD = "pdzy fphw zjkg zxoh"


def send_reset_email(to_email, token):
    reset_link = f"http://127.0.0.1:5000/reset-password?token={token}"

    msg = EmailMessage()
    msg["Subject"] = "Password Reset Request"
    msg["From"] = RESET_EMAIL_ADDRESS
    msg["To"] = to_email
    msg.set_content(
        f"""You requested a password reset.
        Click the link below to reset your password:
        {reset_link}
        This link expires in 15 minutes.
      """
    )

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(RESET_EMAIL_ADDRESS, RESET_EMAIL_PASSWORD)
        server.send_message(msg)


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")

        if not username or not email or not password:
            flash("All fields are required", "danger")
            return redirect(url_for(".register"))

        hashed_password = generate_password_hash(password)

        try:
            create_user(username, email, hashed_password)
            flash("Account successfully created", "success")
            return redirect(url_for(".login"))
        except IntegrityError:
            db.session.rollback()
            flash("Username or email already exists", "danger")

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            flash("Invalid username or password", "danger")
            return redirect(url_for(".login"))

        user = get_user_by_username(username)

        if user and check_password_hash(user.password_hash, password):
            flash("Login successful", "success")
            session["user_id"] = user.id
            session["shop_id"] = user.shop_id
            return redirect(url_for("pages.dashboard"))
        else:
            flash("Invalid username or password", "danger")

    return render_template("login.html")


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def forgot_password():
    if request.method == "GET":
        return render_template("forgot-password.html")

    email = request.form.get("email")

    if not email:
        return jsonify({"message": "Invalid request"}), 400

    user = get_user_by_email(email)

    if user:
        token = secrets.token_urlsafe(32)
        hashed_token = hashlib.sha256(token.encode()).hexdigest()
        expiry = int(time.time()) + 900

        user.reset_token = hashed_token
        user.reset_token_expiry = expiry
        db.session.commit()
        send_reset_email(email, token)

    return redirect(url_for(".resetmessage"))


@auth_bp.route("/reset-password", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def reset_password():
    if request.method == "GET":
        token = request.args.get("token")
        if not token:
            return jsonify({"message": "Invalid request"}), 400
        return render_template("reset-password.html", token=token)

    token = request.form.get("token")
    new_password = request.form.get("new_password")

    if not token or not new_password:
        return jsonify({"message": "Invalid request"}), 400

    hashed_token = hashlib.sha256(token.encode()).hexdigest()

    from models import User

    user = User.query.filter(
        User.reset_token == hashed_token,
        User.reset_token_expiry > int(time.time()),
    ).first()

    if not user:
        return jsonify({"message": "Invalid or expired token"}), 400

    user.password_hash = generate_password_hash(new_password)
    user.reset_token = None
    user.reset_token_expiry = None
    db.session.commit()

    return jsonify({"message": "Password successfully reset"})


@auth_bp.route("/resetmessage")
def resetmessage():
    return render_template("resetmessage.html")


def get_current_user():
    """Shared by every blueprint that needs to check who's logged in."""
    user_id = session.get("user_id")
    if not user_id:
        return None

    user = get_user_by_id(user_id)
    if not user:
        session.clear()
        return None

    return user