"""
AI Playground — main application factory.

Registers all API blueprints and serves the interactive web UI.
Import `app` from here in tests or WSGI servers (gunicorn, uWSGI).

Storage backend is selected automatically at startup:
  • PostgreSQL — when DATABASE_URL is set in the environment
  • JSON file  — fallback (sessions_store.json in project root)
"""
import os
import time
import logging
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# Load .env file if python-dotenv is installed (ignored gracefully if not)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger(__name__)


def create_app() -> Flask:
    """Application factory — create and configure the Flask app."""
    flask_app = Flask(__name__, template_folder="templates")
    flask_app.secret_key = os.environ.get("SESSION_SECRET", os.urandom(24).hex())
    CORS(flask_app)

    # ── Register API blueprints ───────────────────────────────────────────────
    from api.models import bp as models_bp
    from api.chat import bp as chat_bp
    from api.images import bp as images_bp
    from api.vision import bp as vision_bp
    from api.extract import bp as extract_bp
    from api.sessions import bp as sessions_bp

    for bp in (models_bp, chat_bp, images_bp, vision_bp, extract_bp, sessions_bp):
        flask_app.register_blueprint(bp)

    # ── Core routes ───────────────────────────────────────────────────────────

    @flask_app.route("/", methods=["GET"])
    def index():
        accept = request.headers.get("Accept", "")
        if "text/html" in accept:
            # Serve directly to avoid Jinja2 conflicting with Handlebars {{ }} syntax
            return send_from_directory(flask_app.template_folder, "index.html")
        return jsonify({
            "service": "AI Playground API",
            "version": "3.0.0",
            "ui": "Open in a browser for the interactive playground",
            "endpoints": {
                "GET  /v1/models": "List all available models",
                "GET  /v1/providers": "List providers and capabilities",
                "POST /v1/chat/completions": "Chat (OpenAI-compatible, session history)",
                "POST /v1/images/generations": "Text-to-image generation",
                "POST /v1/upload": "Vision — analyse an uploaded image",
                "POST /v1/extract": "Extract text from PDF/Word/Excel/CSV/TXT",
                "GET  /v1/sessions": "List active sessions",
                "GET  /v1/sessions/{id}": "Get session history",
                "DELETE /v1/sessions/{id}": "Clear one session",
                "DELETE /v1/sessions": "Clear all sessions",
            },
        })

    @flask_app.route("/health", methods=["GET"])
    def health():
        from db.sessions import store
        session_count = len(store.list_all())
        return jsonify({
            "status": "ok",
            "uptime": time.time(),
            "storage_backend": store.backend,
            "active_sessions": session_count,
        })

    return flask_app


app = create_app()
