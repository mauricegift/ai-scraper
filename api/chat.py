"""
Blueprint: POST /v1/chat/completions

OpenAI-compatible chat endpoint with:
  - Multi-turn session memory (PostgreSQL or JSON file)
  - Provider auto-detection from model name
  - SSE streaming support
  - HuggingFace credit-depletion detection with user-friendly guidance
"""
import json
import time
import uuid
import logging
from flask import Blueprint, jsonify, request, Response, stream_with_context
from db.sessions import store
from utils.providers import (
    FREE_MODELS, HF_CHAT_MODELS, HF_VISION_MODELS,
    is_hf_depletion_error, detect_provider,
)
from utils.g4f_client import build_client, extract_text_from_response

bp = Blueprint("chat", __name__)
log = logging.getLogger(__name__)

_HF_DEPLETED_MSG = (
    "HuggingFace monthly credits depleted. "
    "Switch to a free model — GPT-4.1, GPT-5, Claude, Mistral via Perplexity, "
    "or OpenAI Fast via PollinationsAI. No token needed."
)


def _resolve_provider(body: dict, model: str) -> str:
    explicit = body.get("provider")
    return detect_provider(model, explicit)


@bp.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    """
    OpenAI-compatible chat completions.

    Request body (JSON):
      model          — model ID  (default: auto via Perplexity)
      messages       — list of {role, content} (required)
      provider       — provider key; auto-detected from model if omitted
      session_id     — optional key for persistent conversation history
      system         — optional system prompt (prepended to every request)
      max_tokens     — int  (default: 2048)
      temperature    — float  (default: 0.7)
      stream         — bool SSE streaming (default: false)
      reset_session  — bool clear history before this turn (default: false)
      hf_token       — optional HuggingFace token override

    Response: OpenAI ChatCompletion object
    """
    body = request.get_json(force=True)
    model = body.get("model", "auto")
    messages = body.get("messages", [])
    session_id = body.get("session_id")
    system_prompt = body.get("system")
    max_tokens = body.get("max_tokens", 2048)
    temperature = body.get("temperature", 0.7)
    do_stream = body.get("stream", False)
    reset = body.get("reset_session", False)
    hf_token = body.get("hf_token") or request.headers.get("X-HF-Token")

    provider_name = _resolve_provider(body, model)

    # ── Session management ────────────────────────────────────────────────────
    history = []
    if session_id:
        if reset:
            store.delete(session_id)
        history = store.get(session_id)

    # ── Build full message list ───────────────────────────────────────────────
    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(history)
    full_messages.extend(messages)

    if not full_messages:
        return jsonify({"error": "No messages provided"}), 400

    log.info(f"[{provider_name}] model={model} session={session_id} msgs={len(full_messages)}")

    try:
        client = build_client(provider_name, hf_token)
        kwargs = {"model": model, "messages": full_messages}
        if max_tokens:
            kwargs["max_tokens"] = max_tokens

        # ── Streaming response ────────────────────────────────────────────────
        if do_stream:
            def generate():
                resp_text = ""
                chunk_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
                try:
                    response = client.chat.completions.create(**kwargs, stream=True)
                    for chunk in response:
                        delta = chunk.choices[0].delta.content or ""
                        resp_text += delta
                        yield f"data: {json.dumps({'id': chunk_id, 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': model, 'choices': [{'index': 0, 'delta': {'content': delta}, 'finish_reason': None}]})}\n\n"

                    # Persist turn to session store
                    if session_id and resp_text:
                        for m in messages:
                            history.append(m)
                        history.append({"role": "assistant", "content": resp_text})
                        meta = store.list_all().get(session_id, {})
                        store.save(session_id, history, meta.get("turns", 0) + 1)

                    yield "data: [DONE]\n\n"

                except Exception as exc:
                    err = str(exc)
                    depleted = is_hf_depletion_error(err)
                    yield f"data: {json.dumps({'error': _HF_DEPLETED_MSG if depleted else err, 'hf_depleted': depleted})}\n\n"

            return Response(stream_with_context(generate()), content_type="text/event-stream")

        # ── Non-streaming response ────────────────────────────────────────────
        response = client.chat.completions.create(**kwargs)
        content = extract_text_from_response(response)

        # Persist turn to session store
        if session_id and content:
            for m in messages:
                history.append({
                    "role": m["role"],
                    "content": m["content"] if isinstance(m["content"], str) else str(m["content"]),
                })
            history.append({"role": "assistant", "content": content})
            meta = store.list_all().get(session_id, {})
            store.save(session_id, history, meta.get("turns", 0) + 1)

        return jsonify({
            "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "provider": provider_name,
            "session_id": session_id,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": -1, "completion_tokens": -1, "total_tokens": -1},
        })

    except Exception as exc:
        err_str = str(exc)
        log.error(f"Chat error: {exc}")
        depleted = is_hf_depletion_error(err_str)
        return jsonify({
            "error": _HF_DEPLETED_MSG if depleted else err_str,
            "provider": provider_name,
            "model": model,
            "hf_depleted": depleted,
        }), 500
