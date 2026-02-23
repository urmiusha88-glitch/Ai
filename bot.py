import logging
import psycopg2
import random
import string
import psutil
import platform
import urllib.parse
import httpx
import re
from datetime import date, datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

# ======================================================
# 👇 CONFIGURATION
# ======================================================
TOKEN = "8290942305:AAGFtnKV8P5xk591NejJ5hsKEJ02foiRpEk"
ADMIN_ID = 6198703244  
ADMIN_USERNAME = "@yours_ononto"

DEEPSEEK_API_KEY = "sk-5da4d6648bbe48158c9dd2ba656ac26d"
DATABASE_URL = "postgresql://postgres:hQKBupovepWPRJyTUCiqYrUfEnoeRYYv@trolley.proxy.rlwy.net:36125/railway"

BKASH_NUMBER = "01846849460"    
NAGAD_NUMBER = "01846849460"    
ADMIN_LOG_ID = -1003769033152
PUBLIC_LOG_ID = -1003775622081
CHANNEL_ID = "@minatologs"
CHANNEL_INVITE_LINK = "https://t.me/minatologs/2"

PLAN_DAYS = {"BRONZE": 3, "SILVER": 5, "GOLD": 7, "PLATINUM": 15, "DIAMOND": 30}

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- DATABASE ENGINE ---
def get_db_conn():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_db_conn()
    c = conn.cursor()
    # ১. টেবিল তৈরি ও কলাম ফিক্স
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id BIGINT PRIMARY KEY, credits INTEGER DEFAULT 0, role TEXT DEFAULT 'Free', 
                  generated_count INTEGER DEFAULT 0, full_name TEXT, expiry_date DATE DEFAULT CURRENT_DATE)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS codes 
                 (code TEXT PRIMARY KEY, credit_amount INTEGER, role_reward TEXT, is_redeemed INTEGER DEFAULT 0)''')
    
    # ২. গুরুত্বপূর্ণ: NULL ভ্যালু থাকলে সেগুলোকে ০ করে দেওয়া (যাতে রিডিম ফিক্স হয়)
    c.execute("UPDATE codes SET is_redeemed = 0 WHERE is_redeemed IS NULL")
    
    try:
        c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS generated_count INTEGER DEFAULT 0")
        c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS expiry_date DATE DEFAULT CURRENT_DATE")
    except: pass
    
    conn.commit()
    conn.close()
    print("✅ Database Fixed & Synchronized!")

init_db()

# --- USER HELPER ---
def get_user(user_id, name="User"):
    conn = get_db_conn()
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
async def ask_ai(prompt):
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    data = {"model": "deepseek-chat", "messages": [{"role": "system", "content": "Helpful AI"}, {"role": "user", "content": prompt}]}
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post("https://api.deepseek.com/chat/completions", json=data, headers=headers, timeout=60)
            return r.json()['choices'][0]['message']['content']
        except: return "❌ Server Busy."

# --- START UI ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await check_join(user.id, context):
        await update.message.reply_text("❌ Join @minatologs First!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Join", url=CHANNEL_INVITE_LINK)]]))
        return

    try:
        u = get_user(user.id, user.first_name)
        expiry = u[5]
        status = f"✅ Premium ({u[2]})" if expiry > date.today() else "🆓 Free"
        
        text = (
            f"🤖 **𝐌𝐈𝐍𝐀𝐓𝐎 𝐀𝐈 𝐀𝐒𝐒𝐈𝐒𝐓𝐀𝐍𝐓**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 **User:** `{u[4]}`\n"
            f"💎 **Coins:** `{u[1]}`\n"
            f"👑 **Rank:** `{status}`\n"
            f"📅 **Expiry:** `{expiry}`\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        kb = [
            [InlineKeyboardButton("🧠 AI Menu", callback_data='ai_menu')],
            [InlineKeyboardButton("💰 Buy Credits", callback_data='deposit'), InlineKeyboardButton("🎫 Redeem", callback_data='redeem_ui')]
        ]
        if update.message: await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        else: await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    except Exception as e:
        print(f"Start Error: {e}")

# --- AI COMMANDS ---
async def ai_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cmd = update.message.text.split()[0].replace('/', '')
    prompt = " ".join(context.args)
    if not prompt: return await update.message.reply_text(f"Usage: `/{cmd} your prompt`")

    u = get_user(update.effective_user.id)
    cost = 20 if cmd == 'image' else 5
    if u[1] < cost: return await update.message.reply_text("❌ No Credits!")

    m = await update.message.reply_text("⏳ Thinking...")
    if cmd == 'image':
        url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}"
        await update.message.reply_photo(url, caption="🎨 **Enjoy our AI!**", parse_mode='Markdown')
        await m.delete()
    else:
        res = await ask_ai(prompt)
        await m.edit_text(f"{res}\n\n⚡ **Enjoy our AI!**", parse_mode='Markdown')
    
    conn = get_db_conn(); c = conn.cursor()
    c.execute("UPDATE users SET credits=credits-%s WHERE user_id=%s", (cost, u[0]))
    conn.commit(); conn.close()

# --- ADMIN STATS ---
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    cpu, ram = psutil.cpu_percent(), psutil.virtual_memory().percent
    await update.message.reply_text(f"🖥 **SERVER STATS**\nCPU: {cpu}% | RAM: {ram}%")

# --- GEN & REDEEM FIX ---
async def gencoins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        amt, plan = int(context.args[0]), context.args[1].upper()
        code = f"CODE-{''.join(random.choices(string.ascii_uppercase + string.digits, k=10))}"
        conn = get_db_conn(); c = conn.cursor()
        c.execute("INSERT INTO codes (code, credit_amount, role_reward, is_redeemed) VALUES (%s, %s, %s, 0)", (code, amt, plan))
        conn.commit(); conn.close()
        await update.message.reply_text(f"🎫 **New Code:** `{code}`\nPlan: {plan}\nCoins: {amt}\n\n💡 Reply with /redeem to activate!", parse_mode='Markdown')
    except: await update.message.reply_text("❌ Usage: `/gencoins 500 GOLD`")

async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code_text = None
    if update.message.reply_to_message:
        match = re.search(r'CODE-[A-Z0-9]+', update.message.reply_to_message.text)
        if match: code_text = match.group(0)
    elif context.args:
        code_text = context.args[0].strip()

    if not code_text: return await update.message.reply_text("❌ Reply to a code message with /redeem")

    conn = get_db_conn(); c = conn.cursor()
    # COALESCE ব্যবহার করা হয়েছে যাতে NULL থাকলেও সেটা ০ হিসেবে গণ্য হয়
    c.execute("SELECT credit_amount, role_reward FROM codes WHERE code=%s AND COALESCE(is_redeemed, 0) = 0", (code_text,))
    res = c.fetchone()
    
    if res:
        amt, plan = res[0], res[1]
        new_expiry = date.today() + timedelta(days=PLAN_DAYS.get(plan, 1))
        c.execute("UPDATE codes SET is_redeemed = 1 WHERE code=%s", (code_text,))
        c.execute("UPDATE users SET credits=credits+%s, role=%s, expiry_date=%s WHERE user_id=%s", (amt, plan, new_expiry, update.effective_user.id))
        conn.commit()
        await update.message.reply_text(f"🎉 **Redeem Successful!**\n💎 {amt} Coins Added.\n👑 Rank: {plan}\n\n⚡ **Enjoy our AI!**", parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ Invalid or Already Redeemed.")
    conn.close()

# --- CALLBACKS ---
async def handle_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.data == 'main_menu': await start(update, context)
    elif q.data == 'ai_menu':
        await q.message.edit_text("💡 **AI Commands:**\n/chat, /image, /script, /code", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='main_menu')]]))
    elif q.data == 'deposit':
        await q.message.edit_text(f"💳 **Payment:**\nBkash/Nagad: `{BKASH_NUMBER}`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='main_menu')]]))

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler(["chat", "image", "script", "code"], ai_handler))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("gencoins", gencoins))
    app.add_handler(CommandHandler("redeem", redeem))
    app.add_handler(CallbackQueryHandler(handle_cb))
    print("🤖 Bot is fixed and running!")
    app.run_polling()

if __name__ == '__main__':
    main()
