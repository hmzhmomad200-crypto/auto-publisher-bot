import os
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

BOT_USERNAME = os.getenv("BOT_USERNAME", "your_bot")
WEBAPP_URL   = os.getenv("WEBAPP_URL", "https://yourdomain.com/index.html")

# ═══════════════════════════════════════
#  نظام الألوان (إيموجيات بديل بصري)
# ═══════════════════════════════════════
_COLOR_PREFIX = {
    'red'  : '🔴',
    'green': '🟢',
    'blue' : '🔵',
}

def btn(text, cbd=None, url=None, color=None):
    """
    ينشئ زر inline.
    color: 'red' | 'green' | 'blue'  — يضيف إيموجي لوني قبل النص
    """
    if color and color in _COLOR_PREFIX:
        text = f"{_COLOR_PREFIX[color]} {text}"
    if cbd:
        return InlineKeyboardButton(text=text, callback_data=cbd)
    if url:
        return InlineKeyboardButton(text=text, url=url)
    return InlineKeyboardButton(text=text, callback_data="noop")

def kb(*rows):
    """
    ينشئ InlineKeyboardMarkup من صفوف.
    كل عنصر إما زر واحد أو list من الأزرار.
    مثال:
        kb(
            btn("زر 1", cbd="a"),
            [btn("زر 2", cbd="b"), btn("زر 3", cbd="c")],
        )
    """
    keyboard = []
    for row in rows:
        if isinstance(row, list):
            keyboard.append(row)
        else:
            keyboard.append([row])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# ═══════════════════════════════════════
#  القوائم
# ═══════════════════════════════════════

def webapp_btn(text, url=None):
    """زر يفتح Mini App"""
    _url = url or WEBAPP_URL
    return InlineKeyboardButton(text=text, web_app=WebAppInfo(url=_url))

def main_menu():
    return kb(
        webapp_btn("🚀 فتح القائمة الرئيسية"),
        btn("🤖 اختر النموذج",   cbd="choose_model"),
        btn("📊 إحصائياتي",      cbd="stats_me"),
        btn("💬 رصيدي",          cbd="my_credits"),
        btn("➕ أضفني للمجموعة", url=f"https://t.me/{BOT_USERNAME}?startgroup=start"),
    )

def back_button(target="main_menu"):
    return kb(
        btn("🔙 رجوع", cbd=target, color='red'),
    )

def model_keyboard(selected=None):
    models = [
        ("Claude — 💬 شات",                         "claude"),
        ("GPT-4 — 💬 شات",                          "openai"),
        ("Gemini — 💬 شات",                         "gemini"),
        ("DeepSeek — 💬 شات",                       "deepseek"),
        ("Perplexity — 💬 شات + 🔍 بحث",            "perplexity"),
        ("Llama — 💬 شات",                          "llama"),
        ("Groq — 💬 شات ⚡ سريع",                   "groq_fast"),
        ("Gemini Pro — 💬 شات + 📷 صور + 📂 ملفات", "gemini_pro"),
    ]
    rows = []
    for label, key in models:
        tick = " ✅" if key == selected else ""
        rows.append(btn(f"{label}{tick}", cbd=f"model_{key}"))
    rows.append(btn("🔙 رجوع", cbd="main_menu", color='red'))
    return kb(*rows)

def admin_menu():
    return kb(
        btn("📊 إحصائيات كاملة",         cbd="admin_stats"),
        btn("👥 قائمة المستخدمين",        cbd="admin_users"),
        btn("🏘 الجروبات والقنوات",        cbd="admin_chats"),
        btn("📢 بث رسالة للمستخدمين",     cbd="admin_broadcast_prompt"),
        btn("📣 بث لجميع المجموعات",      cbd="admin_group_broadcast_prompt"),
        btn("📌 إدارة الاشتراك الإجباري", cbd="admin_channel_menu"),
        btn("🔋 إدارة الرصيد",            cbd="admin_credits_menu", color='blue'),
        btn("🚫 حظر مستخدم",              cbd="admin_ban_prompt"),
        btn("✅ رفع حظر مستخدم",          cbd="admin_unban_prompt"),
        btn("🗑 مسح ذاكرة مستخدم",        cbd="admin_clear_prompt"),
        btn("📤 تصدير المستخدمين CSV",    cbd="admin_export_csv"),
        btn("🔙 رجوع",                    cbd="main_menu", color='red'),
    )

def channel_menu(current_channel=None):
    ch_text = f"القناة: {current_channel}" if current_channel else "لا توجد قناة مفعّلة"
    return kb(
        btn(f"📌 {ch_text}",              cbd="noop"),
        btn("➕ إضافة / تغيير القناة",   cbd="admin_addchannel_prompt", color='green'),
        btn("🗑 إلغاء الاشتراك الإجباري", cbd="admin_removechannel",    color='red'),
        btn("🔙 رجوع للوحة الأدمن",      cbd="back_admin",             color='red'),
    )

def subscription_required_keyboard(channel_username):
    return kb(
        btn("📢 اشترك في القناة", url=f"https://t.me/{channel_username.lstrip('@')}",  color='blue'),
        btn("✅ تحققت من الاشتراك", cbd="check_subscription", color='green'),
    )

def credits_keyboard():
    return kb(
        btn("📊 رصيدي الحالي", cbd="my_credits"),
        btn("🔙 رجوع",         cbd="main_menu", color='red'),
    )

def admin_credits_menu(free_mode=False):
    free_label = "🆓 إيقاف المجاني ✅" if free_mode else "🆓 تفعيل مجاني للكل"
    free_color = "red" if free_mode else "green"
    return kb(
        btn("➕ أضف رصيد لمستخدم",      cbd="admin_add_credits",    color='green'),
        btn("🔧 اضبط رصيد مستخدم",      cbd="admin_set_credits",    color='blue'),
        btn("📋 عرض رصيد مستخدم",       cbd="admin_view_credits"),
        btn("♾ أضف للوايت ليست",        cbd="admin_whitelist_add",  color='green'),
        btn("🗑 أزل من الوايت ليست",     cbd="admin_whitelist_remove",color='red'),
        btn(free_label,                  cbd="admin_toggle_free",    color=free_color),
        btn("🔙 رجوع للوحة الأدمن",     cbd="back_admin",           color='red'),
    )

def confirm_keyboard(action, cancel="main_menu"):
    return kb(
        [
            btn("✅ تأكيد", cbd=action,  color='green'),
            btn("❌ إلغاء", cbd=cancel,  color='red'),
        ]
    )

def daily_limit_keyboard(channel_username=None):
    """يظهر عند انتهاء الرصيد اليومي"""
    rows = []
    if channel_username:
        rows.append(btn("📢 اشترك للحصول على رصيد إضافي",
                        url=f"https://t.me/{channel_username.lstrip('@')}", color='blue'))
    rows.append(btn("📊 رصيدي", cbd="my_credits"))
    rows.append(btn("🔙 رجوع",  cbd="main_menu", color='red'))
    return kb(*rows)
