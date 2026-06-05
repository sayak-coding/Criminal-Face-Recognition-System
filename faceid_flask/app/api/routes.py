from flask import Blueprint, jsonify, request
from flask_login import login_required
from ..face_engine import get_all_persons, get_person_info, load_database

api_bp = Blueprint("api", __name__)


@api_bp.route("/persons", methods=["GET"])
@login_required
def persons():
    return jsonify(get_all_persons())


@api_bp.route("/persons/<string:name>", methods=["GET"])
@login_required
def person(name):
    info = get_person_info(name)
    if not info:
        return jsonify({"error": "Not found"}), 404
    return jsonify(info)


@api_bp.route("/db/status", methods=["GET"])
@login_required
def db_status():
    database = load_database()
    return jsonify({
        "embeddings": len(database),
        "persons"   : len({d["name"] for d in database}),
    })


@api_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})
