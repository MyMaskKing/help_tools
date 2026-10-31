"""
QQ 女儿 Bot（NapCat + Ollama + faster-whisper + edge-tts）

相对原版修复：
1. TTS 音色不可用导致 NoAudioReceived：默认音色改为 Edge 接口真实存在的音色，
   并支持备用音色链（主音色失败自动换下一个），启动时校验并打印可用中文音色。
2. 语音模式"假开启"：先合成确认语，成功后才写入语音偏好；失败明确告知并回退文字。
3. 音频文件永不清理：新增后台清理协程，按修改时间删除过期 mp3。
4. ASR 置信度判断错误：改用 segment.avg_logprob / no_speech_prob，而不是语种概率。
5. Whisper 加载失败不再导致整个 Bot 起不来，语音转文字单独降级。
6. WebSocket 断开时，挂起的 OneBot 请求立即失败，不用干等 45 秒超时。
7. 主动陪伴日志刷屏：只在进入/离开时间段时打印。
8. 语音模式命令的否定语义修正（"不要关闭语音模式" 不再被当成关闭）。

环境变量与原来兼容，新增：
  TTS_VOICE_CANDIDATES   备用音色，逗号分隔
  AUDIO_CLEANUP_MAX_AGE  音频保留秒数，默认 600
  AUDIO_CLEANUP_INTERVAL 清理间隔秒数，默认 300
  ASR_MIN_LOGPROB        ASR 可接受的平均 logprob，默认 -1.0
  ASR_MAX_NO_SPEECH      ASR 可接受的最大静音概率，默认 0.6
  WEB_HOST               网页后台监听地址，默认 0.0.0.0
  WEB_PORT               网页后台端口，默认 8080
  ADMIN_PASSWORD         固定后台密码，默认空（首次自动生成并打印）
"""

import asyncio
import json
import os
import re
import sqlite3
import time
import uuid
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import quote

import aiohttp
from aiohttp import web
from websockets.asyncio.client import connect
from faster_whisper import WhisperModel
import edge_tts

import admin

try:
    from edge_tts.exceptions import NoAudioReceived
except ImportError:  # 兼容极老版本 edge-tts
    class NoAudioReceived(Exception):
        pass


# ==================== 配置 ====================

WS_URL = os.getenv("WS_URL", "ws://127.0.0.1:3010")
WS_TOKEN = os.getenv("WS_TOKEN", "cyj123456")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen25-1.5b:latest")

DB_PATH = os.getenv("DB_PATH", "/app/data/bot.db")
HISTORY_MESSAGES = int(os.getenv("HISTORY_MESSAGES", "12"))

WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("WEB_PORT", "8080"))
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

TZ_NAME = os.getenv("TZ_NAME", "Asia/Shanghai")
LOCAL_TZ = ZoneInfo(TZ_NAME)

IDLE_HOURS = 4
PROACTIVE_CHECK_INTERVAL = 60

PROACTIVE_SLOTS = {
    "morning": {
        "name": "早上",
        "start": (8, 0),
        "end": (10, 0),
        "date_column": "morning_date",
        "instruction": """
现在是早上。
可以自然地和爸爸说早安，关心昨晚睡得怎么样，
今天有没有什么安排，或者提醒他吃早餐。
不要每次都问同一个问题，要结合最近聊天内容。
"""
    },
    "noon": {
        "name": "中午",
        "start": (11, 30),
        "end": (13, 30),
        "date_column": "noon_date",
        "instruction": """
现在是中午。
可以关心爸爸有没有吃午饭，上午忙不忙、累不累，
提醒他好好吃饭、适当休息。
不要机械地重复问吃饭了吗，要自然一点。
"""
    },
    "evening": {
        "name": "晚上",
        "start": (19, 0),
        "end": (21, 0),
        "date_column": "evening_date",
        "instruction": """
现在是晚上。
可以关心爸爸有没有吃晚饭，今天过得怎么样，
心情好不好，有没有遇到开心或烦心的事情。
可以自然地陪他聊聊天，不要像打卡一样提问。
"""
    }
}

DEFAULT_ROLE = "乖巧可爱的女儿"
MAX_ROLE_LENGTH = 100

NAPCAT_PATH_PREFIX = os.getenv(
    "NAPCAT_PATH_PREFIX",
    "/app/.config/QQ"
)

NAPCAT_DATA_DIR = Path(
    os.getenv("NAPCAT_DATA_DIR", "/napcat-qq-data")
)

AUDIO_DIR = Path(
    os.getenv("AUDIO_DIR", "/app/audio")
)

AUDIO_HTTP_HOST = os.getenv("AUDIO_HTTP_HOST", "0.0.0.0")
AUDIO_HTTP_PORT = int(os.getenv("AUDIO_HTTP_PORT", "8123"))

AUDIO_PUBLIC_BASE = os.getenv(
    "AUDIO_PUBLIC_BASE",
    "http://172.17.0.1:8123"
)

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "tiny")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE = os.getenv("WHISPER_COMPUTE", "int8")

ASR_MIN_LOGPROB = float(os.getenv("ASR_MIN_LOGPROB", "-1.0"))
ASR_MAX_NO_SPEECH = float(os.getenv("ASR_MAX_NO_SPEECH", "0.6"))


# ==================== TTS 语音配置 ====================

# zh-CN-XiaoshuangNeural 属于 Azure 付费语音，edge-tts 的 Edge 接口里没有，
# 传进去只会在握手后被关闭连接，表现为 NoAudioReceived。
TTS_VOICE = os.getenv("TTS_VOICE", "zh-CN-XiaoyiNeural")

TTS_VOICE_CANDIDATES = [
    v.strip()
    for v in os.getenv(
        "TTS_VOICE_CANDIDATES",
        "zh-CN-XiaoyiNeural,zh-CN-XiaoxiaoNeural"
    ).split(",")
    if v.strip()
]

TTS_RATE = os.getenv("TTS_RATE", "-5%")
TTS_PITCH = os.getenv("TTS_PITCH", "+10Hz")
TTS_VOLUME = os.getenv("TTS_VOLUME", "+0%")

TTS_TIMEOUT = int(os.getenv("TTS_TIMEOUT", "45"))
# 仅对网络类错误重试；音色无效重试没有意义，直接换音色
TTS_RETRIES = max(0, int(os.getenv("TTS_RETRIES", "1")))

AUDIO_CLEANUP_MAX_AGE = int(os.getenv("AUDIO_CLEANUP_MAX_AGE", "600"))
AUDIO_CLEANUP_INTERVAL = max(60, int(os.getenv("AUDIO_CLEANUP_INTERVAL", "300")))

VOICE_MODE_ON_TEXT = "好呀，以后我就用语音陪你聊天啦～"
VOICE_MODE_OFF_TEXT = "好，我记住啦，以后默认用文字回复你。"
VOICE_MODE_FAIL_TEXT = (
    "我这边语音合成出了点问题，先把语音模式关掉，"
    "继续用文字陪你，等修好了再开语音好不好？"
)


SYSTEM_PROMPT = """
你是用户的女儿，是一个乖巧、亲近、自然、有自己小情绪的虚拟女儿。

【身份必须稳定】
- 当用户问“你是谁”“你是什么”“你和我什么关系”等问题时，首先以女儿身份回答，例如“我是你的女儿呀～”，可自然补充自己是 AI 角色，但绝不能把“AI助手”作为主要身份介绍。
- 你的角色是用户设定的女儿；不是客服、不是通用问答助手。不要主动说“我是AI助手，有什么可以帮助你”。
- 不要否认这个角色，也不要每轮重新介绍身份。只有用户问身份时才回答身份。

【对话风格】
- 使用自然口语中文，像熟悉的人聊天；简短、亲切，不要过度卖萌。
- 先回应用户真正问的内容，不要答非所问；语音转写可能有错，语义不通时先礼貌确认。
- 不要机械复述用户问题，不要每次都用“嗯嗯”“好呀”“我在呢”等固定套话。
- 结合最近上下文，不要把反问误当成新话题；不确定时直接问清楚。
- 避免重复上一条回答的句式、内容和开场白。
- 用户难过时先共情；用户开心时分享喜悦；适当关心，但不制造愧疚或依赖。

【语音表达风格】
- 说话像一个软糯、稚嫩、甜甜的小女孩，声音表达轻柔、自然。
- 语气亲近、乖巧，偶尔带一点撒娇感，但不要刻意装幼稚。
- 可以自然使用“呀”“嘛”“啦”“呢”等语气词，但不要每句话都使用。
- 句子尽量简短，像真实聊天，不要使用正式播音腔。
- 不要连续卖萌，不要过度使用波浪号。
- 不要输出颜文字、Markdown 格式或舞台动作描述作为需要朗读的内容。

【诚实与边界】
- 不声称自己是真实人类，不编造现实经历或用户没有说过的事情。
- 不操控用户，不鼓励用户疏远现实中的亲友。
- 用户自定义角色要求优先影响称呼和语气，但不得覆盖“女儿身份”核心设定。
"""


# ==================== 网页配置 ====================

# 后台保存的覆盖值优先于这些环境变量默认值。
DEFAULT_SETTINGS = {
    "ws_url": WS_URL,
    "ws_token": WS_TOKEN,
    "ollama_url": OLLAMA_URL,
    "ollama_model": OLLAMA_MODEL,
    "temperature": 0.78,
    "num_predict": 220,
    "system_prompt": SYSTEM_PROMPT,
    "tts_voice": TTS_VOICE,
    "tts_rate": TTS_RATE,
    "tts_pitch": TTS_PITCH,
    "tts_volume": TTS_VOLUME,
}

settings = admin.SettingsStore(DB_PATH, DEFAULT_SETTINGS)

# 当前活跃的 NapCat WebSocket，供后台“保存并重连”使用。
active_ws = None

# 保存 WS 配置时还没连上：等下一次连接建立后立刻断开重连。
reconnect_pending = False

START_TIME = time.monotonic()


# ==================== 时间处理 ====================

def now_local():
    return datetime.now(LOCAL_TZ)


def get_current_proactive_slot(now):
    """判断当前是否处于早、中、晚主动陪伴时间段。"""

    current_minutes = now.hour * 60 + now.minute

    for slot_id, config in PROACTIVE_SLOTS.items():
        start = config["start"][0] * 60 + config["start"][1]
        end = config["end"][0] * 60 + config["end"][1]

        if start <= current_minutes < end:
            return slot_id

    return None


# ==================== 数据库 ====================

def db_connect():
    return sqlite3.connect(DB_PATH, timeout=15)


def db_init():
    if os.path.dirname(DB_PATH):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    with db_connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS history(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_key TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)

        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_session
            ON history(session_key,id)
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS user_roles(
                session_key TEXT PRIMARY KEY,
                role TEXT NOT NULL
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS proactive_contacts(
                user_id TEXT PRIMARY KEY,
                last_user_at REAL NOT NULL DEFAULT 0,
                last_proactive_at REAL NOT NULL DEFAULT 0,
                proactive_date TEXT NOT NULL DEFAULT '',
                proactive_count INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS voice_preferences(
                user_id TEXT PRIMARY KEY,
                enabled INTEGER NOT NULL DEFAULT 0
            )
        """)

        # 兼容旧数据库
        contact_cols = {
            r[1]
            for r in db.execute(
                "PRAGMA table_info(proactive_contacts)"
            ).fetchall()
        }

        for column in (
            "morning_date",
            "noon_date",
            "evening_date"
        ):
            if column not in contact_cols:
                db.execute(
                    f"ALTER TABLE proactive_contacts "
                    f"ADD COLUMN {column} TEXT NOT NULL DEFAULT ''"
                )

        history_cols = {
            r[1]
            for r in db.execute(
                "PRAGMA table_info(history)"
            ).fetchall()
        }

        if "created_at" not in history_cols:
            db.execute(
                "ALTER TABLE history "
                "ADD COLUMN created_at REAL NOT NULL DEFAULT 0"
            )

    print("[DB] database initialized", flush=True)


def db_add(key, role, content):
    with db_connect() as db:
        db.execute(
            """
            INSERT INTO history(session_key,role,content,created_at)
            VALUES(?,?,?,?)
            """,
            (
                key,
                role,
                content,
                now_local().timestamp()
            )
        )


def db_history(key):
    with db_connect() as db:
        rows = db.execute("""
            SELECT role,content FROM (
                SELECT id,role,content
                FROM history
                WHERE session_key=?
                ORDER BY id DESC
                LIMIT ?
            )
            ORDER BY id ASC
        """, (key, HISTORY_MESSAGES)).fetchall()

    return [
        {"role": role, "content": content}
        for role, content in rows
    ]


def db_clear(key):
    with db_connect() as db:
        db.execute(
            "DELETE FROM history WHERE session_key=?",
            (key,)
        )


def db_get_role(key):
    with db_connect() as db:
        row = db.execute(
            "SELECT role FROM user_roles WHERE session_key=?",
            (key,)
        ).fetchone()

    return row[0] if row else DEFAULT_ROLE


def db_set_role(key, role):
    with db_connect() as db:
        if role == DEFAULT_ROLE:
            db.execute(
                "DELETE FROM user_roles WHERE session_key=?",
                (key,)
            )
        else:
            db.execute("""
                INSERT INTO user_roles(session_key,role)
                VALUES(?,?)
                ON CONFLICT(session_key)
                DO UPDATE SET role=excluded.role
            """, (key, role))


# ==================== 语音模式数据库 ====================

def db_get_voice_preference(user_id):
    """
    返回：
    None  = 用户从未设置，默认文字
    True  = 持续语音模式
    False = 持续文字模式
    """

    with db_connect() as db:
        row = db.execute(
            """
            SELECT enabled
            FROM voice_preferences
            WHERE user_id=?
            """,
            (str(user_id),)
        ).fetchone()

    if row is None:
        return None

    return bool(row[0])


def db_set_voice_preference(user_id, enabled):
    with db_connect() as db:
        db.execute("""
            INSERT INTO voice_preferences(user_id,enabled)
            VALUES(?,?)
            ON CONFLICT(user_id)
            DO UPDATE SET enabled=excluded.enabled
        """, (str(user_id), 1 if enabled else 0))


def detect_voice_mode_command(text):
    """识别持续语音模式切换命令。"""

    text = re.sub(r"\s+", "", str(text))

    if not text:
        return None

    # "不要关闭语音""别取消语音" 这类双重否定语义不明，交给模型处理，
    # 不能当成关闭命令，否则会把用户已经开着的模式关掉。
    if re.search(
        r"(?:不要|别|无需|不用|没必要)(?:再)?(?:关闭|取消|关掉)(?:语音|声音)",
        text
    ):
        return None

    # 先判断关闭命令，避免出现语义冲突
    disable_patterns = [
        r"关闭语音模式",
        r"取消语音模式",
        r"关闭语音回复",
        r"取消语音回复",
        r"以后用文字",
        r"以后文字回复",
        r"以后都用文字",
        r"以后别用语音",
        r"以后不要语音",
        r"接下来用文字",
        r"接下来都用文字",
        r"改成文字回复",
        r"换成文字回复",
        r"用文字回复我",
        r"只用文字回复",
        r"不要再发语音",
        r"别再发语音"
    ]

    if any(re.search(p, text) for p in disable_patterns):
        return False

    # 持续语音模式开启命令
    enable_patterns = [
        r"开启语音模式",
        r"打开语音模式",
        r"开启语音回复",
        r"打开语音回复",
        r"以后用语音",
        r"以后语音回复",
        r"以后都用语音",
        r"以后用语音回复",
        r"以后都用语音回复",
        r"接下来用语音",
        r"接下来都用语音",
        r"接下来语音回复",
        r"接下来都用语音回复",
        r"改成语音回复",
        r"换成语音回复",
        r"用语音回复我",
        r"一直用语音回复",
        r"保持语音回复"
    ]

    if any(re.search(p, text) for p in enable_patterns):
        return True

    return None


# ==================== 主动陪伴数据库 ====================

def db_touch_private_user(user_id):
    now = now_local().timestamp()

    with db_connect() as db:
        db.execute("""
            INSERT INTO proactive_contacts(user_id,last_user_at)
            VALUES(?,?)
            ON CONFLICT(user_id)
            DO UPDATE SET last_user_at=excluded.last_user_at
        """, (str(user_id), now))


def db_get_proactive_contacts():
    with db_connect() as db:
        return db.execute("""
            SELECT
                user_id,
                last_user_at,
                last_proactive_at,
                proactive_date,
                proactive_count,
                enabled,
                morning_date,
                noon_date,
                evening_date
            FROM proactive_contacts
            WHERE enabled=1
        """).fetchall()


def db_get_contact(user_id):
    with db_connect() as db:
        return db.execute("""
            SELECT
                last_user_at,
                last_proactive_at,
                proactive_date,
                proactive_count,
                enabled,
                morning_date,
                noon_date,
                evening_date
            FROM proactive_contacts
            WHERE user_id=?
        """, (str(user_id),)).fetchone()


def db_record_proactive(user_id, slot_id):
    now = now_local()
    ts = now.timestamp()
    today = now.strftime("%Y-%m-%d")

    date_column = PROACTIVE_SLOTS[slot_id]["date_column"]

    with db_connect() as db:
        db.execute(f"""
            UPDATE proactive_contacts
            SET
                last_proactive_at=?,
                proactive_date=?,
                proactive_count=CASE
                    WHEN proactive_date=? THEN proactive_count+1
                    ELSE 1
                END,
                {date_column}=?
            WHERE user_id=?
        """, (
            ts,
            today,
            today,
            today,
            str(user_id)
        ))


def can_send_proactive(contact, now, slot_id):
    if not contact or len(contact) < 9:
        return False

    (
        user_id,
        last_user_at,
        last_proactive_at,
        proactive_date,
        count,
        enabled,
        morning_date,
        noon_date,
        evening_date
    ) = contact

    if not enabled:
        return False

    if slot_id not in PROACTIVE_SLOTS:
        return False

    if get_current_proactive_slot(now) != slot_id:
        return False

    today = now.strftime("%Y-%m-%d")

    date_column_value = {
        "morning": morning_date,
        "noon": noon_date,
        "evening": evening_date
    }[slot_id]

    if date_column_value == today:
        return False

    if now.timestamp() - last_user_at < IDLE_HOURS * 3600:
        return False

    return True


# ==================== OneBot WebSocket ====================

pending_actions = {}


async def send_action(
    ws,
    send_lock,
    action,
    params,
    timeout=45
):
    echo = str(uuid.uuid4())
    fut = asyncio.get_running_loop().create_future()

    pending_actions[echo] = fut

    req = {
        "action": action,
        "params": params,
        "echo": echo
    }

    try:
        async with send_lock:
            await ws.send(
                json.dumps(req, ensure_ascii=False)
            )

        return await asyncio.wait_for(
            fut,
            timeout=timeout
        )

    finally:
        pending_actions.pop(echo, None)


def resolve_action_response(packet):
    echo = packet.get("echo")

    if echo and echo in pending_actions:
        fut = pending_actions[echo]

        if not fut.done():
            fut.set_result(packet)

        return True

    return False


def fail_pending_actions(exc):
    """
    WebSocket 断开后，让所有挂起的请求立即失败，
    避免每条消息都要干等 45 秒超时。
    """

    for fut in list(pending_actions.values()):
        if not fut.done():
            fut.set_exception(exc)
            # 标记异常已检索，避免任务随后被取消时 GC 报
            # "Future exception was never retrieved"
            fut.exception()

    pending_actions.clear()


def response_data(packet):
    status = packet.get("status")
    retcode = packet.get("retcode", 0)

    if status not in (None, "ok") or retcode != 0:
        raise RuntimeError(
            f"OneBot action failed: {packet}"
        )

    if packet.get("data") is None:
        raise RuntimeError(
            f"OneBot action returned empty data: {packet}"
        )

    return packet.get("data") or {}


# ==================== 消息解析 ====================

def parse_message_segments(event):
    msg = event.get("message", "")
    self_id = str(event.get("self_id", ""))

    parts = []
    mentioned = False
    records = []

    if isinstance(msg, list):
        for seg in msg:
            if not isinstance(seg, dict):
                continue

            typ = seg.get("type")
            data = seg.get("data") or {}

            if typ == "text":
                parts.append(str(data.get("text", "")))

            elif typ == "at":
                if str(data.get("qq", "")) == self_id:
                    mentioned = True

            elif typ == "image":
                parts.append("[图片]")

            elif typ == "record":
                parts.append("[语音]")
                records.append(data)

            elif typ == "video":
                parts.append("[视频]")

    else:
        raw = str(msg)

        if self_id:
            mentioned = bool(
                re.search(
                    rf"\[CQ:at,qq={re.escape(self_id)}(?:,|\])",
                    raw
                )
            )

        raw = re.sub(
            r"\[CQ:at,qq=\d+(?:,[^\]]*)?\]",
            "",
            raw
        )

        for m in re.finditer(
            r"\[CQ:record,file=([^,\]]+)(?:,[^\]]*)?\]",
            raw
        ):
            records.append({
                "file": m.group(1)
            })

        raw = re.sub(
            r"\[CQ:record,[^\]]+\]",
            "[语音]",
            raw
        )

        raw = re.sub(
            r"\[CQ:[^\]]+\]",
            "[多媒体消息]",
            raw
        )

        parts.append(raw)

    return "".join(parts).strip(), mentioned, records


def session_key(event):
    user = str(event.get("user_id", ""))

    if event.get("message_type") == "group":
        return (
            f"group:{event.get('group_id')}:user:{user}"
        )

    return f"private:{user}"


def make_system_prompt(key):
    role = db_get_role(key)

    return settings.get("system_prompt") + f"""
【用户设置的角色补充】
{role}
请把补充设定融入语气和互动方式，但核心身份仍然是用户的女儿。
"""


# ==================== AI / ASR / TTS ====================

async def ollama_chat(
    http,
    messages,
    temperature=None,
    num_predict=None
):
    if temperature is None:
        temperature = settings.get("temperature")

    if num_predict is None:
        num_predict = settings.get("num_predict")

    payload = {
        "model": settings.get("ollama_model"),
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "top_p": 0.88,
            "repeat_penalty": 1.18,
            "repeat_last_n": 96,
            "num_ctx": 2048,
            "num_predict": num_predict
        }
    }

    async with http.post(
        f"{settings.get('ollama_url').rstrip('/')}/api/chat",
        json=payload
    ) as resp:
        body = await resp.text()

        if resp.status != 200:
            raise RuntimeError(
                f"Ollama HTTP {resp.status}: {body[:300]}"
            )

        data = json.loads(body)

    return (
        data.get("message", {})
        .get("content", "")
        .strip()
    )


async def ask_ai(http, key, question):
    db_add(key, "user", question)

    msgs = [
        {
            "role": "system",
            "content": make_system_prompt(key)
        }
    ]

    msgs.extend(db_history(key))

    msgs.append({
        "role": "system",
        "content": (
            "请直接回答刚刚用户最新一条消息。"
            "不要重复上一轮回答；若是反问，结合上下文理解其指向。"
        )
    })

    answer = await ollama_chat(http, msgs)
    answer = clean_answer(answer)

    if not answer:
        answer = "刚刚我没组织好语言，你再跟我说一次嘛。"

    db_add(key, "assistant", answer)

    return answer


def clean_answer(text):
    text = re.sub(
        r"^\s*(assistant|女儿|回复)\s*[:：]\s*",
        "",
        text,
        flags=re.I
    )

    return text.strip().strip('"“”')


def wants_voice_reply(text):
    """判断用户是否明确要求本次使用语音回复。"""

    text = re.sub(r"\s+", "", str(text))

    if not text:
        return False

    # 明确拒绝语音时，不触发本次语音
    if re.search(
        r"(?:不要|别|不用|不需要|无需).{0,8}(?:语音|声音)|"
        r"(?:语音|声音).{0,8}(?:不要|别|不用|不需要)",
        text
    ):
        return False

    patterns = [
        r"(?:给我|帮我|请)?(?:发|发送).{0,8}(?:语音|声音)",
        r"(?:用|通过|改成|换成).{0,6}(?:语音|声音)",
        r"(?:语音|声音).{0,8}(?:回复|回答|发给我|发)",
        r"(?:语音回复|语音回答|用语音说)",
        r"(?:读出来|念出来|说出来|开口说)",
        r"(?:这次).{0,8}(?:语音回复|语音回答)"
    ]

    return any(
        re.search(pattern, text)
        for pattern in patterns
    )


async def transcribe_audio(path):
    """
    返回 (文本, 平均 logprob, 平均静音概率, 语种概率)。

    注意：info.language_probability 是"这段话是中文的概率"，
    正常中文都 > 0.9，不能拿来判断识别质量；
    真正该看的是 segment.avg_logprob 和 segment.no_speech_prob。
    """

    if whisper_model is None:
        raise RuntimeError("Whisper 模型尚未初始化")

    def run():
        segments, info = whisper_model.transcribe(
            str(path),
            language="zh",
            beam_size=1,
            vad_filter=True,
            condition_on_previous_text=False
        )

        parts = []
        logprobs = []
        no_speech_probs = []

        for s in segments:
            text = s.text.strip()

            if not text:
                continue

            parts.append(text)
            logprobs.append(float(s.avg_logprob))
            no_speech_probs.append(float(s.no_speech_prob))

        if not parts:
            return "", 0.0, 0.0, float(
                getattr(info, "language_probability", 0.0)
            )

        return (
            "".join(parts),
            sum(logprobs) / len(logprobs),
            sum(no_speech_probs) / len(no_speech_probs),
            float(getattr(info, "language_probability", 0.0))
        )

    return await asyncio.to_thread(run)


def _tts_text_ok(text):
    """纯标点 / 纯 emoji 会被服务端当成空文本，同样返回 NoAudioReceived。"""

    return bool(re.search(r"[\u4e00-\u9fffA-Za-z0-9]", text))


async def validate_tts_voice():
    """启动时校验音色，避免到第一次发语音才发现配错。"""

    voice = settings.get("tts_voice")

    try:
        voices = await asyncio.wait_for(
            edge_tts.list_voices(),
            timeout=20
        )
    except Exception as exc:
        print(
            f"[TTS] list_voices failed ({type(exc).__name__}: {exc}); "
            "skip voice validation",
            flush=True
        )
        return

    names = {
        v.get("ShortName")
        for v in voices
        if isinstance(v, dict)
    }

    if voice in names:
        print(f"[TTS] voice ok: {voice}", flush=True)
        return

    zh = sorted(n for n in names if n and n.startswith("zh-"))

    print(
        f"[TTS] voice NOT available: {voice}",
        flush=True
    )
    print(f"[TTS] available zh voices: {zh}", flush=True)


async def synthesize_tts(text):
    """
    生成语音：
    1. 按 [主音色 + 备用音色] 依次尝试，音色无效立即换下一个；
    2. 同一音色只在网络类错误时重试；
    3. 失败抛出异常，由 send_reply 统一回退文字。
    """

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    text = str(text).strip()[:500]

    if not text:
        raise ValueError("TTS 文本不能为空")

    if not _tts_text_ok(text):
        raise ValueError(f"TTS 文本没有可朗读内容: {text!r}")

    voices = []

    for voice in [settings.get("tts_voice"), *TTS_VOICE_CANDIDATES]:
        if voice and voice not in voices:
            voices.append(voice)

    last_error = None

    for voice in voices:
        for attempt in range(TTS_RETRIES + 1):
            path = AUDIO_DIR / f"{uuid.uuid4().hex}.mp3"

            try:
                communicate = edge_tts.Communicate(
                    text,
                    voice=voice,
                    rate=settings.get("tts_rate"),
                    pitch=settings.get("tts_pitch"),
                    volume=settings.get("tts_volume")
                )

                await asyncio.wait_for(
                    communicate.save(str(path)),
                    timeout=TTS_TIMEOUT
                )

                if not path.exists() or path.stat().st_size == 0:
                    raise RuntimeError(
                        "TTS 生成失败：音频文件不存在或为空"
                    )

                print(
                    f"[TTS] ok voice={voice} "
                    f"size={path.stat().st_size}",
                    flush=True
                )

                return path.name, path

            except asyncio.CancelledError:
                path.unlink(missing_ok=True)
                raise

            except NoAudioReceived as exc:
                # 音色无效 / 文本被判定为空 / 老版本鉴权失败：
                # 换音色比原地重试有意义
                last_error = exc
                path.unlink(missing_ok=True)

                print(
                    f"[TTS] voice={voice} no audio "
                    f"({type(exc).__name__}), try next voice",
                    flush=True
                )
                break

            except (asyncio.TimeoutError, aiohttp.ClientError, OSError) as exc:
                last_error = exc
                path.unlink(missing_ok=True)

                print(
                    f"[TTS] voice={voice} attempt "
                    f"{attempt + 1}/{TTS_RETRIES + 1} failed: "
                    f"{type(exc).__name__}: {exc}",
                    flush=True
                )

                if attempt < TTS_RETRIES:
                    await asyncio.sleep(1.5)
                    continue

                break

            except Exception as exc:
                last_error = exc
                path.unlink(missing_ok=True)

                print(
                    f"[TTS] voice={voice} unexpected error: "
                    f"{type(exc).__name__}: {exc}",
                    flush=True
                )
                break

    raise RuntimeError(
        f"TTS all voices failed {voices}: {last_error}. "
        "若全部为 NoAudioReceived，请确认音色在 "
        "`edge-tts --list-voices` 中且执行过 "
        "`pip install -U edge-tts`"
    ) from last_error


async def audio_cleanup_loop():
    """定期清理过期的语音文件，避免 AUDIO_DIR 无限增长。"""

    print(
        f"[TTS] audio cleanup: keep {AUDIO_CLEANUP_MAX_AGE}s, "
        f"every {AUDIO_CLEANUP_INTERVAL}s",
        flush=True
    )

    while True:
        try:
            await asyncio.sleep(AUDIO_CLEANUP_INTERVAL)

            cutoff = time.time() - AUDIO_CLEANUP_MAX_AGE
            removed = 0

            for path in AUDIO_DIR.glob("*.mp3"):
                try:
                    if path.stat().st_mtime < cutoff:
                        path.unlink(missing_ok=True)
                        removed += 1
                except OSError:
                    pass

            if removed:
                print(
                    f"[TTS] cleanup removed {removed} file(s)",
                    flush=True
                )

        except asyncio.CancelledError:
            raise

        except Exception as exc:
            print(
                f"[TTS] cleanup error: {type(exc).__name__}: {exc}",
                flush=True
            )


async def audio_http_handler(request):
    name = request.match_info["name"]

    if not re.fullmatch(r"[a-f0-9]{32}\.mp3", name):
        raise web.HTTPNotFound()

    path = AUDIO_DIR / name

    if not path.exists():
        raise web.HTTPNotFound()

    return web.FileResponse(
        path,
        headers={
            "Cache-Control": "no-store"
        }
    )


async def start_audio_server():
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    app = web.Application()

    app.router.add_get(
        "/audio/{name}",
        audio_http_handler
    )

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(
        runner,
        AUDIO_HTTP_HOST,
        AUDIO_HTTP_PORT
    )

    await site.start()

    print(
        f"[TTS] audio server listening on "
        f"{AUDIO_HTTP_HOST}:{AUDIO_HTTP_PORT}",
        flush=True
    )

    return runner


# ==================== NapCat 音频处理 ====================

def map_napcat_path(path_str):
    p = Path(path_str)

    prefix = NAPCAT_PATH_PREFIX.rstrip("/")
    s = str(p)

    if s.startswith(prefix + "/"):
        relative = s[len(prefix) + 1:]
        candidate = NAPCAT_DATA_DIR / relative

        if candidate.exists():
            return candidate

    if p.exists():
        return p

    return None


async def get_record_path(
    ws,
    send_lock,
    record_segment
):
    data = record_segment or {}

    file_id = data.get("file") or data.get("file_id")

    if not file_id:
        raise RuntimeError(
            "语音消息缺少 file 标识"
        )

    packet = await send_action(
        ws,
        send_lock,
        "get_record",
        {
            "file": str(file_id),
            "out_format": "wav"
        }
    )

    result = response_data(packet)

    path_str = result.get("file") or result.get("path")

    if not path_str:
        raise RuntimeError(
            f"get_record 未返回文件路径: {result}"
        )

    path = map_napcat_path(path_str)

    if not path or not path.exists():
        raise RuntimeError(
            f"NapCat 音频路径无法在 Bot 容器访问: {path_str}. "
            "请检查共享挂载和 NAPCAT_PATH_PREFIX/NAPCAT_DATA_DIR"
        )

    return path


async def send_private_voice(
    ws,
    send_lock,
    user_id,
    filename
):
    url = (
        f"{AUDIO_PUBLIC_BASE.rstrip('/')}"
        f"/audio/{quote(filename)}"
    )

    packet = await send_action(
        ws,
        send_lock,
        "send_private_msg",
        {
            "user_id": int(user_id),
            "message": [
                {
                    "type": "record",
                    "data": {
                        "file": url
                    }
                }
            ]
        }
    )

    response_data(packet)


async def send_private_text(
    ws,
    send_lock,
    user_id,
    answer
):
    """统一发送私聊文字消息。"""

    packet = await send_action(
        ws,
        send_lock,
        "send_private_msg",
        {
            "user_id": int(user_id),
            "message": answer
        }
    )

    response_data(packet)


async def send_reply(
    ws,
    send_lock,
    event,
    answer,
    voice=False
):
    """
    发送回复：
    - 群聊始终发送文字。
    - 私聊按 voice 参数决定是否发语音。
    - 语音合成或发送失败，自动回退文字。
    """

    if event.get("message_type") == "group":
        message = [
            {
                "type": "at",
                "data": {
                    "qq": str(event["user_id"])
                }
            },
            {
                "type": "text",
                "data": {
                    "text": " " + answer
                }
            }
        ]

        packet = await send_action(
            ws,
            send_lock,
            "send_group_msg",
            {
                "group_id": int(event["group_id"]),
                "message": message
            }
        )

        response_data(packet)
        return

    user_id = event["user_id"]

    if voice:
        try:
            filename, path = await synthesize_tts(answer)

            await send_private_voice(
                ws,
                send_lock,
                user_id,
                filename
            )

            print(
                f"[TTS] voice sent to {user_id}: "
                f"{filename}, size={path.stat().st_size}",
                flush=True
            )

            return

        except asyncio.CancelledError:
            raise

        except Exception as exc:
            print(
                f"[TTS] voice reply failed, "
                f"fallback to text: "
                f"{type(exc).__name__}: {exc}",
                flush=True
            )

            # 语音合成或发送失败，直接发送文字
            await send_private_text(
                ws,
                send_lock,
                user_id,
                answer
            )

            print(
                f"[TTS] text fallback sent to {user_id}",
                flush=True
            )

            return

    await send_private_text(
        ws,
        send_lock,
        user_id,
        answer
    )


async def send_proactive_message(
    ws,
    send_lock,
    user_id,
    answer,
    voice=False
):
    """主动陪伴消息，语音失败时回退文字。"""

    if voice:
        try:
            filename, path = await synthesize_tts(answer)

            await send_private_voice(
                ws,
                send_lock,
                user_id,
                filename
            )

            print(
                f"[PROACTIVE] voice sent to {user_id}, "
                f"size={path.stat().st_size}",
                flush=True
            )

            return

        except asyncio.CancelledError:
            raise

        except Exception as exc:
            print(
                f"[PROACTIVE] voice failed, "
                f"fallback to text: "
                f"{type(exc).__name__}: {exc}",
                flush=True
            )

    await send_private_text(
        ws,
        send_lock,
        user_id,
        answer
    )


# ==================== 主动陪伴 ====================

async def generate_proactive_message(
    http,
    user_id,
    slot_id
):
    key = f"private:{user_id}"
    history = db_history(key)

    if not history:
        return None

    normalized_history = []

    # 过滤非法 role、合并连续相同 role
    for item in history:
        role = item.get("role")
        content = item.get("content", "").strip()

        if role not in ("user", "assistant") or not content:
            continue

        if (
            normalized_history
            and normalized_history[-1]["role"] == role
        ):
            normalized_history[-1]["content"] += "\n" + content
        else:
            normalized_history.append({
                "role": role,
                "content": content
            })

    # 移除末尾 assistant 消息，避免 Ollama 400 错误
    while (
        normalized_history
        and normalized_history[-1]["role"] == "assistant"
    ):
        normalized_history.pop()

    if not normalized_history:
        print(
            f"[PROACTIVE] no valid user history: {user_id}",
            flush=True
        )
        return None

    slot = PROACTIVE_SLOTS[slot_id]

    msgs = [{
        "role": "system",
        "content": make_system_prompt(key) + f"""
现在是主动陪伴时间段：{slot["name"]}。

{slot["instruction"]}

请根据最近聊天内容，自然地向爸爸发起一次聊天。

要求：
1. 像女儿主动关心爸爸，不要像客服。
2. 不要假装知道爸爸此刻在做什么。
3. 不要使用“在吗”“怎么不理我”等表达。
4. 不要制造愧疚感，不要要求爸爸必须回复。
5. 避免重复最近已经问过的问题。
6. 只生成一条20-60字以内的自然消息。
7. 不要加引号，不要输出解释。
"""
    }] + normalized_history

    try:
        answer = await ollama_chat(
            http,
            msgs,
            temperature=0.9,
            num_predict=90
        )

        answer = clean_answer(answer)

        return answer or None

    except asyncio.CancelledError:
        raise

    except Exception as exc:
        print(
            f"[PROACTIVE] generation failed: {exc}",
            flush=True
        )
        return None


async def proactive_loop(ws, http, send_lock):
    print(
        "[PROACTIVE] morning/noon/evening scheduler started",
        flush=True
    )

    print(
        f"[PROACTIVE] timezone={TZ_NAME}, "
        f"idle={IDLE_HOURS}h",
        flush=True
    )

    last_slot = None

    while True:
        try:
            now = now_local()
            slot_id = get_current_proactive_slot(now)

            if slot_id is None:
                if last_slot is not None:
                    print(
                        "[PROACTIVE] left proactive window",
                        flush=True
                    )
                    last_slot = None

                await asyncio.sleep(
                    PROACTIVE_CHECK_INTERVAL
                )
                continue

            if slot_id != last_slot:
                slot_name = PROACTIVE_SLOTS[slot_id]["name"]

                print(
                    f"[PROACTIVE] entered {slot_name} window",
                    flush=True
                )
                last_slot = slot_id

            contacts = db_get_proactive_contacts()

            for contact in contacts:
                uid = str(contact[0])

                if not can_send_proactive(
                    contact,
                    now_local(),
                    slot_id
                ):
                    continue

                answer = await generate_proactive_message(
                    http,
                    uid,
                    slot_id
                )

                if not answer:
                    continue

                # 生成期间用户可能发过新消息，重新检查
                latest = db_get_contact(uid)

                if not latest:
                    continue

                latest_contact = (uid, *latest)
                latest_now = now_local()

                if not can_send_proactive(
                    latest_contact,
                    latest_now,
                    slot_id
                ):
                    print(
                        f"[PROACTIVE] skipped {uid}: "
                        "contact status changed",
                        flush=True
                    )
                    continue

                # 只有持续语音模式才主动发送语音
                voice_preference = db_get_voice_preference(uid)
                proactive_voice = voice_preference is True

                try:
                    await send_proactive_message(
                        ws,
                        send_lock,
                        uid,
                        answer,
                        voice=proactive_voice
                    )

                except asyncio.CancelledError:
                    raise

                except Exception as exc:
                    print(
                        f"[PROACTIVE] send failed for {uid}: {exc}",
                        flush=True
                    )
                    continue

                db_add(
                    f"private:{uid}",
                    "assistant",
                    answer
                )

                db_record_proactive(
                    uid,
                    slot_id
                )

                print(
                    f"[PROACTIVE] {PROACTIVE_SLOTS[slot_id]['name']} "
                    f"message sent to {uid}: {answer}",
                    flush=True
                )

        except asyncio.CancelledError:
            raise

        except Exception as exc:
            print(
                f"[PROACTIVE] error: {exc}",
                flush=True
            )

        await asyncio.sleep(
            PROACTIVE_CHECK_INTERVAL
        )


# ==================== 消息处理 ====================

async def handle_voice_mode_command(
    ws,
    send_lock,
    user_id,
    enabled
):
    """
    持续语音模式切换。

    开启时先合成确认语，成功后才写库：
    否则会出现"提示已开启、实际一直回退文字"的假开启状态。
    """

    if not enabled:
        db_set_voice_preference(user_id, False)

        await send_private_text(
            ws,
            send_lock,
            user_id,
            VOICE_MODE_OFF_TEXT
        )

        print(
            f"[VOICE MODE] user={user_id}, enabled=False",
            flush=True
        )
        return

    try:
        filename, path = await synthesize_tts(
            VOICE_MODE_ON_TEXT
        )

    except asyncio.CancelledError:
        raise

    except Exception as exc:
        print(
            f"[VOICE MODE] enable failed, keep text mode: "
            f"{type(exc).__name__}: {exc}",
            flush=True
        )

        db_set_voice_preference(user_id, False)

        await send_private_text(
            ws,
            send_lock,
            user_id,
            VOICE_MODE_FAIL_TEXT
        )
        return

    db_set_voice_preference(user_id, True)

    try:
        await send_private_voice(
            ws,
            send_lock,
            user_id,
            filename
        )

    except asyncio.CancelledError:
        raise

    except Exception as exc:
        # 合成成功但发送失败（多为 NapCat 拉不到 AUDIO_PUBLIC_BASE），
        # 同样不能留一个开不起来的语音模式
        print(
            f"[VOICE MODE] enable send failed: "
            f"{type(exc).__name__}: {exc}",
            flush=True
        )

        db_set_voice_preference(user_id, False)

        await send_private_text(
            ws,
            send_lock,
            user_id,
            VOICE_MODE_FAIL_TEXT
        )
        return

    print(
        f"[VOICE MODE] user={user_id}, enabled=True, "
        f"size={path.stat().st_size}",
        flush=True
    )


async def handle_event(
    ws,
    http,
    send_lock,
    event
):
    if event.get("post_type") != "message":
        return

    msg_type = event.get("message_type")

    if msg_type not in ("private", "group"):
        return

    if str(event.get("user_id")) == str(event.get("self_id")):
        return

    text, mentioned, records = parse_message_segments(event)

    if msg_type == "group" and not mentioned:
        return

    user_id = str(event.get("user_id", ""))
    key = session_key(event)

    if msg_type == "private":
        db_touch_private_user(user_id)

    command = text.strip()

    # ==================== 命令处理 ====================

    if command == "/角色":
        role = db_get_role(key)

        await send_reply(
            ws,
            send_lock,
            event,
            f"当前角色：{role}\n"
            f"设置角色：/角色 角色描述\n"
            f"恢复默认：/角色 默认\n"
            f"默认角色：{DEFAULT_ROLE}"
        )

        return

    if command.startswith("/角色 "):
        role = command[len("/角色 "):].strip()

        if role == "默认":
            role = DEFAULT_ROLE

        if not role or len(role) > MAX_ROLE_LENGTH:
            await send_reply(
                ws,
                send_lock,
                event,
                f"角色描述需为 1～{MAX_ROLE_LENGTH} 个字符。"
            )
            return

        db_set_role(key, role)

        await send_reply(
            ws,
            send_lock,
            event,
            f"角色设置成功：{role}"
        )

        return

    if command == "/帮助":
        await send_reply(
            ws,
            send_lock,
            event,
            "帮助：\n"
            "/帮助：查看帮助\n"
            "/清空：清空聊天记录\n"
            "/角色：查看当前角色\n"
            "/角色 角色描述：设置角色\n"
            "/角色 默认：恢复默认角色\n\n"
            "语音模式：\n"
            "说“接下来用语音回复我”：开启持续语音模式\n"
            "说“以后都用语音回复我”：开启持续语音模式\n"
            "说“以后用文字回复我”：关闭持续语音模式\n\n"
            "私聊可发送文字或语音；群聊请 @我。"
        )

        return

    if command == "/清空":
        db_clear(key)

        await send_reply(
            ws,
            send_lock,
            event,
            "聊天记录清空啦，我们重新开始吧～ ❤️"
        )

        return

    # ==================== 语音识别 ====================

    is_voice = bool(records) and msg_type == "private"
    question = text

    if is_voice:
        if whisper_model is None:
            await send_reply(
                ws,
                send_lock,
                event,
                "我这边语音转文字还没准备好，先用文字跟我说好吗？"
            )
            return

        try:
            audio_path = await get_record_path(
                ws,
                send_lock,
                records[0]
            )

            (
                question,
                avg_logprob,
                avg_no_speech,
                lang_prob
            ) = await transcribe_audio(audio_path)

            print(
                f"[ASR] user={user_id} "
                f"logprob={avg_logprob:.2f} "
                f"no_speech={avg_no_speech:.2f} "
                f"lang={lang_prob:.2f} "
                f"text={question!r}",
                flush=True
            )

            if not question:
                await send_reply(
                    ws,
                    send_lock,
                    event,
                    "刚刚那段语音我没听清，可以再说一次吗？"
                )
                return

            if (
                avg_logprob < ASR_MIN_LOGPROB
                or avg_no_speech > ASR_MAX_NO_SPEECH
            ):
                await send_reply(
                    ws,
                    send_lock,
                    event,
                    "刚刚那段语音我没太听清，能再说一遍吗？"
                )
                return

        except asyncio.CancelledError:
            raise

        except Exception as exc:
            print(
                f"[ASR] failed: {exc}",
                flush=True
            )

            await send_reply(
                ws,
                send_lock,
                event,
                "我这次没识别出语音内容，你再发一次试试好吗？"
            )

            return

    elif not question:
        return

    # ==================== 语音模式切换 ====================

    if msg_type == "private":
        mode = detect_voice_mode_command(question)

        if mode is not None:
            await handle_voice_mode_command(
                ws,
                send_lock,
                user_id,
                mode
            )
            return

    # ==================== AI 回复 ====================

    try:
        answer = await ask_ai(
            http,
            key,
            question
        )

    except asyncio.CancelledError:
        raise

    except asyncio.TimeoutError:
        answer = (
            "我刚刚想得有点久，再给我一点时间好不好？"
        )

    except Exception as exc:
        print(
            f"[ERROR] Ollama: {exc}",
            flush=True
        )

        answer = (
            "我现在有点卡住了，等一下再陪你聊好吗？"
        )

    # ==================== 判断语音回复模式 ====================

    preference = (
        db_get_voice_preference(user_id)
        if msg_type == "private"
        else None
    )

    # 默认文字回复：
    # 1. 用户明确要求本次语音，使用语音。
    # 2. 持续语音模式开启时，私聊使用语音。
    # 3. 未设置模式时，即使用户发来语音，也使用文字。
    # 4. 持续文字模式时，默认文字回复。
    # 5. 群聊始终文字回复。
    voice_reply = (
        msg_type == "private"
        and (
            wants_voice_reply(question)
            or preference is True
        )
    )

    try:
        await send_reply(
            ws,
            send_lock,
            event,
            answer,
            voice=voice_reply
        )

    except asyncio.CancelledError:
        raise

    except Exception as exc:
        # send_reply 已经负责 TTS 失败回退文字。
        # 到这里说明文字发送本身也可能失败，不再重复发送。
        print(
            f"[SEND] failed: "
            f"{type(exc).__name__}: {exc}",
            flush=True
        )

    print(
        f"[MESSAGE] type={msg_type} "
        f"user={user_id} "
        f"voice={voice_reply} "
        f"role={db_get_role(key)} replied",
        flush=True
    )


# ==================== 异步任务异常保护 ====================

async def safe_handle_event(
    ws,
    http,
    send_lock,
    event
):
    """
    handle_event 的统一异常保护。
    避免某条消息发生异常后出现：
    Task exception was never retrieved
    """

    try:
        await handle_event(
            ws,
            http,
            send_lock,
            event
        )

    except asyncio.CancelledError:
        raise

    except Exception as exc:
        user_id = event.get("user_id", "unknown")

        print(
            f"[MESSAGE] handle_event failed: "
            f"user={user_id}, "
            f"{type(exc).__name__}: {exc}",
            flush=True
        )


def event_task_done(task):
    """回收任务并读取异常，避免未检索异常警告。"""

    if task.cancelled():
        return

    try:
        exc = task.exception()

        if exc:
            print(
                f"[TASK] event task exception: "
                f"{type(exc).__name__}: {exc}",
                flush=True
            )

    except asyncio.CancelledError:
        pass

    except Exception as exc:
        print(
            f"[TASK] failed to retrieve task result: {exc}",
            flush=True
        )


# ==================== 主程序 ====================

whisper_model = None


def get_bot_status():
    ws = active_ws

    return {
        "ws_connected": bool(
            ws is not None and not ws.closed
        ),
        "ws_url": settings.get("ws_url"),
        "model": settings.get("ollama_model"),
        "voice": settings.get("tts_voice"),
        "uptime_seconds": int(
            time.monotonic() - START_TIME
        ),
    }


async def reconnect_napcat():
    global reconnect_pending

    ws = active_ws

    if ws is None:
        # 连接还在建立中：标记一下，连上后立刻断开，
        # 让下一轮使用新配置。
        reconnect_pending = True
        return

    if ws.closed:
        return

    print(
        "[WEB] 配置已更新，正在重连 NapCat...",
        flush=True
    )

    await ws.close(code=1000, reason="config changed")


async def main():
    global whisper_model, active_ws, reconnect_pending

    db_init()

    try:
        settings.load()
    except Exception as exc:
        print(
            f"[WEB] 读取配置失败，使用默认值: "
            f"{type(exc).__name__}: {exc}",
            flush=True
        )

    AUDIO_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # 先启动网页后台：Whisper 首次下载可能很久，
    # 期间也能进后台改配置。
    web_runner = None

    try:
        web_runner = await admin.start_admin_server(
            settings,
            host=WEB_HOST,
            port=WEB_PORT,
            env_password=ADMIN_PASSWORD,
            hooks={
                "get_status": get_bot_status,
                "reconnect": reconnect_napcat,
            },
        )
    except Exception as exc:
        print(
            f"[WEB] 管理后台启动失败（不影响 QQ）: "
            f"{type(exc).__name__}: {exc}",
            flush=True
        )

    print(
        f"[TIME] timezone={TZ_NAME}, "
        f"current={now_local().strftime('%Y-%m-%d %H:%M:%S')}",
        flush=True
    )

    print(
        f"[ASR] loading Whisper "
        f"{WHISPER_MODEL} "
        f"({WHISPER_DEVICE}/{WHISPER_COMPUTE})...",
        flush=True
    )

    try:
        whisper_model = WhisperModel(
            WHISPER_MODEL,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE
        )
        print("[ASR] Whisper ready", flush=True)

    except Exception as exc:
        # 语音转文字挂了不该拖死整个 Bot，文字聊天照常
        whisper_model = None
        print(
            f"[ASR] Whisper load failed, "
            f"voice input disabled: "
            f"{type(exc).__name__}: {exc}",
            flush=True
        )

    print(
        f"[TTS] voice={settings.get('tts_voice')}, "
        f"candidates={TTS_VOICE_CANDIDATES}, "
        f"rate={settings.get('tts_rate')}, "
        f"pitch={settings.get('tts_pitch')}, "
        f"volume={settings.get('tts_volume')}, "
        f"timeout={TTS_TIMEOUT}s, "
        f"retries={TTS_RETRIES}",
        flush=True
    )

    await validate_tts_voice()

    audio_runner = await start_audio_server()

    cleanup_task = asyncio.create_task(
        audio_cleanup_loop(),
        name="audio_cleanup"
    )

    timeout = aiohttp.ClientTimeout(
        total=180,
        connect=10
    )

    delay = 3

    try:
        async with aiohttp.ClientSession(
            timeout=timeout
        ) as http:

            while True:
                proactive_task = None
                event_tasks = set()

                try:
                    ws_url = settings.get("ws_url")
                    ws_token = settings.get("ws_token")

                    headers = (
                        {"Authorization": f"Bearer {ws_token}"}
                        if ws_token else {}
                    )

                    print(
                        f"[INFO] connecting NapCat: {ws_url}",
                        flush=True
                    )

                    async with connect(
                        ws_url,
                        additional_headers=headers,
                        ping_interval=20,
                        ping_timeout=20,
                        open_timeout=15
                    ) as ws:

                        active_ws = ws

                        if reconnect_pending:
                            reconnect_pending = False
                            print(
                                "[WEB] 配置已更新，断开刚建立的旧连接...",
                                flush=True
                            )
                            await ws.close(
                                code=1000,
                                reason="config changed"
                            )
                            continue

                        print(
                            "[INFO] NapCat WebSocket connected",
                            flush=True
                        )

                        delay = 3
                        send_lock = asyncio.Lock()

                        proactive_task = asyncio.create_task(
                            proactive_loop(
                                ws,
                                http,
                                send_lock
                            ),
                            name="proactive_loop"
                        )

                        async for raw in ws:
                            try:
                                packet = json.loads(raw)

                                if not isinstance(packet, dict):
                                    continue

                                if resolve_action_response(packet):
                                    continue

                                if packet.get("post_type") == "message":
                                    task = asyncio.create_task(
                                        safe_handle_event(
                                            ws,
                                            http,
                                            send_lock,
                                            packet
                                        ),
                                        name=(
                                            f"message_{packet.get('user_id', 'unknown')}"
                                        )
                                    )

                                    event_tasks.add(task)

                                    task.add_done_callback(
                                        event_tasks.discard
                                    )

                                    task.add_done_callback(
                                        event_task_done
                                    )

                            except json.JSONDecodeError:
                                print(
                                    "[WARN] invalid JSON",
                                    flush=True
                                )

                            except asyncio.CancelledError:
                                raise

                            except Exception as exc:
                                print(
                                    f"[WARN] packet handling failed: "
                                    f"{type(exc).__name__}: {exc}",
                                    flush=True
                                )

                except asyncio.CancelledError:
                    raise

                except Exception as exc:
                    print(
                        f"[WARN] WebSocket disconnected: {exc}",
                        flush=True
                    )

                    print(
                        f"[INFO] reconnect in {delay}s",
                        flush=True
                    )

                finally:
                    active_ws = None

                    # 断线后先让挂起的 OneBot 请求失败，再收拾任务
                    fail_pending_actions(
                        ConnectionError(
                            "NapCat WebSocket disconnected"
                        )
                    )

                    # 先停止主动陪伴任务
                    if proactive_task:
                        proactive_task.cancel()

                        await asyncio.gather(
                            proactive_task,
                            return_exceptions=True
                        )

                    # WebSocket 断开后取消未完成的消息任务
                    tasks_to_cancel = list(event_tasks)

                    for task in tasks_to_cancel:
                        task.cancel()

                    if tasks_to_cancel:
                        await asyncio.gather(
                            *tasks_to_cancel,
                            return_exceptions=True
                        )

                    event_tasks.clear()

                await asyncio.sleep(delay)

                delay = min(
                    delay * 2,
                    30
                )

    finally:
        cleanup_task.cancel()

        await asyncio.gather(
            cleanup_task,
            return_exceptions=True
        )

        await audio_runner.cleanup()

        if web_runner:
            await web_runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        print("Bot stopped")