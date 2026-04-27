"""
Provider and model catalog.

Free providers require no API key or credits.
HuggingFace providers need a valid HF_TOKEN with remaining monthly credits.
"""

# ── Provider registry ─────────────────────────────────────────────────────────
PROVIDERS = {
    # Free providers — confirmed working from hosted environments, no signup required
    "pollinations": {
        "cls": "PollinationsAI",
        "needs_key": False,
        "description": "PollinationsAI — free, fast, no signup. Chat and vision.",
        "supports": ["chat", "vision", "image"],
        "free": True,
    },
    "perplexity": {
        "cls": "Perplexity",
        "needs_key": False,
        "description": "Perplexity AI — free. GPT-4.1, GPT-5, Claude, Llama, Mistral.",
        "supports": ["chat"],
        "free": True,
    },
    "yqcloud": {
        "cls": "Yqcloud",
        "needs_key": False,
        "description": "YqCloud — free GPT-4/4o access, no key needed.",
        "supports": ["chat"],
        "free": True,
    },
    "opera": {
        "cls": "OperaAria",
        "needs_key": False,
        "description": "Opera Aria — free chat and image generation.",
        "supports": ["chat", "image"],
        "free": True,
    },
    # HuggingFace — requires HF_TOKEN env var or per-request token.
    # Monthly free credits apply; returns HTTP 402 when depleted.
    "huggingface": {
        "cls": "HuggingFace",
        "needs_key": True,
        "key_type": "hf",
        "description": (
            "HuggingFace Spaces — 15+ models, vision, image gen. "
            "Requires HF token. Monthly credits apply."
        ),
        "supports": ["chat", "vision", "image"],
        "free": False,
    },
}

# ── Free models (no token, no credits) — all confirmed working ────────────────
FREE_MODELS = [
    # Perplexity ─ 8 models
    {"id": "auto",          "provider": "perplexity", "label": "Perplexity Auto",      "capabilities": ["chat"]},
    {"id": "turbo",         "provider": "perplexity", "label": "Perplexity Turbo",      "capabilities": ["chat"]},
    {"id": "gpt41",         "provider": "perplexity", "label": "GPT-4.1 (Perplexity)", "capabilities": ["chat"]},
    {"id": "gpt5",          "provider": "perplexity", "label": "GPT-5 (Perplexity)",   "capabilities": ["chat"]},
    {"id": "gpt5_thinking", "provider": "perplexity", "label": "GPT-5 Thinking",        "capabilities": ["chat"]},
    {"id": "llama",         "provider": "perplexity", "label": "Llama (Perplexity)",   "capabilities": ["chat"]},
    {"id": "mistral",       "provider": "perplexity", "label": "Mistral (Perplexity)", "capabilities": ["chat"]},
    {"id": "claude",        "provider": "perplexity", "label": "Claude (Perplexity)",  "capabilities": ["chat"]},
    # PollinationsAI ─ 3 models
    {"id": "openai",        "provider": "pollinations", "label": "OpenAI (Pollinations)", "capabilities": ["chat", "vision"]},
    {"id": "openai-fast",   "provider": "pollinations", "label": "OpenAI Fast",           "capabilities": ["chat", "vision"]},
    {"id": "flux",          "provider": "pollinations", "label": "FLUX (Pollinations)",   "capabilities": ["image"]},
    # YqCloud ─ 3 models
    {"id": "gpt-4",         "provider": "yqcloud", "label": "GPT-4 (YqCloud)",        "capabilities": ["chat"]},
    {"id": "gpt-4o",        "provider": "yqcloud", "label": "GPT-4o (YqCloud)",       "capabilities": ["chat"]},
    {"id": "gpt-3.5-turbo", "provider": "yqcloud", "label": "GPT-3.5 Turbo",          "capabilities": ["chat"]},
    # Opera Aria ─ 1 model
    {"id": "aria",          "provider": "opera",  "label": "Aria (Opera)",            "capabilities": ["chat", "image"]},
]

# ── HuggingFace models (need HF token + monthly credits) ─────────────────────
HF_CHAT_MODELS = [
    "deepseek-ai/DeepSeek-V4-Pro",
    "deepseek-ai/DeepSeek-R1",
    "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
    "meta-llama/Llama-3.1-8B-Instruct",
    "meta-llama/Llama-3.3-70B-Instruct",
    "Qwen/Qwen2.5-7B-Instruct",
    "Qwen/Qwen2.5-Coder-32B-Instruct",
    "Qwen/Qwen3-8B",
    "Qwen/Qwen3-Coder-Next",
    "Qwen/QwQ-32B",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "zai-org/GLM-5.1",
    "MiniMaxAI/MiniMax-M2.7",
    "stepfun-ai/Step-3.5-Flash",
]
HF_IMAGE_MODELS = [
    "black-forest-labs/FLUX.1-dev",
    "black-forest-labs/FLUX.1-schnell",
]
HF_VISION_MODELS = [
    "meta-llama/Llama-3.2-11B-Vision-Instruct",
    "Qwen/Qwen2-VL-7B-Instruct",
]

# ── HuggingFace depletion detection ──────────────────────────────────────────
_HF_DEPLETION_PHRASES = [
    "402", "depleted", "monthly included credits",
    "pre-paid credits", "subscribe to PRO",
]

def is_hf_depletion_error(err_str: str) -> bool:
    """Return True if the error string indicates HF monthly credits are exhausted."""
    return any(p in err_str for p in _HF_DEPLETION_PHRASES)


def detect_provider(model: str, explicit_provider: str | None = None) -> str:
    """
    Resolve which provider to use for a given model.

    Priority order:
      1. Explicit provider from request body (unless 'auto' or empty)
      2. FREE_MODELS lookup table
      3. HuggingFace model prefix patterns
      4. Fallback to Perplexity (free and reliable)
    """
    if explicit_provider and explicit_provider != "auto":
        return explicit_provider

    # Check free model catalog first
    free_match = next((m for m in FREE_MODELS if m["id"] == model), None)
    if free_match:
        return free_match["provider"]

    # Known HuggingFace model prefixes
    hf_prefixes = (
        "deepseek-ai/", "meta-llama/", "Qwen/", "openai/gpt-oss",
        "zai-org/", "MiniMaxAI/", "stepfun-ai/", "black-forest-labs/",
    )
    if model in HF_CHAT_MODELS + HF_IMAGE_MODELS + HF_VISION_MODELS:
        return "huggingface"
    if model.startswith(hf_prefixes):
        return "huggingface"

    # Free fallback
    return "perplexity"


def detect_image_provider(model: str, explicit_provider: str | None = None) -> str:
    """Resolve image provider for a given model."""
    if explicit_provider and explicit_provider != "auto":
        return explicit_provider

    free_match = next(
        (m for m in FREE_MODELS if m["id"] == model and "image" in m["capabilities"]),
        None,
    )
    if free_match:
        return free_match["provider"]

    if model in HF_IMAGE_MODELS:
        return "huggingface"

    return "pollinations"  # default free image provider
