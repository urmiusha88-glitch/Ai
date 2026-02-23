import logging
import psycopg2
import random
import string
import psutil
import urllib.parse
import httpx
import re
from datetime import datetime, timedelta
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
CHANNEL_ID = "@minatologs"
CHANNEL_INVITE_LINK = "https://t.me/minatologs/2"

# Plans config exactly as you requested
PLAN_DAYS = {"BRONZE": 3, "SILVER": 5, "GOLD": 7, "PLATINIAM": 15, "DIAMOND": 30}

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

active_chats = set()

# --- TIMEZONE FIX (BANGLADESH TIME) ---
def get_bd_time():
    return datetime.utcnow() + timedelta(hours=6)

# --- DATABASE ENGINE ---
def get_db_conn():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_db_conn()
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id BIGINT PRIMARY KEY, credits INTEGER DEFAULT 0, role TEXT DEFAULT 'Free', 
                 generated_count INTEGER DEFAULT 0, full_name TEXT, expiry_date TIMESTAMP)''')
    
    try:
        c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS credits INTEGER DEFAULT 0")
        c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name TEXT")
        c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'Free'")
        c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS generated_count INTEGER DEFAULT 0")
        c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS expiry_date TIMESTAMP")
        c.execute("ALTER TABLE users ALTER COLUMN expiry_date TYPE TIMESTAMP USING expiry_date::TIMESTAMP")
        conn.commit()
    except Exception:
        conn.rollback() 
        
    c.execute('''CREATE TABLE IF NOT EXISTS codes 
                 (code TEXT PRIMARY KEY, credit_amount INTEGER, role_reward TEXT, is_redeemed INTEGER DEFAULT 0)''')
    
    try:
        c.execute("UPDATE codes SET is_redeemed = 0 WHERE is_redeemed IS NULL")
        conn.commit()
    except:
        conn.rollback()
        
    conn.close()

init_db()

# --- USER HELPER ---
def get_user(user_id, name="User"):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT user_id, credits, role, generated_count, full_name, expiry_date FROM users WHERE user_id=%s", (user_id,))
    user = c.fetchone()
    if not user:
        bd_time = get_bd_time()
        c.execute("INSERT INTO users (user_id, credits, role, generated_count, full_name, expiry_date) VALUES (%s, 50, 'Free', 0, %s, %s)", 
                  (user_id, name, bd_time))
        conn.commit()
        user = (user_id, 50, 'Free', 0, name, bd_time)
    conn.close()
    return user

async def check_join(user_id, context):
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status not in ['left', 'kicked']
    except:
        return True

async def ask_ai(prompt, user_name="User"):
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    system_msg = f"You are Minato AI. The user's name talking to you is {user_name}. Be friendly."
    data = {
        "model": "deepseek-chat", 
        "messages": [
            {"role": "system", "content": system_msg}, 
            {"role": "user", "content": prompt}
        ]
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            r = await client.post("https://api.deepseek.com/chat/completions", json=data, headers=headers)
            return r.json()['choices'][0]['message']['content']
        except Exception:
            return "❌ Server Busy. Pare abar try korun."

# --- UI & STATUS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await check_join(user.id, context):
        await update.message.reply_text("❌ Join @minatologs First!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Join", url=CHANNEL_INVITE_LINK)]]))
        return

    try:
        u = get_user(user.id, user.first_name)
        expiry = u[5]
        status = f"✅ Premium ( {u[2]} )" if isinstance(expiry, datetime) and expiry > get_bd_time() else "🆓 Free"
        
        text = (
            f"🤖 **𝐌𝐈𝐍𝐀𝐓𝐎 𝐀𝐈 𝐀𝐒𝐒𝐈𝐒𝐓𝐀𝐍𝐓**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 **User:** `{u[4]}`\n"
            f"💎 **Coins:** `{u[1]}`\n"
            f"👑 **Rank:** `{status}`\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        kb = [
            [InlineKeyboardButton("👤 My Status", callback_data='my_status'), InlineKeyboardButton("🧠 AI Menu", callback_data='ai_menu')],
            [InlineKeyboardButton("💰 Buy Credits", callback_data='deposit'), InlineKeyboardButton("🎫 Redeem", callback_data='redeem_ui')]
        ]
        
        if update.message:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        elif update.callback_query:
            await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    except Exception as e:
        print(f"Start Error: {e}")

# /status Command
async def user_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u = get_user(user.id, user.first_name)
    expiry = u[5]
    
    if isinstance(expiry, datetime) and expiry > get_bd_time():
        status_text = f"Premium ( {u[2]} )"
        exp_str = expiry.strftime("%d %B %Y, %I:%M %p")
    else:
        status_text = "Free"
        exp_str = "None/Expired"

    text = (
        f"👤 **APNAR PROFILE STATUS** 👤\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💎 **Coins:** `{u[1]}`\n"
        f"👑 **Membership:** `{status_text}`\n"
        f"📅 **Expiration Date:** `{exp_str}`\n"
        f"━━━━━━━━━━━━━━━━━━"
    )
    if update.message:
        await update.message.reply_text(text, parse_mode='Markdown')
    elif update.callback_query:
        await update.callback_query.message.edit_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='main_menu')]]))

# --- CHAT & IMAGE ---
async def process_ai_message(update: Update, prompt: str):
    user = update.effective_user
    u = get_user(user.id, user.first_name)
    cost = 1 
    
    if u[1] < cost:
        if user.id in active_chats: active_chats.remove(user.id)
        return await update.message.reply_text("❌ Not enough Credits! Chat mode off hoye geche.")

    m = await update.message.reply_text("⏳ Thinking...")
    res = await ask_ai(prompt, user.first_name)
    
    await m.edit_text(f"{res}\n\n_(Chat off korte /stop likhun)_", parse_mode='Markdown')
    
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET credits=credits-%s, generated_count=generated_count+1 WHERE user_id=%s", (cost, u[0]))
    conn.commit()
    conn.close()

async def chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    prompt = " ".join(context.args)
    active_chats.add(user_id)
    if not prompt:
        await update.message.reply_text("✅ **Chat Mode ON!**\nEkhon theke apni normal message dilei AI uttor dibe. Thamate chaile `/stop` likhun.", parse_mode='Markdown')
        return
    await process_ai_message(update, prompt)

async def stop_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in active_chats:
        active_chats.remove(user_id)
        await update.message.reply_text("🛑 **Chat mode stopped.**\nAbar suru korte `/chat` likhun.", parse_mode='Markdown')
    else:
        await update.message.reply_text("Apni toh ekhon chat mode e nai. Suru korte `/chat` likhun.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in active_chats:
        await process_ai_message(update, update.message.text)

async def image_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args)
    if not prompt:
        return await update.message.reply_text("Usage: `/image apnar prompt`", parse_mode='Markdown')

    u = get_user(update.effective_user.id)
    cost = 20 
    
    if u[1] < cost:
        return await update.message.reply_text("❌ Not enough Credits for Image! Please buy more.")

    m = await update.message.reply_text("🎨 Drawing your photo... Please wait.")
    
    try:
        url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width=1024&height=1024&nologo=true"
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                await update.message.reply_photo(photo=response.content, caption="🎨 **Apnar Image!**", parse_mode='Markdown')
                await m.delete()
            else:
                return await m.edit_text("❌ Image api error. Photo generate korte pareni.")
    except Exception:
        return await m.edit_text("❌ Error generating image.")
        
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET credits=credits-%s, generated_count=generated_count+1 WHERE user_id=%s", (cost, u[0]))
    conn.commit()
    conn.close()

# --- ADMIN STATS ---
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*), SUM(generated_count) FROM users")
    res = c.fetchone()
    total_users = res[0] or 0
    total_activities = res[1] or 0
    
    c.execute("SELECT COUNT(*) FROM users WHERE role != 'Free'")
    premium_users = c.fetchone()[0] or 0
    conn.close()
    
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    
    text = (
        f"📊 **ADMIN STATS & PERFORMANCE**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👥 **Total Users:** `{total_users}`\n"
        f"💎 **Premium Users:** `{premium_users}`\n"
        f"🔄 **Total User Activities:** `{total_activities}`\n\n"
        f"🖥 **HOST DETAILS**\n"
        f"⚙️ **CPU Usage:** `{cpu}%`\n"
        f"💾 **RAM Usage:** `{ram}%`\n"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

# --- GEN & REDEEM FIXES ---
async def gencoins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        plan = context.args[0].upper()
        if plan not in PLAN_DAYS:
            return await update.message.reply_text("❌ Valid plans: BRONZE, SILVER, GOLD, PLATINIAM, DIAMOND")
            
        amt = int(context.args[1]) if len(context.args) > 1 else 100
        
        # Generator: CODE-XXXXXXXXXXXXXX (14 Chars exact)
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=14))
        code = f"CODE-{random_str}"
        
        conn = get_db_conn()
        c = conn.cursor()
        c.execute("INSERT INTO codes (code, credit_amount, role_reward, is_redeemed) VALUES (%s, %s, %s, 0)", (code, amt, plan))
        conn.commit()
        conn.close()
        
        # format: CODE-XXXXXXXXXXXXXX ( GOLD )
        await update.message.reply_text(f"🎫 **New Code Generated:**\n\n`{code}` ( {plan} )\n\nCoins: {amt}\n💡 Reply to this message with `/redeem` to claim!", parse_mode='Markdown')
    except Exception:
        await update.message.reply_text("❌ Usage: `/gencoin GOLD 500` ba `/gencoin SILVER 200`", parse_mode='Markdown')

async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code_text = None
    if update.message.reply_to_message and update.message.reply_to_message.text:
        match = re.search(r'CODE-[A-Z0-9]{14}', update.message.reply_to_message.text)
        if match: code_text = match.group(0)
            
    if not code_text and context.args:
        code_text = context.args[0].strip()

    if not code_text:
        return await update.message.reply_text("❌ Kono code e reply kore `/redeem` likhun ba `/redeem CODE-XXXX...` likhun.", parse_mode='Markdown')

    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT credit_amount, role_reward FROM codes WHERE code=%s AND COALESCE(is_redeemed, 0) = 0", (code_text,))
    res = c.fetchone()
    
    if res:
        amt, plan = res[0], res[1]
        
        # BD Time e exact expiration time!
        new_expiry = get_bd_time() + timedelta(days=PLAN_DAYS.get(plan, 1))
        exp_formatted = new_expiry.strftime("%d %B %Y, %I:%M %p")
        
        c.execute("UPDATE codes SET is_redeemed = 1 WHERE code=%s", (code_text,))
        c.execute("UPDATE users SET credits=credits+%s, role=%s, expiry_date=%s WHERE user_id=%s", (amt, plan, new_expiry, update.effective_user.id))
        conn.commit()
        
        await update.message.reply_text(
            f"🎉 **Redeem Successful!**\n"
            f"💎 Coins Added: `{amt}`\n"
            f"👑 Membership: Premium ( {plan} )\n"
            f"📅 Exact Expiry: `{exp_formatted}`\n\n"
            f"⚡ **Enjoy our AI! 🎉**", 
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ Invalid dekhacche! Ei code ta bhul ba already use kora hoye geche.")
        
    conn.close()

# --- CALLBACKS ---
async def handle_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    if q.data == 'main_menu':
        await start(update, context)
    elif q.data == 'my_status':
        await user_status(update, context)
    elif q.data == 'ai_menu':
        await q.message.edit_text("💡 **AI Commands:**\n`/chat` - Continuous Chat On\n`/stop` - Chat Off\n`/image [prompt]` - Create Image", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='main_menu')]]))
    elif q.data == 'deposit':
        await q.message.edit_text(f"💳 **Payment Info:**\nBkash/Nagad: `{BKASH_NUMBER}`\n\nPayment kore admin er sathe jogajog korun: {ADMIN_USERNAME}", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='main_menu')]]))
    elif q.data == 'redeem_ui':
        await q.message.edit_text("🎫 **Redeem System:**\nKono code e reply kore `/redeem` likhun, othoba `/redeem CODE-XXXX` format e command din.", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='main_menu')]]))

def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", user_status))
    app.add_handler(CommandHandler(["chat", "script", "code"], chat_command))
    app.add_handler(CommandHandler("stop", stop_chat))
    app.add_handler(CommandHandler(["image", "photo"], image_handler))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler(["gencoins", "gencoin"], gencoins))
    app.add_handler(CommandHandler("redeem", redeem))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_cb))
    
    print("🤖 Bot is successfully running with Bangladesh Timezone and perfectly formatted Codes!")
    app.run_polling()

if __name__ == '__main__':
    main()
