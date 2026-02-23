import logging
import psycopg2
import random
import string
import psutil
import platform
import urllib.parse
import httpx
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

PLAN_DAYS = {
    "BRONZE": 3, "SILVER": 5, "GOLD": 7, "PLATINUM": 15, "DIAMOND": 30
}

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- DB HELPERS ---
def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    # ১. ইউজার টেবিল চেক ও তৈরি
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id BIGINT PRIMARY KEY, credits INTEGER DEFAULT 0, role TEXT DEFAULT 'Free', 
                  generated_count INTEGER DEFAULT 0, full_name TEXT, 
                  expiry_date DATE DEFAULT CURRENT_DATE)''')
    
    # ২. কলাম মিসিং থাকলে তা অ্যাড করা (যাতে ওই এরর আর না আসে)
    try:
        c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS generated_count INTEGER DEFAULT 0")
        c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS expiry_date DATE DEFAULT CURRENT_DATE")
        c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name TEXT")
    except:
        pass # ইতিমধ্যে থাকলে এরর এড়িয়ে যাবে

    c.execute('''CREATE TABLE IF NOT EXISTS codes 
                 (code TEXT PRIMARY KEY, credit_amount INTEGER, role_reward TEXT, is_redeemed INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()
    print("✅ Database Tables Fixed & Synchronized!")

init_db()

# --- GET USER HELPER ---
def get_user(user_id, name="User"):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT user_id, credits, role, generated_count, full_name, expiry_date FROM users WHERE user_id=%s", (user_id,))
    user = c.fetchone()
    if not user:
        c.execute("INSERT INTO users (user_id, credits, role, generated_count, full_name, expiry_date) VALUES (%s, 50, 'Free', 0, %s, %s)", 
                  (user_id, name, date.today()))
        conn.commit()
        # রিটার্ন করার সময় ইনডেক্স ঠিক রাখা
        user = (user_id, 50, 'Free', 0, name, date.today())
    conn.close()
    return user

# --- STATUS COMMAND ---
async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u = get_user(user.id, user.first_name)
    
    # u[5] এখন expiry_date হিসেবে কাজ করবে
    expiry = u[5]
    today = date.today()
    
    if expiry <= today and u[2] != 'Free':
        status_text = "❌ Expired"
        days_left = 0
    else:
        status_text = f"✅ Premium ({u[2]})" if u[2] != 'Free' else "🆓 Free User"
        days_left = (expiry - today).days if expiry > today else 0

    text = (
        f"📊 **𝐘𝐎𝐔𝐑 𝐒𝐓𝐀𝐓𝐔𝐒**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 **Name:** `{u[4]}`\n"
        f"💰 **Coins:** `{u[1]}`\n"
        f"👑 **Rank:** `{status_text}`\n"
        f"📅 **Expiry:** `{expiry}`\n"
        f"⏳ **Left:** `{max(0, days_left)} Days`\n"
        f"━━━━━━━━━━━━━━━━━━"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

# --- ADMIN STATS ---
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_u = c.fetchone()[0]
    c.execute("SELECT SUM(generated_count) FROM users")
    total_req = c.fetchone()[0] or 0
    conn.close()

    text = (
        f"🖥 **𝐒𝐄𝐑𝐕𝐄𝐑 𝐒𝐓𝐀𝐓𝐒**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👥 Users: `{total_u}`\n"
        f"🚀 Total Req: `{total_req}`\n"
        f"🔥 CPU: `{cpu}%` | RAM: `{ram}%`"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

# --- GENCOIN (ADMIN) ---
async def gencoins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        amt = int(context.args[0])
        plan = context.args[1].upper()
        if plan not in PLAN_DAYS: return await update.message.reply_text("Plan: BRONZE, SILVER, GOLD, PLATINUM, DIAMOND")

        code = f"CODE-{''.join(random.choices(string.ascii_uppercase + string.digits, k=10))}-{plan}"
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("INSERT INTO codes (code, credit_amount, role_reward) VALUES (%s, %s, %s)", (code, amt, plan))
        conn.commit(); conn.close()
        await update.message.reply_text(f"✅ Code: `{code}`\nCoins: {amt}\nPlan: {plan}")
    except:
        await update.message.reply_text("Usage: `/gencoins 500 GOLD`")

# --- REDEEM ---
async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return
    code_text = context.args[0].strip()
    conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT credit_amount, role_reward FROM codes WHERE code=%s AND is_redeemed=0", (code_text,))
    res = c.fetchone()
    
    if res:
        amt, plan = res[0], res[1]
        new_expiry = date.today() + timedelta(days=PLAN_DAYS[plan])
        c.execute("UPDATE codes SET is_redeemed=1 WHERE code=%s", (code_text,))
        c.execute("UPDATE users SET credits=credits+%s, role=%s, expiry_date=%s WHERE user_id=%s", (amt, plan, new_expiry, update.effective_user.id))
        conn.commit()
        await update.message.reply_text(f"🎉 Redeemed! {amt} coins & {plan} membership added.")
    else:
        await update.message.reply_text("❌ Invalid Code.")
    conn.close()

# --- MAIN ---
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", status_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("gencoins", gencoins))
    app.add_handler(CommandHandler("redeem", redeem))
    app.run_polling()

if __name__ == '__main__':
    main()
