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
# 👇 CONFIGURATION (সব ডিটেইলস এখানে)
# ======================================================
TOKEN = "8290942305:AAGFtnKV8P5xk591NejJ5hsKEJ02foiRpEk"
ADMIN_ID = 6198703244  
ADMIN_USERNAME = "@yours_ononto"

# 🤖 API KEYS
DEEPSEEK_API_KEY = "sk-5da4d6648bbe48158c9dd2ba656ac26d"

# 💰 PAYMENT & CHANNELS
BKASH_NUMBER = "01846849460"    
NAGAD_NUMBER = "01846849460"    
DATABASE_URL = "postgresql://postgres:hQKBupovepWPRJyTUCiqYrUfEnoeRYYv@trolley.proxy.rlwy.net:36125/railway"
ADMIN_LOG_ID = -1003769033152
PUBLIC_LOG_ID = -1003775622081
CHANNEL_ID = "@minatologs"
CHANNEL_INVITE_LINK = "https://t.me/minatologs/2"

# Membership Durations
PLAN_DAYS = {"BRONZE": 3, "SILVER": 5, "GOLD": 7, "PLATINUM": 15, "DIAMOND": 30}

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- DATABASE INIT & FIX ---
def init_db():
    conn = psycopg2.connect(DATABASE_URL)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id BIGINT PRIMARY KEY, credits INTEGER DEFAULT 0, role TEXT DEFAULT 'Free', 
                  generated_count INTEGER DEFAULT 0, full_name TEXT, expiry_date DATE DEFAULT CURRENT_DATE)''')
    # Missing Column Fixer
    try:
        c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS generated_count INTEGER DEFAULT 0")
        c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS expiry_date DATE DEFAULT CURRENT_DATE")
        c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'Free'")
    except: pass
    c.execute('''CREATE TABLE IF NOT EXISTS codes 
                 (code TEXT PRIMARY KEY, credit_amount INTEGER, role_reward TEXT, is_redeemed INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

init_db()

# --- HELPERS ---
def get_user(user_id, name="User"):
    conn = psycopg2.connect(DATABASE_URL)
    c = conn.cursor()
    c.execute("SELECT user_id, credits, role, generated_count, full_name, expiry_date FROM users WHERE user_id=%s", (user_id,))
    user = c.fetchone()
    if not user:
        c.execute("INSERT INTO users (user_id, credits, role, generated_count, full_name, expiry_date) VALUES (%s, 50, 'Free', 0, %s, %s)", 
                  (user_id, name, date.today()))
        conn.commit()
        user = (user_id, 50, 'Free', 0, name, date.today())
    conn.close()
    return user

async def check_join(user_id, context):
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status not in ['left', 'kicked']
    except: return True

# --- AI API ---
async def ask_ai(prompt, system="You are a helpful AI."):
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    data = {"model": "deepseek-chat", "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post("https://api.deepseek.com/chat/completions", json=data, headers=headers, timeout=60)
            return r.json()['choices'][0]['message']['content']
        except: return "❌ AI Server Busy. Try again."

# --- MAIN START UI ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await check_join(user.id, context):
        await update.message.reply_text("❌ Join @minatologs First!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Join", url=CHANNEL_INVITE_LINK)]]))
        return

    u = get_user(user.id, user.first_name)
    expiry = u[5]
    status = f"✅ {u[2]}" if expiry > date.today() else "🆓 Free"
    
    text = (
        f"🤖 **𝐌𝐈𝐍𝐀𝐓𝐎 𝐀𝐈 𝐀𝐒𝐒𝐈𝐒𝐓𝐀𝐍𝐓**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 **User:** `{u[4]}`\n"
        f"💎 **Coins:** `{u[1]}`\n"
        f"👑 **Membership:** `{status}`\n"
        f"📅 **Expiry:** `{expiry}`\n"
        f"━━━━━━━━━━━━━━━━━━"
    )
    kb = [
        [InlineKeyboardButton("🧠 AI Menu", callback_data='ai_menu')],
        [InlineKeyboardButton("💰 Buy Credits", callback_data='deposit'), InlineKeyboardButton("🎁 Bonus", callback_data='bonus')],
        [InlineKeyboardButton("🎫 Redeem Code", callback_data='redeem_ui')],
        [InlineKeyboardButton("📞 Support", url=f"https://t.me/{ADMIN_USERNAME.replace('@','')}")]
    ]
    
    if update.message: await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    else: await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

# --- ADMIN STATS ---
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    cpu, ram = psutil.cpu_percent(), psutil.virtual_memory().percent
    conn = psycopg2.connect(DATABASE_URL); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users"); total_u = c.fetchone()[0]
    conn.close()
    await update.message.reply_text(f"🖥 **STATS**\nUsers: {total_u}\nCPU: {cpu}% | RAM: {ram}%")

# --- AI COMMANDS ---
async def chat_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    if u[1] < 5: return await update.message.reply_text("❌ Need 5 Coins!")
    prompt = " ".join(context.args)
    if not prompt: return await update.message.reply_text("Usage: /chat <msg>")
    m = await update.message.reply_text("⏳ Thinking...")
    res = await ask_ai(prompt)
    conn = psycopg2.connect(DATABASE_URL); c = conn.cursor()
    c.execute("UPDATE users SET credits=credits-5, generated_count=generated_count+1 WHERE user_id=%s", (u[0],))
    conn.commit(); conn.close()
    await m.edit_text(res)

async def image_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    if u[1] < 20: return await update.message.reply_text("❌ Need 20 Coins!")
    prompt = " ".join(context.args)
    if not prompt: return await update.message.reply_text("Usage: /image <prompt>")
    url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}"
    await update.message.reply_photo(url, caption=f"🎨 {prompt}")
    conn = psycopg2.connect(DATABASE_URL); c = conn.cursor()
    c.execute("UPDATE users SET credits=credits-20, generated_count=generated_count+1 WHERE user_id=%s", (u[0],))
    conn.commit(); conn.close()

# --- COIN GEN & REDEEM ---
async def gencoins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        amt, plan = int(context.args[0]), context.args[1].upper()
        code = f"CODE-{''.join(random.choices(string.ascii_uppercase + string.digits, k=10))}-{plan}"
        conn = psycopg2.connect(DATABASE_URL); c = conn.cursor()
        c.execute("INSERT INTO codes (code, credit_amount, role_reward) VALUES (%s, %s, %s)", (code, amt, plan))
        conn.commit(); conn.close()
        await update.message.reply_text(f"✅ Generated: `{code}`")
    except: await update.message.reply_text("Usage: /gencoins 500 GOLD")

async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return
    code = context.args[0].strip()
    conn = psycopg2.connect(DATABASE_URL); c = conn.cursor()
    c.execute("SELECT credit_amount, role_reward FROM codes WHERE code=%s AND is_redeemed=0", (code,))
    res = c.fetchone()
    if res:
        new_expiry = date.today() + timedelta(days=PLAN_DAYS.get(res[1], 1))
        c.execute("UPDATE codes SET is_redeemed=1 WHERE code=%s", (code,))
        c.execute("UPDATE users SET credits=credits+%s, role=%s, expiry_date=%s WHERE user_id=%s", (res[0], res[1], new_expiry, update.effective_user.id))
        conn.commit()
        await update.message.reply_text(f"🎉 Redeemed {res[0]} Coins & {res[1]} Rank!")
    else: await update.message.reply_text("❌ Invalid Code.")
    conn.close()

# --- CALLBACKS ---
async def handle_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.data == 'main_menu': await start(update, context)
    elif q.data == 'ai_menu':
        await q.message.edit_text("💡 **AI COMMANDS**\n\n/chat <msg>\n/image <prompt>\n/script <topic>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='main_menu')]]))
    elif q.data == 'deposit':
        await q.message.edit_text(f"💳 **PAYMENT**\n\nBkash/Nagad: `{BKASH_NUMBER}`\nSend SS & TrxID here.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='main_menu')]]))

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", start))
    app.add_handler(CommandHandler("chat", chat_cmd))
    app.add_handler(CommandHandler("image", image_cmd))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("gencoins", gencoins))
    app.add_handler(CommandHandler("redeem", redeem))
    app.add_handler(CallbackQueryHandler(handle_cb))
    app.run_polling()

if __name__ == '__main__':
    main()
