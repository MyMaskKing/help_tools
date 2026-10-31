"""
网页配置后台。

- SettingsStore：把覆盖配置存进同一个 SQLite（settings 表），默认值来自 bot.py 的环境变量。
- build_app / start_admin_server：登录、配置读取/保存/重置、Ollama 连通性测试。
- 页面在 admin.html，无外部 CDN，单页，移动端可用。

安全：
- 密码 PBKDF2-HMAC-SHA256（20 万次迭代 + 随机盐）；
- 登录后发随机会话 Cookie（HttpOnly + SameSite=Strict，12 小时）；
- 同一 IP 连续失败 5 次锁定 60 秒；
- 页面不提供 HTTPS，建议只在内网或 SSH 隧道下使用。
"""

import asyncio
import hashlib
import hmac
import inspect
import json
import math
import re
import secrets
import sqlite3
import time
from pathlib import Path
from urllib.parse import urlparse

from aiohttp import ClientSession, ClientTimeout, web


SESSION_COOKIE = "qqbot_admin"
SESSION_TTL = 12 * 3600
PBKDF2_ITERATIONS = 200_000
MAX_BODY = 512 * 1024

SECTIONS = {
    "qq": ["ws_url", "ws_token"],
    "ai": [
        "ollama_url",
        "ollama_model",
        "temperature",
        "num_predict",
        "system_prompt",
    ],
    "tts": ["tts_voice", "tts_rate", "tts_pitch", "tts_volume"],
}

FIELD_LABELS = {
    "ws_url": "QQ WebSocket 地址",
    "ws_token": "QQ WebSocket Token",
    "ollama_url": "Ollama 地址",
    "ollama_model": "Ollama 模型",
    "temperature": "温度",
    "num_predict": "回复长度",
    "system_prompt": "人设提示词",
    "tts_voice": "语音音色",
    "tts_rate": "语速",
    "tts_pitch": "音调",
    "tts_volume": "音量",
}

_HTML_PATH = Path(__file__).with_name("admin.html")

try:
    ADMIN_HTML = _HTML_PATH.read_text(encoding="utf-8")
except OSError:
    ADMIN_HTML = (
        "<!doctype html><meta charset='utf-8'>"
        "<h1>admin.html 缺失</h1>"
        "<p>请确认镜像中包含 admin.html。</p>"
    )


class ConfigError(Exception):
    """字段校验失败。errors 为 {字段: 错误说明}。"""

    def __init__(self, errors):
        self.errors = dict(errors)
        message = "；".join(
            f"{FIELD_LABELS.get(key, key)}：{value}"
            for key, value in self.errors.items()
        )
        super().__init__(message or "配置不合法")


# ==================== 字段校验 ====================

def _as_text(value):
    if not isinstance(value, str):
        raise ValueError("必须是字符串")
    return value


def _clean_text(value):
    if not isinstance(value, str):
        raise ValueError("必须是字符串")
    return value.strip()


def _v_ws_url(value):
    value = _clean_text(value)

    if not value:
        raise ValueError("不能为空")

    if len(value) > 500:
        raise ValueError("长度不能超过 500")

    if any(ch.isspace() for ch in value):
        raise ValueError("不能包含空格")

    try:
        parsed = urlparse(value)
    except ValueError:
        raise ValueError("格式不正确")

    if parsed.scheme not in ("ws", "wss") or not parsed.netloc:
        raise ValueError("必须以 ws:// 或 wss:// 开头，并包含主机")

    return value


def _v_ollama_url(value):
    value = _clean_text(value)

    if not value:
        raise ValueError("不能为空")

    if len(value) > 500:
        raise ValueError("长度不能超过 500")

    if any(ch.isspace() for ch in value):
        raise ValueError("不能包含空格")

    try:
        parsed = urlparse(value)
    except ValueError:
        raise ValueError("格式不正确")

    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("必须以 http:// 或 https:// 开头，并包含主机")

    return value.rstrip("/")


def _v_ws_token(value):
    value = _as_text(value)

    if len(value) > 200:
        raise ValueError("长度不能超过 200")

    if "\n" in value or "\r" in value:
        raise ValueError("不能包含换行")

    value = value.strip()

    if not re.fullmatch(r"[\x20-\x7e]*", value):
        raise ValueError("只能包含 ASCII 可打印字符")

    return value


def _v_model(value):
    value = _clean_text(value)

    if not value:
        raise ValueError("不能为空")

    if len(value) > 200:
        raise ValueError("长度不能超过 200")

    if re.search(r"[\x00-\x1f\x7f]", value):
        raise ValueError("不能包含控制字符")

    return value


def _v_temperature(value):
    if isinstance(value, bool):
        raise ValueError("必须是数字")

    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError("必须是数字")

    if not math.isfinite(number):
        raise ValueError("必须是有限数字")

    if number < 0 or number > 2:
        raise ValueError("范围是 0～2")

    return round(number, 2)


def _v_num_predict(value):
    if isinstance(value, bool):
        raise ValueError("必须是整数")

    if isinstance(value, int):
        number = value
    elif isinstance(value, float) and value.is_integer():
        number = int(value)
    elif isinstance(value, str) and re.fullmatch(r"\d+", value.strip()):
        number = int(value.strip())
    else:
        raise ValueError("必须是整数")

    if number < 16 or number > 2048:
        raise ValueError("范围是 16～2048")

    return number


def _v_prompt(value):
    value = _as_text(value)

    if not value.strip():
        raise ValueError("不能为空")

    if len(value) > 20000:
        raise ValueError("长度不能超过 20000 字符")

    return value


def _v_voice(value):
    value = _clean_text(value)

    if not re.fullmatch(r"[A-Za-z0-9-]+Neural", value):
        raise ValueError("格式应类似 zh-CN-XiaoyiNeural")

    if len(value) > 100:
        raise ValueError("长度不能超过 100")

    return value


def _v_percent(value):
    value = _clean_text(value)

    if not re.fullmatch(r"[+-]\d{1,3}%", value):
        raise ValueError("格式应类似 -5% 或 +0%")

    return value


def _v_pitch(value):
    value = _clean_text(value)

    if not re.fullmatch(r"[+-]\d{1,3}Hz", value):
        raise ValueError("格式应类似 +10Hz")

    return value


VALIDATORS = {
    "ws_url": _v_ws_url,
    "ws_token": _v_ws_token,
    "ollama_url": _v_ollama_url,
    "ollama_model": _v_model,
    "temperature": _v_temperature,
    "num_predict": _v_num_predict,
    "system_prompt": _v_prompt,
    "tts_voice": _v_voice,
    "tts_rate": _v_percent,
    "tts_pitch": _v_pitch,
    "tts_volume": _v_percent,
}


def validate_values(values, defaults):
    if not isinstance(values, dict):
        raise ConfigError({"values": "配置必须是对象"})

    clean = {}
    errors = {}

    for key, raw in values.items():
        if key not in defaults:
            errors[key] = "未知配置项"
            continue

        try:
            clean[key] = VALIDATORS[key](raw)
        except (ValueError, TypeError) as exc:
            errors[key] = str(exc)

    if errors:
        raise ConfigError(errors)

    if not clean:
        raise ConfigError({"values": "没有需要保存的配置"})

    return clean


# ==================== 密码 ====================

def _hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return (
        f"pbkdf2_sha256${PBKDF2_ITERATIONS}"
        f"${salt.hex()}${digest.hex()}"
    )


def _verify_password_hash(password, stored):
    if not isinstance(stored, str):
        return False

    try:
        algo, iterations, salt_hex, digest_hex = stored.split("$")

        if algo != "pbkdf2_sha256":
            return False

        rounds = int(iterations)

        if rounds < 10_000 or rounds > 1_000_000:
            return False

        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            rounds,
        )

        return hmac.compare_digest(actual, expected)

    except (ValueError, TypeError):
        return False


# ==================== 配置存储 ====================

class SettingsStore:
    """把覆盖配置写入 SQLite；默认值不落库，reset 即删除覆盖。"""

    def __init__(self, db_path, defaults):
        self.db_path = str(db_path)
        self.defaults = dict(defaults)
        self._values = {}
        self._secrets = {}
        self.env_password = ""
        self._ensure_schema()

    def _connect(self):
        return sqlite3.connect(self.db_path, timeout=15)

    def _ensure_schema(self):
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS settings(
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

    def load(self):
        self._ensure_schema()

        with self._connect() as db:
            rows = db.execute(
                "SELECT key, value FROM settings"
            ).fetchall()

        values = {}
        secrets_ = {}

        for key, raw in rows:
            if not isinstance(key, str):
                continue

            try:
                value = json.loads(raw)
            except (TypeError, ValueError):
                continue

            if key.startswith("_"):
                secrets_[key] = value
                continue

            if key not in self.defaults:
                continue

            try:
                cleaned = validate_values(
                    {key: value},
                    self.defaults,
                )
            except ConfigError:
                # 数据库里的旧值不合法时忽略，回退默认值。
                continue

            values[key] = cleaned[key]

        self._values = values
        self._secrets = secrets_

    def get(self, key):
        return self._values.get(key, self.defaults.get(key))

    def public_values(self):
        return {key: self.get(key) for key in self.defaults}

    def default_values(self):
        return dict(self.defaults)

    def save(self, incoming):
        clean = validate_values(incoming, self.defaults)
        changed = [
            key for key in clean
            if self.get(key) != clean[key]
        ]

        if not changed:
            return []

        with self._connect() as db:
            for key in changed:
                if clean[key] == self.defaults[key]:
                    db.execute(
                        "DELETE FROM settings WHERE key=?",
                        (key,),
                    )
                else:
                    db.execute(
                        """
                        INSERT INTO settings(key,value)
                        VALUES(?,?)
                        ON CONFLICT(key)
                        DO UPDATE SET value=excluded.value
                        """,
                        (
                            key,
                            json.dumps(
                                clean[key],
                                ensure_ascii=False,
                            ),
                        ),
                    )

        for key in changed:
            if clean[key] == self.defaults[key]:
                self._values.pop(key, None)
            else:
                self._values[key] = clean[key]

        return changed

    def reset(self, section):
        keys = SECTIONS.get(section)

        if not keys:
            raise ConfigError({"section": "未知的分区"})

        placeholders = ",".join("?" for _ in keys)

        with self._connect() as db:
            db.execute(
                f"DELETE FROM settings WHERE key IN ({placeholders})",
                keys,
            )

        for key in keys:
            self._values.pop(key, None)

        return keys

    def _get_secret(self, key):
        return self._secrets.get(key)

    def _set_secret(self, key, value):
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO settings(key,value)
                VALUES(?,?)
                ON CONFLICT(key)
                DO UPDATE SET value=excluded.value
                """,
                (key, json.dumps(value, ensure_ascii=False)),
            )

        self._secrets[key] = value

    @property
    def password_fixed_by_env(self):
        return bool(self.env_password)

    def ensure_password(self, env_password=""):
        self.env_password = (env_password or "").strip()

        if self.env_password:
            if len(self.env_password) < 8:
                print(
                    "[WEB] 警告：ADMIN_PASSWORD 少于 8 位，"
                    "建议换成长密码",
                    flush=True,
                )
            return "env", None

        if self._get_secret("_admin_password_hash"):
            return "stored", None

        plain = secrets.token_urlsafe(9)
        self.set_password(plain)
        return "generated", plain

    def verify_password(self, password):
        if not isinstance(password, str):
            return False

        if self.env_password:
            return hmac.compare_digest(
                password.encode("utf-8"),
                self.env_password.encode("utf-8"),
            )

        stored = self._get_secret("_admin_password_hash")
        return _verify_password_hash(password, stored)

    def set_password(self, password):
        if not isinstance(password, str) or not (
            8 <= len(password) <= 128
        ):
            raise ValueError("密码长度需为 8～128 位")

        self._set_secret(
            "_admin_password_hash",
            _hash_password(password),
        )


# ==================== 会话 / 登录限流 ====================

class Sessions:
    def __init__(self, ttl=SESSION_TTL):
        self.ttl = ttl
        self._data = {}

    def create(self):
        token = secrets.token_urlsafe(32)
        self._data[token] = time.time() + self.ttl
        return token

    def valid(self, token):
        if not token:
            return False

        expiry = self._data.get(token)

        if not expiry:
            return False

        if expiry < time.time():
            self._data.pop(token, None)
            return False

        return True

    def drop(self, token):
        self._data.pop(token, None)

    def clear(self):
        self._data.clear()


class LoginLimiter:
    def __init__(self, max_failures=5, block_seconds=60):
        self.max_failures = max_failures
        self.block_seconds = block_seconds
        self._state = {}

    def remaining(self, ip):
        _, until = self._state.get(ip, (0, 0))
        left = int(until - time.time())
        return left if left > 0 else 0

    def fail(self, ip):
        now = time.time()
        count, until = self._state.get(ip, (0, 0))

        if until > now:
            return int(until - now)

        count += 1

        if count >= self.max_failures:
            until = now + self.block_seconds
            count = 0

        self._state[ip] = (count, until)

        left = int(until - now)
        return left if left > 0 else 0

    def success(self, ip):
        self._state.pop(ip, None)


# ==================== HTTP 工具 ====================

def _error(message, status=400, errors=None, headers=None):
    body = {"ok": False, "error": message}

    if errors:
        body["errors"] = errors

    return web.json_response(body, status=status, headers=headers)


async def _read_json(request):
    if request.content_type != "application/json":
        return None

    try:
        data = await request.json()
    except (json.JSONDecodeError, ValueError, TypeError):
        return None

    return data if isinstance(data, dict) else None


def require_auth(handler):
    async def wrapped(request):
        token = request.cookies.get(SESSION_COOKIE, "")

        if not request.app["sessions"].valid(token):
            return _error("请先登录", 401)

        request["session_token"] = token
        return await handler(request)

    return wrapped


async def _call_hook(app, name):
    hook = app["hooks"].get(name)

    if not hook:
        return None

    result = hook()

    if inspect.isawaitable(result):
        result = await result

    return result


# ==================== 路由 ====================

async def index(request):
    return web.Response(
        text=ADMIN_HTML,
        content_type="text/html",
        charset="utf-8",
        headers={"Cache-Control": "no-store"},
    )


async def login(request):
    ip = request.remote or "-"
    wait = request.app["limiter"].remaining(ip)

    if wait:
        return _error(
            f"尝试次数过多，请 {wait} 秒后再试",
            429,
            headers={"Retry-After": str(wait)},
        )

    data = await _read_json(request)

    if data is None:
        return _error("请求格式错误")

    password = data.get("password")

    if not isinstance(password, str) or not password:
        return _error("请输入密码")

    store = request.app["store"]

    if not store.verify_password(password):
        await asyncio.sleep(0.35)
        wait = request.app["limiter"].fail(ip)

        if wait:
            return _error(
                f"密码错误次数过多，请 {wait} 秒后再试",
                429,
                headers={"Retry-After": str(wait)},
            )

        return _error("密码错误", 401)

    request.app["limiter"].success(ip)
    token = request.app["sessions"].create()

    response = web.json_response({"ok": True})
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_TTL,
        httponly=True,
        samesite="Strict",
        path="/",
    )
    return response


async def logout(request):
    token = request.cookies.get(SESSION_COOKIE, "")
    request.app["sessions"].drop(token)

    response = web.json_response({"ok": True})
    response.del_cookie(SESSION_COOKIE, path="/")
    return response


@require_auth
async def api_config(request):
    store = request.app["store"]

    return web.json_response({
        "ok": True,
        "values": store.public_values(),
        "defaults": store.default_values(),
        "sections": SECTIONS,
        "meta": {
            "password_fixed_by_env": store.password_fixed_by_env,
        },
    })


@require_auth
async def api_save(request):
    data = await _read_json(request)

    if data is None:
        return _error("请求格式错误")

    values = data.get("values")

    if not isinstance(values, dict):
        return _error("values 必须是对象")

    store = request.app["store"]

    try:
        changed = store.save(values)
    except ConfigError as exc:
        return _error(str(exc), 400, exc.errors)

    reconnected = False

    if any(key in ("ws_url", "ws_token") for key in changed):
        try:
            await _call_hook(request.app, "reconnect")
            reconnected = True
        except Exception as exc:
            print(
                f"[WEB] 触发重连失败: "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )

    if changed:
        print(
            f"[WEB] 配置已更新: {', '.join(changed)}",
            flush=True,
        )

    return web.json_response({
        "ok": True,
        "values": store.public_values(),
        "reconnected": reconnected,
    })


@require_auth
async def api_reset(request):
    data = await _read_json(request)

    if data is None:
        return _error("请求格式错误")

    section = data.get("section")

    if not isinstance(section, str):
        return _error("section 必须是字符串")

    store = request.app["store"]

    try:
        store.reset(section)
    except ConfigError as exc:
        return _error(str(exc), 400, exc.errors)

    reconnected = False

    if section == "qq":
        try:
            await _call_hook(request.app, "reconnect")
            reconnected = True
        except Exception as exc:
            print(
                f"[WEB] 触发重连失败: "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )

    print(f"[WEB] 已恢复默认: {section}", flush=True)

    return web.json_response({
        "ok": True,
        "values": store.public_values(),
        "reconnected": reconnected,
    })


@require_auth
async def api_status(request):
    store = request.app["store"]
    body = {
        "ok": True,
        "ws_connected": False,
        "ws_url": store.get("ws_url"),
        "model": store.get("ollama_model"),
        "voice": store.get("tts_voice"),
        "uptime_seconds": 0,
        "password_fixed_by_env": store.password_fixed_by_env,
    }

    try:
        status = await _call_hook(request.app, "get_status")

        if isinstance(status, dict):
            body.update(status)
    except Exception as exc:
        print(
            f"[WEB] 获取状态失败: "
            f"{type(exc).__name__}: {exc}",
            flush=True,
        )

    return web.json_response(body)


@require_auth
async def api_test_ollama(request):
    store = request.app["store"]
    data = await _read_json(request)

    if data is None:
        data = {}

    url = data.get("ollama_url") or store.get("ollama_url")
    model = data.get("ollama_model") or store.get("ollama_model")

    try:
        url = _v_ollama_url(url)
        model = _v_model(model)
    except ValueError as exc:
        return web.json_response({
            "ok": False,
            "error": str(exc),
        })

    url = url.rstrip("/") + "/api/tags"

    try:
        timeout = ClientTimeout(total=8)

        async with ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                text = await response.text()

                if response.status != 200:
                    return web.json_response({
                        "ok": False,
                        "error": f"HTTP {response.status}: {text[:200]}",
                    })

        data = json.loads(text)

    except Exception as exc:
        return web.json_response({
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        })

    names = []

    for item in data.get("models", []) if isinstance(data, dict) else []:
        if not isinstance(item, dict):
            continue

        name = item.get("name") or item.get("model")

        if isinstance(name, str):
            names.append(name)

    names = sorted(set(names))

    return web.json_response({
        "ok": True,
        "models": names,
        "model": model,
        "model_found": model in names,
    })


@require_auth
async def api_password(request):
    store = request.app["store"]

    if store.password_fixed_by_env:
        return _error(
            "当前密码由 ADMIN_PASSWORD 环境变量固定，"
            "请修改 compose 后重启",
            400,
        )

    data = await _read_json(request)

    if data is None:
        return _error("请求格式错误")

    old_password = data.get("old_password")
    new_password = data.get("new_password")

    if not isinstance(old_password, str) or not isinstance(new_password, str):
        return _error("密码必须是字符串")

    if not store.verify_password(old_password):
        await asyncio.sleep(0.35)
        return _error("当前密码错误", 400)

    if not (8 <= len(new_password) <= 128):
        return _error("新密码长度需为 8～128 位", 400)

    store.set_password(new_password)
    request.app["sessions"].clear()
    print("[WEB] 管理密码已修改", flush=True)

    return web.json_response({"ok": True})


# ==================== 应用 ====================

@web.middleware
async def security_headers(request, handler):
    response = await handler(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; "
        "connect-src 'self'",
    )
    return response


def build_app(store, hooks=None):
    app = web.Application(
        client_max_size=MAX_BODY,
        middlewares=[security_headers],
    )

    app["store"] = store
    app["hooks"] = hooks or {}
    app["sessions"] = Sessions()
    app["limiter"] = LoginLimiter()

    app.router.add_get("/", index)
    app.router.add_post("/api/login", login)
    app.router.add_post("/api/logout", logout)
    app.router.add_get("/api/config", require_auth(api_config))
    app.router.add_post("/api/save", require_auth(api_save))
    app.router.add_post("/api/reset", require_auth(api_reset))
    app.router.add_get("/api/status", require_auth(api_status))
    app.router.add_post(
        "/api/test/ollama",
        require_auth(api_test_ollama),
    )
    app.router.add_post(
        "/api/password",
        require_auth(api_password),
    )

    return app


async def start_admin_server(
    store,
    host="0.0.0.0",
    port=8080,
    env_password="",
    hooks=None,
):
    mode, generated = store.ensure_password(env_password)

    app = build_app(store, hooks)
    runner = web.AppRunner(app, access_log=None)

    await runner.setup()

    try:
        site = web.TCPSite(runner, host, port)
        await site.start()
    except Exception:
        await runner.cleanup()
        raise

    print(f"[WEB] admin listening on {host}:{port}", flush=True)

    if host in ("0.0.0.0", "::"):
        print(
            f"[WEB] 浏览器打开 http://服务器IP:{port}",
            flush=True,
        )
    else:
        print(
            f"[WEB] 浏览器打开 http://{host}:{port}",
            flush=True,
        )

    if mode == "generated":
        print(f"[WEB] 首次登录密码: {generated}", flush=True)
        print(
            "[WEB] 登录后可在「安全」页修改密码",
            flush=True,
        )
    elif mode == "env":
        print(
            "[WEB] 管理密码使用 ADMIN_PASSWORD 环境变量",
            flush=True,
        )
    else:
        print("[WEB] 管理密码已从数据库加载", flush=True)

    return runner
