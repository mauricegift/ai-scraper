"""
Blueprint: POST /v1/images/generations

Text-to-image generation.
Free options: FLUX via PollinationsAI, Aria via Opera.
HuggingFace options: FLUX.1-dev / FLUX.1-schnell (need token + credits).
"""
import time
import logging
from flask import Blueprint, jsonify, request
from utils.providers import HF_IMAGE_MODELS, is_hf_depletion_error, detect_image_provider
from utils.g4f_client import build_client

bp = Blueprint("images", __name__)
log = logging.getLogger(__name__)

_HF_DEPLETED_MSG = (
    "HuggingFace monthly credits depleted. "
    "Switch to FLUX (Pollinations) or Aria (Opera) — both are free with no token needed."
)


@bp.route("/v1/images/generations", methods=["POST"])
def generate_image():
    """
    Generate an image from a text prompt.

    Request body (JSON):
      prompt    — description of the image (required)
      model     — model ID (default: flux via PollinationsAI)
      provider  — provider key (auto-detected if omitted)
      size      — "WxH" string (default: 1024x1024)
      n         — number of images to generate (default: 1)
      hf_token  — optional HuggingFace token override

    Response: { created, model, provider, data: [{ url, revised_prompt }] }
    """
    body = request.get_json(force=True)
    prompt = body.get("prompt")
    model = body.get("model", "flux")
    size = body.get("size", "1024x1024")
    n = body.get("n", 1)
    hf_token = body.get("hf_token") or request.headers.get("X-HF-Token")

    if not prompt:
        return jsonify({"error": "'prompt' is required"}), 400

    # Resolve provider
    explicit = body.get("provider")
    provider_name = detect_image_provider(model, explicit)

    # Normalise short model aliases
    if model == "flux":
        provider_name = "pollinations"
    elif model == "flux-schnell":
        model, provider_name = "black-forest-labs/FLUX.1-schnell", "huggingface"
    elif model == "flux-dev":
        model, provider_name = "black-forest-labs/FLUX.1-dev", "huggingface"
    elif model == "aria":
        provider_name = "opera"

    # Parse size
    width, height = 1024, 1024
    if size and "x" in size:
        try:
            w, h = size.split("x")
            width, height = int(w), int(h)
        except ValueError:
            pass

    log.info(f"[image/{provider_name}] model={model} size={width}x{height} prompt={prompt[:60]!r}")

    try:
        client = build_client(provider_name, hf_token)
        response = client.images.generate(
            model=model, prompt=prompt,
            response_format="url", width=width, height=height, n=n,
        )
        images = [{"url": d.url, "revised_prompt": prompt} for d in response.data]
        return jsonify({
            "created": int(time.time()),
            "model": model,
            "provider": provider_name,
            "data": images,
        })

    except Exception as exc:
        err_str = str(exc)
        log.error(f"Image gen error: {exc}")
        depleted = is_hf_depletion_error(err_str)
        return jsonify({
            "error": _HF_DEPLETED_MSG if depleted else err_str,
            "hf_depleted": depleted,
        }), 500
