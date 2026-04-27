"""
Entry point — kept for backwards compatibility with the Replit workflow.
The full application logic now lives in app.py and the api/, db/, utils/ packages.
"""
import os
from app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
