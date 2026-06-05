from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from ..models import db, User

auth_bp = Blueprint("auth", __name__)


# ── Role decorator ──────────────────────────────────────────────────────────
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash("Admin access required.", "danger")
            return redirect(url_for("recognize.upload"))
        return f(*args, **kwargs)
    return decorated


# ── Login ───────────────────────────────────────────────────────────────────
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("recognize.upload"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user, remember=True)
            next_page = request.args.get("next")
            flash(f"Welcome back, {user.username}!", "success")
            return redirect(next_page or url_for("recognize.upload"))
        flash("Invalid username or password.", "danger")

    return render_template("auth/login.html")


# ── Logout ──────────────────────────────────────────────────────────────────
@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


# ── User management (admin only) ─────────────────────────────────────────────
@auth_bp.route("/users")
@login_required
@admin_required
def users():
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template("auth/users.html", users=all_users)


@auth_bp.route("/users/add", methods=["POST"])
@login_required
@admin_required
def add_user():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    role     = request.form.get("role", "viewer")

    if not username or not password:
        flash("Username and password are required.", "danger")
        return redirect(url_for("auth.users"))

    if User.query.filter_by(username=username).first():
        flash(f"Username '{username}' already exists.", "danger")
        return redirect(url_for("auth.users"))

    user = User(
        username      = username,
        password_hash = generate_password_hash(password),
        role          = role,
    )
    db.session.add(user)
    db.session.commit()
    flash(f"User '{username}' created as {role}.", "success")
    return redirect(url_for("auth.users"))


@auth_bp.route("/users/delete/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("You cannot delete your own account.", "danger")
        return redirect(url_for("auth.users"))
    db.session.delete(user)
    db.session.commit()
    flash(f"User '{user.username}' deleted.", "success")
    return redirect(url_for("auth.users"))


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        old_pw = request.form.get("old_password", "")
        new_pw = request.form.get("new_password", "")
        if not check_password_hash(current_user.password_hash, old_pw):
            flash("Current password is incorrect.", "danger")
        else:
            current_user.password_hash = generate_password_hash(new_pw)
            db.session.commit()
            flash("Password updated successfully.", "success")
    return render_template("auth/change_password.html")
