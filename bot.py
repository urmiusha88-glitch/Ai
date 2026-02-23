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
TOKEN = "8290942305:AAGFtnKV8P5xk591NejJ5hsKEJ02foiRpEk"
ADMIN_ID = 6198703244  

# 🤖 API KEYS
DEEPSEEK_API_KEY = "sk-5da4d6648bbe48158c9dd2ba656ac26d"

# 💰 PAYMENT DETAILS
BKASH_NUMBER = "01846849460"    
NAGAD_NUMBER = "01846849460"    

# 🗄️ DATABASE URL
DATABASE_URL = "postgresql://postgres:hQKBupovepWPRJyTUCiqYrUfEnoeRYYv@trolley.proxy.rlwy.net:36125/railway"

# 🔴 GROUP & CHANNEL IDS
ADMIN_LOG_ID = -1003769033152
PUBLIC_LOG_ID = -1003775622081

# ⚠️ Force Join Channel
CHANNEL_ID = "@minatologs"
CHANNEL_INVITE_LINK = "https://t.me/minatologs/2"

FB_ID_LINK ="https://www.facebook.com/yours.ononto"
# ======================================================

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

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

def is_admin(user_id):
    if user_id == ADMIN_ID: return True
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
        c.execute("INSERT INTO users (user_id, credits, role, generated_count, full_name) VALUES (%s, 50, 'Free', 0, %s)", (user_id, first_name))
        conn.commit()
        user = (user_id, 50, 'Free', 0, first_name)
    conn.close()
    return user

async def check_join(user_id, context):
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status not in ['left', 'kicked']
    except: return True

def deduct_credits(user_id, amount):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET credits = credits - %s, generated_count = generated_count + 1 WHERE user_id=%s", (amount, user_id))
    conn.commit()
    conn.close()

async def generate_deepseek_response(prompt, system_instruction="You are a helpful AI assistant."):
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    data = {"model": "deepseek-chat", "messages": [{"role": "system", "content": system_instruction}, {"role": "user", "content": prompt}]}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post("https://api.deepseek.com/chat/completions", json=data, headers=headers, timeout=60.0)
            return response.json()['choices'][0]['message']['content']
        except Exception as e: return f"❌ AI Error: {e}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await check_join(user.id, context):
        await update.message.reply_text("❌ Join @minatologs first!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Join Channel", url=CHANNEL_INVITE_LINK)]]))
        return
    
    db_user = get_user(user.id, user.first_name)
    text = f"🤖 **MINATO AI ASSISTANT**\n\n👤 **User:** {user.first_name}\n💎 **Credits:** {db_user[1]}\n🚀 **Used:** {db_user[3]}"
    kb = [
        [InlineKeyboardButton("🧠 AI Commands", callback_data='ai_commands')],
        [InlineKeyboardButton("💰 Buy Credits", callback_data='deposit_info'), InlineKeyboardButton("🎁 Bonus", callback_data='daily_bonus')],
        [InlineKeyboardButton("🎫 Redeem Code", callback_data='redeem_btn')]
    ]
    if update.message: await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    else: await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

async def ai_commands_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🧠 **AI COMMANDS**\n\n🔹 `/chat` (5 Cr)\n🔹 `/script` (10 Cr)\n🔹 `/code` (10 Cr)\n🔹 `/image` (20 Cr)"
    await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='main_menu')]]), parse_mode='Markdown')

async def ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    prompt = " ".join(context.args)
    if not prompt: return await update.message.reply_text("Usage: `/chat your message`")
    
    db_user = get_user(user_id)
    if db_user[1] < 5: return await update.message.reply_text("❌ Not enough credits!")
    
    msg = await update.message.reply_text("⏳ Thinking...")
    res = await generate_deepseek_response(prompt)
    deduct_credits(user_id, 5)
    await msg.edit_text(f"💡 **AI:**\n\n{res}", parse_mode='Markdown')

async def ai_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    prompt = " ".join(context.args)
    if not prompt: return await update.message.reply_text("Usage: `/image prompt`")
    
    db_user = get_user(user_id)
    if db_user[1] < 20: return await update.message.reply_text("❌ Not enough credits!")
    
    msg = await update.message.reply_text("🎨 Generating...")
    url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}"
    await update.message.reply_photo(photo=url, caption=f"🎨 **Prompt:** {prompt}")
    deduct_credits(user_id, 20)
    await msg.delete()

async def deposit_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "💸 **BUY CREDITS**\n\n🟢 50 BDT -> 200 Cr\n🔵 100 BDT -> 500 Cr\n\nSelect Method:"
    kb = [[InlineKeyboardButton("🟣 Bkash", callback_data='method_bkash'), InlineKeyboardButton("🟠 Nagad", callback_data='method_nagad')], [InlineKeyboardButton("🔙 Back", callback_data='main_menu')]]
    await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

async def payment_method_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    method = query.data.split('_')[1]
    context.user_data['deposit_method'] = method
    context.user_data['waiting_for_proof'] = 'deposit_ss'
    num = BKASH_NUMBER if method == 'bkash' else NAGAD_NUMBER
    await query.message.edit_text(f"💳 **{method.upper()}**\n\nNumber: `{num}`\n\nSend money and send **Screenshot** here.")

async def handle_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('waiting_for_proof') == 'deposit_ss':
        context.user_data['deposit_photo'] = update.message.photo[-1].file_id
        context.user_data['waiting_for_proof'] = 'deposit_trxid'
        await update.message.reply_text("✅ Screenshot received! Now send the **TrxID**.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('waiting_for_proof') == 'deposit_trxid':
        trxid = update.message.text
        photo = context.user_data.get('deposit_photo')
        method = context.user_data.get('deposit_method')
        user = update.effective_user
        caption = f"💰 **NEW DEPOSIT**\nUser: {user.first_name} ({user.id})\nMethod: {method}\nTrxID: {trxid}"
        kb = [[InlineKeyboardButton("Approve 500Cr", callback_data=f"pay_{user.id}_500_Basic")], [InlineKeyboardButton("❌ Reject", callback_data="reject_action")]]
        await context.bot.send_photo(chat_id=ADMIN_LOG_ID, photo=photo, caption=caption, reply_markup=InlineKeyboardMarkup(kb))
        await update.message.reply_text("✅ Request sent to Admin!")
        context.user_data.clear()

async def btn_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.data == 'main_menu': await start(update, context)
    elif q.data == 'ai_commands': await ai_commands_menu(update, context)
    elif q.data == 'deposit_info': await deposit_info(update, context)
    elif q.data.startswith('method_'): await payment_method_handler(update, context)
    elif q.data.startswith('pay_'):
        parts = q.data.split("_")
        conn = get_db_connection(); c = conn.cursor()
        c.execute("UPDATE users SET credits = credits + %s WHERE user_id=%s", (int(parts[2]), int(parts[1])))
        conn.commit(); conn.close()
        await q.answer("✅ Approved!"); await q.message.edit_caption("✅ Approved")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("chat", ai_chat))
    app.add_handler(CommandHandler("image", ai_image))
    app.add_handler(CallbackQueryHandler(btn_handler))
    app.add_handler(MessageHandler(filters.PHOTO, handle_screenshot))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("🤖 Bot Live!")
    app.run_polling()

if __name__ == '__main__':
    main()
