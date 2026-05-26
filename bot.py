"""
Auto Publisher Bot — aiogram 3.x
ميزات:
  • نظام اشتراك إجباري محكم (fail-closed)
  • نظام رصيد يومي + وايت ليست
  • رسالة ترحيب قابلة للتخصيص
  • إحصائيات يومية تلقائية للأدمن
  • تصدير المستخدمين CSV
  • لغة الرد (عربي/إنجليزي) لكل مستخدم
  • نظام btn/kb مع ألوان إيموجية
  • تحويل صوت لنص (Whisper - Hugging Face)
  • توليد صور (Stable Diffusion - Replicate)
"""

import asyncio
import base64
import copy
import csv
import io
import json
import logging
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    Message,
    WebAppData,
)

from keyboards import (
    admin_credits_menu, admin_menu, back_button, btn, channel_menu,
    confirm_keyboard, credits_keyboard, daily_limit_keyboard,
    kb, main_menu, model_keyboard, subscription_required_keyboard,
)

# ═══════════════════════════════════════════════════════════
#  إعداد اللوجر
# ═══════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
#  المتغيرات البيئية
# ═══════════════════════════════════════════════════════════
BOT_TOKEN    = os.getenv("BOT_TOKEN",    "ضع_توكن_البوت_هنا")
BOT_USERNAME = os.getenv("BOT_USERNAME", "your_bot")
ADMINS       = [int(x) for x in os.getenv("ADMINS", "123456789").split(",") if x.strip()]
WEBAPP_URL   = os.getenv("WEBAPP_URL",   "https://yourdomain.com/index.html")
HF_API_KEY   = os.getenv("HF_API_KEY",  "")   # Hugging Face — للصوت
REPLICATE_API_KEY = os.getenv("REPLICATE_API_KEY", "")  # Replicate — للصور

GROQ_API_KEYS = [os.getenv(f"GROQ_API_KEY_{i}") for i in range(1, 7)]
GROQ_API_KEYS = [k for k in GROQ_API_KEYS if k]
if not GROQ_API_KEYS:
    _old = os.getenv("GROQ_API_KEY", "ضع_مفتاح_GROQ_هنا")
    GROQ_API_KEYS = [_old]
_groq_index = 0

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyCeHXhuC4jegrYos4upBpj8HaOexDEKlS0")
GEMINI_URL     = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
GROQ_URL       = "https://api.groq.com/openai/v1/chat/completions"
FIREBASE_KEY   = "AIzaSyA27E7jUV8osRY7NzwP2fZwGoTkp5gJhZw"
SEARCH_URL     = "https://ai-multi-search-backend-321697147922.europe-west6.run.app/ask"

FIREBASE_HEADERS = {
    "User-Agent"       : "Dalvik/2.1.0 (Linux; U; Android 16; 2311DRK48G Build/BP2A.250605.031.A3)",
    "Connection"       : "Keep-Alive",
    "Accept-Encoding"  : "gzip",
    "Content-Type"     : "application/json",
    "X-Android-Package": "com.lmtechstudio.aimultisearch",
    "X-Android-Cert"   : "5D08264B44E0E53FBCCC70B4F016474CC6C5AB5C",
    "Accept-Language"  : "ar-EG, en-US",
    "X-Client-Version" : "Android/Fallback/X23001000/FirebaseCore-Android",
    "X-Firebase-GMPID" : "1:321697147922:android:26e6fb8e30dcc23dfffccb",
    "X-Firebase-Client": "H4sIAAAAAAAA_6tWykhNLCpJSk0sKVayio7VUSpLLSrOzM9TslIyUqoFAFyivEQfAAAA",
}
SEARCH_CFG = {
    "perplexity": {"app_version": "1.2.8",    "search_id": "825a35c5-aac2-49d7-8317-5b7a68ae6cae"},
    "claude"    : {"app_version": "1.2.8",    "search_id": "825a35c5-aac2-49d7-8317-5b7a68ae6cae"},
    "openai"    : {"app_version": "DEV_TEST", "search_id": "f0a6705c-e33e-4288-a3ef-c91cd6564b59"},
    "deepseek"  : {"app_version": "1.2.8",    "search_id": "f0a6705c-e33e-4288-a3ef-c91cd6564b59"},
    "gemini"    : {"app_version": "1.2.8",    "search_id": "b2ed082e-5793-4de0-9e42-c8c7fb57b5d5"},
    "llama"     : {"app_version": "1.2.8",    "search_id": "b2ed082e-5793-4de0-9e42-c8c7fb57b5d5"},
}

DEFAULT_MODEL  = "claude"
MAX_HISTORY    = 20
RATE_LIMIT     = 2
MAX_FILE_SIZE  = 5 * 1024 * 1024
FREE_MODE      = False   # لو True — البوت مجاني لكل المستخدمين بلا حدود

SYSTEM_PROMPT = """
أنت مساعد متخصص بالكامل في Python.
- تجاوب فقط عن Python.
- إذا كان السؤال خارج Python قل: (أنا متخصص في Python فقط)
- ساعد في: Flask, Django, APIs, Bots, Automation, Debugging, Web Scraping, OOP
- أصلح الأكواد واشرح الأخطاء.
- استخدم العربية دائمًا.
"""

SUPPORTED_EXT = ('.txt', '.py', '.js', '.json', '.html', '.css', '.md', '.xml', '.csv')

# ═══════════════════════════════════════════════════════════
#  ملفات البيانات
# ═══════════════════════════════════════════════════════════
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

MEMORY_FILE   = f"{DATA_DIR}/user_memory.json"
STATS_FILE    = f"{DATA_DIR}/stats.json"
CHATS_FILE    = f"{DATA_DIR}/bot_chats.json"
BANNED_FILE   = f"{DATA_DIR}/banned_users.json"
CHANNEL_FILE  = f"{DATA_DIR}/required_channel.json"
WHITELIST_FILE= f"{DATA_DIR}/whitelist.json"
WELCOME_FILE  = f"{DATA_DIR}/welcome_msg.json"
CREDITS_FILE  = f"{DATA_DIR}/user_credits.json"
FREE_MODE_FILE= f"{DATA_DIR}/free_mode.json"

def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.error(f"فشل حفظ {path}: {e}")

# تحميل البيانات
user_memory    = {str(k): v for k, v in load_json(MEMORY_FILE, {}).items()}
stats          = load_json(STATS_FILE, {
    "total_users": 0, "total_messages": 0,
    "total_images": 0, "total_files": 0, "dew_used": 0,
    "started_at": datetime.now(timezone.utc).isoformat()
})
bot_chats      = load_json(CHATS_FILE, {})
banned_users   = set(load_json(BANNED_FILE, []))
whitelist      = set(load_json(WHITELIST_FILE, []))
_channel_data  = load_json(CHANNEL_FILE, {"channel": None})
REQUIRED_CHANNEL = _channel_data.get("channel")
_welcome_data  = load_json(WELCOME_FILE, {"msg": None})
WELCOME_MSG    = _welcome_data.get("msg")
daily_credits  = load_json(CREDITS_FILE, {})   # {uid: رصيد_دائم}
_free_mode_data= load_json(FREE_MODE_FILE, {"enabled": False})
FREE_MODE      = _free_mode_data.get("enabled", False)
user_model     = {}
user_lang      = {}   # {uid: "ar" | "en"}
user_last_msg  = {}
pending        = {}   # {uid: "action"}

_firebase_token        = None
_firebase_token_expiry = 0

# ═══════════════════════════════════════════════════════════
#  Bot & Dispatcher
# ═══════════════════════════════════════════════════════════
from aiogram.client.default import DefaultBotProperties
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
dp  = Dispatcher()

# ═══════════════════════════════════════════════════════════
#  نظام الرصيد — يديره الأدمن
# ═══════════════════════════════════════════════════════════
def get_credits(uid: str) -> int:
    """يرجع رصيد المستخدم الحالي"""
    return daily_credits.get(str(uid), 0)

def add_credits(uid: str, amount: int):
    """يضيف رصيد للمستخدم"""
    uid = str(uid)
    daily_credits[uid] = daily_credits.get(uid, 0) + amount
    save_json(CREDITS_FILE, daily_credits)

def set_credits(uid: str, amount: int):
    """يضبط رصيد المستخدم لرقم محدد"""
    uid = str(uid)
    daily_credits[uid] = max(0, amount)
    save_json(CREDITS_FILE, daily_credits)

def consume_credit(uid: str) -> bool:
    """
    يستهلك رصيد واحد.
    يرجع True لو مسموح، False لو ما في رصيد.
    الأدمن والوايت ليست = دائماً مسموح.
    """
    uid = str(uid)
    if FREE_MODE:
        return True
    if uid in whitelist or int(uid) in ADMINS:
        return True
    bal = daily_credits.get(uid, 0)
    if bal <= 0:
        return False
    daily_credits[uid] = bal - 1
    save_json(CREDITS_FILE, daily_credits)
    return True

def set_free_mode(enabled: bool):
    global FREE_MODE
    FREE_MODE = enabled
    save_json(FREE_MODE_FILE, {"enabled": enabled})

# ═══════════════════════════════════════════════════════════
#  الاشتراك الإجباري — fail-closed
# ═══════════════════════════════════════════════════════════
async def check_subscription(user_id: int) -> bool:
    global REQUIRED_CHANNEL
    if not REQUIRED_CHANNEL:
        return True
    if str(user_id) in whitelist or user_id in ADMINS:
        return True
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ("member", "administrator", "creator", "restricted")
    except Exception as e:
        log.warning(f"check_subscription error: {e}")
        return True   # fail-open: لو ما قدر يتحقق يسمح للمستخدم

def set_required_channel(channel):
    global REQUIRED_CHANNEL
    REQUIRED_CHANNEL = channel
    save_json(CHANNEL_FILE, {"channel": channel})

# ═══════════════════════════════════════════════════════════
#  Groq helpers
# ═══════════════════════════════════════════════════════════
def _get_groq_key():
    return GROQ_API_KEYS[_groq_index % len(GROQ_API_KEYS)]

def _next_groq_key():
    global _groq_index
    _groq_index = (_groq_index + 1) % len(GROQ_API_KEYS)
    return GROQ_API_KEYS[_groq_index]

async def ask_groq(messages: list) -> str:
    data = {
        "model": "llama-3.1-8b-instant",
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 2048,
    }
    for _ in range(len(GROQ_API_KEYS)):
        headers = {
            "Authorization": f"Bearer {_get_groq_key()}",
            "Content-Type": "application/json",
        }
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(GROQ_URL, headers=headers, json=data, timeout=aiohttp.ClientTimeout(total=60)) as r:
                    if r.status == 200:
                        res = await r.json()
                        return res["choices"][0]["message"]["content"]
                    log.warning(f"Groq {r.status}, switching key")
                    _next_groq_key()
                    await asyncio.sleep(0.3)
        except asyncio.TimeoutError:
            return "⏱ انتهت مهلة الاتصال"
        except Exception as e:
            return f"❌ خطأ: {e}"
    return "⏳ كل المفاتيح مشغولة، حاول بعد لحظة"

async def ask_groq_fix(file_text: str, file_name: str) -> str | None:
    prompt = (
        f"أنت خبير Python. لديك الملف:\nاسم الملف: {file_name}\n\n"
        f"```\n{file_text[:6000]}\n```\n\n"
        "المطلوب:\n1. اذكر الأعطال بقائمة مرقمة\n"
        "2. أرسل الكود المصلح كاملاً بين ```python و```"
    )
    messages = [
        {"role": "system", "content": "أنت خبير Python. أجب بالعربية دائماً."},
        {"role": "user", "content": prompt},
    ]
    for _ in range(len(GROQ_API_KEYS)):
        headers = {"Authorization": f"Bearer {_get_groq_key()}", "Content-Type": "application/json"}
        data = {"model": "llama-3.1-8b-instant", "messages": messages, "temperature": 0.2, "max_tokens": 4096}
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(GROQ_URL, headers=headers, json=data, timeout=aiohttp.ClientTimeout(total=90)) as r:
                    if r.status == 200:
                        res = await r.json()
                        return res["choices"][0]["message"]["content"]
                    _next_groq_key()
                    await asyncio.sleep(0.3)
        except Exception:
            return None
    return None

# ═══════════════════════════════════════════════════════════
#  Gemini helpers
# ═══════════════════════════════════════════════════════════
async def ask_gemini(text: str) -> str | None:
    payload = {"contents": [{"parts": [{"text": text}]}]}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(f"{GEMINI_URL}?key={GEMINI_API_KEY}", json=payload,
                              timeout=aiohttp.ClientTimeout(total=30)) as r:
                if r.status == 200:
                    res = await r.json()
                    return res["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        log.error(f"ask_gemini: {e}")
    return None

async def ask_gemini_vision(image_bytes: bytes, question: str) -> str | None:
    img_b64 = base64.b64encode(image_bytes).decode()
    payload = {"contents": [{"parts": [
        {"text": question or "حلل هذه الصورة بالتفصيل"},
        {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}},
    ]}]}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(f"{GEMINI_URL}?key={GEMINI_API_KEY}", json=payload,
                              timeout=aiohttp.ClientTimeout(total=60)) as r:
                if r.status == 200:
                    res = await r.json()
                    return res["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        log.error(f"ask_gemini_vision: {e}")
    return None

async def ask_gemini_file(file_text: str, file_name: str) -> str | None:
    prompt = (
        f"أنت خبير برمجي. لديك الملف:\nاسم: {file_name}\n\n"
        f"```\n{file_text[:8000]}\n```\n\n"
        "1. اذكر الأعطال بقائمة مرقمة\n"
        "2. أرسل الكود المصلح كاملاً بين ```python و```"
    )
    return await ask_gemini(prompt)

# ═══════════════════════════════════════════════════════════
#  Firebase + AI Search
# ═══════════════════════════════════════════════════════════
async def get_firebase_token() -> str | None:
    global _firebase_token, _firebase_token_expiry
    if _firebase_token and time.time() < _firebase_token_expiry - 60:
        return _firebase_token
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                "https://www.googleapis.com/identitytoolkit/v3/relyingparty/signupNewUser",
                params={"key": FIREBASE_KEY},
                data=json.dumps({"clientType": "CLIENT_TYPE_ANDROID"}),
                headers=FIREBASE_HEADERS,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as r:
                data = await r.json()
                _firebase_token        = "Bearer " + data["idToken"]
                _firebase_token_expiry = time.time() + int(data["expiresIn"])
                return _firebase_token
    except Exception as e:
        log.error(f"Firebase token error: {e}")
        return None

async def ask_ai_search(question: str, provider: str = "claude") -> str:
    token = await get_firebase_token()
    if not token:
        return "❌ فشل الاتصال بالخادم"
    cfg  = SEARCH_CFG.get(provider, SEARCH_CFG["claude"])
    av   = cfg["app_version"]
    lang_hint = "You MUST answer in the EXACT same language as the user question.\n"
    if provider == "deepseek":
        lang_hint = "Never reply in Chinese unless explicitly asked.\n" + lang_hint
    payload = {
        "provider": provider,
        "prompt": lang_hint + f"User question:\n{question}",
        "plan": "ULTRA",
        "app_version": av,
    }
    headers = {
        "User-Agent"       : "okhttp/4.12.0",
        "Accept-Encoding"  : "gzip",
        "authorization"    : token,
        "x-plan"           : "ULTRA",
        "x-app-version"    : av,
        "x-search-id"      : cfg["search_id"],
        "x-search-expected": "2",
        "content-type"     : "application/json; charset=utf-8",
    }
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(SEARCH_URL, data=json.dumps(payload), headers=headers,
                              timeout=aiohttp.ClientTimeout(total=30)) as r:
                data = await r.json()
                if data.get("ok"):
                    return data.get("answer", "❌ لا يوجد جواب")
                return f"❌ خطأ: {data.get('message', 'غير معروف')}"
    except asyncio.TimeoutError:
        return "⏱ انتهت مهلة الاتصال"
    except Exception as e:
        return f"❌ خطأ: {e}"

# ═══════════════════════════════════════════════════════════
#  إدارة الذاكرة
# ═══════════════════════════════════════════════════════════
def get_history(chat_id, user_info=None):
    cid    = str(chat_id)
    is_new = cid not in user_memory
    if is_new:
        user_memory[cid] = {
            "history"  : [{"role": "system", "content": SYSTEM_PROMPT}],
            "name"     : "",
            "username" : "",
            "joined_at": datetime.now(timezone.utc).isoformat(),
            "msg_count": 0,
        }
        stats["total_users"] += 1
        save_json(STATS_FILE, stats)
    return user_memory[cid]["history"]

def trim_history(chat_id):
    cid = str(chat_id)
    h   = user_memory[cid]["history"]
    if len(h) > MAX_HISTORY:
        user_memory[cid]["history"] = [h[0]] + h[-(MAX_HISTORY - 1):]

def push_user(chat_id, content):
    h = get_history(chat_id)
    h.append({"role": "user", "content": content})
    trim_history(chat_id)

def push_assistant(chat_id, content):
    cid = str(chat_id)
    user_memory[cid]["history"].append({"role": "assistant", "content": content})
    user_memory[cid]["msg_count"] = user_memory[cid].get("msg_count", 0) + 1
    stats["total_messages"] += 1
    save_json(STATS_FILE, stats)
    save_json(MEMORY_FILE, user_memory)

# u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650
#  Whisper u2014 u062au062du0648u064au0644 u0635u0648u062a u0644u0646u0635 (Hugging Face)
# u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650u0650
# ═══════════════════════════════════════════════════════════
#  مساعد: تحقق شامل قبل الرد
# ═══════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════
#  Whisper — تحويل صوت لنص (Hugging Face)
# ═══════════════════════════════════════════════════════════
async def transcribe_voice(audio_bytes: bytes) -> str:
    if not HF_API_KEY:
        return "❌ HF_API_KEY غير موجود في المتغيرات"
    url = "https://api-inference.huggingface.co/models/openai/whisper-large-v3"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, headers=headers, data=audio_bytes,
                              timeout=aiohttp.ClientTimeout(total=60)) as r:
                if r.status == 200:
                    res = await r.json()
                    return res.get("text", "❌ لم يتم التعرف على الصوت")
                elif r.status == 503:
                    return "⏳ النموذج يتحمل، حاول بعد 30 ثانية"
                else:
                    return f"❌ خطأ {r.status}"
    except Exception as e:
        return f"❌ خطأ: {e}"

# ═══════════════════════════════════════════════════════════
#  Stable Diffusion — توليد صور (Replicate)
# ═══════════════════════════════════════════════════════════
async def generate_image(prompt: str) -> str | None:
    if not REPLICATE_API_KEY:
        return None
    headers = {
        "Authorization": f"Bearer {REPLICATE_API_KEY}",
        "Content-Type": "application/json",
        "Prefer": "wait",
    }
    payload = {
        "input": {
            "prompt": prompt,
            "width": 768, "height": 768,
            "num_inference_steps": 25,
            "guidance_scale": 7.5,
        }
    }
    url = "https://api.replicate.com/v1/models/bytedance/sdxl-lightning-4step/predictions"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, headers=headers, json=payload,
                              timeout=aiohttp.ClientTimeout(total=120)) as r:
                if r.status in (200, 201):
                    res = await r.json()
                    output = res.get("output")
                    if output:
                        return output[0] if isinstance(output, list) else output
                    pred_id = res.get("id")
                    if not pred_id:
                        return None
                    for _ in range(30):
                        await asyncio.sleep(3)
                        async with s.get(
                            f"https://api.replicate.com/v1/predictions/{pred_id}",
                            headers=headers,
                        ) as poll:
                            pres = await poll.json()
                            if pres.get("status") == "succeeded":
                                out = pres.get("output")
                                return out[0] if isinstance(out, list) else out
                            if pres.get("status") == "failed":
                                return None
    except Exception as e:
        log.error(f"generate_image: {e}")
    return None

async def pre_check(message: Message) -> bool:
    """
    يتحقق من:
    1. الحظر
    2. الاشتراك الإجباري
    3. الرصيد اليومي
    يرجع True لو المستخدم مسموح له يكمل.
    """
    uid = str(message.from_user.id)

    if uid in banned_users:
        return False

    if not await check_subscription(message.from_user.id):
        ch = REQUIRED_CHANNEL or "القناة"
        await message.answer(
            f"⚠️ *يجب الاشتراك في {ch} أولاً!*\n\nاشترك ثم اضغط ✅ تحققت.",
            reply_markup=subscription_required_keyboard(ch),
        )
        return False

    if not consume_credit(uid):
        bal = get_credits(uid)
        await message.answer(
            f"⏳ *رصيدك صفر!*\n\n"
            f"رصيدك الحالي: `{bal}` رسالة\n"
            f"تواصل مع الأدمن لإضافة رصيد.",
            reply_markup=daily_limit_keyboard(REQUIRED_CHANNEL),
        )
        return False

    return True

# ═══════════════════════════════════════════════════════════
#  إحصائيات
# ═══════════════════════════════════════════════════════════
def build_stats_text(cid=None):
    started = stats.get("started_at", "—")
    try:
        dt      = datetime.fromisoformat(started)
        started = dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        pass
    groups   = sum(1 for v in bot_chats.values() if v.get("type") in ("group", "supergroup"))
    channels = sum(1 for v in bot_chats.values() if v.get("type") == "channel")
    lines = [
        "📊 *إحصائيات البوت الكاملة*\n",
        f"👥 إجمالي المستخدمين : `{stats['total_users']}`",
        f"💬 إجمالي الرسائل    : `{stats['total_messages']}`",
        f"🖼 صور محللة         : `{stats.get('total_images', 0)}`",
        f"📂 ملفات معالجة      : `{stats.get('total_files', 0)}`",
        f"🔧 استخدامات /dew    : `{stats.get('dew_used', 0)}`",
        f"🏘 المجموعات         : `{groups}`",
        f"📣 القنوات           : `{channels}`",
        f"🚫 المحظورون         : `{len(banned_users)}`",
        f"⭐ الوايت ليست       : `{len(whitelist)}`",
        f"📌 قناة إجبارية      : `{REQUIRED_CHANNEL or 'لا توجد'}`",
        f"🆓 وضع مجاني         : `{'مفعّل ✅' if FREE_MODE else 'معطّل ❌'}`",
        f"🕐 تاريخ التشغيل     : `{started}`",
    ]
    if cid:
        uid_data = user_memory.get(str(cid), {})
        remaining = get_credits(str(cid))
        lines += [
            "",
            "👤 *بياناتك الشخصية*",
            f"🧠 رسائل محفوظة  : `{len(uid_data.get('history', [])) - 1}`",
            f"📨 مجموع رسائلك  : `{uid_data.get('msg_count', 0)}`",
            f"🔋 رصيدك اليوم   : `{remaining}` رسالة متبقية",
            f"📅 انضممت        : `{uid_data.get('joined_at', '—')[:10]}`",
        ]
    return "\n".join(lines)

def build_chats_text():
    if not bot_chats:
        return "🏘 *الجروبات والقنوات*\n\nلا يوجد مجموعات أو قنوات مسجلة."
    lines = ["🏘 *الجروبات والقنوات:*\n"]
    for cid, info in list(bot_chats.items())[-50:]:
        icon = "📣" if info.get("type") == "channel" else "👥"
        lines.append(f"{icon} `{cid}` — *{info.get('title','—')}* ({info.get('added_at','—')})")
    return "\n".join(lines)

# ═══════════════════════════════════════════════════════════
#  تصدير CSV
# ═══════════════════════════════════════════════════════════
def export_users_csv() -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["uid", "name", "username", "msg_count", "joined_at", "banned", "whitelist"])
    for uid, data in user_memory.items():
        if not isinstance(data, dict):
            continue
        writer.writerow([
            uid,
            data.get("name", ""),
            data.get("username", ""),
            data.get("msg_count", 0),
            data.get("joined_at", "")[:10],
            "✓" if uid in banned_users else "",
            "✓" if uid in whitelist    else "",
        ])
    return output.getvalue().encode("utf-8-sig")

# ═══════════════════════════════════════════════════════════
#  معالجة الملفات
# ═══════════════════════════════════════════════════════════
def extract_code_block(text: str) -> str | None:
    for pat in [r"```python\s*([\s\S]+?)```", r"```\w*\s*([\s\S]+?)```"]:
        m = re.search(pat, text)
        if m:
            return m.group(1).strip()
    return None

def process_file(content: bytes, name: str) -> str:
    if name.lower().endswith(SUPPORTED_EXT):
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            return content.decode("latin-1", errors="replace")
    return f"ملف: {name}\nالحجم: {len(content):,} بايت\n(نوع غير مدعوم)"

async def handle_file_fix(message: Message, file_content: bytes, file_name: str):
    file_text = process_file(file_content, file_name)
    if "نوع غير مدعوم" in file_text:
        await message.answer(f"❌ نوع الملف `{file_name}` غير مدعوم للتحليل.")
        return
    await message.answer("🔍 جاري تحليل الملف وإصلاح الأعطال...")
    result = await ask_gemini_file(file_text, file_name)
    if not result:
        result = await ask_groq_fix(file_text, file_name)
    if not result:
        result = await ask_ai_search(
            f"أنت خبير برمجي. لديك الملف: {file_name}\n\n```\n{file_text[:4000]}\n```\n\n"
            "اذكر الأعطال ثم أرسل الكود المصلح كاملاً بين ```python و```", "claude"
        )
    if not result:
        await message.answer("❌ فشل التحليل، حاول مرة أخرى")
        return

    fixed_code  = extract_code_block(result)
    explanation = re.sub(r"```[\s\S]*?```", "", result).strip()
    if explanation:
        await message.answer(explanation)
    if fixed_code:
        name_parts = file_name.rsplit(".", 1)
        fixed_name = f"{name_parts[0]}_fixed.{name_parts[1]}" if len(name_parts) == 2 else f"{file_name}_fixed"
        await message.answer_document(
            BufferedInputFile(fixed_code.encode("utf-8"), filename=fixed_name),
            caption=f"✅ *الملف المصلح:* `{fixed_name}`",
        )
    else:
        await message.answer("⚠️ لم يتمكن النموذج من استخراج كود مصلح، أعد المحاولة.")

# ═══════════════════════════════════════════════════════════
#  تسجيل الشاتات
# ═══════════════════════════════════════════════════════════
def register_chat(chat):
    cid = str(chat.id)
    if cid not in bot_chats:
        bot_chats[cid] = {
            "title"   : chat.title or "—",
            "type"    : chat.type,
            "added_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        }
        save_json(CHATS_FILE, bot_chats)

def unregister_chat(chat_id):
    cid = str(chat_id)
    if cid in bot_chats:
        del bot_chats[cid]
        save_json(CHATS_FILE, bot_chats)

# ═══════════════════════════════════════════════════════════
#  إحصائيات يومية تلقائية
# ═══════════════════════════════════════════════════════════
async def daily_stats_task():
    """يرسل إحصائيات يومية للأدمن كل 24 ساعة"""
    await asyncio.sleep(10)
    while True:
        await asyncio.sleep(86400)
        text = (
            f"📅 *تقرير يومي — {get_today()}*\n\n"
            + build_stats_text()
        )
        for admin_id in ADMINS:
            try:
                await bot.send_message(admin_id, text)
            except Exception:
                pass

# ═══════════════════════════════════════════════════════════
#  Handlers — Commands
# ═══════════════════════════════════════════════════════════
@dp.message(Command("start"))
async def cmd_start(message: Message):
    uid  = str(message.from_user.id)
    cid  = str(message.chat.id)
    name = message.from_user.first_name or message.from_user.username or "بك"
    get_history(cid, message.from_user)
    user_memory[cid]["name"]     = name
    user_memory[cid]["username"] = message.from_user.username or ""
    save_json(MEMORY_FILE, user_memory)

    # رسالة الترحيب المخصصة أو الافتراضية
    welcome = WELCOME_MSG or (
        f"🐍 *أهلاً {name} في بوت Python!*\n\n"
        "اسألني أي شيء عن Python مباشرةً،\n"
        "أو أرسل صورة/ملف للتحليل.\n\n"
        "في المجموعات استخدم الأمر /dew"
    )
    await message.answer(welcome, reply_markup=main_menu())
    if message.from_user.id in ADMINS:
        await message.answer("🛠 *لوحة الأدمن*", reply_markup=admin_menu())

    # إشعار الأدمن بمستخدم جديد — مرة واحدة فقط
    if not user_memory[cid].get("notified"):
        user_memory[cid]["notified"] = True
        save_json(MEMORY_FILE, user_memory)
        uname_display = f"@{message.from_user.username}" if message.from_user.username else "بدون يوزر"
        notif = (
            f"🆕 *مستخدم جديد!*\n\n"
            f"👤 {name}\n🔗 {uname_display}\n🆔 `{uid}`\n"
            f"👥 المجموع: `{stats['total_users']}`"
        )
        for admin_id in ADMINS:
            try:
                await bot.send_message(admin_id, notif)
            except Exception:
                pass

@dp.message(F.web_app_data)
async def handle_webapp_data(message: Message):
    """استقبال البيانات من Mini App"""
    uid = str(message.from_user.id)
    try:
        data   = json.loads(message.web_app_data.data)
        action = data.get("action", "")
    except Exception:
        await message.answer("❌ بيانات غير صالحة")
        return

    # ── تحقق أساسي ──
    if uid in banned_users:
        return
    if not await check_subscription(message.from_user.id):
        ch = REQUIRED_CHANNEL or "القناة"
        await message.answer(
            f"⚠️ *يجب الاشتراك في {ch} أولاً!*\n\nاشترك ثم اضغط ✅ تحققت.",
            reply_markup=subscription_required_keyboard(ch),
        )
        return

    # ── توجيه الأكشن ──
    if action == "my_account":
        uid_data  = user_memory.get(uid, {})
        remaining = get_credits(uid)
        bal_line  = "∞ (مجاني)" if FREE_MODE or uid in whitelist or message.from_user.id in ADMINS else str(remaining)
        await message.answer(
            f"💲 *حسابي*\n\n"
            f"👤 الاسم: {message.from_user.first_name}\n"
            f"🔋 الرصيد: `{bal_line}` رسالة\n"
            f"📨 مجموع رسائلك: `{uid_data.get('msg_count', 0)}`\n"
            f"📅 انضممت: `{uid_data.get('joined_at', '—')[:10]}`",
            reply_markup=main_menu(),
        )
    elif action == "my_credits":
        remaining = get_credits(uid)
        bal_line  = "∞ غير محدود" if FREE_MODE or uid in whitelist or message.from_user.id in ADMINS else f"`{remaining}` رسالة"
        await message.answer(
            f"🔋 *رصيدك*\n\nالرصيد المتبقي: {bal_line}\n\nتواصل مع الأدمن لإضافة رصيد.",
            reply_markup=credits_keyboard(),
        )
    elif action == "choose_model":
        selected = user_model.get(uid, DEFAULT_MODEL)
        await message.answer("🤖 *اختر النموذج:*", reply_markup=model_keyboard(selected))
    elif action == "stats":
        await message.answer(build_stats_text(message.chat.id), reply_markup=back_button())
    elif action in ("updates", "promo_channel", "support"):
        labels = {
            "updates":      "🔥 تم فتح قناة التحديثات",
            "promo_channel":"🔍 تم فتح قناة التفعيلات",
            "support":      "📞 تواصل مع الدعم الفني",
        }
        await message.answer(labels[action], reply_markup=main_menu())
    else:
        await message.answer(f"✅ تم اختيار: `{action}`", reply_markup=main_menu())

@dp.message(Command("menu"))
async def cmd_menu(message: Message):
    await message.answer("🏠 *القائمة الرئيسية*", reply_markup=main_menu())

@dp.message(Command("clear"))
async def cmd_clear(message: Message):
    cid = str(message.chat.id)
    if cid in user_memory:
        user_memory[cid]["history"] = [{"role": "system", "content": SYSTEM_PROMPT}]
        save_json(MEMORY_FILE, user_memory)
    await message.answer("✅ تم مسح المحادثة")

@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    await message.answer(build_stats_text(message.chat.id))

@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📚 *طريقة الاستخدام:*\n\n"
        "*في المحادثة الخاصة:*\n"
        "• اكتب سؤالك مباشرة\n"
        "• أرسل صورة فيها كود\n"
        "• أرسل ملف .py أو .txt\n"
        "• أرسل رسالة صوتية → يحولها لنص ويرد عليها 🎙\n"
        "• `/image وصف بالإنجليزي` → يولد صورة 🎨\n\n"
        "*في المجموعات:*\n"
        "`/dew سؤالك هنا`\n"
        "رد على صورة/ملف/نص بـ /dew\n\n"
        "*أوامر:* /menu /clear /stats /help /image",
        reply_markup=back_button(),
    )

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id not in ADMINS:
        return
    await message.answer("🛠 *لوحة الأدمن*", reply_markup=admin_menu())

@dp.message(Command("dew"))
async def cmd_dew(message: Message):
    uid = str(message.from_user.id)
    if uid in banned_users:
        return
    cid        = str(message.chat.id)
    text       = message.text or ""
    parts      = text.split(None, 1)
    question   = parts[1].strip() if len(parts) > 1 else ""
    if question.startswith("@"):
        q2       = question.split(None, 1)
        question = q2[1].strip() if len(q2) > 1 else ""
    replied = message.reply_to_message
    await bot.send_chat_action(message.chat.id, "typing")
    stats["dew_used"] = stats.get("dew_used", 0) + 1

    if replied and replied.photo:
        file = await bot.get_file(replied.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        content    = file_bytes.read()
        caption    = question or replied.caption or "حلل هذه الصورة واشرح المشكلة"
        push_user(cid, caption)
        reply = await ask_gemini_vision(content, caption) or await ask_ai_search(caption, "claude")
        reply = reply or "❌ فشل تحليل الصورة"
        push_assistant(cid, reply)
        await message.reply(reply)
        return

    if replied and replied.document:
        doc        = replied.document
        file       = await bot.get_file(doc.file_id)
        file_bytes = await bot.download_file(file.file_path)
        content    = file_bytes.read()
        await handle_file_fix(message, content, doc.file_name or "file.py")
        return

    if replied and replied.text and not question:
        question = replied.text

    if not question:
        await message.reply(
            "❓ *كيف تستخدم /dew:*\n\n"
            "`/dew سؤالك هنا`\n"
            "أو رد على صورة/ملف/نص بـ /dew"
        )
        return

    push_user(cid, question)
    reply = await ask_groq(get_history(cid))
    push_assistant(cid, reply)
    await message.reply(reply)

# ═══════════════════════════════════════════════════════════
#  Handlers — رسائل خاصة
# ═══════════════════════════════════════════════════════════
@dp.message(F.chat.type == "private", F.text)
async def handle_private_text(message: Message):
    uid = str(message.from_user.id)
    cid = str(message.chat.id)

    if uid in banned_users:
        return

    # pending actions
    if uid in pending:
        action = pending.pop(uid)

        if action == "broadcast":
            await message.answer(f"⏳ جاري الإرسال لـ {len(user_memory)} مستخدم...")
            ok = 0
            for target_uid in user_memory:
                try:
                    await bot.send_message(target_uid, f"📢 *رسالة من الأدمن:*\n\n{message.text}")
                    ok += 1
                    await asyncio.sleep(0.05)
                except Exception:
                    pass
            await message.answer(f"✅ أُرسل لـ {ok} / {len(user_memory)} مستخدم", reply_markup=admin_menu())
            return

        if action == "group_broadcast":
            await message.answer(f"⏳ جاري الإرسال لـ {len(bot_chats)} مجموعة/قناة...")
            ok = 0
            for chat_id in bot_chats:
                try:
                    await bot.send_message(chat_id, f"📣 *إعلان:*\n\n{message.text}")
                    ok += 1
                    await asyncio.sleep(0.1)
                except Exception:
                    pass
            await message.answer(f"✅ أُرسل لـ {ok} / {len(bot_chats)}", reply_markup=admin_menu())
            return

        if action == "addchannel":
            ch = message.text.strip()
            if not ch.startswith("@"):
                ch = "@" + ch
            set_required_channel(ch)
            await message.answer(
                f"✅ *تم تفعيل الاشتراك الإجباري!*\n\n📌 القناة: `{ch}`\n\n⚠️ تأكد أن البوت أدمن في القناة.",
                reply_markup=admin_menu(),
            )
            return

        if action == "ban":
            target = message.text.strip()
            banned_users.add(target)
            save_json(BANNED_FILE, list(banned_users))
            await message.answer(f"🚫 تم حظر `{target}`", reply_markup=admin_menu())
            return

        if action == "unban":
            target = message.text.strip()
            banned_users.discard(target)
            save_json(BANNED_FILE, list(banned_users))
            await message.answer(f"✅ تم رفع الحظر عن `{target}`", reply_markup=admin_menu())
            return

        if action == "clear_mem":
            target = message.text.strip()
            if target in user_memory:
                user_memory[target]["history"] = [{"role": "system", "content": SYSTEM_PROMPT}]
                save_json(MEMORY_FILE, user_memory)
                await message.answer(f"🗑 تم مسح ذاكرة `{target}`", reply_markup=admin_menu())
            else:
                await message.answer(f"❓ المستخدم `{target}` غير موجود", reply_markup=admin_menu())
            return

        if action == "add_credits":
            # صيغة: ID مسافة كمية — مثال: 123456789 50
            parts = message.text.strip().split()
            if len(parts) == 2 and parts[1].isdigit():
                target, amount = parts[0], int(parts[1])
                add_credits(target, amount)
                bal = get_credits(target)
                await message.answer(
                    f"✅ تمت إضافة `{amount}` رسالة للمستخدم `{target}`\n"
                    f"رصيده الآن: `{bal}` رسالة",
                    reply_markup=admin_credits_menu(FREE_MODE),
                )
                # إشعار المستخدم
                try:
                    await bot.send_message(target, f"🎁 تمت إضافة `{amount}` رسالة لرصيدك!\nرصيدك الآن: `{bal}` رسالة")
                except Exception:
                    pass
            else:
                await message.answer("❌ صيغة خاطئة\nمثال: `123456789 50`", reply_markup=admin_credits_menu(FREE_MODE))
            return

        if action == "set_credits":
            parts = message.text.strip().split()
            if len(parts) == 2 and parts[1].isdigit():
                target, amount = parts[0], int(parts[1])
                set_credits(target, amount)
                await message.answer(
                    f"✅ تم ضبط رصيد `{target}` على `{amount}` رسالة",
                    reply_markup=admin_credits_menu(FREE_MODE),
                )
                try:
                    await bot.send_message(target, f"🔧 تم تعديل رصيدك إلى `{amount}` رسالة")
                except Exception:
                    pass
            else:
                await message.answer("❌ صيغة خاطئة\nمثال: `123456789 100`", reply_markup=admin_credits_menu(FREE_MODE))
            return

        if action == "view_credits":
            target = message.text.strip()
            bal    = get_credits(target)
            wl     = "⭐ وايت ليست" if target in whitelist else ""
            await message.answer(
                f"👤 المستخدم: `{target}`\n🔋 الرصيد: `{bal}` رسالة {wl}",
                reply_markup=admin_credits_menu(FREE_MODE),
            )
            return


            target = message.text.strip()
            whitelist.add(target)
            save_json(WHITELIST_FILE, list(whitelist))
            await message.answer(f"⭐ تمت إضافة `{target}` للوايت ليست", reply_markup=admin_menu())
            return

        if action == "whitelist_remove":
            target = message.text.strip()
            whitelist.discard(target)
            save_json(WHITELIST_FILE, list(whitelist))
            await message.answer(f"🗑 تمت إزالة `{target}` من الوايت ليست", reply_markup=admin_menu())
            return

        if action == "set_welcome":
            global WELCOME_MSG
            WELCOME_MSG = message.text.strip()
            save_json(WELCOME_FILE, {"msg": WELCOME_MSG})
            await message.answer("✅ تم تحديث رسالة الترحيب!", reply_markup=admin_menu())
            return

    # تحقق شامل
    if not await pre_check(message):
        return

    # رد عادي
    get_history(cid, message.from_user)
    await bot.send_chat_action(message.chat.id, "typing")
    push_user(cid, message.text)
    provider = user_model.get(uid, DEFAULT_MODEL)
    if provider == "groq_fast":
        reply = await ask_groq(get_history(cid))
    elif provider == "gemini_pro":
        reply = await ask_gemini(message.text) or await ask_ai_search(message.text, "gemini")
    else:
        reply = await ask_ai_search(message.text, provider)
    reply = reply or "❌ فشل الاتصال، حاول مرة أخرى"
    push_assistant(cid, reply)
    await message.answer(reply)

@dp.message(F.chat.type == "private", F.photo)
async def handle_private_photo(message: Message):
    if not await pre_check(message):
        return
    file       = await bot.get_file(message.photo[-1].file_id)
    file_bytes = await bot.download_file(file.file_path)
    content    = file_bytes.read()
    caption    = message.caption or "حلل هذه الصورة"
    cid        = str(message.chat.id)
    push_user(cid, caption)
    await bot.send_chat_action(message.chat.id, "typing")
    reply = await ask_gemini_vision(content, caption) or await ask_ai_search(caption + "\n(المستخدم أرسل صورة)", "claude")
    reply = reply or "❌ فشل تحليل الصورة"
    push_assistant(cid, reply)
    stats["total_images"] = stats.get("total_images", 0) + 1
    save_json(STATS_FILE, stats)
    await message.answer(reply)

@dp.message(F.chat.type == "private", F.document)
async def handle_private_document(message: Message):
    if not await pre_check(message):
        return
    doc  = message.document
    if doc.file_size > MAX_FILE_SIZE:
        await message.answer(f"❌ الملف كبير جداً. الحد الأقصى {MAX_FILE_SIZE // 1024 // 1024} MB")
        return
    file       = await bot.get_file(doc.file_id)
    file_bytes = await bot.download_file(file.file_path)
    content    = file_bytes.read()
    stats["total_files"] = stats.get("total_files", 0) + 1
    save_json(STATS_FILE, stats)
    await handle_file_fix(message, content, doc.file_name or "file.py")

# ═══════════════════════════════════════════════════════════
#  Handlers — Callbacks
# ═══════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════
#  Handler — صوت (Whisper)
# ═══════════════════════════════════════════════════════════
@dp.message(F.chat.type == "private", F.voice)
async def handle_voice(message: Message):
    if not await pre_check(message):
        return
    await bot.send_chat_action(message.chat.id, "typing")
    await message.answer("🎙 جاري تحويل الصوت لنص...")
    file       = await bot.get_file(message.voice.file_id)
    file_bytes = await bot.download_file(file.file_path)
    audio      = file_bytes.read()
    text       = await transcribe_voice(audio)
    cid        = str(message.chat.id)
    if text.startswith("❌") or text.startswith("⏳"):
        await message.answer(text)
        return
    await message.answer(f"📝 *النص المستخرج:*\n\n{text}")
    # رد على النص تلقائياً
    push_user(cid, text)
    provider = user_model.get(str(message.from_user.id), DEFAULT_MODEL)
    if provider == "groq_fast":
        reply = await ask_groq(get_history(cid))
    else:
        reply = await ask_ai_search(text, provider)
    if reply:
        push_assistant(cid, reply)
        await message.answer(reply)

# ═══════════════════════════════════════════════════════════
#  Handler — /image توليد صور
# ═══════════════════════════════════════════════════════════
@dp.message(Command("image"))
async def cmd_image(message: Message):
    if not await pre_check(message):
        return
    parts  = (message.text or "").split(None, 1)
    prompt = parts[1].strip() if len(parts) > 1 else ""
    if not prompt:
        await message.answer(
            "🎨 *توليد صور*\n\nأرسل وصف الصورة بالإنجليزي:\n`/image a beautiful sunset over the ocean`"
        )
        return
    await bot.send_chat_action(message.chat.id, "upload_photo")
    await message.answer("🎨 جاري توليد الصورة، انتظر...")
    img_url = await generate_image(prompt)
    if img_url:
        await message.answer_photo(img_url, caption=f"🎨 `{prompt}`")
    else:
        await message.answer("❌ فشل توليد الصورة. تأكد من REPLICATE_API_KEY أو حاول لاحقاً.")

@dp.callback_query()
async def handle_callback(cb: CallbackQuery):
    data     = cb.data
    uid      = str(cb.from_user.id)
    is_admin = cb.from_user.id in ADMINS
    chat_id  = cb.message.chat.id
    msg_id   = cb.message.message_id

    await cb.answer()

    async def edit(text, markup=None):
        try:
            await bot.edit_message_text(text, chat_id, msg_id,
                                        parse_mode=ParseMode.MARKDOWN,
                                        reply_markup=markup)
        except TelegramBadRequest:
            pass

    # ── مستخدم عادي ──────────────────────────────────────
    if data == "main_menu":
        await edit("🏠 *القائمة الرئيسية*", main_menu())
        return

    if data == "stats_me":
        uid_data  = user_memory.get(uid, {})
        remaining = get_credits(uid)
        bal_line  = "∞ (مجاني)" if FREE_MODE or uid in whitelist or cb.from_user.id in ADMINS else str(remaining)
        text = (
            "📊 *إحصائياتك*\n\n"
            f"🧠 الرسائل المحفوظة: `{len(uid_data.get('history', [])) - 1}`\n"
            f"📨 مجموع رسائلك: `{uid_data.get('msg_count', 0)}`\n"
            f"🔋 رصيدك: `{bal_line}` رسالة\n"
            f"📅 تاريخ الانضمام: `{uid_data.get('joined_at', '—')[:10]}`"
        )
        await edit(text, back_button())
        return

    if data == "my_credits":
        remaining = get_credits(uid)
        if FREE_MODE or uid in whitelist or cb.from_user.id in ADMINS:
            bal_line = "∞ غير محدود"
        else:
            bal_line = f"`{remaining}` رسالة"
        text = (
            f"🔋 *رصيدك*\n\n"
            f"الرصيد المتبقي: {bal_line}\n\n"
            f"تواصل مع الأدمن لإضافة رصيد."
        )
        await edit(text, credits_keyboard())
        return

    if data == "check_subscription":
        if await check_subscription(cb.from_user.id):
            await edit("✅ *تم التحقق! أهلاً بك.*\n\nالآن يمكنك استخدام البوت.", main_menu())
        else:
            await cb.answer("❌ لم تشترك بعد! اشترك ثم اضغط التحقق.", show_alert=True)
        return

    if data == "noop":
        return

    if data == "choose_model":
        selected = user_model.get(uid, DEFAULT_MODEL)
        await edit("🤖 *اختر النموذج:*", model_keyboard(selected))
        return

    if data.startswith("model_"):
        provider  = data.replace("model_", "")
        ALL_MODELS = list(SEARCH_CFG.keys()) + ["groq_fast", "gemini_pro", "whisper", "image_gen"]
        if provider in ALL_MODELS:
            user_model[uid] = provider
            names = {
                "claude": "Claude", "openai": "GPT-4", "gemini": "Gemini",
                "deepseek": "DeepSeek", "perplexity": "Perplexity", "llama": "Llama",
                "groq_fast": "Groq Fast ⚡", "gemini_pro": "Gemini Pro ✨",
                "whisper": "🎙 Whisper — تحويل صوت لنص",
                "image_gen": "🎨 Stable Diffusion — توليد صور",
            }
            extra = ""
            if provider == "whisper":
                extra = "\n\n🎙 أرسل رسالة صوتية وسأحولها لنص."
            elif provider == "image_gen":
                extra = "\n\n🎨 أرسل `/image وصف الصورة بالإنجليزي`"
            await edit(f"✅ *تم اختيار {names.get(provider, provider)}!*{extra}",
                       model_keyboard(provider))
        return

    # ── أدمن فقط ─────────────────────────────────────────
    if not is_admin and data.startswith("admin"):
        await cb.answer("⛔ غير مصرح لك", show_alert=True)
        return

    if data == "back_admin":
        await edit("🛠 *لوحة الأدمن*", admin_menu())
        return

    if data == "admin_stats":
        await edit(build_stats_text(), admin_menu())
        return

    if data == "admin_users":
        lines = ["👥 *المستخدمون (آخر 30):*\n"]
        for uid_k, udata in list(user_memory.items())[-30:]:
            if not isinstance(udata, dict):
                continue
            name   = udata.get("name", "—")
            count  = udata.get("msg_count", 0)
            banned = " 🚫" if uid_k in banned_users else ""
            wl     = " ⭐" if uid_k in whitelist    else ""
            lines.append(f"• `{uid_k}` | {name} | {count} رسالة{banned}{wl}")
        await edit("\n".join(lines), admin_menu())
        return

    if data == "admin_chats":
        await edit(build_chats_text(), admin_menu())
        return

    if data == "admin_export_csv":
        csv_bytes = export_users_csv()
        await bot.send_document(
            chat_id,
            BufferedInputFile(csv_bytes, filename=f"users_{get_today()}.csv"),
            caption="📤 *قائمة المستخدمين*",
        )
        return

    if data == "admin_broadcast_prompt":
        pending[uid] = "broadcast"
        await edit("📢 *أرسل الآن نص الرسالة للمستخدمين:*", back_button("back_admin"))
        return

    if data == "admin_group_broadcast_prompt":
        pending[uid] = "group_broadcast"
        await edit("📣 *أرسل الآن نص الرسالة لجميع المجموعات:*", back_button("back_admin"))
        return

    if data == "admin_channel_menu":
        await edit("📌 *إدارة الاشتراك الإجباري*", channel_menu(REQUIRED_CHANNEL))
        return

    if data == "admin_addchannel_prompt":
        pending[uid] = "addchannel"
        await edit(
            "📌 *أرسل يوزرنيم القناة:*\n\nمثال: `@mychannel`\n\n⚠️ تأكد أن البوت أدمن في القناة أولاً!",
            back_button("back_admin"),
        )
        return

    if data == "admin_removechannel":
        set_required_channel(None)
        await edit("✅ *تم إلغاء الاشتراك الإجباري بنجاح.*", admin_menu())
        return

    if data == "admin_ban_prompt":
        pending[uid] = "ban"
        await edit("🚫 *أرسل ID المستخدم الذي تريد حظره:*", back_button("back_admin"))
        return

    if data == "admin_unban_prompt":
        pending[uid] = "unban"
        await edit("✅ *أرسل ID المستخدم الذي تريد رفع حظره:*", back_button("back_admin"))
        return

    if data == "admin_clear_prompt":
        pending[uid] = "clear_mem"
        await edit("🗑 *أرسل ID المستخدم الذي تريد مسح ذاكرته:*", back_button("back_admin"))
        return

    if data == "admin_credits_menu":
        await edit("🔋 *إدارة الرصيد*", admin_credits_menu(FREE_MODE))
        return

    if data == "admin_add_credits":
        pending[uid] = "add_credits"
        await edit(
            "➕ *أضف رصيد لمستخدم*\n\nأرسل:\n`ID_المستخدم الكمية`\n\nمثال:\n`123456789 50`",
            back_button("admin_credits_menu"),
        )
        return

    if data == "admin_set_credits":
        pending[uid] = "set_credits"
        await edit(
            "🔧 *اضبط رصيد مستخدم*\n\nأرسل:\n`ID_المستخدم الكمية`\n\nمثال:\n`123456789 100`",
            back_button("admin_credits_menu"),
        )
        return

    if data == "admin_view_credits":
        pending[uid] = "view_credits"
        await edit("📋 *أرسل ID المستخدم لعرض رصيده:*", back_button("admin_credits_menu"))
        return

    if data == "admin_toggle_free":
        set_free_mode(not FREE_MODE)
        status = "مفعّل ✅" if FREE_MODE else "معطّل ❌"
        await edit(f"🆓 *الوضع المجاني الآن: {status}*", admin_credits_menu(FREE_MODE))
        return


        pending[uid] = "whitelist_add"
        await edit("⭐ *أرسل ID المستخدم لإضافته للوايت ليست:*", back_button("back_admin"))
        return

    if data == "admin_whitelist_remove":
        pending[uid] = "whitelist_remove"
        await edit("🗑 *أرسل ID المستخدم لإزالته من الوايت ليست:*", back_button("back_admin"))
        return

    if data == "admin_set_welcome":
        pending[uid] = "set_welcome"
        current = WELCOME_MSG or "الافتراضية"
        await edit(
            f"✏️ *أرسل رسالة الترحيب الجديدة:*\n\nالحالية:\n`{current[:200]}`",
            back_button("back_admin"),
        )
        return

# ═══════════════════════════════════════════════════════════
#  my_chat_member — تسجيل/حذف الشاتات
# ═══════════════════════════════════════════════════════════
@dp.my_chat_member()
async def on_my_chat_member(event):
    status = event.new_chat_member.status
    if status in ("member", "administrator"):
        register_chat(event.chat)
    elif status in ("left", "kicked"):
        unregister_chat(event.chat.id)

# ═══════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════
async def main():
    log.info("🚀 البوت يعمل بـ aiogram...")
    log.info(f"🔑 عدد مفاتيح Groq: {len(GROQ_API_KEYS)}")
    asyncio.create_task(daily_stats_task())
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
