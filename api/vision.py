"""
Blueprint: POST /v1/upload

Vision analysis — upload an image and ask the AI a question about it.
Automatically routes to the correct provider based on the model.
"""
import base64
import logging
from flask import Blueprint, jsonify, request
from db.sessions import store
from utils.providers import FREE_MODELS, is_hf_depletion_error, detect_provider
from utils.g4f_client import build_client, extract_text_from_response, make_vision_content

bp = Blueprint("vision", __name__)
log = logging.getLogger(__name__)

_HF_DEPLETED_MSG = (
    "HuggingFace monthly credits depleted. "
    "Switch to OpenAI (Pollinations) for free vision — no token needed."
)


@bp.route("/v1/upload", methods=["POST"])
def upload_file():
    """
    Analyse an uploaded image with a vision-capable AI model.

    Request  : multipart/form-data
      file       — image file (JPG, PNG, WebP, GIF)
      prompt     — question to ask about the image (default: 'Describe this image in detail.')
      model      — model ID (default: openai from PollinationsAI)
      provider   — provider key (auto-detected from model if omitted)
      session_id — optional session key for conversation history
      system     — optional system prompt
      hf_token   — optional HuggingFace token override

    Response : { answer, model, provider, session_id }
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided. Use multipart/form-data with a 'file' field."}), 400

    f = request.files["file"]
    raw = f.read()
    mime = f.content_type or "image/jpeg"

    if not mime.startswith("image/"):
        return jsonify({"error": f"Vision only supports image files. Received: {mime}"}), 400

    b64 = base64.b64encode(raw).decode()
    prompt = request.form.get("prompt", "Describe this image in detail.")
    model = request.form.get("model", "openai")
    explicit_provider = request.form.get("provider")
    session_id = request.form.get("session_id")
    system_prompt = request.form.get("system", "")
    hf_token = request.form.get("hf_token") or request.headers.get("X-HF-Token")

    provider_name = detect_provider(model, explicit_provider)

    log.info(f"[vision/{provider_name}] model={model} file={f.filename!r} size={len(raw)}")

    try:
        client = build_client(provider_name, hf_token)
        content = make_vision_content(prompt, b64, mime)

        # Build message list with optional system prompt
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if session_id:
            messages.extend(store.get(session_id))
        messages.append({"role": "user", "content": content})

        response = client.chat.completions.create(model=model, messages=messages)
        answer = extract_text_from_response(response)

        # Persist to session if requested
        if session_id and answer:
            history = store.get(session_id)
            history.append({"role": "user", "content": prompt})
            history.append({"role": "assistant", "content": answer})
            meta = store.list_all().get(session_id, {})
            store.save(session_id, history, meta.get("turns", 0) + 1)

        return jsonify({
            "answer": answer,
            "model": model,
            "provider": provider_name,
            "session_id": session_id,
        })

    except Exception as exc:
        err_str = str(exc)
        log.error(f"Vision error: {exc}")
        depleted = is_hf_depletion_error(err_str)
        return jsonify({
            "error": _HF_DEPLETED_MSG if depleted else err_str,
            "hf_depleted": depleted,
        }), 500
