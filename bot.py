import logging
import psycopg2
import random
import string
import urllib.parse
import httpx
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

# ======================================================
# 👇 CONFIGURATION SECTION
# ======================================================
TOKEN = "8290942305:AAGFtnKV8P5xk591NejJ5hsKEJ02foiRpEk"
ADMIN_ID = 6198703244  
ADMIN_USERNAME = "@minato_namikaze143"  # 👈 আপনার টেলিগ্রাম ইউজারনেম এখানে দিন (@ সহ)

# 🤖 API KEYS
DEEPSEEK_API_KEY = "sk-5da4d6648bbe48158c9dd2ba656ac26d"

# 💰 PAYMENT DETAILS
BKASH_NUMBER = "01846849460"    
NAGAD_NUMBER = "01846849460"    

# 🗄️ DATABASE URL
DATABASE_URL = "postgresql://postgres:hQKBupovepWPRJyTUCiqYrUfEnoeRYYv@trolley.proxy.rlwy.net:36125/railway"

# 🔴 LOG CHANNELS
ADMIN_LOG_ID = -1003769033152
PUBLIC_LOG_ID = -1003775622081

# ⚠️ Force Join
CHANNEL_ID = "@minatologs"
CHANNEL_INVITE_LINK = "https://t.me/minatologs/2"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- DB HELPERS ---
def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY, credits INTEGER, role TEXT, generated_count INTEGER DEFAULT 0, full_name TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS codes (code TEXT PRIMARY KEY, credit_amount INTEGER, role_reward TEXT, is_redeemed INTEGER DEFAULT 0)")
    c.execute("CREATE TABLE IF NOT EXISTS bonus (user_id BIGINT PRIMARY KEY, last_claim DATE)")
    conn.commit()
    conn.close()

init_db()

def is_admin(user_id):
    return user_id == ADMIN_ID

def get_user(user_id, name="User"):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
    user = c.fetchone()
    if not user:
        c.execute("INSERT INTO users (user_id, credits, role, generated_count, full_name) VALUES (%s, 50, 'Free', 0, %s)", (user_id, name))
        conn.commit()
        user = (user_id, 50, 'Free', 0, name)
    conn.close()
    return user

# --- UI HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_user(user.id, user.first_name)
    
    text = (
        f"✨ **𝐌𝐈𝐍𝐀𝐓𝐎 𝐀𝐈 𝐀𝐒𝐒𝐈𝐒𝐓𝐀𝐍𝐓** ✨\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 **User:** `{user.first_name}`\n"
        f"💎 **Credits:** `{db_user[1]}`\n"
        f"👑 **Role:** `{db_user[2]}`\n"
        f"🚀 **Requests:** `{db_user[3]}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👨‍💻 **Admin:** {ADMIN_USERNAME}\n"
        f"💡 Use `/help` to see all commands."
    )
    
    kb = [
        [InlineKeyboardButton("🧠 AI Commands", callback_data='ai_commands')],
        [InlineKeyboardButton("💰 Buy Credits", callback_data='deposit'), InlineKeyboardButton("🎁 Daily Bonus", callback_data='bonus')],
        [InlineKeyboardButton("🎫 Redeem Code", callback_data='redeem_ui')],
        [InlineKeyboardButton("📞 Contact Admin", url=f"https://t.me/{ADMIN_USERNAME.replace('@','')}")]
    ]
    
    if update.message: await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    else: await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

# --- COMMANDS SEPARATION ---
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 **USER COMMANDS**\n"
        "━━━━━━━━━━━━━━\n"
        "🔹 `/start` - Open Main Menu\n"
        "🔹 `/chat <text>` - Ask AI anything (5 Cr)\n"
        "🔹 `/image <prompt>` - Generate HD Image (20 Cr)\n"
        "🔹 `/redeem <code>` - Claim your coins\n"
        "🔹 `/help` - Show this list"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

async def admin_cmds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    text = (
        "🛠 **ADMIN CONTROL PANEL**\n"
        "━━━━━━━━━━━━━━\n"
        "🔹 `/gencoins <amt> <role>` - Create redeem code\n"
        "🔹 `/addcredit <id> <amt>` - Add coins to user\n"
        "🔹 `/stats` - View bot statistics\n"
        "📌 *Note: Codes are logged in Admin Group.*"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

# --- COIN GENERATION ---
async def gencoins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try:
        amt = int(context.args[0])
        role = context.args[1] if len(context.args) > 1 else "Premium"
        code = f"MINATO-{''.join(random.choices(string.ascii_uppercase + string.digits, k=10))}"
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("INSERT INTO codes (code, credit_amount, role_reward) VALUES (%s, %s, %s)", (code, amt, role))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"✅ **Code Generated!**\n\nCode: `{code}`\nAmount: `{amt}`\nRole: `{role}`", parse_mode='Markdown')
        await context.bot.send_message(ADMIN_LOG_ID, f"🆕 **New Code Generated**\nBy Admin: {update.effective_user.id}\nCode: `{code}`")
    except:
        await update.message.reply_text("❌ Usage: `/gencoins 500 VIP`")

async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("❌ Usage: `/redeem MINATO-CODE`")
    code = context.args[0].strip()
    uid = update.effective_user.id
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT credit_amount, role_reward FROM codes WHERE code=%s AND is_redeemed=0", (code,))
    res = c.fetchone()
    
    if res:
        c.execute("UPDATE codes SET is_redeemed=1 WHERE code=%s", (code,))
        c.execute("UPDATE users SET credits=credits+%s, role=%s WHERE user_id=%s", (res[0], res[1], uid))
        conn.commit()
        await update.message.reply_text(f"🎉 **Success!**\nYou received `{res[0]}` credits and `{res[1]}` role.")
    else:
        await update.message.reply_text("❌ Invalid or already used code.")
    conn.close()

# --- CALLBACKS ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.data == 'main_menu': await start(update, context)
    elif q.data == 'ai_commands':
        await q.message.edit_text("🧠 **AI MENU**\n\n/chat - Text AI\n/image - Gen Image\n/script - Writing", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='main_menu')]]))
    elif q.data == 'deposit':
        await q.message.edit_text("💳 **PAYMENT**\n\nBkash/Nagad: `01846849460`\nSend money & send SS here.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='main_menu')]]))
    elif q.data == 'redeem_ui':
        await q.answer("Use command: /redeem <code>", show_alert=True)

def main():
    app = Application.builder().token(TOKEN).build()
    
    # User Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("redeem", redeem))
    
    # Admin Handlers
    app.add_handler(CommandHandler("cmds", admin_cmds))
    app.add_handler(CommandHandler("gencoins", gencoins))
    
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    print("Minato Bot is Running...")
    app.run_polling()

if __name__ == '__main__':
    main()
