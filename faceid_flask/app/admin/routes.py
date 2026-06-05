import subprocess
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required
from ..auth.routes import admin_required
from ..face_engine import (
    get_all_persons, get_person_info,
    add_person, update_person, delete_person, load_database
)

admin_bp = Blueprint("admin", __name__)


# ── Dashboard ────────────────────────────────────────────────────────────────
@admin_bp.route("/")
@login_required
@admin_required
def dashboard():
    persons = get_all_persons()
    return render_template("admin/dashboard.html", persons=persons)


# ── Add person ───────────────────────────────────────────────────────────────
@admin_bp.route("/persons/add", methods=["GET", "POST"])
@login_required
@admin_required
def add_person_view():
    if request.method == "POST":
        name       = request.form.get("name", "").strip()
        dob        = request.form.get("date_of_birth", "").strip() or None
        dod        = request.form.get("date_of_death", "").strip() or None
        status     = request.form.get("status", "").strip()
        activities = request.form.get("activities", "").splitlines()

        if not name:
            flash("Name is required.", "danger")
            return redirect(request.url)

        if add_person(name, dob, dod, status, activities):
            flash(f"'{name}' added successfully.", "success")
            return redirect(url_for("admin.dashboard"))
        flash("Error adding person (name may already exist).", "danger")

    return render_template("admin/person_form.html", person=None, action="Add")


# ── Edit person ──────────────────────────────────────────────────────────────
@admin_bp.route("/persons/edit/<int:person_id>", methods=["GET", "POST"])
@login_required
@admin_required
def edit_person(person_id):
    info = get_person_info_by_id(person_id)
    if not info:
        flash("Person not found.", "danger")
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        name       = request.form.get("name", "").strip()
        dob        = request.form.get("date_of_birth", "").strip() or None
        dod        = request.form.get("date_of_death", "").strip() or None
        status     = request.form.get("status", "").strip()
        activities = request.form.get("activities", "").splitlines()

        if update_person(person_id, name, dob, dod, status, activities):
            flash(f"'{name}' updated successfully.", "success")
            return redirect(url_for("admin.dashboard"))
        flash("Error updating person.", "danger")

    return render_template("admin/person_form.html", person=info, action="Edit")


# ── Delete person ─────────────────────────────────────────────────────────────
@admin_bp.route("/persons/delete/<int:person_id>", methods=["POST"])
@login_required
@admin_required
def delete_person_view(person_id):
    if delete_person(person_id):
        flash("Person deleted.", "success")
    else:
        flash("Error deleting person.", "danger")
    return redirect(url_for("admin.dashboard"))


# ── Reload embeddings in memory ───────────────────────────────────────────────
@admin_bp.route("/reload-db", methods=["POST"])
@login_required
@admin_required
def reload_db():
    try:
        db = load_database(force=True)
        flash(f"Embeddings reloaded — {len(db)} embeddings in memory.", "success")
    except Exception as e:
        flash(f"Reload failed: {e}", "danger")
    return redirect(url_for("admin.dashboard"))


# ── Helper: fetch person by ID ────────────────────────────────────────────────
def get_person_info_by_id(person_id: int) -> dict | None:
    import sqlite3
    from flask import current_app
    sqlite_path = current_app.config["TERRORIST_DB_PATH"]
    try:
        conn = sqlite3.connect(sqlite_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM persons WHERE id = ?", (person_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return None
        cur.execute(
            "SELECT activity FROM activities WHERE person_id = ? ORDER BY id",
            (row["id"],)
        )
        activities = [r["activity"] for r in cur.fetchall()]
        conn.close()
        return {
            "id"           : row["id"],
            "name"         : row["name"],
            "date_of_birth": row["date_of_birth"] or "",
            "date_of_death": row["date_of_death"] or "",
            "status"       : row["status"] or "",
            "activities"   : activities,
        }
    except Exception as e:
        return None
