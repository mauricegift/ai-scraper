"""
g4f client helpers.

Provides build_client(), extract_text_from_response(), and make_vision_content().
All provider resolution lives in utils/providers.py.
"""
import os
import logging
from utils.providers import PROVIDERS

log = logging.getLogger(__name__)

# Default HuggingFace token — set HF_TOKEN in your .env or environment.
# Leave blank to require per-request token supply.
DEFAULT_HF_TOKEN: str = os.environ.get("HF_TOKEN", "")


def get_provider_cls(name: str):
    """
    Return (ProviderClass, provider_info_dict) for a provider key.
    Returns (None, None) if the provider is not registered.
    """
    import g4f.Provider as P
    info = PROVIDERS.get(name)
    if not info:
        return None, None
    cls = getattr(P, info["cls"], None)
    return cls, info


def build_client(provider_name: str, hf_token: str | None = None):
    """
    Build a g4f Client for the given provider.

    Parameters
    ----------
    provider_name : key in PROVIDERS dict
    hf_token      : optional HuggingFace token override (falls back to HF_TOKEN env var)

    Raises
    ------
    ValueError if provider_name is not registered.
    """
    from g4f.client import Client
    cls, info = get_provider_cls(provider_name)
    if cls is None:
        raise ValueError(f"Unknown or unsupported provider: '{provider_name}'")

    if info.get("needs_key"):
        token = hf_token or DEFAULT_HF_TOKEN
        if not token:
            raise ValueError(
                f"Provider '{provider_name}' requires an API key. "
                "Set HF_TOKEN in your environment or pass hf_token in the request."
            )
        return Client(provider=cls, api_key=token)

    return Client(provider=cls)


def extract_text_from_response(response) -> str:
    """
    Safely extract text content from a g4f response.
    Handles standard ChatCompletion objects, raw strings, and dicts.
    """
    try:
        return response.choices[0].message.content
    except (AttributeError, IndexError, TypeError):
        pass
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        return response.get("content") or response.get("message") or str(response)
    return str(response)


def make_vision_content(text: str, image_b64: str, mime: str = "image/jpeg") -> list:
    """
    Build an OpenAI-style multimodal message content array
    (text + base64 image) for vision requests.
    """
    return [
        {"type": "text", "text": text},
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}},
    ]
