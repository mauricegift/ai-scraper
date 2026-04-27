"""
Blueprint: /v1/models  and  /v1/providers

Returns the full model catalog grouped by free vs. HuggingFace,
and the provider registry with capability metadata.
"""
import time
from flask import Blueprint, jsonify
from utils.providers import (
    FREE_MODELS, HF_CHAT_MODELS, HF_IMAGE_MODELS, HF_VISION_MODELS, PROVIDERS,
)

bp = Blueprint("models", __name__)


@bp.route("/v1/models", methods=["GET"])
def list_models():
    """
    List all available models.

    Response fields per model:
      id           — model identifier used in API requests
      label        — human-readable name (free models only)
      provider     — provider key (perplexity, pollinations, huggingface, …)
      capabilities — list of supported modes: chat | vision | image
      free         — true = no token needed; false = HF token + credits required
      requires     — "hf_token" for HuggingFace models (absent for free models)
    """
    ts = int(time.time())
    models = []

    # Free models listed first so they appear at the top of selects
    for m in FREE_MODELS:
        models.append({
            "id": m["id"],
            "object": "model",
            "created": ts,
            "label": m["label"],
            "provider": m["provider"],
            "capabilities": m["capabilities"],
            "owned_by": m["provider"],
            "free": True,
        })

    # HuggingFace models — require valid token and monthly credits
    for m in HF_CHAT_MODELS:
        models.append({
            "id": m, "object": "model", "created": ts,
            "provider": "huggingface", "capabilities": ["chat"],
            "owned_by": m.split("/")[0], "free": False, "requires": "hf_token",
        })
    for m in HF_IMAGE_MODELS:
        models.append({
            "id": m, "object": "model", "created": ts,
            "provider": "huggingface", "capabilities": ["image"],
            "owned_by": m.split("/")[0], "free": False, "requires": "hf_token",
        })
    for m in HF_VISION_MODELS:
        models.append({
            "id": m, "object": "model", "created": ts,
            "provider": "huggingface", "capabilities": ["vision"],
            "owned_by": m.split("/")[0], "free": False, "requires": "hf_token",
        })

    return jsonify({"object": "list", "data": models})


@bp.route("/v1/providers", methods=["GET"])
def list_providers():
    """Return the provider registry with capability and auth metadata."""
    result = {
        name: {
            "name": name,
            "description": info["description"],
            "needs_api_key": info.get("needs_key", False),
            "key_type": info.get("key_type", "none"),
            "supports": info["supports"],
            "free": info.get("free", False),
        }
        for name, info in PROVIDERS.items()
    }
    return jsonify(result)
