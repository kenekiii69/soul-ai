# ==========================================================
# Soul AI 💫
# Universal API Manager
# Multi-Provider Health Check + Runtime Failover + Streaming
# DB Driven
# ==========================================================

import json
import time
import threading
import os 
from typing import Any, Dict, Generator, Optional

import mysql.connector
import requests
from google import genai


# ==========================================================
# Database Configuration
# ==========================================================

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "soul_ai")
}

if os.getenv("DB_SSL_MODE", "").upper() == "REQUIRED":
    DB_CONFIG["ssl_disabled"] = False

    if os.getenv("DB_SSL_CA"):
        DB_CONFIG["ssl_ca"] = os.getenv("DB_SSL_CA")

HEALTH_CHECK_INTERVAL = 300
REQUEST_TIMEOUT = 60
HEALTH_TIMEOUT = 20

# Health classification thresholds
# Cloud APIs commonly take a few seconds even when perfectly healthy.
HEALTHY_THRESHOLD_MS = 5000
MODEL_NAME = "gemini-2.5-flash"

# Provider slugs supported by this manager.
SUPPORTED_PROVIDERS = {
    "gemini",
    "openai",
    "anthropic",
    "xai",
    "grok",
    "deepseek",
    "mistral",
    "ollama",
}


# ==========================================================
# Helpers
# ==========================================================

def normalize_provider_slug(provider_slug: str) -> str:
    slug = (provider_slug or "").strip().lower()

    aliases = {
        "google-gemini": "gemini",
        "google_gemini": "gemini",
        "claude": "anthropic",
        "anthropic-claude": "anthropic",
        "grok": "xai",
        "x-ai": "xai",
        "x_ai": "xai",
        "deep-seek": "deepseek",
    }

    return aliases.get(slug, slug)


def clean_base_url(url: Optional[str]) -> str:
    return (url or "").strip().rstrip("/")


def parse_sse_data(raw_line: Any) -> Dict[str, Any]:
    """Safely parse an SSE data line into a dictionary."""
    if raw_line is None:
        return {}

    if isinstance(raw_line, bytes):
        raw_line = raw_line.decode("utf-8", errors="ignore")

    line = str(raw_line).strip()

    if not line or line.startswith(":"):
        return {}

    if line.startswith("data:"):
        line = line[5:].strip()

    if not line or line in {"[DONE]", "[done]"}:
        return {}

    # SSE control fields are not JSON payloads.
    if line.startswith(("event:", "id:", "retry:")):
        return {}

    try:
        parsed = json.loads(line)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


def extract_response_text(data: Any) -> str:
    """Extract response text from Anthropic, OpenAI-compatible, Ollama, or generic JSON."""
    if not isinstance(data, dict):
        return ""

    # Anthropic
    content = data.get("content")
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                value = item.get("text")
                if isinstance(value, str):
                    parts.append(value)
        if parts:
            return "".join(parts)

    # OpenAI-compatible
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0] or {}
        if isinstance(first, dict):
            message = first.get("message") or {}
            if isinstance(message, dict):
                value = message.get("content")
                if isinstance(value, str):
                    return value

            value = first.get("text")
            if isinstance(value, str):
                return value

            delta = first.get("delta") or {}
            if isinstance(delta, dict):
                value = delta.get("content")
                if isinstance(value, str):
                    return value

    # Ollama
    message = data.get("message") or {}
    if isinstance(message, dict):
        value = message.get("content")
        if isinstance(value, str):
            return value

    value = data.get("response")
    if isinstance(value, str):
        return value

    # Generic provider formats
    for key in ("text", "output", "answer"):
        value = data.get(key)
        if isinstance(value, str):
            return value

    return ""


def classify_error(error_text: str) -> str:
    text = (error_text or "").lower()

    if any(marker in text for marker in (
        "429", "rate limit", "rate_limit", "quota",
        "resource exhausted", "resource_exhausted", "too many requests", "throttl",
    )):
        return "rate_limited"

    if any(marker in text for marker in (
        "401", "403", "unauthorized", "invalid api key", "invalid_api_key",
        "permission denied", "forbidden", "api key is invalid",
    )):
        return "invalid"

    # DB/model configuration or provider billing errors make the record
    # unusable for routing. We map them to the existing invalid enum rather
    # than falsely calling them "slow". The detailed error is kept in DB.
    if any(marker in text for marker in (
        "unsupported parameter", "model_slug is missing", "model is missing",
        "model not found", "unknown model", "does not exist", "not found",
        "credit balance is too low", "insufficient_quota", "billing",
    )):
        return "invalid"

    if any(marker in text for marker in (
        "timeout", "timed out", "connection", "connecterror",
        "connection refused", "connection reset", "network",
        "502", "503", "504",
    )):
        return "slow"

    return "slow"


def update_key_stats(
    key_id,
    response_time_ms,
    success=True,
    error_message=None,
):
    connection = None
    cursor = None

    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()

        if success:
            query = """
                UPDATE api_keys
                SET
                    total_requests = total_requests + 1,
                    used_today = used_today + 1,
                    average_response_ms =
                        CASE
                            WHEN total_requests = 0
                            THEN %s
                            ELSE (
                                (
                                    average_response_ms * total_requests
                                ) + %s
                            ) / (total_requests + 1)
                        END,
                    last_used = NOW(),
                    updated_at = NOW()
                WHERE id = %s
            """

            cursor.execute(
                query,
                (
                    int(response_time_ms),
                    int(response_time_ms),
                    key_id,
                ),
            )

        else:
            query = """
                UPDATE api_keys
                SET
                    total_requests = total_requests + 1,
                    total_errors = total_errors + 1,
                    last_error = %s,
                    last_used = NOW(),
                    updated_at = NOW()
                WHERE id = %s
            """

            cursor.execute(
                query,
                (
                    str(error_message)[:1000],
                    key_id,
                ),
            )

        connection.commit()

    except mysql.connector.Error as err:
        print(f"⚠️ Stats Update Error: {err}")

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def update_health_status(
    key_id,
    health_status,
    response_time_ms=None,
    error_message=None,
):
    connection = None
    cursor = None

    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()

        query = """
            UPDATE api_keys
            SET
                health_status = %s,
                last_error = %s,
                average_response_ms =
                    CASE
                        WHEN %s IS NULL
                        THEN average_response_ms
                        ELSE %s
                    END,
                updated_at = NOW()
            WHERE id = %s
        """

        cursor.execute(
            query,
            (
                health_status,
                str(error_message)[:1000] if error_message else None,
                response_time_ms,
                response_time_ms,
                key_id,
            ),
        )

        connection.commit()

    except mysql.connector.Error as err:
        print(f"⚠️ Health DB Update Error: {err}")

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def mark_runtime_failure(selected_api, error_text):
    health_status = classify_error(error_text)

    update_health_status(
        selected_api["id"],
        health_status,
        None,
        error_text,
    )

    print(
        f"⚠️ Runtime Health Update → "
        f"{selected_api.get('provider_name')} | "
        f"{selected_api.get('key_name')} | "
        f"{health_status}"
    )


# ==========================================================
# Provider HTTP Helpers
# ==========================================================

def provider_headers(provider_slug, api_key):
    provider = normalize_provider_slug(provider_slug)

    if provider == "anthropic":
        return {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

    if provider == "ollama":
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def get_chat_endpoint(selected_api):
    provider = normalize_provider_slug(selected_api.get("provider_slug"))
    base_url = clean_base_url(selected_api.get("api_base_url"))

    if provider == "openai":
        if not base_url:
            base_url = "https://api.openai.com/v1"
        if not base_url.endswith("/v1"):
            base_url += "/v1"
        return f"{base_url}/chat/completions"

    if provider == "xai":
        if not base_url:
            base_url = "https://api.x.ai"
        if base_url.endswith("/v1"):
            return f"{base_url}/chat/completions"
        return f"{base_url}/v1/chat/completions"

    if provider == "deepseek":
        if not base_url:
            base_url = "https://api.deepseek.com"
        return f"{base_url}/chat/completions"

    if provider == "mistral":
        if not base_url:
            base_url = "https://api.mistral.ai/v1"
        if not base_url.endswith("/v1"):
            base_url += "/v1"
        return f"{base_url}/chat/completions"

    return ""


# ==========================================================
# Provider Non-streaming Generators
# ==========================================================

def generate_gemini(prompt, selected_api):
    start_time = time.perf_counter()

    try:
        ai = genai.Client(api_key=selected_api["api_key"])

        model_name = (
            selected_api.get("model_slug")
            or MODEL_NAME
        )

        response = ai.models.generate_content(
            model=model_name,
            contents=prompt,
        )

        response_time_ms = (time.perf_counter() - start_time) * 1000
        text = getattr(response, "text", None)

        if not text:
            raise RuntimeError("Gemini returned an empty response.")

        update_key_stats(
            selected_api["id"],
            response_time_ms,
            success=True,
        )

        update_health_status(
            selected_api["id"],
            "healthy" if response_time_ms < HEALTHY_THRESHOLD_MS else "slow",
            response_time_ms,
            None,
        )

        print(
            f"✅ Gemini response generated | "
            f"{int(response_time_ms)} ms | "
            f"{selected_api['key_name']}"
        )

        return text, True

    except Exception as e:
        response_time_ms = (time.perf_counter() - start_time) * 1000
        error_text = str(e)

        print(
            f"❌ Gemini Runtime Error | "
            f"{selected_api['key_name']} | "
            f"{error_text}"
        )

        update_key_stats(
            selected_api["id"],
            response_time_ms,
            success=False,
            error_message=error_text,
        )

        mark_runtime_failure(selected_api, error_text)

        return None, False


def generate_anthropic(prompt, selected_api):
    start_time = time.perf_counter()

    try:
        endpoint = clean_base_url(selected_api.get("api_base_url"))
        if not endpoint:
            endpoint = "https://api.anthropic.com"

        if not endpoint.endswith("/v1"):
            endpoint += "/v1"

        endpoint += "/messages"

        model = selected_api.get("model_slug")
        if not model:
            raise RuntimeError("Anthropic model_slug is missing in DB.")

        max_tokens = int(selected_api.get("max_output_tokens") or 4096)
        max_tokens = min(max_tokens, 16384)

        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "user", "content": prompt}
            ],
        }

        response = requests.post(
            endpoint,
            headers=provider_headers("anthropic", selected_api["api_key"]),
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )

        if not response.ok:
            raise RuntimeError(
                f"Anthropic HTTP {response.status_code}: "
                f"{response.text[:1000]}"
            )

        data = response.json()
        text = extract_response_text(data)

        if not text:
            raise RuntimeError("Anthropic returned an empty response.")

        response_time_ms = (time.perf_counter() - start_time) * 1000

        update_key_stats(selected_api["id"], response_time_ms, True)
        update_health_status(
            selected_api["id"],
            "healthy" if response_time_ms < HEALTHY_THRESHOLD_MS else "slow",
            response_time_ms,
            None,
        )

        print(
            f"✅ Anthropic response generated | "
            f"{int(response_time_ms)} ms | "
            f"{selected_api['key_name']}"
        )

        return text, True

    except Exception as e:
        response_time_ms = (time.perf_counter() - start_time) * 1000
        error_text = str(e)

        print(
            f"❌ Anthropic Runtime Error | "
            f"{selected_api['key_name']} | {error_text}"
        )

        update_key_stats(
            selected_api["id"],
            response_time_ms,
            False,
            error_text,
        )
        mark_runtime_failure(selected_api, error_text)

        return None, False


def generate_openai_compatible(prompt, selected_api):
    start_time = time.perf_counter()
    provider = normalize_provider_slug(selected_api.get("provider_slug"))

    try:
        endpoint = get_chat_endpoint(selected_api)
        if not endpoint:
            raise RuntimeError(
                f"No chat endpoint configured for provider "
                f"{selected_api.get('provider_name')}"
            )

        model = selected_api.get("model_slug")
        if not model:
            raise RuntimeError("model_slug is missing in DB.")

        max_tokens = selected_api.get("max_output_tokens")
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "stream": False,
        }

        if max_tokens:
            if provider == "openai":
                payload["max_completion_tokens"] = min(int(max_tokens), 32768)
            else:
                payload["max_tokens"] = min(int(max_tokens), 32768)

        response = requests.post(
            endpoint,
            headers=provider_headers(provider, selected_api["api_key"]),
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )

        if not response.ok:
            raise RuntimeError(
                f"{selected_api.get('provider_name')} "
                f"HTTP {response.status_code}: "
                f"{response.text[:1000]}"
            )

        data = response.json()
        text = extract_response_text(data)

        if not text:
            raise RuntimeError(
                f"{selected_api.get('provider_name')} returned "
                "an empty response."
            )

        response_time_ms = (time.perf_counter() - start_time) * 1000

        update_key_stats(selected_api["id"], response_time_ms, True)
        update_health_status(
            selected_api["id"],
            "healthy" if response_time_ms < HEALTHY_THRESHOLD_MS else "slow",
            response_time_ms,
            None,
        )

        print(
            f"✅ {selected_api.get('provider_name')} response generated | "
            f"{int(response_time_ms)} ms | "
            f"{selected_api['key_name']}"
        )

        return text, True

    except Exception as e:
        response_time_ms = (time.perf_counter() - start_time) * 1000
        error_text = str(e)

        print(
            f"❌ {selected_api.get('provider_name')} Runtime Error | "
            f"{selected_api['key_name']} | {error_text}"
        )

        update_key_stats(
            selected_api["id"],
            response_time_ms,
            False,
            error_text,
        )
        mark_runtime_failure(selected_api, error_text)

        return None, False


def generate_ollama(prompt, selected_api):
    start_time = time.perf_counter()

    try:
        base_url = clean_base_url(selected_api.get("api_base_url"))
        if not base_url:
            base_url = "http://localhost:11434"

        endpoint = (
            base_url
            if base_url.endswith("/api/chat")
            else f"{base_url}/api/chat"
        )

        model = selected_api.get("model_slug")
        if not model:
            raise RuntimeError("Ollama model_slug is missing in DB.")

        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "stream": False,
        }

        response = requests.post(
            endpoint,
            headers=provider_headers("ollama", selected_api.get("api_key")),
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )

        if not response.ok:
            raise RuntimeError(
                f"Ollama HTTP {response.status_code}: "
                f"{response.text[:1000]}"
            )

        data = response.json()
        text = extract_response_text(data)

        if not text:
            raise RuntimeError("Ollama returned an empty response.")

        response_time_ms = (time.perf_counter() - start_time) * 1000

        update_key_stats(selected_api["id"], response_time_ms, True)
        update_health_status(
            selected_api["id"],
            "healthy" if response_time_ms < HEALTHY_THRESHOLD_MS else "slow",
            response_time_ms,
            None,
        )

        print(
            f"✅ Ollama response generated | "
            f"{int(response_time_ms)} ms | "
            f"{selected_api['key_name']}"
        )

        return text, True

    except Exception as e:
        response_time_ms = (time.perf_counter() - start_time) * 1000
        error_text = str(e)

        print(
            f"❌ Ollama Runtime Error | "
            f"{selected_api['key_name']} | {error_text}"
        )

        update_key_stats(
            selected_api["id"],
            response_time_ms,
            False,
            error_text,
        )
        mark_runtime_failure(selected_api, error_text)

        return None, False


# ==========================================================
# Provider Dispatcher
# ==========================================================

def generate_provider(prompt, selected_api):
    provider = normalize_provider_slug(
        selected_api.get("provider_slug")
    )

    if provider == "gemini":
        return generate_gemini(prompt, selected_api)

    if provider == "anthropic":
        return generate_anthropic(prompt, selected_api)

    if provider == "ollama":
        return generate_ollama(prompt, selected_api)

    if provider in {"openai", "xai", "deepseek", "mistral"}:
        return generate_openai_compatible(prompt, selected_api)

    return (
        f"⚠️ Provider '{selected_api.get('provider_name')}' "
        "is configured but not implemented."
    ), False


# ==========================================================
# Runtime Configuration Guard
# ==========================================================

def api_is_runtime_usable(api):
    """Reject incomplete DB records before they enter the failover chain."""
    provider = normalize_provider_slug(api.get("provider_slug"))
    model = (api.get("model_slug") or "").strip()

    if provider in {"gemini", "openai", "anthropic", "xai", "deepseek", "mistral", "ollama"} and not model:
        return False

    return True


# ==========================================================
# 🧠 SMART ROUTING ENGINE
# ==========================================================

CAPABILITY_COLUMN_MAP = {
    "image": "supports_images",
    "images": "supports_images",
    "vision": "supports_images",
    "file": "supports_files",
    "files": "supports_files",
    "pdf": "supports_files",
    "web": "supports_web_search",
    "web_search": "supports_web_search",
    "search": "supports_web_search",
    "stream": "supports_streaming",
    "streaming": "supports_streaming",
    "function": "supports_function_calling",
    "functions": "supports_function_calling",
    "function_calling": "supports_function_calling",
    "tool": "supports_function_calling",
    "tools": "supports_function_calling",
    "json": "supports_json_mode",
    "json_mode": "supports_json_mode",
}


def _normalize_capability(value):
    value = (value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "image_generation": "image",
        "image_input": "image",
        "vision": "image",
        "document": "files",
        "documents": "files",
        "websearch": "web_search",
        "function_call": "function_calling",
        "tool_use": "function_calling",
        "structured_output": "json_mode",
    }
    return aliases.get(value, value)


def detect_capability(prompt, requested_capability=None):
    """Resolve an explicit capability first, then infer a useful capability."""
    explicit = _normalize_capability(requested_capability)
    if explicit:
        return explicit

    text = (prompt or "").lower()

    # Strong, specific signals first.
    if any(x in text for x in ("json", "json format", "json object", "structured output")):
        return "json_mode"
    if any(x in text for x in ("function calling", "tool call", "tool use", "call a function")):
        return "function_calling"
    if any(x in text for x in ("upload", "attached file", "pdf", "document", "file analysis", "read this file")):
        return "files"
    if any(x in text for x in ("image", "photo", "picture", "screenshot", "vision", "visual")):
        return "images"
    if any(x in text for x in ("latest", "today", "current", "news", "weather", "search the web", "web search", "internet")):
        return "web_search"
    if any(x in text for x in ("stream", "streaming")):
        return "streaming"

    return "general"


def _load_capability_record(capability):
    """Find a DB capability by slug/name. Returns None for general/unmatched."""
    capability = _normalize_capability(capability)
    if not capability or capability == "general":
        return None

    connection = None
    cursor = None
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, capability_name, capability_slug
            FROM ai_capabilities
            WHERE LOWER(capability_slug) = %s
               OR LOWER(capability_name) = %s
            LIMIT 1
        """, (capability, capability.replace("_", " ")))
        return cursor.fetchone()
    except Exception as e:
        print(f"⚠️ Capability Lookup Error: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def _routing_provider_ids(capability_record):
    """Return providers configured by admin routing rules, in priority order."""
    if not capability_record:
        return []

    connection = None
    cursor = None
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                r.primary_provider_id,
                r.fallback_provider_id,
                r.priority
            FROM provider_routing_rules r
            WHERE r.capability_id = %s
              AND r.is_active = 1
            ORDER BY r.priority ASC, r.created_at ASC
        """, (capability_record["id"],))

        ordered = []
        for row in cursor.fetchall():
            for provider_id in (row.get("primary_provider_id"), row.get("fallback_provider_id")):
                if provider_id and provider_id not in ordered:
                    ordered.append(provider_id)
        return ordered
    except Exception as e:
        print(f"⚠️ Routing Rule Lookup Error: {e}")
        return []
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def _api_supports_capability(api, capability):
    capability = _normalize_capability(capability)
    if capability in ("", "general", None):
        return True

    column = CAPABILITY_COLUMN_MAP.get(capability)
    if not column:
        # Unknown custom capability: if the admin created a routing rule,
        # provider selection still works; don't block the request.
        return True

    return bool(api.get(column))


def select_smart_api(prompt, requested_capability=None, excluded_ids=None):
    """Select an API using admin routing rules + model capabilities + health."""
    capability = detect_capability(prompt, requested_capability)
    capability_record = _load_capability_record(capability)
    routed_provider_ids = _routing_provider_ids(capability_record)

    # No configured rule -> preserve the existing health/latency router.
    if not routed_provider_ids:
        api = select_best_api(excluded_ids)
        if api and not _api_supports_capability(api, capability):
            # Fall back to a capability-aware search across all providers.
            api = select_best_api(excluded_ids, required_capability=capability)
        if api:
            print(f"🧠 Smart Routing → {capability} | {api['provider_name']} | {api['key_name']}")
        return api

    api = select_best_api(
        excluded_ids,
        provider_ids=routed_provider_ids,
        required_capability=capability,
    )

    if api:
        print(
            f"🧠 Smart Routing → {capability} | "
            f"{api['provider_name']} | {api['key_name']}"
        )
    else:
        # Rule exists, but no usable key/model exists for that provider.
        # Let universal failover search outside the rule rather than fail the chat.
        print(
            f"⚠️ Smart route unavailable for '{capability}'. "
            "Falling back to universal provider routing."
        )
        api = select_best_api(
            excluded_ids,
            required_capability=capability,
        )
        if api:
            print(
                f"🧠 Smart Fallback → {capability} | "
                f"{api['provider_name']} | {api['key_name']}"
            )

    return api


# ==========================================================
# Select Best Available API
# ==========================================================

def select_best_api(excluded_ids=None, provider_ids=None, required_capability=None):
    excluded_ids = excluded_ids or []

    connection = None
    cursor = None

    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT
                ak.id,
                ak.key_name,
                ak.api_key,
                ak.provider_id,
                ak.model_id,
                ak.priority,
                ak.health_status,
                ak.average_response_ms,

                ap.provider_name,
                ap.provider_slug,
                ap.api_base_url,

                m.model_name,
                m.model_slug,
                m.model_version,
                m.context_window,
                m.max_output_tokens,
                m.supports_images,
                m.supports_files,
                m.supports_web_search,
                m.supports_streaming,
                m.supports_function_calling,
                m.supports_json_mode

            FROM api_keys ak

            INNER JOIN ai_providers ap
                ON ak.provider_id = ap.id

            LEFT JOIN ai_models m
                ON ak.model_id = m.id

            WHERE
                ak.status = 'active'
                AND ak.health_status IN ('healthy', 'slow')
        """

        params = []

        if provider_ids:
            placeholders = ",".join(["%s"] * len(provider_ids))
            query += f"""
                AND ak.provider_id IN ({placeholders})
            """
            params.extend(provider_ids)

        capability_column = CAPABILITY_COLUMN_MAP.get(_normalize_capability(required_capability))
        if capability_column:
            query += f"""
                AND COALESCE(m.{capability_column}, 0) = 1
            """

        if excluded_ids:
            placeholders = ",".join(["%s"] * len(excluded_ids))
            query += f"""
                AND ak.id NOT IN ({placeholders})
            """
            params.extend(excluded_ids)

        query += """
            ORDER BY
                CASE
                    WHEN ak.health_status = 'healthy' THEN 0
                    ELSE 1
                END,
                COALESCE(ak.average_response_ms, 999999) ASC,
                ak.priority ASC,
                ak.id ASC
            LIMIT 1
        """

        cursor.execute(query, tuple(params))
        api = cursor.fetchone()

        # Never route to an incomplete DB record (for example an Anthropic
        # key with no model attached). Try the next valid candidate instead.
        if api and not api_is_runtime_usable(api):
            candidates_query = query.replace("LIMIT 1", "LIMIT 20")
            cursor.execute(candidates_query, tuple(params))
            candidates = cursor.fetchall()
            api = next((item for item in candidates if api_is_runtime_usable(item)), None)

        if not api:
            print("⚠️ No healthy API available.")
            return None

        print(
            f"🏆 Selected API: "
            f"{api['provider_name']} | "
            f"{api['key_name']} | "
            f"{api['average_response_ms']} ms"
        )

        return api

    except Exception as e:
        print(f"❌ Routing Error: {e}")
        return None

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ==========================================================
# NORMAL GENERATE - UNIVERSAL TRUE FAILOVER
# ==========================================================

def generate(prompt, capability=None):
    attempted_ids = []

    while True:
        selected_api = select_smart_api(
            prompt,
            requested_capability=capability,
            excluded_ids=attempted_ids,
        )

        if not selected_api:
            print("❌ All available APIs failed.")

            return (
                "⚠️ Soul AI was unable to get a response from "
                "the available AI providers."
            )

        attempted_ids.append(selected_api["id"])

        print(
            f"🚀 Routing Request → "
            f"{selected_api['provider_name']} | "
            f"{selected_api['key_name']}"
        )

        result, success = generate_provider(
            prompt,
            selected_api,
        )

        if success:
            return result

        print(
            f"🔁 Runtime Failover → trying next API "
            f"(failed: {selected_api['provider_name']} / "
            f"{selected_api['key_name']})"
        )


# ==========================================================
# Streaming - Gemini
# ==========================================================

def generate_gemini_stream(prompt, selected_api):
    start_time = time.perf_counter()
    full_response = ""

    try:
        ai = genai.Client(api_key=selected_api["api_key"])

        model_name = (
            selected_api.get("model_slug")
            or MODEL_NAME
        )

        print(
            f"⚡ Streaming Gemini Response → "
            f"{selected_api['key_name']}"
        )

        stream = ai.models.generate_content_stream(
            model=model_name,
            contents=prompt,
        )

        for chunk in stream:
            text = getattr(chunk, "text", None)

            if not text:
                continue

            full_response += text

            yield {
                "type": "chunk",
                "text": text,
            }

        response_time_ms = (time.perf_counter() - start_time) * 1000

        if not full_response:
            raise RuntimeError(
                "Gemini returned an empty streaming response."
            )

        update_key_stats(
            selected_api["id"],
            response_time_ms,
            True,
        )

        update_health_status(
            selected_api["id"],
            "healthy" if response_time_ms < HEALTHY_THRESHOLD_MS else "slow",
            response_time_ms,
            None,
        )

        print(
            f"\n✅ Gemini streaming completed | "
            f"{int(response_time_ms)} ms | "
            f"{selected_api['key_name']}"
        )

        yield {
            "type": "success",
            "text": "",
        }

    except Exception as e:
        response_time_ms = (time.perf_counter() - start_time) * 1000
        error_text = str(e)

        print(
            f"\n❌ Gemini Streaming Runtime Error | "
            f"{selected_api['key_name']} | "
            f"{error_text}"
        )

        update_key_stats(
            selected_api["id"],
            response_time_ms,
            False,
            error_text,
        )

        mark_runtime_failure(
            selected_api,
            error_text,
        )

        yield {
            "type": "error",
            "text": error_text,
            "partial": bool(full_response),
        }


# ==========================================================
# Streaming - Anthropic
# ==========================================================

def generate_anthropic_stream(prompt, selected_api):
    start_time = time.perf_counter()
    full_response = ""

    try:
        endpoint = clean_base_url(selected_api.get("api_base_url"))
        if not endpoint:
            endpoint = "https://api.anthropic.com"

        if not endpoint.endswith("/v1"):
            endpoint += "/v1"

        endpoint += "/messages"

        model = selected_api.get("model_slug")
        if not model:
            raise RuntimeError("Anthropic model_slug is missing in DB.")

        max_tokens = int(selected_api.get("max_output_tokens") or 4096)
        max_tokens = min(max_tokens, 16384)

        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "stream": True,
            "messages": [
                {"role": "user", "content": prompt}
            ],
        }

        print(
            f"⚡ Streaming Anthropic Response → "
            f"{selected_api['key_name']}"
        )

        with requests.post(
            endpoint,
            headers=provider_headers("anthropic", selected_api["api_key"]),
            json=payload,
            timeout=REQUEST_TIMEOUT,
            stream=True,
        ) as response:

            if not response.ok:
                raise RuntimeError(
                    f"Anthropic HTTP {response.status_code}: "
                    f"{response.text[:1000]}"
                )

            for raw_line in response.iter_lines(
                decode_unicode=True
            ):
                if not raw_line:
                    continue

                data = parse_sse_data(raw_line)

                if not data:
                    continue

                event_type = data.get("type")

                if event_type == "content_block_delta":
                    delta = data.get("delta") or {}
                    text = delta.get("text")

                    if text:
                        full_response += text
                        yield {
                            "type": "chunk",
                            "text": text,
                        }

        response_time_ms = (time.perf_counter() - start_time) * 1000

        if not full_response:
            raise RuntimeError(
                "Anthropic returned an empty streaming response."
            )

        update_key_stats(
            selected_api["id"],
            response_time_ms,
            True,
        )

        update_health_status(
            selected_api["id"],
            "healthy" if response_time_ms < HEALTHY_THRESHOLD_MS else "slow",
            response_time_ms,
            None,
        )

        print(
            f"\n✅ Anthropic streaming completed | "
            f"{int(response_time_ms)} ms | "
            f"{selected_api['key_name']}"
        )

        yield {
            "type": "success",
            "text": "",
        }

    except Exception as e:
        response_time_ms = (time.perf_counter() - start_time) * 1000
        error_text = str(e)

        print(
            f"\n❌ Anthropic Streaming Runtime Error | "
            f"{selected_api['key_name']} | "
            f"{error_text}"
        )

        update_key_stats(
            selected_api["id"],
            response_time_ms,
            False,
            error_text,
        )

        mark_runtime_failure(
            selected_api,
            error_text,
        )

        yield {
            "type": "error",
            "text": error_text,
            "partial": bool(full_response),
        }


# ==========================================================
# Streaming - OpenAI / xAI / DeepSeek / Mistral
# ==========================================================

def generate_openai_compatible_stream(prompt, selected_api):
    start_time = time.perf_counter()
    full_response = ""

    provider = normalize_provider_slug(
        selected_api.get("provider_slug")
    )

    try:
        endpoint = get_chat_endpoint(selected_api)

        if not endpoint:
            raise RuntimeError(
                f"No streaming endpoint configured for "
                f"{selected_api.get('provider_name')}"
            )

        model = selected_api.get("model_slug")
        if not model:
            raise RuntimeError("model_slug is missing in DB.")

        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "stream": True,
        }

        max_tokens = selected_api.get("max_output_tokens")
        if max_tokens:
            if provider == "openai":
                payload["max_completion_tokens"] = min(int(max_tokens), 32768)
            else:
                payload["max_tokens"] = min(int(max_tokens), 32768)

        print(
            f"⚡ Streaming {selected_api.get('provider_name')} "
            f"Response → {selected_api['key_name']}"
        )

        with requests.post(
            endpoint,
            headers=provider_headers(
                provider,
                selected_api["api_key"],
            ),
            json=payload,
            timeout=REQUEST_TIMEOUT,
            stream=True,
        ) as response:

            if not response.ok:
                raise RuntimeError(
                    f"{selected_api.get('provider_name')} "
                    f"HTTP {response.status_code}: "
                    f"{response.text[:1000]}"
                )

            for raw_line in response.iter_lines(
                decode_unicode=True
            ):
                if not raw_line:
                    continue

                data = parse_sse_data(raw_line)

                if not data:
                    continue

                choices = data.get("choices") or []
                if not choices:
                    continue

                delta = choices[0].get("delta") or {}
                text = delta.get("content")

                if isinstance(text, str) and text:
                    full_response += text

                    yield {
                        "type": "chunk",
                        "text": text,
                    }

        response_time_ms = (time.perf_counter() - start_time) * 1000

        if not full_response:
            raise RuntimeError(
                f"{selected_api.get('provider_name')} "
                "returned an empty streaming response."
            )

        update_key_stats(
            selected_api["id"],
            response_time_ms,
            True,
        )

        update_health_status(
            selected_api["id"],
            "healthy" if response_time_ms < HEALTHY_THRESHOLD_MS else "slow",
            response_time_ms,
            None,
        )

        print(
            f"\n✅ {selected_api.get('provider_name')} "
            f"streaming completed | "
            f"{int(response_time_ms)} ms | "
            f"{selected_api['key_name']}"
        )

        yield {
            "type": "success",
            "text": "",
        }

    except Exception as e:
        response_time_ms = (time.perf_counter() - start_time) * 1000
        error_text = str(e)

        print(
            f"\n❌ {selected_api.get('provider_name')} "
            f"Streaming Runtime Error | "
            f"{selected_api['key_name']} | "
            f"{error_text}"
        )

        update_key_stats(
            selected_api["id"],
            response_time_ms,
            False,
            error_text,
        )

        mark_runtime_failure(
            selected_api,
            error_text,
        )

        yield {
            "type": "error",
            "text": error_text,
            "partial": bool(full_response),
        }


# ==========================================================
# Streaming - Ollama
# ==========================================================

def generate_ollama_stream(prompt, selected_api):
    start_time = time.perf_counter()
    full_response = ""

    try:
        base_url = clean_base_url(selected_api.get("api_base_url"))
        if not base_url:
            base_url = "http://localhost:11434"

        endpoint = (
            base_url
            if base_url.endswith("/api/chat")
            else f"{base_url}/api/chat"
        )

        model = selected_api.get("model_slug")
        if not model:
            raise RuntimeError("Ollama model_slug is missing in DB.")

        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "stream": True,
        }

        print(
            f"⚡ Streaming Ollama Response → "
            f"{selected_api['key_name']}"
        )

        with requests.post(
            endpoint,
            headers=provider_headers(
                "ollama",
                selected_api.get("api_key"),
            ),
            json=payload,
            timeout=REQUEST_TIMEOUT,
            stream=True,
        ) as response:

            if not response.ok:
                raise RuntimeError(
                    f"Ollama HTTP {response.status_code}: "
                    f"{response.text[:1000]}"
                )

            for raw_line in response.iter_lines(
                decode_unicode=True
            ):
                if not raw_line:
                    continue

                try:
                    data = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue

                text = (
                    (data.get("message") or {})
                    .get("content")
                )

                if text:
                    full_response += text

                    yield {
                        "type": "chunk",
                        "text": text,
                    }

                if data.get("done"):
                    break

        response_time_ms = (time.perf_counter() - start_time) * 1000

        if not full_response:
            raise RuntimeError(
                "Ollama returned an empty streaming response."
            )

        update_key_stats(
            selected_api["id"],
            response_time_ms,
            True,
        )

        update_health_status(
            selected_api["id"],
            "healthy" if response_time_ms < HEALTHY_THRESHOLD_MS else "slow",
            response_time_ms,
            None,
        )

        print(
            f"\n✅ Ollama streaming completed | "
            f"{int(response_time_ms)} ms | "
            f"{selected_api['key_name']}"
        )

        yield {
            "type": "success",
            "text": "",
        }

    except Exception as e:
        response_time_ms = (time.perf_counter() - start_time) * 1000
        error_text = str(e)

        print(
            f"\n❌ Ollama Streaming Runtime Error | "
            f"{selected_api['key_name']} | "
            f"{error_text}"
        )

        update_key_stats(
            selected_api["id"],
            response_time_ms,
            False,
            error_text,
        )

        mark_runtime_failure(
            selected_api,
            error_text,
        )

        yield {
            "type": "error",
            "text": error_text,
            "partial": bool(full_response),
        }


# ==========================================================
# Streaming Dispatcher
# ==========================================================

def generate_provider_stream(prompt, selected_api):
    provider = normalize_provider_slug(
        selected_api.get("provider_slug")
    )

    if provider == "gemini":
        yield from generate_gemini_stream(
            prompt,
            selected_api,
        )
        return

    if provider == "anthropic":
        yield from generate_anthropic_stream(
            prompt,
            selected_api,
        )
        return

    if provider == "ollama":
        yield from generate_ollama_stream(
            prompt,
            selected_api,
        )
        return

    if provider in {"openai", "xai", "deepseek", "mistral"}:
        yield from generate_openai_compatible_stream(
            prompt,
            selected_api,
        )
        return

    yield {
        "type": "error",
        "text": (
            f"Provider '{selected_api.get('provider_name')}' "
            "is not implemented."
        ),
        "partial": False,
    }


# ==========================================================
# STREAMING ROUTER - UNIVERSAL TRUE FAILOVER
# ==========================================================

def generate_stream(prompt, capability=None):
    attempted_ids = []

    while True:
        selected_api = select_smart_api(
            prompt,
            requested_capability=capability,
            excluded_ids=attempted_ids,
        )

        if not selected_api:
            yield (
                "⚠️ Soul AI was unable to get a response from "
                "the available AI providers."
            )
            return

        attempted_ids.append(selected_api["id"])

        print(
            f"🚀 Streaming Request → "
            f"{selected_api['provider_name']} | "
            f"{selected_api['key_name']}"
        )

        failed = False
        partial_response = False

        for event in generate_provider_stream(
            prompt,
            selected_api,
        ):
            event_type = event.get("type")

            if event_type == "chunk":
                partial_response = True
                yield event["text"]

            elif event_type == "success":
                return

            elif event_type == "error":
                failed = True

                # Never replay a prompt after partial output.
                if partial_response or event.get("partial"):
                    print(
                        "⚠️ Streaming interrupted after "
                        "partial response."
                    )

                    yield (
                        "\n\n⚠️ Connection to the current "
                        "AI provider was interrupted."
                    )
                    return

                break

        if failed:
            print(
                f"🔁 Streaming Runtime Failover → "
                f"trying next API "
                f"(failed: {selected_api['provider_name']} / "
                f"{selected_api['key_name']})"
            )
            continue

        return


# ==========================================================
# UNIVERSAL DB API KEY LOADER
# ==========================================================

def load_all_api_keys(include_unhealthy=True):
    """Load provider/model/key records from MySQL for routing and health audit.

    This function performs DB access only. It never contacts an AI provider.
    include_unhealthy=True is intentional for the passive audit so disabled,
    invalid, and rate-limited records can still be displayed.
    """
    connection = None
    cursor = None

    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT
                ak.id,
                ak.uuid,
                ak.key_name,
                ak.api_key,
                ak.provider_id,
                ak.model_id,
                ak.priority,
                ak.status,
                ak.health_status,
                ak.daily_limit,
                ak.used_today,
                ak.total_requests,
                ak.total_errors,
                ak.average_response_ms,
                ak.last_used,
                ak.last_error,
                ak.created_at,
                ak.updated_at,
                ak.encrypted,
                ak.expires_at,

                ap.provider_name,
                ap.provider_slug,
                ap.api_base_url,

                m.model_name,
                m.model_slug,
                m.model_version,
                m.context_window,
                m.max_output_tokens,
                m.supports_images,
                m.supports_files,
                m.supports_web_search,
                m.supports_streaming,
                m.supports_function_calling,
                m.supports_json_mode

            FROM api_keys ak

            INNER JOIN ai_providers ap
                ON ak.provider_id = ap.id

            LEFT JOIN ai_models m
                ON ak.model_id = m.id

            WHERE ak.status <> 'disabled'
        """

        params = []

        if not include_unhealthy:
            query += """
                AND ak.status = 'active'
                AND ak.health_status IN ('healthy', 'slow')
            """

        query += """
            ORDER BY ak.priority ASC, ak.id ASC
        """

        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()

        # Never expose a missing secret as a usable cloud credential.
        # Ollama may legitimately have no API key.
        result = []
        for row in rows:
            provider = normalize_provider_slug(row.get("provider_slug"))
            if provider != "ollama" and not (row.get("api_key") or "").strip():
                continue
            result.append(row)

        print(f"🔑 Universal DB Keys Loaded: {len(result)}")
        return result

    except mysql.connector.Error as err:
        print(f"❌ Universal DB Key Load Error: {err}")
        return []
    except Exception as err:
        print(f"❌ Universal DB Key Load Error: {err}")
        return []

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ==========================================================
# ZERO-QUOTA HEALTH ENGINE v4
# ==========================================================
# IMPORTANT DESIGN RULE:
# The health monitor MUST NEVER call a cloud AI generation endpoint.
# Any remote AI request can consume provider request/token quota.
# Therefore health is learned from REAL USER REQUESTS only.
#
# This section intentionally performs NO provider API calls.
# It audits the DB state and prints a passive health snapshot.
# Runtime success/failure functions above are the only place where
# provider health is changed after an actual user request.

HEALTH_PROBES_ENABLED = False


def check_provider_key_health(api):
    """
    Passive health check only.

    DO NOT send a request to the provider here.
    A remote request would consume provider-side quota/rate limits.
    Actual user traffic updates health through the runtime functions.
    """
    provider = normalize_provider_slug(api.get("provider_slug"))
    health = (api.get("health_status") or "healthy").lower()

    if provider not in SUPPORTED_PROVIDERS:
        return "unsupported"

    if health in {"healthy", "slow", "rate_limited", "invalid", "disabled"}:
        return health

    return "unknown"


# ==========================================================
# UNIVERSAL API HEALTH AUDIT - ZERO PROVIDER REQUESTS
# ==========================================================

def check_all_api_health():
    """
    Audit API-key health from the database only.

    ZERO network calls.
    ZERO model-generation calls.
    ZERO token generation.
    ZERO intentional provider quota consumption.

    Provider health is updated only when a real user request succeeds
    or fails inside the runtime generation/streaming functions.
    """
    health_keys = load_all_api_keys(include_unhealthy=True)

    if not health_keys:
        print("❌ No active API keys available for health audit.")
        return False

    healthy_count = 0

    print("🛡️ Passive Health Audit → NO provider requests sent")

    for api in health_keys:
        provider = normalize_provider_slug(api.get("provider_slug"))
        key_name = api.get("key_name") or "Unnamed Key"
        health_status = check_provider_key_health(api)

        if health_status == "healthy":
            healthy_count += 1
            icon = "🟢"
        elif health_status == "slow":
            healthy_count += 1
            icon = "🟡"
        elif health_status == "rate_limited":
            icon = "🟠"
        elif health_status in {"invalid", "disabled"}:
            icon = "🔴"
        else:
            icon = "⚪"

        print(
            f"{icon} {api.get('provider_name')} | "
            f"{key_name} | {health_status} | "
            f"last known: {api.get('average_response_ms') or 'N/A'} ms"
        )

    print(
        f"💚 Available APIs: {healthy_count}/{len(health_keys)} "
        f"(DB state only)"
    )
    print("🔒 Health audit consumed ZERO AI generation quota.")

    return healthy_count > 0


# ==========================================================
# Backward-compatible Gemini health function
# ==========================================================

def check_gemini_health():
    return check_all_api_health()


# ==========================================================
# Background Health Monitor
# ==========================================================

def health_monitor():
    print("❤️ Universal API Health Monitor Started")

    while True:
        try:
            print("\n🔍 Running Passive Universal API Health Audit...")
            check_all_api_health()
            print("✅ API Health Check Completed")

        except Exception as e:
            print(f"❌ Health Monitor Error: {e}")

        time.sleep(HEALTH_CHECK_INTERVAL)


# ==========================================================
# Flask Debug Reloader Protection
# ==========================================================

_health_monitor_started = False
_health_monitor_lock = threading.Lock()


def start_health_monitor():
    # Flask debug mode creates a parent process and a reloader child.
    # Start the monitor only in the actual serving child, otherwise once
    # in a normal non-reloader process. The lock also prevents accidental
    # duplicate starts from repeated imports/calls in one process.
    import os

    global _health_monitor_started

    with _health_monitor_lock:
        if _health_monitor_started:
            return None

        werkzeug_main = os.environ.get("WERKZEUG_RUN_MAIN")

        # In Flask debug/reloader mode, only the serving child should start.
        # FLASK_DEBUG is intentionally checked as a hint; app.py may enable
        # debug through another mechanism, in which case WERKZEUG_RUN_MAIN
        # is still the authoritative child-process signal.
        if werkzeug_main == "false":
            return None

        # When the reloader environment explicitly says this is not the
        # serving child, do not start another monitor.
        if werkzeug_main is not None and werkzeug_main.lower() != "true":
            # If WERKZEUG_RUN_MAIN is absent, this is a normal process.
            if werkzeug_main != "":
                return None

        thread = threading.Thread(
            target=health_monitor,
            daemon=True,
            name="SoulAI-UniversalHealthMonitor",
        )

        thread.start()
        _health_monitor_started = True
        return thread


# ==========================================================
# Backward-compatible Gemini client configuration
# ==========================================================

client = None
current_key = None
key_pool = None
API_KEYS = []


def configure():
    global client

    # Keep this function for compatibility with older app.py code.
    # The universal router creates provider clients per request.
    try:
        client = None
    except Exception:
        client = None

    return client


configure()
