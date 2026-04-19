import os
import socket
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / ".env.local", override=True)

FAST_CONNECT_TIMEOUT_SECONDS = 0.35
REQUEST_TIMEOUT = (0.75, 1.5)
REMOTE_REQUEST_TIMEOUT = (4, 12)
DEFAULT_VAPI_URL = "https://api.vapi.ai"
DEFAULT_VAPI_MODEL = "gpt-4o-mini"
DEFAULT_VAULTPROOF_URL = "https://api.vaultproof.dev"
DEFAULT_VAULTPROOF_PROVIDER = "google"
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


def _check_local_endpoint(api_url):
    parsed = urlparse(api_url)
    hostname = (parsed.hostname or "").lower()
    if hostname not in {"localhost", "127.0.0.1"}:
        return None

    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    try:
        with socket.create_connection((hostname, port), timeout=FAST_CONNECT_TIMEOUT_SECONDS):
            return None
    except OSError:
        return {
            "error": f"Voice search service is not running on {hostname}:{port}",
            "hint": f"Start the service that serves {api_url} and try 'voice search for laptop price' again.",
        }


def _looks_like_vaultproof_key(api_key):
    return str(api_key or "").startswith(("vp_live_", "vp_test_"))


def _looks_like_vapi_key(api_key):
    return bool(str(api_key or "").strip()) and not _looks_like_vaultproof_key(api_key)


def _is_local_mock_url(api_url):
    lowered = str(api_url or "").strip().lower()
    return lowered.endswith("/api/voice-search") and "localhost" in lowered


def _extract_vapi_text(payload):
    if not isinstance(payload, dict):
        return None

    output = payload.get("output") or []
    for item in output:
        content = item.get("content") or []
        for part in content:
            text = str(part.get("text") or "").strip()
            if text:
                return text
    return None


def _search_via_vapi(query):
    api_key = (os.getenv("VAPI_API_KEY") or os.getenv("VOICE_SEARCH_API_KEY") or "").strip()
    api_url = (os.getenv("VAPI_API_URL") or DEFAULT_VAPI_URL).rstrip("/")
    model = (os.getenv("VAPI_MODEL") or DEFAULT_VAPI_MODEL).strip()

    system_prompt = (
        "You are a concise desktop voice assistant. "
        "Answer general questions directly in 1 to 3 short sentences. "
        "If the user asks to search or asks a knowledge question, provide the answer naturally instead of listing raw search results. "
        "Do not mention APIs, internal tools, providers, or implementation details."
    )

    payload = {
        "model": model,
        "input": query,
        "stream": False,
        "assistant": {
            "firstMessageMode": "assistant-waits-for-user",
            "model": {
                "provider": "openai",
                "model": model,
                "temperature": 0.4,
                "maxTokens": 90,
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt,
                    }
                ],
            },
        },
    }

    response = requests.post(
        f"{api_url}/chat/responses",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=REMOTE_REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    answer = _extract_vapi_text(payload)
    if not answer:
        return {"error": "Vapi returned no assistant text"}
    return {
        "provider": "vapi",
        "query": query,
        "answer": answer,
        "raw": payload,
    }


def _build_vaultproof_request(query):
    provider = (os.getenv("VOICE_SEARCH_PROVIDER") or DEFAULT_VAULTPROOF_PROVIDER).strip().lower()
    api_root = (os.getenv("VAULTPROOF_API_URL") or DEFAULT_VAULTPROOF_URL).rstrip("/")

    prompt = (
        "You are a concise voice assistant. Answer the user's question directly in 2 to 4 short sentences. "
        "Do not mention APIs, providers, search results, sources, or internal tooling. "
        "If the user is greeting you, respond naturally. "
        f"User: {query}"
    )

    if provider == "google":
        model = (os.getenv("VOICE_SEARCH_MODEL") or DEFAULT_GEMINI_MODEL).strip()
        return {
            "provider": provider,
            "url": f"{api_root}/v1/google/v1beta/models/{model}:generateContent",
            "headers": {
                "Authorization": f"Bearer {os.getenv('VOICE_SEARCH_API_KEY', '').strip()}",
                "Content-Type": "application/json",
            },
            "json": {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": prompt,
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.5,
                    "maxOutputTokens": 180,
                },
            },
        }

    model = (os.getenv("VOICE_SEARCH_MODEL") or DEFAULT_OPENAI_MODEL).strip()
    return {
        "provider": provider,
        "url": f"{api_root}/v1/{provider}/v1/chat/completions",
        "headers": {
            "Authorization": f"Bearer {os.getenv('VOICE_SEARCH_API_KEY', '').strip()}",
            "Content-Type": "application/json",
        },
        "json": {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a concise voice assistant. Reply directly and naturally in 2 to 4 short sentences.",
                },
                {
                    "role": "user",
                    "content": query,
                },
            ],
            "temperature": 0.5,
            "max_tokens": 180,
        },
    }


def _extract_vaultproof_text(provider, payload):
    if not isinstance(payload, dict):
        return None

    if provider == "google":
        candidates = payload.get("candidates") or []
        for candidate in candidates:
            content = candidate.get("content") or {}
            parts = content.get("parts") or []
            texts = [str(part.get("text") or "").strip() for part in parts if str(part.get("text") or "").strip()]
            if texts:
                return " ".join(texts).strip()
        return None

    choices = payload.get("choices") or []
    for choice in choices:
        message = choice.get("message") or {}
        content = str(message.get("content") or "").strip()
        if content:
            return content
    return None


def _search_via_vaultproof(query):
    request_config = _build_vaultproof_request(query)
    response = requests.post(
        request_config["url"],
        headers=request_config["headers"],
        json=request_config["json"],
        timeout=REMOTE_REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    answer = _extract_vaultproof_text(request_config["provider"], payload)
    if not answer:
        return {"error": "Conversation provider returned no answer"}
    return {
        "provider": f"vaultproof-{request_config['provider']}",
        "query": query,
        "answer": answer,
        "raw": payload,
    }


def search_voice(query):
    api_key = (os.getenv("VAPI_API_KEY") or os.getenv("VOICE_SEARCH_API_KEY") or "").strip()
    if not api_key:
        return {"error": "API key not found"}

    api_url = (os.getenv("VOICE_SEARCH_API_URL") or "").strip()
    preferred_provider = (os.getenv("VOICE_SEARCH_PROVIDER") or "").strip().lower()

    if preferred_provider == "vapi" or _looks_like_vapi_key(api_key):
        try:
            return _search_via_vapi(query)
        except requests.HTTPError as error:
            status_code = getattr(error.response, "status_code", None)
            if status_code == 401:
                return {
                    "error": "Vapi rejected the API key",
                    "hint": "Check that VAPI_API_KEY in backend/.env.local is a valid private API key from your Vapi dashboard.",
                }
            return {"error": str(error)}
        except requests.Timeout:
            return {
                "error": "Conversation request timed out",
                "hint": "The Vapi conversation service did not respond quickly enough.",
            }
        except requests.ConnectionError:
            return {
                "error": "Could not connect to the Vapi conversation service",
                "hint": "Check your internet connection and Vapi configuration.",
            }
        except Exception as error:
            return {"error": str(error)}

    if _looks_like_vaultproof_key(api_key) and (not api_url or _is_local_mock_url(api_url)):
        try:
            return _search_via_vaultproof(query)
        except requests.Timeout:
            return {
                "error": "Conversation request timed out",
                "hint": "The VaultProof conversation proxy did not respond quickly enough.",
            }
        except requests.ConnectionError:
            return {
                "error": "Could not connect to the VaultProof conversation proxy",
                "hint": "Check your internet connection and VaultProof configuration.",
            }
        except Exception as error:
            return {"error": str(error)}

    if not api_url:
        return {
            "error": "VOICE_SEARCH_API_URL is not configured",
            "hint": "Add VOICE_SEARCH_API_URL to backend/.env or backend/.env.local to test the voice search provider.",
        }

    local_endpoint_error = _check_local_endpoint(api_url)
    if local_endpoint_error:
        return local_endpoint_error

    try:
        headers = {"Authorization": f"Bearer {api_key}"}
        params = {"query": query}
        response = requests.get(api_url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.Timeout:
        return {
            "error": "Voice search request timed out",
            "hint": f"The provider at {api_url} did not respond quickly enough.",
        }
    except requests.ConnectionError:
        return {
            "error": f"Could not connect to voice search provider at {api_url}",
            "hint": "Check that the service is running and reachable from the backend.",
        }
    except Exception as error:
        return {"error": str(error)}
