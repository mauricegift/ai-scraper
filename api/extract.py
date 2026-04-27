"""
Blueprint: POST /v1/extract

Extract readable text from uploaded documents.
Supports PDF, Word, Excel, CSV, and most text/code formats.
"""
import logging
from flask import Blueprint, jsonify, request
from utils.file_extract import extract_text_from_file, MAX_CHARS

bp = Blueprint("extract", __name__)
log = logging.getLogger(__name__)


@bp.route("/v1/extract", methods=["POST"])
def extract_file():
    """
    Extract text from an uploaded file.

    Request  : multipart/form-data with a 'file' field
    Response : {
        filename  : original file name,
        mime      : detected MIME type,
        size      : bytes,
        chars     : character count of extracted text,
        text      : extracted text (capped at 50,000 chars),
        truncated : true if text was capped
    }
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided. Send a multipart/form-data request with a 'file' field."}), 400

    f = request.files["file"]
    raw = f.read()
    mime = f.content_type or "application/octet-stream"

    log.info(f"[extract] file={f.filename!r} mime={mime} size={len(raw)}")

    text = extract_text_from_file(raw, f.filename or "", mime)
    return jsonify({
        "filename": f.filename,
        "mime": mime,
        "size": len(raw),
        "chars": len(text),
        "text": text[:MAX_CHARS],
        "truncated": len(text) > MAX_CHARS,
    })
