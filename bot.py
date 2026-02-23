import logging
import psycopg2
import random
import string
import os
import urllib.parse
import httpx
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

# ======================================================
# 👇 CONFIGURATION SECTION
# ======================================================
TOKEN = "8290942305:AAGFtnKV8P5xk591NejJ5hsKEJ02foiRpEk"  # ⚠️ BotFather থেকে পাওয়া টোকেনটি বসান
ADMIN_ID = 6198703244  # Your Telegram ID (MAIN OWNER)

# 🤖 API KEYS
DEEPSEEK_API_KEY = "sk-5da4d6648bbe48158c9dd2ba656ac26d"

# 💰 PAYMENT DETAILS
BKASH_NUMBER = "01846849460"    
NAGAD_NUMBER = "01846849460"    
BINANCE_PAY_ID = "Unavailable"  

# 🗄️ DATABASE URL
DATABASE_URL = "postgresql://postgres:hQKBupovepWPRJyTUCiqYrUfEnoeRYYv@trolley.proxy.rlwy.net:36125/railway"

# 🔴 GROUP & CHANNEL IDS
ADMIN_LOG_ID = -1003769033152
PUBLIC_LOG_ID = -1003775622081

# ⚠️ Force Join Channel
CHANNEL_ID = "@minatologs"
CHANNEL_INVITE_LINK = "https://t.me/minatologs/2"

# ======================================================
FB_ID_LINK ="https://www.facebook.com/yours.ononto"
FB_PAGE_LINK = "https://www.facebook.com/toxicnaaa69"
# ======================================================

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- DATABASE CONNECTION HELPER ---
def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

# --- INIT DATABASE ---
def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id BIGINT PRIMARY KEY, credits INTEGER, role TEXT, generated_count INTEGER DEFAULT 0, full_name TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS codes 
                 (code TEXT PRIMARY KEY, credit_amount INTEGER, role_reward TEXT, is_redeemed INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS admins 
                 (admin_id BIGINT PRIMARY KEY)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bonus 
                 (user_id BIGINT PRIMARY KEY, last_claim DATE)''')
    conn.commit()
    conn.close()

init_db()

# --- HELPER FUNCTIONS ---
def is_admin(user_id):
    if user_id == ADMIN_ID:
        return True
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM admins WHERE admin_id=%s", (user_id,))
    res = c.fetchone()
    conn.close()
    return bool(res)

def get_user(user_id, first_name="Unknown"):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
    user = c.fetchone()
    if not user:
        # New users get 50 free credits to test the AI
        c.execute("INSERT INTO users (user_id, credits, role, generated_count, full_name) VALUES (%s, %s, %s, 0, %s)", (user_id, 50, 'Free', first_name))
        conn.commit()
        user = (user_id, 50, 'Free', 0, first_name)
    else:
        if first_name != "Unknown":
            c.execute("UPDATE users SET full_name=%s WHERE user_id=%s", (first_name, user_id))
            conn.commit()
    conn.close()
    return user

async def check_join(user_id, context):
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if member.status in ['left', 'kicked']: return False
        return True
    except: 
        return True 

def deduct_credits(user_id, amount):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET credits = credits - %s, generated_count = generated_count + 1 WHERE user_id=%s", (amount, user_id))
    conn.commit()
    conn.close()

# --- AI INTEGRATION (DEEPSEEK) ---
async def generate_deepseek_response(prompt, system_instruction="You are a helpful AI assistant."):
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt}
        ]
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post("https://api.deepseek.com/chat/completions", json=data, headers=headers, timeout=60.0)
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content']
        except Exception as e:
            return f"❌ AI Error: {e}"

# --- HANDLERS ---

# 1. MAIN MENU UI
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await check_join(user.id, context):
        await update.message.reply_text(
            f"❌ **ACCESS DENIED**\n\n⚠️ You must join our official channel to use this bot.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Join Channel First", url=CHANNEL_INVITE_LINK)]])
        )
        return

    db_user = get_user(user.id, user.first_name)
    
    welcome_text = (
        f"🤖 **𝐌𝐈𝐍𝐀𝐓𝐎 𝐀𝐈 𝐀𝐒𝐒𝐈𝐒𝐓𝐀𝐍𝐓** 🤖\n"
        f"▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱\n"
        f"👋 **Welcome, {user.first_name}!**\n"
        f"Powered by Advanced DeepSeek AI 🧠\n\n"
        f"👤 **𝐀𝐜𝐜𝐨𝐮𝐧𝐭 𝐈𝐧𝐟𝐨𝐫𝐦𝐚𝐭𝐢𝐨𝐧:**\n"
        f"├ 🆔 **ID:** `{user.id}`\n"
        f"├ 💎 **Credits:** `{db_user[1]}`\n"
        f"├ 👑 **Role:** `{db_user[2]}`\n"
        f"└ 🚀 **AI Requests:** `{db_user[3]}`\n\n"
        f"💡 **Use Commands like:** `/chat`, `/image`, `/script`, `/code`\n"
        f"▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱"
    )
    
    keyboard = [
        [InlineKeyboardButton("🧠 AI Commands", callback_data='ai_commands')],
        [InlineKeyboardButton("💰 Buy Credits", callback_data='deposit_info'), InlineKeyboardButton("🎁 Daily Bonus", callback_data='daily_bonus')],
        [InlineKeyboardButton("🎫 Redeem Code", callback_data='redeem_btn')],
        [InlineKeyboardButton("👨‍💻 Admin Support", url=f"tg://user?id={ADMIN_ID}")] 
    ]
    
    if update.message: await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else: 
        try: await update.callback_query.message.edit_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        except: pass

async def ai_commands_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🧠 **𝐀𝐈 𝐂𝐎𝐌𝐌𝐀𝐍𝐃𝐒 𝐋𝐈𝐒𝐓**\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 `/chat <your message>` - General AI Chat (5 Cr)\n"
        "🔹 `/script <topic>` - YouTube/TikTok Scripts (10 Cr)\n"
        "🔹 `/code <prompt>` - Coding & Debugging (10 Cr)\n"
        "🔹 `/image <prompt>` - Generate HD Images (20 Cr)\n\n"
        "Example: `/image A futuristic cyber city at night`"
    )
    kb = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data='main_menu')]]
    await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

# --- AI COMMANDS ---

async def ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await check_join(user_id, context): return
    
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("⚠️ Usage: `/chat Hello, how are you?`", parse_mode='Markdown')
        return

    db_user = get_user(user_id)
    if db_user[1] < 5:
        await update.message.reply_text("❌ Not enough credits! You need 5 Credits for this. Please deposit.")
        return

    msg = await update.message.reply_text("⏳ Thinking...")
    response = await generate_deepseek_response(prompt)
    deduct_credits(user_id, 5)
    await msg.edit_text(f"💡 **DeepSeek:**\n\n{response}", parse_mode='Markdown')

async def ai_script(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await check_join(user_id, context): return
    
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("⚠️ Usage: `/script A 60-second TikTok video about space travel`", parse_mode='Markdown')
        return

    db_user = get_user(user_id)
    if db_user[1] < 10:
        await update.message.reply_text("❌ Not enough credits! You need 10 Credits for this.")
        return

    msg = await update.message.reply_text("📝 Writing your script...")
    sys_prompt = "You are an expert scriptwriter for YouTube and TikTok. Write engaging, viral scripts with visual cues."
    response = await generate_deepseek_response(prompt, sys_prompt)
    deduct_credits(user_id, 10)
    await msg.edit_text(f"🎬 **Your Script:**\n\n{response}", parse_mode='Markdown')

async def ai_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await check_join(user_id, context): return
    
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("⚠️ Usage: `/code Write a python telegram bot`", parse_mode='Markdown')
        return

    db_user = get_user(user_id)
    if db_user[1] < 10:
        await update.message.reply_text("❌ Not enough credits! You need 10 Credits for this.")
        return

    msg = await update.message.reply_text("💻 Coding...")
    sys_prompt = "You are an expert senior programmer. Provide clean, efficient code with minimal explanation."
    response = await generate_deepseek_response(prompt, sys_prompt)
    deduct_credits(user_id, 10)
    await msg.edit_text(f"👨‍💻 **Code Result:**\n\n{response}", parse_mode='Markdown')

async def ai_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await check_join(user_id, context): return
    
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("⚠️ Usage: `/image A cute cat wearing sunglasses`", parse_mode='Markdown')
        return

    db_user = get_user(user_id)
    if db_user[1] < 20:
        await update.message.reply_text("❌ Not enough credits! You need 20 Credits for Image Generation.")
        return

    msg = await update.message.reply_text("🎨 Generating high-quality image...")
    # Using Pollinations AI for free image generation
    image_url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}"
    
    try:
        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=image_url, caption=f"🎨 **Prompt:** {prompt}\n\n⚡ Generated by Minato AI", parse_mode='Markdown')
        deduct_credits(user_id, 20)
        await msg.delete()
    except Exception as e:
        await msg.edit_text("❌ Error generating image. Please try a different prompt.")

# --- DAILY BONUS ---
async def daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    if not await check_join(user_id, context):
        await query.answer("❌ Join Channel First!", show_alert=True)
        return

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT last_claim FROM bonus WHERE user_id=%s", (user_id,))
    res = c.fetchone()
    today = date.today()
    
    if res and res[0] == today:
        await query.answer("❌ You already claimed your bonus today! Come back tomorrow.", show_alert=True)
    else:
        bonus_amount = random.randint(15, 50)
        c.execute("UPDATE users SET credits = credits + %s WHERE user_id=%s", (bonus_amount, user_id))
        if res:
            c.execute("UPDATE bonus SET last_claim=%s WHERE user_id=%s", (today, user_id))
        else:
            c.execute("INSERT INTO bonus (user_id, last_claim) VALUES (%s, %s)", (user_id, today))
        conn.commit()
        await query.answer(f"🎉 Awesome! You received {bonus_amount} Free Credits today!", show_alert=True)
        
    conn.close()
    await start(update, context)


# --- DEPOSIT INFO & METHOD SELECTION ---
async def deposit_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "💸 **𝐁𝐔𝐘 𝐀𝐈 𝐂𝐑𝐄𝐃𝐈𝐓𝐒**\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🟢 **Starter Plan:** 50 BDT / $0.50 ➔ 200 Credits\n"
        "🔵 **Basic Plan:** 100 BDT / $1.00 ➔ 500 Credits\n"
        "🟣 **Pro Plan:** 300 BDT / $3.00 ➔ 2500 Credits\n"
        "⚡ **Max Plan:** 1000 BDT / $10.00 ➔ 10,000 Credits\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "👇 **SELECT PAYMENT METHOD:**"
    )
    kb = [
        [InlineKeyboardButton("🟣 Bkash", callback_data='method_bkash'), InlineKeyboardButton("🟠 Nagad", callback_data='method_nagad')],
        [InlineKeyboardButton("🟡 Binance Pay", callback_data='method_binance')],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data='main_menu')]
    ]
    if update.callback_query: 
        await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

async def payment_method_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    method = query.data.split('_')[1] 
    
    context.user_data['deposit_method'] = method
    context.user_data['waiting_for_proof'] = 'deposit_ss'

    if method == 'bkash':
        details = f"📱 **Bkash Personal:** `{BKASH_NUMBER}`"
    elif method == 'nagad':
        details = f"📱 **Nagad Personal:** `{NAGAD_NUMBER}`"
    else:
        details = f"🟡 **Binance Pay ID:** `{BINANCE_PAY_ID}`"

    text = (
        f"💳 **PAY VIA {method.upper()}**\n\n"
        f"{details}\n\n"
        "⚠️ **STEP 1:** Send the money to the details above.\n"
        "⚠️ **STEP 2:** Send the payment **Screenshot** here."
    )
    kb = [[InlineKeyboardButton("🔙 Back to Deposit", callback_data='deposit_info')]]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

# --- SCREENSHOT LOGS ---
async def handle_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    photo = update.message.photo[-1].file_id
    state = context.user_data.get('waiting_for_proof')
    
    if state == 'deposit_ss':
        context.user_data['deposit_photo'] = photo
        context.user_data['waiting_for_proof'] = 'deposit_trxid'
        await update.message.reply_text(
            "✅ **Screenshot Received!**\n\n"
            "📝 Now, please type and send the **Transaction ID (TrxID)** or Binance Order ID."
        )
    else:
        pass

# --- TEXT HANDLER FOR TRXID ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('waiting_for_proof')
    if state == 'deposit_trxid':
        trxid = update.message.text
        photo = context.user_data.get('deposit_photo')
        method = context.user_data.get('deposit_method', 'Unknown').upper()
        user = update.effective_user
        user_link = f"[{user.first_name}](tg://user?id={user.id})"

        caption = (
            f"💰 **NEW DEPOSIT REQUEST**\n"
            f"👤 From: {user_link} (`{user.id}`)\n"
            f"💳 Method: `{method}`\n"
            f"🧾 **TrxID:** `{trxid}`\n\n"
            f"ℹ️ Verify TrxID & Approve:"
        )
        keyboard = [
            [InlineKeyboardButton("Starter (200 Cr)", callback_data=f"pay_{user.id}_200_Starter")],
            [InlineKeyboardButton("Basic (500 Cr)", callback_data=f"pay_{user.id}_500_Basic")],
            [InlineKeyboardButton("Pro (2500 Cr)", callback_data=f"pay_{user.id}_2500_Pro")],
            [InlineKeyboardButton("Ultra (4500 Cr)", callback_data=f"pay_{user.id}_4500_Ultra")],
            [InlineKeyboardButton("Max (10000 Cr)", callback_data=f"pay_{user.id}_10000_Max")],
            [InlineKeyboardButton("❌ Reject", callback_data="reject_action")]
        ]
        
        await update.message.reply_text("✅ **Deposit Request Sent!**\nPlease wait for admin approval.")
        
        try: 
            await context.bot.send_photo(chat_id=ADMIN_LOG_ID, photo=photo, caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        except Exception as e: 
            pass

        context.user_data['waiting_for_proof'] = None
        context.user_data['deposit_photo'] = None
        context.user_data['deposit_method'] = None

# --- ADMIN ACTIONS ---
async def admin_log_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id): return
    data = query.data
    conn = get_db_connection()
    c = conn.cursor()

    if data.startswith("pay_"):
        parts = data.split("_")
        target_id, amount, plan = int(parts[1]), int(parts[2]), parts[3]
        c.execute("UPDATE users SET credits = credits + %s, role = %s WHERE user_id=%s", (amount, plan, target_id))
        conn.commit()
        await query.answer(f"✅ Approved {plan}!")
        await query.message.edit_caption(caption=query.message.caption + f"\n\n✅ **APPROVED: {plan}**")
        try: await context.bot.send_message(target_id, f"✅ **Payment Received!**\nPackage: {plan}\nCredits: +{amount}")
        except: pass
        try: await context.bot.send_message(PUBLIC_LOG_ID, f"⚡ **AI CREDITS PURCHASED!**\n👤 User: `{target_id}`\n💎 Plan: `{plan}`", parse_mode='Markdown')
        except: pass

    elif data == "reject_action":
        await query.message.delete()
        
    conn.close()

# --- ADMIN COMMANDS ---
async def active_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT full_name, user_id, credits, generated_count FROM users ORDER BY generated_count DESC LIMIT 10")
    users = c.fetchall()
    conn.close()
    if not users:
        await update.message.reply_text("❌ No active users.")
        return
    msg = f"📊 **TOP AI USERS**\n━━━━━━━━━━━━━━━━━━\n"
    for i, u in enumerate(users, 1):
        name = u[0] if u[0] else "User"
        mention = f"[{name}](tg://user?id={u[1]})"
        msg += f"{i}. {mention} | 💰 {u[2]} | 🚀 **{u[3]}**\n"
    await update.message.reply_text(msg, parse_mode='Markdown')

def generate_minato_code(role_tag="PREMIUM"):
    part1 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    part2 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    return f"MINATO-{part1}-{part2}-{role_tag.upper()}"

async def gen_code_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try:
        amt = int(context.args[0])
        role = context.args[1].upper() if len(context.args) > 1 else "PREMIUM"
        code = generate_minato_code(role)
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("INSERT INTO codes (code, credit_amount, role_reward, is_redeemed) VALUES (%s,%s,%s,0)", (code, amt, role))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"`{code}`")
    except: pass

async def add_credit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try:
        tid, amt = int(context.args[0]), int(context.args[1])
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("UPDATE users SET credits=credits+%s WHERE user_id=%s", (amt, tid))
        conn.commit()
        conn.close()
        await update.message.reply_text("✅ Done")
    except: pass

async def redeem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        code = context.args[0].strip(); uid = update.effective_user.id
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM codes WHERE code=%s AND is_redeemed=0", (code,))
        res = c.fetchone()
        if res:
            c.execute("UPDATE codes SET is_redeemed=1 WHERE code=%s", (code,))
            c.execute("UPDATE users SET credits=credits+%s, role=%s WHERE user_id=%s", (res[1], res[2], uid))
            conn.commit()
            await update.message.reply_text(f"✅ Redeemed {res[1]} Cr!")
            try: await context.bot.send_message(PUBLIC_LOG_ID, f"⚡ **REDEEMED!**\n👤 User: `{uid}`\n💎 Role: `{res[2]}`", parse_mode='Markdown')
            except: pass
        else: await update.message.reply_text("❌ Invalid.")
        conn.close()
    except: await update.message.reply_text("Usage: `/redeem CODE`")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🛠 **AI COMMANDS & HELP**\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 `/start` - Open the main menu\n"
        "🔹 `/chat <msg>` - Ask AI anything\n"
        "🔹 `/image <prompt>` - Generate HD Images\n"
        "🔹 `/script <topic>` - Write Video Scripts\n"
        "🔹 `/code <prompt>` - Programming help\n"
        "🔹 `/redeem <code>` - Redeem credit code\n\n"
        f"👨‍💻 **Contact Admin:** [Ononto Hasan](tg://user?id={ADMIN_ID})\n"
        f"🌐 **Facebook:** [Official Profile]({FB_ID_LINK})"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

# --- MAIN CALLBACK HANDLER ---
async def btn_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.data.startswith(('pay_', 'reject_')): await admin_log_actions(update, context)
    elif q.data in ['profile', 'main_menu']: await start(update, context)
    elif q.data == 'ai_commands': await ai_commands_menu(update, context)
    elif q.data == 'deposit_info': await deposit_info(update, context)
    elif q.data == 'daily_bonus': await daily_bonus(update, context)
    elif q.data.startswith('method_'): await payment_method_handler(update, context)
    elif q.data == 'redeem_btn': await q.answer(); await q.message.reply_text("Type `/redeem CODE`")

def main():
    print("🤖 MINATO AI Bot Started...")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command)) 
    app.add_handler(CommandHandler("chat", ai_chat)) 
    app.add_handler(CommandHandler("script", ai_script)) 
    app.add_handler(CommandHandler("code", ai_code)) 
    app.add_handler(CommandHandler("image", ai_image)) 
    app.add_handler(CommandHandler("active", active_users_command))
    app.add_handler(CommandHandler("gencode", gen_code_command))
    app.add_handler(CommandHandler("addcredit", add_credit_command))
    app.add_handler(CommandHandler("redeem", redeem_command))
    app.add_handler(MessageHandler(filters.PHOTO, handle_screenshot))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(btn_handler))
    app.run_polling()

if __name__ == '__main__':
    main()
