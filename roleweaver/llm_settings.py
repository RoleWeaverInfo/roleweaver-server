"""Owner-only provider settings, deliberately separate from world backups."""

import copy, ipaddress, json, os, re, secrets, tempfile, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

ENDPOINTS = {
    "openai": "https://api.openai.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "lmstudio": "http://127.0.0.1:1234/v1",
}
GEMINI_FREE_FLASH = (
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError("Provider redirects are not allowed")


def open_url(request, timeout):
    handlers = [NoRedirect()]
    try:
        endpoint("lmstudio", request.full_url.rsplit("/", 1)[0].removesuffix("/chat"))
        handlers.append(urllib.request.ProxyHandler({}))
    except ValueError:
        pass
    return urllib.request.build_opener(*handlers).open(request, timeout=timeout)


def endpoint(kind, value):
    if kind in ("openai", "gemini"):
        return ENDPOINTS[kind]
    if not isinstance(value, str) or len(value) > 256:
        raise ValueError("Enter an LM Studio server address")
    p = urllib.parse.urlsplit(value.strip().rstrip("/"))
    try:
        host = p.hostname
        port = p.port
        local = host == "localhost" or (
            host
            and any(
                ipaddress.ip_address(host) in ipaddress.ip_network(n)
                for n in (
                    "127.0.0.0/8",
                    "10.0.0.0/8",
                    "172.16.0.0/12",
                    "192.168.0.0/16",
                    "::1/128",
                    "fc00::/7",
                )
            )
        )
    except ValueError:
        local = False
    if (
        p.scheme not in ("http", "https")
        or not local
        or p.username
        or p.password
        or p.query
        or p.fragment
        or p.path not in ("", "/v1")
    ):
        raise ValueError(
            "Use an LM Studio local/private IP address, such as http://192.168.1.20:1234/v1"
        )
    return urllib.parse.urlunsplit((p.scheme, p.netloc, "/v1", "", ""))


class Settings:
    def __init__(self, directory, config):
        self.path = Path(directory) / "llm-settings.json"
        self.base = dict(config)
        profiles = {
            k: dict(
                base_url=v,
                model="",
                max_output_tokens=1024,
                request_timeout=60,
                key="",
                key_env="",
            )
            for k, v in ENDPOINTS.items()
        }
        active = "existing"
        for k, p in profiles.items():
            if (
                config.get("provider") == "openai-compatible"
                and config.get("base_url", "").rstrip("/") == p["base_url"]
            ):
                active = k
                p.update(
                    model=config.get("model", ""),
                    max_output_tokens=config.get("max_output_tokens", 1024),
                    key_env=config.get("api_key_env", "ROLEWEAVER_API_KEY"),
                )
        if config.get("provider") == "offline":
            active = "offline"
        self.data = dict(
            active=active, revision=secrets.token_hex(12), profiles=profiles
        )
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
            self.path.chmod(0o600)
        self.data["profiles"]["gemini"].setdefault("fallback_on_busy", False)

    def status(self):
        result = copy.deepcopy(self.data)
        for p in result["profiles"].values():
            key = p.pop("key", "")
            env = p.pop("key_env", "")
            p["key_set"] = bool(key or (env and os.environ.get(env)))
            p["key_source"] = (
                "saved"
                if key
                else "environment" if env and os.environ.get(env) else "none"
            )
        result["existing_model"] = self.base.get("model", "")
        return result

    def candidate(self, body, require_model=True):
        if not isinstance(body, dict):
            raise ValueError("Supply provider settings")
        kind = body.get("service")
        if kind not in (*ENDPOINTS, "offline", "existing"):
            raise ValueError("Choose a supported provider")
        if kind in ("offline", "existing"):
            return kind, None
        saved = self.data["profiles"][kind]
        p = copy.deepcopy(saved)
        p["base_url"] = endpoint(kind, body.get("base_url", p["base_url"]))
        if p["base_url"] != saved["base_url"]:
            p.update(key="", key_env="")
        model = body.get("model", "")
        if (
            not isinstance(model, str)
            or len(model) > 128
            or (model and not re.fullmatch(r"[A-Za-z0-9_./:@+\-]+", model))
        ):
            raise ValueError("Enter a valid model ID")
        if require_model and not model:
            raise ValueError("Select or enter a model")
        p["model"] = model
        if kind == "gemini":
            enabled = body.get("fallback_on_busy", p.get("fallback_on_busy", False))
            if type(enabled) is not bool:
                raise ValueError("Invalid Gemini fallback setting")
            if (
                enabled
                and require_model
                and model.removeprefix("models/") not in GEMINI_FREE_FLASH
            ):
                raise ValueError(
                    "Fallback supports Gemini 3.8/3.7/3.6/3.5 Flash and 3.5/3.1 Flash-Lite only"
                )
            p["fallback_on_busy"] = enabled
        for field, low, high in (
            ("max_output_tokens", 128, 8192),
            ("request_timeout", 10, 180),
        ):
            value = body.get(field, p[field])
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"{field} must be between {low} and {high}")
            p[field] = value
        key = body.get("api_key", "")
        action = body.get("key_action", "keep")
        if action not in ("keep", "replace", "clear"):
            raise ValueError("Invalid key action")
        if action == "replace":
            if (
                not isinstance(key, str)
                or not 1 <= len(key.strip()) <= 4096
                or any(ord(c) < 33 or ord(c) > 126 for c in key.strip())
            ):
                raise ValueError("Enter a valid API key")
            p.update(key=key.strip(), key_env="")
        elif action == "clear":
            p.update(key="", key_env="")
        elif key:
            raise ValueError("Choose Replace key to use the entered key")
        return kind, p

    def key(self, p):
        return p.get("key", "") or os.environ.get(p.get("key_env", ""), "")

    def runtime(self, kind=None, p=None):
        if kind is None and not self.path.exists():
            return dict(self.base)
        kind = kind or self.data["active"]
        c = dict(self.base)
        if kind == "existing":
            return c
        if kind == "offline":
            return dict(c, provider="offline", _api_key="")
        p = p or self.data["profiles"][kind]
        return dict(
            c,
            provider="openai-compatible",
            llm_service=kind,
            base_url=p["base_url"],
            model=p["model"],
            _api_key=self.key(p),
            token_limit_parameter=(
                "max_completion_tokens" if kind == "openai" else "max_tokens"
            ),
            max_output_tokens=p["max_output_tokens"],
            request_timeout=p["request_timeout"],
            _managed_endpoint=True,
            gemini_fallback_on_busy=kind == "gemini"
            and p.get("fallback_on_busy", False),
        )

    def save(self, body):
        if body.get("revision") != self.data["revision"]:
            raise ValueError("Settings changed. Reload before saving.")
        kind, p = self.candidate(body)
        data = copy.deepcopy(self.data)
        data["active"] = kind
        data["revision"] = secrets.token_hex(12)
        if p is not None:
            data["profiles"][kind] = p
        fd, name = tempfile.mkstemp(prefix=".llm-", dir=self.path.parent)
        try:
            os.chmod(name, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)
        self.data = data
        return self.runtime()

    def probe(self, body, models=False):
        kind, p = self.candidate(body, require_model=not models)
        if p is None:
            raise ValueError("Choose OpenAI, Gemini or LM Studio to test")
        if kind in ("openai", "gemini") and not self.key(p):
            raise ValueError("Add an API key for this provider")
        c = self.runtime(kind, p)
        headers = {"Content-Type": "application/json"}
        if c["_api_key"]:
            headers["Authorization"] = "Bearer " + c["_api_key"]
        start = time.perf_counter()
        try:
            if models:
                with open_url(
                    urllib.request.Request(c["base_url"] + "/models", headers=headers),
                    15,
                ) as response:
                    raw = response.read(1048577)
                if len(raw) > 1048576:
                    raise ValueError("Model list too large")
                d = json.loads(raw)
                ids = sorted(
                    set(
                        row["id"]
                        for row in d["data"]
                        if isinstance(row, dict)
                        and isinstance(row.get("id"), str)
                        and len(row["id"]) <= 128
                    )
                )[:1000]
                return dict(models=ids)
            from . import provider

            payload = {
                "model": c["model"],
                "messages": [
                    {
                        "role": "system",
                        "content": "Return only JSON with speech set to Hello and action set to an empty string.",
                    },
                    {"role": "user", "content": "Say hello."},
                ],
                c["token_limit_parameter"]: c["max_output_tokens"],
                **provider.json_format(c),
            }

            def decode(d):
                value = json.loads(d["choices"][0]["message"]["content"])
                if (
                    not isinstance(value, dict)
                    or not isinstance(value.get("speech"), str)
                    or not value["speech"].strip()
                    or value.get("action") != ""
                ):
                    raise ValueError(
                        "Model did not return the required NPC JSON format"
                    )
                return True

            provider.complete(
                c["base_url"] + "/chat/completions",
                json.dumps(payload).encode(),
                headers,
                c["request_timeout"],
                1048576,
                decode,
                config=c,
            )
            return dict(
                ok=True,
                message="Connection and NPC JSON response passed.",
                duration_ms=round((time.perf_counter() - start) * 1000),
            )
        except urllib.error.HTTPError as exc:
            messages = {
                401: "API key rejected",
                403: "Provider denied access",
                404: "Endpoint or model not found",
                429: "Provider rate limit or quota reached",
            }
            raise ValueError(
                messages.get(exc.code, "Provider HTTP error") + f" ({exc.code})."
            ) from None
        except Exception:
            raise ValueError(
                "Connection test failed. Check the address, model, API key, timeout and JSON-capable model support."
            ) from None
