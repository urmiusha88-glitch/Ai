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

# 🤖 API KEYS
DEEPSEEK_API_KEY = "sk-5da4d6648bbe48158c9dd2ba656ac26d"

# 💰 PAYMENT & DB
BKASH_NUMBER = "01846849460"    
NAGAD_NUMBER = "01846849460"    
DATABASE_URL = "postgresql://postgres:hQKBupovepWPRJyTUCiqYrUfEnoeRYYv@trolley.proxy.rlwy.net:36125/railway"
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
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id BIGINT PRIMARY KEY, credits INTEGER DEFAULT 0, role TEXT DEFAULT 'Free', 
                  generated_count INTEGER DEFAULT 0, full_name TEXT, expiry_date DATE DEFAULT CURRENT_DATE)''')
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
async def ask_ai(prompt, system="You are a helpful AI assistant."):
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    data = {"model": "deepseek-chat", "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post("https://api.deepseek.com/chat/completions", json=data, headers=headers, timeout=60)
            return r.json()['choices'][0]['message']['content']
        except: return "❌ AI Busy. Please try again later."

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
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💡 Commands: `/chat`, `/image`, `/script`, `/code`"
        )
        kb = [
            [InlineKeyboardButton("🧠 AI Menu", callback_data='ai_menu')],
            [InlineKeyboardButton("💰 Buy Credits", callback_data='deposit'), InlineKeyboardButton("🎫 Redeem", callback_data='redeem_ui')],
            [InlineKeyboardButton("👨‍💻 Admin Support", url=f"https://t.me/{ADMIN_USERNAME.replace('@','')}")]
        ]
        if update.message: await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        else: await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    except Exception as e:
        print(f"Error in Start: {e}")

# --- AI COMMANDS ---
async def ai_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cmd = update.message.text.split()[0].replace('/', '')
    prompt = " ".join(context.args)
    
    if not prompt:
        return await update.message.reply_text(f"⚠️ Usage: `/{cmd} your prompt`", parse_mode='Markdown')

    u = get_user(user_id)
    cost = 20 if cmd == 'image' else 5
    
    if u[1] < cost:
        return await update.message.reply_text(f"❌ Low Credits! Need {cost} coins.")

    m = await update.message.reply_text("⏳ Processing...")
    
    if cmd == 'image':
        url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}"
        await update.message.reply_photo(url, caption=f"🎨 **Prompt:** {prompt}\n⚡ Enjoy our AI!", parse_mode='Markdown')
        await m.delete()
    else:
        res = await ask_ai(prompt)
        await m.edit_text(f"💡 **AI:**\n\n{res}\n\n⚡ Enjoy our AI!", parse_mode='Markdown')
    
    conn = get_db_conn(); c = conn.cursor()
    c.execute("UPDATE users SET credits=credits-%s, generated_count=generated_count+1 WHERE user_id=%s", (cost, user_id))
    conn.commit(); conn.close()

# --- ADMIN STATS ---
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    cpu, ram = psutil.cpu_percent(), psutil.virtual_memory().percent
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users"); total_u = c.fetchone()[0]
    conn.close()
    await update.message.reply_text(f"🖥 **SERVER STATS**\nUsers: {total_u}\nCPU: {cpu}% | RAM: {ram}%")

# --- GEN & REDEEM (AUTO REPLY SYSTEM) ---
async def gencoins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        amt, plan = int(context.args[0]), context.args[1].upper()
        code = f"CODE-{''.join(random.choices(string.ascii_uppercase + string.digits, k=10))}"
        conn = get_db_conn(); c = conn.cursor()
        c.execute("INSERT INTO codes (code, credit_amount, role_reward) VALUES (%s, %s, %s)", (code, amt, plan))
        conn.commit(); conn.close()
        await update.message.reply_text(f"🎫 **New Redeem Code**\n\nCode: `{code}`\nPlan: {plan}\nCoins: {amt}\n\n💡 *Tip: Reply to this message with /redeem to activate!*", parse_mode='Markdown')
    except: await update.message.reply_text("❌ Usage: `/gencoins 500 GOLD`")

async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code_text = None
    
    # Check if user replied to a message containing the code
    if update.message.reply_to_message:
        reply_text = update.message.reply_to_message.text
        match = re.search(r'CODE-\w+', reply_text)
        if match: code_text = match.group(0)
    
    # If not reply, check arguments
    if not code_text and context.args:
        code_text = context.args[0].strip()

    if not code_text:
        return await update.message.reply_text("❌ Please provide a code or reply to a code message with /redeem.")

    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT credit_amount, role_reward FROM codes WHERE code=%s AND is_redeemed=0", (code_text,))
    res = c.fetchone()
    
    if res:
        amt, plan = res[0], res[1]
        new_expiry = date.today() + timedelta(days=PLAN_DAYS.get(plan, 1))
        c.execute("UPDATE codes SET is_redeemed=1 WHERE code=%s", (code_text,))
        c.execute("UPDATE users SET credits=credits+%s, role=%s, expiry_date=%s WHERE user_id=%s", (amt, plan, new_expiry, update.effective_user.id))
        conn.commit()
        await update.message.reply_text(f"🎉 **Redeem Successful!**\n\n💎 {amt} Coins Added.\n👑 Rank: {plan}\n📅 New Expiry: {new_expiry}\n\n⚡ **Enjoy our AI!**", parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ Invalid or already used code.")
    conn.close()

# --- CALLBACKS ---
async def handle_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.data == 'main_menu': await start(update, context)
    elif q.data == 'ai_menu':
        await q.message.edit_text("💡 **AI COMMANDS**\n\n/chat <msg>\n/image <prompt>\n/script <topic>\n/code <prompt>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='main_menu')]]))
    elif q.data == 'deposit':
        await q.message.edit_text(f"💳 **PAYMENT**\n\nBkash/Nagad: `{BKASH_NUMBER}`\nSend Screenshot and TrxID.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='main_menu')]]))
    elif q.data == 'redeem_ui':
        await q.answer("💡 Reply to a code with /redeem or type: /redeem CODE-XXXX", show_alert=True)

import re # needed for code extraction
# --- MAIN ---
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", start))
    app.add_handler(CommandHandler(["chat", "image", "script", "code"], ai_handler))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("gencoins", gencoins))
    app.add_handler(CommandHandler("redeem", redeem))
    app.add_handler(CallbackQueryHandler(handle_cb))
    print("🤖 Minato Fix Bot is Live!")
    app.run_polling()

if __name__ == '__main__':
    main()
