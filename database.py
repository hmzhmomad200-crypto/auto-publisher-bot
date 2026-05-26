"""
database.py — Turso (libSQL) بديل كامل لنظام JSON files
يستبدل كل load_json / save_json بقاعدة بيانات دائمة على Railway
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone

import aiohttp

log = logging.getLogger(__name__)

TURSO_URL   = os.getenv("TURSO_DATABASE_URL", "")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "")

# ═══════════════════════════════════════════════════════════
#  HTTP client للـ Turso
# ═══════════════════════════════════════════════════════════

async def _execute(sql: str, params: list = None) -> dict:
    """تنفيذ استعلام SQL على Turso عبر HTTP API"""
    if not TURSO_URL or not TURSO_TOKEN:
        raise RuntimeError("TURSO_DATABASE_URL أو TURSO_AUTH_TOKEN غير موجودين في المتغيرات")

    url = TURSO_URL.rstrip("/") + "/v2/pipeline"
    headers = {
        "Authorization": f"Bearer {TURSO_TOKEN}",
        "Content-Type": "application/json",
    }

    stmt = {"type": "execute", "stmt": {"sql": sql}}
    if params:
        stmt["stmt"]["named_args"] = [
            {"name": str(i), "value": {"type": "text", "value": str(p)}}
            for i, p in enumerate(params)
        ]

    body = {"requests": [stmt, {"type": "close"}]}

    async with aiohttp.ClientSession() as s:
        async with s.post(url, headers=headers, json=body,
                          timeout=aiohttp.ClientTimeout(total=15)) as r:
            data = await r.json()
            if r.status != 200:
                raise RuntimeError(f"Turso HTTP {r.status}: {data}")
            result = data["results"][0]
            if result.get("type") == "error":
                raise RuntimeError(f"Turso SQL error: {result.get('error')}")
            return result.get("response", {}).get("result", {})


async def _executemany(statements: list[tuple]) -> None:
    """تنفيذ عدة استعلامات دفعة واحدة"""
    if not TURSO_URL or not TURSO_TOKEN:
        raise RuntimeError("TURSO credentials missing")

    url = TURSO_URL.rstrip("/") + "/v2/pipeline"
    headers = {
        "Authorization": f"Bearer {TURSO_TOKEN}",
        "Content-Type": "application/json",
    }

    requests = []
    for sql, params in statements:
        stmt = {"type": "execute", "stmt": {"sql": sql}}
        if params:
            stmt["stmt"]["named_args"] = [
                {"name": str(i), "value": {"type": "text", "value": str(p)}}
                for i, p in enumerate(params)
            ]
        requests.append(stmt)
    requests.append({"type": "close"})

    body = {"requests": requests}
    async with aiohttp.ClientSession() as s:
        async with s.post(url, headers=headers, json=body,
                          timeout=aiohttp.ClientTimeout(total=15)) as r:
            if r.status != 200:
                data = await r.json()
                raise RuntimeError(f"Turso HTTP {r.status}: {data}")


# ═══════════════════════════════════════════════════════════
#  تهيئة الجداول
# ═══════════════════════════════════════════════════════════

async def init_db():
    """إنشاء الجداول إذا لم تكن موجودة"""
    tables = [
        """CREATE TABLE IF NOT EXISTS user_memory (
            uid       TEXT PRIMARY KEY,
            data      TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS stats (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS bot_chats (
            chat_id TEXT PRIMARY KEY,
            data    TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS banned_users (
            uid TEXT PRIMARY KEY
        )""",
        """CREATE TABLE IF NOT EXISTS whitelist (
            uid TEXT PRIMARY KEY
        )""",
        """CREATE TABLE IF NOT EXISTS config (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS user_credits (
            uid     TEXT PRIMARY KEY,
            credits INTEGER NOT NULL DEFAULT 0
        )""",
    ]
    stmts = [(sql, None) for sql in tables]
    await _executemany(stmts)
    log.info("✅ Turso: الجداول جاهزة")


# ═══════════════════════════════════════════════════════════
#  user_memory
# ═══════════════════════════════════════════════════════════

async def get_all_user_memory() -> dict:
    result = await _execute("SELECT uid, data FROM user_memory")
    rows = result.get("rows", [])
    out = {}
    for row in rows:
        uid  = row[0]["value"]
        data = json.loads(row[1]["value"])
        out[uid] = data
    return out


async def save_user_memory(uid: str, data: dict):
    payload = json.dumps(data, ensure_ascii=False)
    now     = datetime.now(timezone.utc).isoformat()
    await _execute(
        "INSERT INTO user_memory (uid, data, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(uid) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at",
        [uid, payload, now],
    )


async def delete_user_memory(uid: str):
    await _execute("DELETE FROM user_memory WHERE uid = ?", [uid])


# ═══════════════════════════════════════════════════════════
#  stats
# ═══════════════════════════════════════════════════════════

_STATS_DEFAULT = {
    "total_users": 0, "total_messages": 0,
    "total_images": 0, "total_files": 0, "dew_used": 0,
    "started_at": datetime.now(timezone.utc).isoformat(),
}

async def get_stats() -> dict:
    result = await _execute("SELECT key, value FROM stats")
    rows   = result.get("rows", [])
    out    = dict(_STATS_DEFAULT)
    for row in rows:
        k, v = row[0]["value"], row[1]["value"]
        try:
            out[k] = json.loads(v)
        except Exception:
            out[k] = v
    return out


async def save_stats(data: dict):
    stmts = []
    for k, v in data.items():
        val = json.dumps(v) if not isinstance(v, str) else v
        stmts.append((
            "INSERT INTO stats (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            [k, val],
        ))
    if stmts:
        await _executemany(stmts)


# ═══════════════════════════════════════════════════════════
#  bot_chats
# ═══════════════════════════════════════════════════════════

async def get_all_chats() -> dict:
    result = await _execute("SELECT chat_id, data FROM bot_chats")
    rows   = result.get("rows", [])
    return {row[0]["value"]: json.loads(row[1]["value"]) for row in rows}


async def save_chat(chat_id: str, data: dict):
    payload = json.dumps(data, ensure_ascii=False)
    await _execute(
        "INSERT INTO bot_chats (chat_id, data) VALUES (?, ?) "
        "ON CONFLICT(chat_id) DO UPDATE SET data=excluded.data",
        [chat_id, payload],
    )


async def delete_chat(chat_id: str):
    await _execute("DELETE FROM bot_chats WHERE chat_id = ?", [chat_id])


# ═══════════════════════════════════════════════════════════
#  banned_users
# ═══════════════════════════════════════════════════════════

async def get_banned_users() -> set:
    result = await _execute("SELECT uid FROM banned_users")
    rows   = result.get("rows", [])
    return {row[0]["value"] for row in rows}


async def ban_user(uid: str):
    await _execute(
        "INSERT INTO banned_users (uid) VALUES (?) ON CONFLICT(uid) DO NOTHING",
        [uid],
    )


async def unban_user(uid: str):
    await _execute("DELETE FROM banned_users WHERE uid = ?", [uid])


# ═══════════════════════════════════════════════════════════
#  whitelist
# ═══════════════════════════════════════════════════════════

async def get_whitelist() -> set:
    result = await _execute("SELECT uid FROM whitelist")
    rows   = result.get("rows", [])
    return {row[0]["value"] for row in rows}


async def add_to_whitelist(uid: str):
    await _execute(
        "INSERT INTO whitelist (uid) VALUES (?) ON CONFLICT(uid) DO NOTHING",
        [uid],
    )


async def remove_from_whitelist(uid: str):
    await _execute("DELETE FROM whitelist WHERE uid = ?", [uid])


# ═══════════════════════════════════════════════════════════
#  config (channel, welcome_msg, free_mode)
# ═══════════════════════════════════════════════════════════

async def get_config(key: str, default=None):
    try:
        result = await _execute("SELECT value FROM config WHERE key = ?", [key])
        rows   = result.get("rows", [])
        if rows:
            return json.loads(rows[0][0]["value"])
    except Exception:
        pass
    return default


async def set_config(key: str, value):
    payload = json.dumps(value, ensure_ascii=False)
    await _execute(
        "INSERT INTO config (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        [key, payload],
    )


# ═══════════════════════════════════════════════════════════
#  user_credits
# ═══════════════════════════════════════════════════════════

async def get_all_credits() -> dict:
    result = await _execute("SELECT uid, credits FROM user_credits")
    rows   = result.get("rows", [])
    return {row[0]["value"]: int(row[1]["value"]) for row in rows}


async def get_user_credits(uid: str) -> int:
    result = await _execute("SELECT credits FROM user_credits WHERE uid = ?", [uid])
    rows   = result.get("rows", [])
    return int(rows[0][0]["value"]) if rows else 0


async def set_user_credits(uid: str, amount: int):
    await _execute(
        "INSERT INTO user_credits (uid, credits) VALUES (?, ?) "
        "ON CONFLICT(uid) DO UPDATE SET credits=excluded.credits",
        [uid, max(0, amount)],
    )


async def add_user_credits(uid: str, amount: int):
    await _execute(
        "INSERT INTO user_credits (uid, credits) VALUES (?, ?) "
        "ON CONFLICT(uid) DO UPDATE SET credits=credits+?",
        [uid, amount, amount],
    )


async def consume_user_credit(uid: str) -> bool:
    """يستهلك رصيد واحد — يرجع True لو نجح"""
    bal = await get_user_credits(uid)
    if bal <= 0:
        return False
    await set_user_credits(uid, bal - 1)
    return True
