"""
Blueprint: /v1/sessions

CRUD operations on stored conversation sessions.
Storage engine is selected automatically in db/sessions.py
(PostgreSQL if DATABASE_URL is set, else JSON file).
"""
from flask import Blueprint, jsonify, request
from db.sessions import store

bp = Blueprint("sessions", __name__)


@bp.route("/v1/sessions", methods=["GET"])
def list_sessions():
    """Return metadata for all stored sessions."""
    all_sessions = store.list_all()
    return jsonify({
        "count": len(all_sessions),
        "backend": store.backend,
        "sessions": all_sessions,
    })


@bp.route("/v1/sessions/<session_id>", methods=["GET"])
def get_session(session_id: str):
    """Return the full message history for a session."""
    messages = store.get(session_id)
    return jsonify({
        "session_id": session_id,
        "message_count": len(messages),
        "messages": messages,
    })


@bp.route("/v1/sessions/<session_id>", methods=["DELETE"])
def delete_session(session_id: str):
    """Delete a single session and its history."""
    store.delete(session_id)
    return jsonify({"deleted": session_id})


@bp.route("/v1/sessions", methods=["DELETE"])
def delete_all_sessions():
    """Delete every stored session. Use with caution."""
    store.delete_all()
    return jsonify({"deleted": "all"})
