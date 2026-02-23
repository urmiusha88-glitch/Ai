import logging
import psycopg2
import random
import string
import psutil
import platform
from datetime import date, datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

# ======================================================
# 👇 CONFIGURATION
# ======================================================
TOKEN = "8290942305:AAGFtnKV8P5xk591NejJ5hsKEJ02foiRpEk"
ADMIN_ID = 6198703244  
ADMIN_USERNAME = "@yours_ononto"

DATABASE_URL = "postgresql://postgres:hQKBupovepWPRJyTUCiqYrUfEnoeRYYv@trolley.proxy.rlwy.net:36125/railway"

# Membership Durations (Days)
PLAN_DAYS = {
    "BRONZE": 3,
    "SILVER": 5,
    "GOLD": 7,
    "PLATINUM": 15,
    "DIAMOND": 30
}

# ======================================================

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    # Updated table with expiry date
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id BIGINT PRIMARY KEY, credits INTEGER, role TEXT, 
                  generated_count INTEGER DEFAULT 0, full_name TEXT, 
                  expiry_date DATE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS codes 
                 (code TEXT PRIMARY KEY, credit_amount INTEGER, role_reward TEXT, is_redeemed INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

init_db()

# --- HELPERS ---
def is_admin(user_id):
    return user_id == ADMIN_ID

def get_user(user_id, name="User"):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
    user = c.fetchone()
    if not user:
        c.execute("INSERT INTO users (user_id, credits, role, generated_count, full_name, expiry_date) VALUES (%s, 50, 'Free', 0, %s, %s)", 
                  (user_id, name, date.today()))
        conn.commit()
        user = (user_id, 50, 'Free', 0, name, date.today())
    conn.close()
    return user

# --- STATUS COMMAND (USER) ---
async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u = get_user(user.id, user.first_name)
    
    # u[5] is expiry_date
    expiry = u[5]
    today = date.today()
    
    if expiry < today:
        membership_status = "❌ Expired / No Membership"
        remaining_days = 0
    else:
        membership_status = f"✅ Premium ({u[2]})"
        remaining_days = (expiry - today).days

    text = (
        f"📊 **𝐘𝐎𝐔𝐑 𝐒𝐓𝐀𝐓𝐔𝐒**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 **Name:** `{u[4]}`\n"
        f"💰 **Coins:** `{u[1]}`\n"
        f"👑 **Membership:** `{membership_status}`\n"
        f"📅 **Expiry Date:** `{expiry}`\n"
        f"⏳ **Remaining:** `{remaining_days} Days`\n"
        f"━━━━━━━━━━━━━━━━━━"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

# --- STATS COMMAND (ADMIN ONLY) ---
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    
    # Host Performance
    cpu_usage = psutil.cpu_percent()
    ram = psutil.virtual_memory()
    
    # DB Stats
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT SUM(generated_count) FROM users")
    total_requests = c.fetchone()[0]
    conn.close()

    text = (
        f"🖥 **𝐒𝐄𝐑𝐕𝐄𝐑 & 𝐁𝐎𝐓 𝐒𝐓𝐀𝐓𝐒**\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 **Total Users:** `{total_users}`\n"
        f"🤖 **AI Requests:** `{total_requests}`\n\n"
        f"⚙️ **System Performance:**\n"
        f"├ **CPU Usage:** `{cpu_usage}%`\n"
        f"├ **RAM Usage:** `{ram.percent}%`\n"
        f"└ **OS:** `{platform.system()}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

# --- GENCOIN (ADMIN) ---
async def gencoins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try:
        amt = int(context.args[0])
        plan_type = context.args[1].upper()
        
        if plan_type not in PLAN_DAYS:
            return await update.message.reply_text(f"❌ Invalid Plan! Use: {list(PLAN_DAYS.keys())}")

        code = f"CODE-{''.join(random.choices(string.ascii_uppercase + string.digits, k=12))}"
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("INSERT INTO codes (code, credit_amount, role_reward) VALUES (%s, %s, %s)", (code, amt, plan_type))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(
            f"🎫 **𝐍𝐄𝐖 𝐂𝐎𝐃𝐄 𝐆𝐄𝐍𝐄𝐑𝐀𝐓𝐄𝐃**\n\n"
            f"🔑 **Code:** `{code}`\n"
            f"💰 **Coins:** `{amt}`\n"
            f"🏆 **Membership:** `{plan_type}`\n"
            f"⏳ **Validity:** `{PLAN_DAYS[plan_type]} Days`", 
            parse_mode='Markdown'
        )
    except:
        await update.message.reply_text("❌ Usage: `/gencoins 500 GOLD`")

# --- REDEEM (USER) ---
async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("❌ Usage: `/redeem CODE-XXXX`")
    code_text = context.args[0].strip()
    uid = update.effective_user.id
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT credit_amount, role_reward FROM codes WHERE code=%s AND is_redeemed=0", (code_text,))
    res = c.fetchone()
    
    if res:
        amt, plan_type = res[0], res[1]
        days_to_add = PLAN_DAYS.get(plan_type, 0)
        
        # Calculate New Expiry
        new_expiry = date.today() + timedelta(days=days_to_add)
        
        c.execute("UPDATE codes SET is_redeemed=1 WHERE code=%s", (code_text,))
        c.execute("UPDATE users SET credits=credits+%s, role=%s, expiry_date=%s WHERE user_id=%s", 
                  (amt, plan_type, new_expiry, uid))
        conn.commit()
        
        await update.message.reply_text(
            f"🎉 **𝐑𝐄𝐃𝐄𝐄𝐌 𝐒𝐔𝐂𝐂𝐄𝐒𝐒𝐅𝐔𝐋**\n\n"
            f"💎 **Added:** `{amt} Coins`\n"
            f"👑 **Rank:** `{plan_type} (Premium)`\n"
            f"📅 **New Expiry:** `{new_expiry}`",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ Invalid or used code.")
    conn.close()

# --- MAIN SETUP ---
def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", status_cmd)) # ইউজার স্টার্ট দিলেই স্ট্যাটাস দেখতে পাবে
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("gencoins", gencoins))
    app.add_handler(CommandHandler("redeem", redeem))
    
    print("Minato Professional Bot is Running...")
    app.run_polling()

if __name__ == '__main__':
    main()
