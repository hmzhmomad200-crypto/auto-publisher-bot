# keyboards.py

def main_menu():
    return {
        "inline_keyboard": [
            [
                {"text": "➕ أضفني لمجموعاتك", "url": "https://t.me/BOT_USERNAME?startgroup=true"},
                {"text": "💬 اسألني",          "callback_data": "ask_me"}
            ]
        ]
    }


def back_button():
    return {
        "inline_keyboard": [
            [{"text": "🔙 رجوع للقائمة", "callback_data": "main_menu"}]
        ]
    }


def admin_menu():
    return {
        "inline_keyboard": [
            [{"text": "📊 إحصائيات كاملة",              "callback_data": "admin_stats"}],
            [{"text": "👥 قائمة المستخدمين",             "callback_data": "admin_users"}],
            [{"text": "🏘 الجروبات والقنوات",             "callback_data": "admin_chats"}],
            [{"text": "📢 بث رسالة للمستخدمين",          "callback_data": "admin_broadcast_prompt"}],
            [{"text": "📣 بث لجميع المجموعات",           "callback_data": "admin_group_broadcast_prompt"}],
            [{"text": "🔒 إدارة الاشتراك الإجباري",      "callback_data": "admin_force_sub_menu"}],
            [{"text": "🚫 حظر مستخدم",                   "callback_data": "admin_ban_prompt"}],
            [{"text": "✅ رفع حظر مستخدم",               "callback_data": "admin_unban_prompt"}],
            [{"text": "🗑 مسح ذاكرة مستخدم",             "callback_data": "admin_clear_prompt"}],
        ]
    }


def force_sub_menu(channels):
    """channels: list of @username strings"""
    kb = []
    for ch in channels:
        kb.append([
            {"text": f"❌ حذف {ch}", "callback_data": f"admin_force_sub_del|{ch}"}
        ])
    kb.append([{"text": "➕ إضافة قناة",  "callback_data": "admin_force_sub_add"}])
    kb.append([{"text": "🔙 رجوع",        "callback_data": "admin_panel"}])
    return {"inline_keyboard": kb}


def not_subscribed_kb(channels):
    """أزرار الاشتراك للمستخدم غير المشترك"""
    kb = []
    for ch in channels:
        username = ch.lstrip("@")
        kb.append([{"text": f"📢 اشترك في {ch}", "url": f"https://t.me/{username}"}])
    kb.append([{"text": "✅ اشتركت، تحقق الآن", "callback_data": "check_sub"}])
    return {"inline_keyboard": kb}
