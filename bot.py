import logging
import psycopg2
import random
import string
import psutil
import urllib.parse
import httpx
import re
import io
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

# ======================================================
# 👇 CONFIGURATION
# ======================================================
TOKEN = "8290942305:AAGFtnKV8P5xk591NejJ5hsKEJ02foiRpEk"
OWNER_ID = 6198703244  # Apni (Owner)
ADMIN_USERNAME = "@yours_ononto"

DEEPSEEK_API_KEY = "sk-5da4d6648bbe48158c9dd2ba656ac26d"
DATABASE_URL = "postgresql://postgres:hQKBupovepWPRJyTUCiqYrUfEnoeRYYv@trolley.proxy.rlwy.net:36125/railway"

BKASH_NUMBER = "01846849460"
NAGAD_NUMBER = "01846849460"
CHANNEL_ID = "@minatologs"
CHANNEL_INVITE_LINK = "https://t.me/minatologs/2"

# Plans config exactly as requested
PLAN_DAYS = {"BRONZE": 3, "SILVER": 5, "GOLD": 7, "PLATINIAM": 15, "DIAMOND": 30}
PLAN_COINS = {"BRONZE": 100, "SILVER": 500, "GOLD": 2000, "PLATINIAM": 5000, "DIAMOND": 10000}

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

active_chats = {}
MAINTENANCE_MODE = False

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
                 generated_count INTEGER DEFAULT 0, full_name TEXT, expiry_date TIMESTAMP,
                 is_admin INTEGER DEFAULT 0, is_banned INTEGER DEFAULT 0, last_claim_date TIMESTAMP)''')
    
    try:
        c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS credits INTEGER DEFAULT 0")
        c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name TEXT")
        c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'Free'")
        c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS generated_count INTEGER DEFAULT 0")
        c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS expiry_date TIMESTAMP")
        c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin INTEGER DEFAULT 0")
        c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned INTEGER DEFAULT 0")
        c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_claim_date TIMESTAMP")
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
    c.execute("SELECT user_id, credits, role, generated_count, full_name, expiry_date, is_admin, is_banned, last_claim_date FROM users WHERE user_id=%s", (user_id,))
    user = c.fetchone()
    if not user:
        bd_time = get_bd_time()
        c.execute("INSERT INTO users (user_id, credits, role, generated_count, full_name, expiry_date, is_admin, is_banned, last_claim_date) VALUES (%s, 50, 'Free', 0, %s, %s, 0, 0, NULL)", 
                  (user_id, name, bd_time))
        conn.commit()
        user = (user_id, 50, 'Free', 0, name, bd_time, 0, 0, None)
    conn.close()
    return user

def check_admin(user_id):
    if user_id == OWNER_ID: return True
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT is_admin FROM users WHERE user_id=%s", (user_id,))
    res = c.fetchone()
    conn.close()
    return bool(res and res[0] == 1)

def check_banned(user_id):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT is_banned FROM users WHERE user_id=%s", (user_id,))
    res = c.fetchone()
    conn.close()
    return bool(res and res[0] == 1)

async def check_join(user_id, context):
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status not in ['left', 'kicked']
    except:
        return True

async def ask_ai(prompt, user_name="User"):
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    
    system_msg = (
        f"You are Minato AI, an advanced AI assistant created by Ononto Hasan. "
        f"The user's name talking to you is {user_name}. "
        f"CRITICAL LANGUAGE RULE: Always detect the underlying language of any Romanized input and ALWAYS respond in the proper native script of that language. "
        f"This applies globally to ALL languages. If the user types in Romanized Bengali/Banglish (e.g., 'kemon aso'), you MUST reply in proper Bengali script (বাংলা). "
        f"If Romanized Hindi/Hinglish, reply in proper Hindi script (हिंदी). "
        f"If the user types in English, reply in English. "
        f"Never reply in Romanized/Latin formats for languages that have their own native scripts. Be friendly and helpful."
    )
    
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

# ======================================================
# PUBLIC UI & COMMANDS
# ======================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if check_banned(user.id): return await update.message.reply_text("❌ You are banned from using this bot.")
    
    if MAINTENANCE_MODE and not check_admin(user.id):
        return await update.message.reply_text("🛠 *𝗦𝗬𝗦𝗧𝗘𝗠 𝗠𝗔𝗜𝗡𝗧𝗘𝗡𝗔𝗡𝗖𝗘 𝗔𝗟𝗘𝗥𝗧*\nThe bot is currently undergoing scheduled maintenance. Please check back later.", parse_mode='Markdown')
    
    if not await check_join(user.id, context):
        await update.message.reply_text("❌ Join @minatologs First!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Join", url=CHANNEL_INVITE_LINK)]]))
        return

    try:
        u = get_user(user.id, user.first_name)
        expiry = u[5]
        is_owner = (user.id == OWNER_ID)
        
        if is_owner:
            status = "👑 Owner"
            coins_display = "Unlimited ♾️"
        elif isinstance(expiry, datetime) and expiry > get_bd_time():
            status = f"✅ Premium ( {u[2]} )"
            coins_display = f"`{u[1]}`"
        else:
            status = "🆓 Free"
            coins_display = f"`{u[1]}`"
        
        text = (
            f"🤖 **𝐌𝐈𝐍𝐀𝐓𝐎 𝐀𝐈 𝐀𝐒𝐒𝐈𝐒𝐓𝐀𝐍𝐓**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 **User:** `{u[4]}`\n"
            f"💎 **Coins:** {coins_display}\n"
            f"👑 **Rank:** `{status}`\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        
        kb = [
            [InlineKeyboardButton("👤 My Status", callback_data='my_status'), InlineKeyboardButton("🎁 Daily Claim", callback_data='daily_claim')],
            [InlineKeyboardButton("🧠 AI Menu", callback_data='ai_menu'), InlineKeyboardButton("💰 Buy Credits", callback_data='deposit')],
            [InlineKeyboardButton("🎫 Redeem", callback_data='redeem_ui')]
        ]
        
        if update.message:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        elif update.callback_query:
            await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    except Exception as e:
        print(f"Start Error: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if check_banned(update.effective_user.id): return
    text = (
        "💡 **USER COMMANDS** 💡\n\n"
        "🔹 `/start` - Start the bot & show profile\n"
        "🔹 `/status` - Check Membership & Coins status\n"
        "🔹 `/chat <prompt>` - Start Continuous AI Chat\n"
        "🔹 `/stop` - Stop Continuous Chat\n"
        "🔹 `/image <prompt>` - Generate Image using AI\n"
        "🔹 `/redeem <code>` - Claim premium/coins\n"
        "🔹 `/report <msg>` - Send a bug report/suggestion to Admin\n"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

async def report_bug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if check_banned(user.id): return
    
    msg = " ".join(context.args)
    if not msg:
        return await update.message.reply_text("❌ Please likhun apni ki janate chan.\n**Usage:** `/report chat e problem hocche` ba kono suggestion.", parse_mode='Markdown')
        
    report_text = (
        f"🚨 **NEW REPORT / SUGGESTION** 🚨\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 **From:** {user.first_name} (`{user.id}`)\n"
        f"💬 **Message:** {msg}\n"
        f"━━━━━━━━━━━━━━━━━━"
    )
    
    try:
        await context.bot.send_message(OWNER_ID, report_text, parse_mode='Markdown')
        await update.message.reply_text("✅ Apnar message sothik vabe Owner er kache send kora hoyeche. Dhonnobad!", parse_mode='Markdown')
    except Exception:
        await update.message.reply_text("❌ Owner ke message pathate somossa hoyeche.")

async def user_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if check_banned(user.id): return
    u = get_user(user.id, user.first_name)
    expiry = u[5]
    is_owner = (user.id == OWNER_ID)
    
    if is_owner:
        status_text = "👑 Owner"
        exp_str = "`Lifetime ♾️`"
        coins_display = "`Unlimited ♾️`"
    elif isinstance(expiry, datetime) and expiry > get_bd_time():
        status_text = f"Premium ( {u[2]} )"
        exp_str = f"`{expiry.strftime('%d %B %Y, %I:%M %p')}`"
        coins_display = f"`{u[1]}`"
    else:
        status_text = "Free"
        exp_str = "`None/Expired`"
        coins_display = f"`{u[1]}`"

    text = (
        f"👤 **APNAR PROFILE STATUS** 👤\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💎 **Coins:** {coins_display}\n"
        f"👑 **Membership:** `{status_text}`\n"
        f"📅 **Expiration Date:** {exp_str}\n"
        f"━━━━━━━━━━━━━━━━━━"
    )
    if update.message:
        await update.message.reply_text(text, parse_mode='Markdown')
    elif update.callback_query:
        await update.callback_query.message.edit_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='main_menu')]]))

# ======================================================
# AI CHAT & IMAGE
# ======================================================
async def process_ai_message(update: Update, prompt: str):
    user = update.effective_user
    if check_banned(user.id): return
    
    if MAINTENANCE_MODE and not check_admin(user.id):
        return await update.message.reply_text("🛠 *𝗦𝗬𝗦𝗧𝗘𝗠 𝗠𝗔𝗜𝗡𝗧𝗘𝗡𝗔𝗡𝗖𝗘 𝗔𝗟𝗘𝗥𝗧*\nThe bot is currently undergoing scheduled maintenance. Please check back later.", parse_mode='Markdown')
    
    u = get_user(user.id, user.first_name)
    cost = 2 
    is_owner = (user.id == OWNER_ID)
    
    if not is_owner and u[1] < cost:
        if user.id in active_chats: 
            del active_chats[user.id]
        return await update.message.reply_text("❌ Not enough Credits! Chat mode off hoye geche.")

    m = await update.message.reply_text("⏳ Thinking...")
    res = await ask_ai(prompt, user.first_name)
    
    if user.id in active_chats and not active_chats[user.id].get("greeted", True):
        intro_text = (
            f"👋 Hello **{user.first_name}**!\n"
            f"🤖 I am Minato AI, created by **Ononto Hasan**.\n"
            f"🔗 [FB: Ononto Hasan](https://www.facebook.com/yours.ononto)\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
        )
        res = intro_text + res
        active_chats[user.id]["greeted"] = True 
    
    await m.edit_text(res, parse_mode='Markdown', disable_web_page_preview=True)
    
    conn = get_db_conn()
    c = conn.cursor()
    if not is_owner:
        c.execute("UPDATE users SET credits=credits-%s, generated_count=generated_count+1 WHERE user_id=%s", (cost, u[0]))
    else:
        c.execute("UPDATE users SET generated_count=generated_count+1 WHERE user_id=%s", (u[0],))
    conn.commit()
    conn.close()

async def chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if check_banned(user_id): return
    prompt = " ".join(context.args)
    
    if user_id not in active_chats:
        active_chats[user_id] = {"greeted": False}
    
    if not prompt:
        await update.message.reply_text("✅ **Chat Mode ON!**\nEkhon theke apni normal message dilei AI uttor dibe. Thamate chaile `/stop` likhun.", parse_mode='Markdown')
        return
    await process_ai_message(update, prompt)

async def stop_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in active_chats:
        del active_chats[user_id]
        await update.message.reply_text("🛑 **Chat mode stopped.**\nAbar suru korte `/chat` likhun.", parse_mode='Markdown')
    else:
        await update.message.reply_text("Apni toh ekhon chat mode e nai. Suru korte `/chat` likhun.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if check_banned(user_id): return
    if user_id in active_chats:
        await process_ai_message(update, update.message.text)

async def image_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if check_banned(user_id): return
    
    if MAINTENANCE_MODE and not check_admin(user_id):
        return await update.message.reply_text("🛠 *𝗦𝗬𝗦𝗧𝗘𝗠 𝗠𝗔𝗜𝗡𝗧𝗘𝗡𝗔𝗡𝗖𝗘 𝗔𝗟𝗘𝗥𝗧*\nThe bot is currently undergoing scheduled maintenance. Please check back later.", parse_mode='Markdown')
    
    prompt = " ".join(context.args)
    if not prompt:
        return await update.message.reply_text("Usage: `/image apnar prompt`", parse_mode='Markdown')

    u = get_user(user_id)
    cost = 20 
    is_owner = (user_id == OWNER_ID)
    
    if not is_owner and u[1] < cost:
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
    if not is_owner:
        c.execute("UPDATE users SET credits=credits-%s, generated_count=generated_count+1 WHERE user_id=%s", (cost, u[0]))
    else:
        c.execute("UPDATE users SET generated_count=generated_count+1 WHERE user_id=%s", (u[0],))
    conn.commit()
    conn.close()

# ======================================================
# ADMIN COMMANDS
# ======================================================
async def admin_cmds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_admin(update.effective_user.id): return
    
    text = (
        "🛠 **ADMIN COMMANDS** 🛠\n"
        "🔹 `/stats` - Server & Bot Stats\n"
        "🔹 `/addcoin <id> <amount>` - Add coins to user\n"
        "🔹 `/ban <id>` or `/ban_user <id>` - Ban user\n"
        "🔹 `/unban <id>` or `/unban_user <id>` - Unban user\n"
        "🔹 `/admins` - View list of admins\n"
        "🔹 `/broadcast <text>` - Send msg to all users\n"
        "🔹 `/gencoins <PLAN> [amount]` - Gen code\n\n"
        "👑 **OWNER EXCLUSIVE COMMANDS** 👑\n"
        "🔸 `/add_admin <id>` - Make a user admin\n"
        "🔸 `/ban_admin <id>` - Remove admin role\n"
        "🔸 `/maintenance on/off [msg]` - Auto alert to all users\n"
        "🔸 `/setplan <id> <plan>` - Direct premium\n"
        "🔸 `/removecoin <id> <amount>` - Deduct coins\n"
        "🔸 `/userlist` - Download all users database\n"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_admin(update.effective_user.id): return
    
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
    m_status = "🔴 ON" if MAINTENANCE_MODE else "🟢 OFF"
    
    text = (
        f"📊 **ADMIN STATS & PERFORMANCE**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👥 **Total Users:** `{total_users}`\n"
        f"💎 **Premium Users:** `{premium_users}`\n"
        f"🔄 **Total User Activities:** `{total_activities}`\n\n"
        f"🖥 **HOST DETAILS**\n"
        f"⚙️ **CPU Usage:** `{cpu}%`\n"
        f"💾 **RAM Usage:** `{ram}%`\n"
        f"🛠 **Maintenance:** `{m_status}`\n"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

async def add_coin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_admin(update.effective_user.id): return
    try:
        target_id = int(context.args[0])
        amt = int(context.args[1])
        
        conn = get_db_conn()
        c = conn.cursor()
        c.execute("SELECT user_id FROM users WHERE user_id=%s", (target_id,))
        if not c.fetchone():
            return await update.message.reply_text("❌ Ei user konodin bot start koreni.")
            
        c.execute("UPDATE users SET credits=credits+%s WHERE user_id=%s", (amt, target_id))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"✅ User `{target_id}` ke {amt} coins deya hoyeche.", parse_mode='Markdown')
        try:
            await context.bot.send_message(target_id, f"🎉 Admin apnake {amt} notun Coins diyeche! Enjoy!")
        except: pass
    except Exception:
        await update.message.reply_text("❌ Usage: `/addcoin <user_id> <amount>`", parse_mode='Markdown')

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_admin(update.effective_user.id): return
    try:
        target_id = int(context.args[0])
        if target_id == OWNER_ID:
            return await update.message.reply_text("❌ Owner ke ban kora jabe na!")
            
        conn = get_db_conn()
        c = conn.cursor()
        c.execute("UPDATE users SET is_banned=1 WHERE user_id=%s", (target_id,))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ User `{target_id}` Banned successfully!", parse_mode='Markdown')
    except Exception:
        await update.message.reply_text("❌ Usage: `/ban <user_id>`")

async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_admin(update.effective_user.id): return
    try:
        target_id = int(context.args[0])
        conn = get_db_conn()
        c = conn.cursor()
        c.execute("UPDATE users SET is_banned=0 WHERE user_id=%s", (target_id,))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ User `{target_id}` Unbanned successfully!", parse_mode='Markdown')
    except Exception:
        await update.message.reply_text("❌ Usage: `/unban <user_id>`")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_admin(update.effective_user.id): return
    msg = " ".join(context.args)
    if not msg:
        return await update.message.reply_text("❌ Usage: `/broadcast <your message>`")
        
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE is_banned=0")
    users = c.fetchall()
    conn.close()
    
    success = 0
    await update.message.reply_text(f"📢 Sending message to {len(users)} users...")
    for u in users:
        try:
            await context.bot.send_message(u[0], f"📢 **Announcement:**\n\n{msg}", parse_mode='Markdown')
            success += 1
        except: pass
            
    await update.message.reply_text(f"✅ Broadcast complete! Delivered to {success} users.")

async def gencoins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_admin(update.effective_user.id): return
    try:
        plan = context.args[0].upper()
        if plan not in PLAN_DAYS:
            return await update.message.reply_text("❌ Valid plans: BRONZE, SILVER, GOLD, PLATINIAM, DIAMOND")
            
        amt = int(context.args[1]) if len(context.args) > 1 else PLAN_COINS[plan]
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=14))
        code = f"CODE-{random_str}"
        
        conn = get_db_conn()
        c = conn.cursor()
        c.execute("INSERT INTO codes (code, credit_amount, role_reward, is_redeemed) VALUES (%s, %s, %s, 0)", (code, amt, plan))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"🎫 **New Code Generated:**\n\n`{code}` ( {plan} )\n\nCoins: {amt}\n💡 Reply to this message with `/redeem` to claim!", parse_mode='Markdown')
    except Exception:
        await update.message.reply_text("❌ Usage: `/gencoin GOLD` ba custom giveaway er jonno `/gencoin GOLD 500`", parse_mode='Markdown')

# ======================================================
# OWNER ONLY COMMANDS
# ======================================================
async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    try:
        target_id = int(context.args[0])
        conn = get_db_conn()
        c = conn.cursor()
        c.execute("UPDATE users SET is_admin=1 WHERE user_id=%s", (target_id,))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ User `{target_id}` is now an Admin.", parse_mode='Markdown')
        try:
            await context.bot.send_message(target_id, "🎉 Apnake bot er Admin banano hoyeche! Command dekhte `/cmds` likhun.")
        except: pass
    except Exception:
        await update.message.reply_text("❌ Usage: `/add_admin <user_id>`")

async def ban_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    try:
        target_id = int(context.args[0])
        conn = get_db_conn()
        c = conn.cursor()
        c.execute("UPDATE users SET is_admin=0 WHERE user_id=%s", (target_id,))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ User `{target_id}` is no longer an Admin.", parse_mode='Markdown')
    except Exception:
        await update.message.reply_text("❌ Usage: `/ban_admin <user_id>`")

async def view_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_admin(update.effective_user.id): return
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT user_id, full_name FROM users WHERE is_admin=1")
    admins = c.fetchall()
    conn.close()
    
    text = f"👑 **Owner:** `{OWNER_ID}`\n\n🛠 **Admins List:**\n"
    if not admins:
        text += "No admins found."
    else:
        for a in admins: text += f"- {a[1]} (`{a[0]}`)\n"
    await update.message.reply_text(text, parse_mode='Markdown')

# --- PROFESSIONAL ENGLISH MAINTENANCE COMMAND ---
async def toggle_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    global MAINTENANCE_MODE
    
    if not context.args:
        return await update.message.reply_text("Usage:\n`/maintenance on`\n`/maintenance off added claim button, fixed bug, improved speed`", parse_mode='Markdown')
        
    state = context.args[0].lower()
    
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE is_banned=0")
    users = c.fetchall()
    conn.close()

    if state == "on":
        MAINTENANCE_MODE = True
        await update.message.reply_text("🛠 **Maintenance Mode ON.** Broadcasting English alert to users...", parse_mode='Markdown')
        
        msg = (
            "🛠 *𝗦𝗬𝗦𝗧𝗘𝗠 𝗠𝗔𝗜𝗡𝗧𝗘𝗡𝗔𝗡𝗖𝗘 𝗔𝗟𝗘𝗥𝗧* 🛠\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "Dear Users,\n"
            "Our bot is currently undergoing scheduled maintenance to bring you a better and faster experience.\n\n"
            "⏳ *Status:* Offline for Upgrades\n"
            "⚙️ *Reason:* Core System Updates & Feature Additions\n\n"
            "Please bear with us. You will be automatically notified once the system is back online. Thank you for your patience! ❤️"
        )
        
        success = 0
        for u in users:
            try:
                await context.bot.send_message(u[0], msg, parse_mode='Markdown')
                success += 1
            except: pass
        await update.message.reply_text(f"✅ Maintenance ON message sent to {success} users.")
        
    elif state == "off":
        MAINTENANCE_MODE = False
        
        # Format update notes automatically
        if len(context.args) > 1:
            updates_raw = " ".join(context.args[1:])
            # Split sentences by comma or dot to create automatic bullet points
            updates_list = [u.strip() for u in re.split(r'[,|.]', updates_raw) if u.strip()]
            updates_formatted = "\n".join([f"▪️ {u.capitalize()}" for u in updates_list])
        else:
            # Default professional update notes if owner types nothing
            updates_formatted = (
                "▪️ Core system performance optimized.\n"
                "▪️ Minor bug fixes for smoother chats.\n"
                "▪️ Server response time improved."
            )
            
        msg = (
            "✅ *𝗦𝗬𝗦𝗧𝗘𝗠 𝗢𝗡𝗟𝗜𝗡𝗘 & 𝗨𝗣𝗗𝗔𝗧𝗘𝗗* ✅\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "Great news! The maintenance is complete and the bot is now fully operational.\n\n"
            "🚀 *𝗪𝗵𝗮𝘁'𝘀 𝗡𝗲𝘄 & 𝗙𝗶𝘅𝗲𝗱:*\n"
            f"{updates_formatted}\n\n"
            "Enjoy the newly improved AI experience! Type /start to continue."
        )
        
        await update.message.reply_text("✅ **Maintenance Mode OFF.** Broadcasting English updates to users...", parse_mode='Markdown')
        success = 0
        for u in users:
            try:
                await context.bot.send_message(u[0], msg, parse_mode='Markdown')
                success += 1
            except: pass
        await update.message.reply_text(f"✅ Maintenance OFF message sent to {success} users.")
    else:
        await update.message.reply_text("Usage:\n`/maintenance on`\n`/maintenance off added premium, fixed bugs`", parse_mode='Markdown')

async def remove_coin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    try:
        target_id = int(context.args[0])
        amt = int(context.args[1])
        conn = get_db_conn()
        c = conn.cursor()
        c.execute("UPDATE users SET credits=credits-%s WHERE user_id=%s AND credits >= %s", (amt, target_id, amt))
        if c.rowcount == 0:
            c.execute("UPDATE users SET credits=0 WHERE user_id=%s", (target_id,))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ User `{target_id}` er theke {amt} coins kete neya hoyeche.", parse_mode='Markdown')
    except Exception:
        await update.message.reply_text("❌ Usage: `/removecoin <user_id> <amount>`", parse_mode='Markdown')

async def set_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    try:
        target_id = int(context.args[0])
        plan = context.args[1].upper()
        if plan not in PLAN_DAYS:
            return await update.message.reply_text("❌ Valid plans: BRONZE, SILVER, GOLD, PLATINIAM, DIAMOND")
            
        new_expiry = get_bd_time() + timedelta(days=PLAN_DAYS.get(plan, 1))
        added_coins = PLAN_COINS[plan] 
        
        conn = get_db_conn()
        c = conn.cursor()
        c.execute("UPDATE users SET credits=credits+%s, role=%s, expiry_date=%s WHERE user_id=%s", (added_coins, plan, new_expiry, target_id))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"✅ User `{target_id}` ke direct {plan} plan (+{added_coins} coins) deya hoyeche.", parse_mode='Markdown')
        try:
            await context.bot.send_message(target_id, f"🎉 Admin apnake direct Premium ( {plan} ) ar {added_coins} coins diyeche! Check /status")
        except: pass
    except Exception:
        await update.message.reply_text("❌ Usage: `/setplan <user_id> <plan>`", parse_mode='Markdown')

async def user_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT user_id, full_name, credits, role FROM users")
    users = c.fetchall()
    conn.close()
    
    content = "User ID | Name | Coins | Role\n" + "-"*50 + "\n"
    for u in users:
        content += f"{u[0]} | {u[1]} | {u[2]} | {u[3]}\n"
        
    f = io.BytesIO(content.encode('utf-8'))
    f.name = "database_users.txt"
    await update.message.reply_document(document=f, caption="📄 **Bot All Users Database**", parse_mode='Markdown')

# ======================================================
# REDEEM & CALLBACKS
# ======================================================
async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if check_banned(user_id): return
    
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
        new_expiry = get_bd_time() + timedelta(days=PLAN_DAYS.get(plan, 1))
        exp_formatted = new_expiry.strftime("%d %B %Y, %I:%M %p")
        
        c.execute("UPDATE codes SET is_redeemed = 1 WHERE code=%s", (code_text,))
        c.execute("UPDATE users SET credits=credits+%s, role=%s, expiry_date=%s WHERE user_id=%s", (amt, plan, new_expiry, user_id))
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

async def handle_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    if q.data == 'main_menu':
        await start(update, context)
        
    elif q.data == 'daily_claim':
        user_id = update.effective_user.id
        if check_banned(user_id): return
        
        conn = get_db_conn()
        c = conn.cursor()
        c.execute("SELECT last_claim_date FROM users WHERE user_id=%s", (user_id,))
        res = c.fetchone()
        
        now = get_bd_time()
        last_claim = res[0] if res else None
        
        if last_claim is None or (now - last_claim) >= timedelta(hours=24):
            c.execute("UPDATE users SET credits=credits+50, last_claim_date=%s WHERE user_id=%s", (now, user_id))
            conn.commit()
            await q.answer("🎉 50 Coins claimed successfully!", show_alert=True)
            await start(update, context)
        else:
            diff = timedelta(hours=24) - (now - last_claim)
            total_seconds = int(diff.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            await q.answer(f"⏳ Please wait {hours} hours and {minutes} minutes before claiming again.", show_alert=True)
            
        conn.close()
        
    elif q.data == 'my_status':
        await user_status(update, context)
    elif q.data == 'ai_menu':
        await q.message.edit_text("💡 **AI Commands:**\n`/chat` - Continuous Chat On\n`/stop` - Chat Off\n`/image [prompt]` - Create Image\n`/help` - Show all commands", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='main_menu')]]))
    elif q.data == 'deposit':
        await q.message.edit_text(f"💳 **Payment Info:**\nBkash/Nagad: `{BKASH_NUMBER}`\n\nPayment kore admin er sathe jogajog korun: {ADMIN_USERNAME}", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='main_menu')]]))
    elif q.data == 'redeem_ui':
        await q.message.edit_text("🎫 **Redeem System:**\nKono code e reply kore `/redeem` likhun, othoba `/redeem CODE-XXXX` format e command din.", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='main_menu')]]))

def main():
    app = Application.builder().token(TOKEN).build()
    
    # Public Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", user_status))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("report", report_bug))
    app.add_handler(CommandHandler(["chat", "script", "code"], chat_command))
    app.add_handler(CommandHandler("stop", stop_chat))
    app.add_handler(CommandHandler(["image", "photo"], image_handler))
    app.add_handler(CommandHandler("redeem", redeem))
    
    # Admin Commands
    app.add_handler(CommandHandler("cmds", admin_cmds))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler(["gencoins", "gencoin"], gencoins))
    app.add_handler(CommandHandler("addcoin", add_coin))
    app.add_handler(CommandHandler(["ban_user", "ban"], ban_user))
    app.add_handler(CommandHandler(["unban_user", "unban"], unban_user))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("admins", view_admins))
    
    # Owner Exclusive Commands
    app.add_handler(CommandHandler("add_admin", add_admin))
    app.add_handler(CommandHandler("ban_admin", ban_admin))
    app.add_handler(CommandHandler("maintenance", toggle_maintenance))
    app.add_handler(CommandHandler("removecoin", remove_coin))
    app.add_handler(CommandHandler("setplan", set_plan))
    app.add_handler(CommandHandler("userlist", user_list))
    
    # Callbacks & Text Handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_cb))
    
    print("🤖 Bot is completely ready with Professional English Maintenance System!")
    app.run_polling()

if __name__ == '__main__':
    main()
