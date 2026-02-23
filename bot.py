import telebot
import requests
import os
import psutil
import psycopg2
from openai import OpenAI
from io import BytesIO

# ==========================================
# Configuration (Syntax Error Fixed)
# ==========================================
# os.getenv এর কাজ হলো Railway Variables থেকে ডাটা নেওয়া। 
# যদি ভেরিয়েবল না থাকে, তাহলে কমার (,) পরের অংশটুকু কাজ করবে।
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8718001559:AAEJNbpg2BqFqujbjdVIYQMKa4bHO2b4S4I")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-5da4d6648bbe48158c9dd2ba656ac26d")

# Railway তে Postgres অ্যাড করলে এই DATABASE_URL টি অটোমেটিক পেয়ে যাবেন
DATABASE_URL = os.getenv("postgresql://postgres:cIJaXIJvmBepjzPcXskiJgFPwvkLdlEA@maglev.proxy.rlwy.net:22522/railway") 

OWNER_ID = 6198703244  

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

# ==========================================
# Database Setup (PostgreSQL)
# ==========================================
def get_db_connection():
    # PostgreSQL ডাটাবেসের সাথে কানেক্ট করার ফাংশন
    return psycopg2.connect(DATABASE_URL)

def setup_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Users Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            name TEXT,
            coins INTEGER,
            role TEXT,
            queries INTEGER
        )
    ''')
    
    # Bot Stats Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_stats (
            id INTEGER PRIMARY KEY,
            total_queries INTEGER
        )
    ''')
    # ON CONFLICT হচ্ছে Postgres এর স্পেশাল রুল (SQLite এর INSERT OR IGNORE এর মতো)
    cursor.execute('INSERT INTO bot_stats (id, total_queries) VALUES (1, 0) ON CONFLICT (id) DO NOTHING')
    
    conn.commit()
    cursor.close()
    conn.close()

FREE_COINS = 5

def init_user(user):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = %s', (user.id,))
    if not cursor.fetchone():
        cursor.execute('INSERT INTO users (user_id, name, coins, role, queries) VALUES (%s, %s, %s, %s, %s)',
                       (user.id, user.first_name, FREE_COINS, 'free', 0))
    else:
        cursor.execute('UPDATE users SET name = %s WHERE user_id = %s', (user.first_name, user.id))
    conn.commit()
    cursor.close()
    conn.close()

def deduct_coin(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT coins FROM users WHERE user_id = %s', (user_id,))
    result = cursor.fetchone()
    success = False
    if result and result[0] > 0:
        cursor.execute('UPDATE users SET coins = coins - 1, queries = queries + 1 WHERE user_id = %s', (user_id,))
        cursor.execute('UPDATE bot_stats SET total_queries = total_queries + 1 WHERE id = 1')
        success = True
    conn.commit()
    cursor.close()
    conn.close()
    return success

def get_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT name, coins, role, queries FROM users WHERE user_id = %s', (user_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result

# ==========================================
# Bot Commands
# ==========================================

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    init_user(message.from_user)
    user_data = get_user(message.from_user.id)
    
    welcome_text = (
        f"👋 Swagatom {user_data[0]}! Ami ekta Advanced AI Bot.\n\n"
        "Amar madhyome apni ja ja korte parben:\n"
        "📝 /script [topic] - DeepSeek AI diye script/chat (1 Coin)\n"
        "🎨 /photo [prompt] - AI Image generation (1 Coin)\n"
        "👤 /status - Apnar profile ar coins dekhun\n"
        "💎 /premium - Premium subscription nite click korun"
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['status'])
def user_status(message):
    init_user(message.from_user)
    user_data = get_user(message.from_user.id)
    
    role_badge = "🌟 Premium" if user_data[2] == 'premium' else "👤 Free"
    
    status_text = (
        f"📋 **APNAR PROFILE STATUS** 📋\n\n"
        f"Name: {user_data[0]}\n"
        f"Role: {role_badge}\n"
        f"Coins: 🪙 {user_data[1]}\n"
        f"Total Used: ⚡ {user_data[3]} times"
    )
    bot.reply_to(message, status_text)

@bot.message_handler(commands=['stats'])
def admin_stats(message):
    if message.from_user.id != OWNER_ID:
        return
    
    try:
        owner_name = bot.get_chat(OWNER_ID).first_name
    except:
        owner_name = "Admin"

    cpu_usage = psutil.cpu_percent(interval=0.5)
    ram_usage = psutil.virtual_memory().percent
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'premium'")
    premium_users = cursor.fetchone()[0]
    free_users = total_users - premium_users

    cursor.execute('SELECT total_queries FROM bot_stats WHERE id = 1')
    total_queries = cursor.fetchone()[0]
    
    cursor.close()
    conn.close()

    stats_text = (
        f"👑 **OWNER**: {owner_name}\n\n"
        f"🖥️ **SERVER ACTIVITIES**\n"
        f"├ CPU Usage: {cpu_usage}%\n"
        f"└ RAM Usage: {ram_usage}%\n\n"
        f"📊 **BOT STATISTICS**\n"
        f"├ Total Users: {total_users}\n"
        f"├ Premium Users: {premium_users}\n"
        f"├ Free Users: {free_users}\n"
        f"└ Total Bot Queries: {total_queries}"
    )
    bot.reply_to(message, stats_text)

@bot.message_handler(commands=['premium', 'buy'])
def premium_menu(message):
    payment_info = (
        "💎 **PREMIUM SUBSCRIPTION & COINS** 💎\n\n"
        "🪙 100 Coins = 100 Taka\n"
        "🪙 500 Coins = 400 Taka\n\n"
        "💳 **Payment Methods:**\n"
        "🟢 bKash (Personal): 017XXXXXXXX\n"
        "🟠 Nagad (Personal): 017XXXXXXXX\n"
        "🟡 Binance Pay ID: 123456789\n\n"
        "Payment kore TrxID ba screenshot Admin er kache pathan."
    )
    bot.reply_to(message, payment_info)

@bot.message_handler(commands=['script', 'chat', 'code'])
def generate_script(message):
    init_user(message.from_user)
    user_id = message.from_user.id
    prompt = message.text.replace('/script', '').replace('/chat', '').replace('/code', '').strip()
    
    if not prompt:
        bot.reply_to(message, "Topic likhun. Jemon: /script ekta python bot er code dao")
        return

    if deduct_coin(user_id):
        bot.send_message(message.chat.id, "⏳ DeepSeek apnar uttor toiri korche...")
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "You are an expert AI assistant and developer."},
                    {"role": "user", "content": prompt}
                ]
            )
            reply_text = response.choices[0].message.content
            current_coins = get_user(user_id)[1]
            bot.reply_to(message, f"{reply_text}\n\n🪙 Baki Coins: {current_coins}")
        except Exception as e:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET coins = coins + 1 WHERE user_id = %s', (user_id,))
            conn.commit()
            cursor.close()
            conn.close()
            bot.reply_to(message, f"❌ Somossa hoyeche: {e}")
    else:
        bot.reply_to(message, "❌ Apnar Coin sesh! Notun coin nite /premium e click korun.")

@bot.message_handler(commands=['photo', 'image'])
def generate_photo(message):
    init_user(message.from_user)
    user_id = message.from_user.id
    prompt = message.text.replace('/photo', '').replace('/image', '').strip()
    
    if not prompt:
        bot.reply_to(message, "Details likhun. Jemon: /photo a neon futuristic city")
        return

    if deduct_coin(user_id):
        bot.send_message(message.chat.id, "🎨 Chobi generate hocche...")
        try:
            image_url = f"https://image.pollinations.ai/prompt/{prompt}?width=1024&height=1024&nologo=true"
            response = requests.get(image_url)
            
            if response.status_code == 200:
                image_bytes = BytesIO(response.content)
                current_coins = get_user(user_id)[1]
                bot.send_photo(message.chat.id, image_bytes, caption=f"✨ Apnar Chobi.\n🪙 Baki Coins: {current_coins}")
            else:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('UPDATE users SET coins = coins + 1 WHERE user_id = %s', (user_id,))
                conn.commit()
                cursor.close()
                conn.close()
                bot.reply_to(message, "❌ Chobi generate korte parini.")
        except Exception as e:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET coins = coins + 1 WHERE user_id = %s', (user_id,))
            conn.commit()
            cursor.close()
            conn.close()
            bot.reply_to(message, f"❌ Somossa hoyeche: {e}")
    else:
        bot.reply_to(message, "❌ Apnar Coin sesh! Notun coin nite /premium e click korun.")

@bot.message_handler(commands=['addcoin'])
def add_coin_and_premium(message):
    if message.from_user.id != OWNER_ID:
        return
    
    try:
        args = message.text.split()
        target_id = int(args[1])
        coins_to_add = int(args[2])
        new_role = args[3].lower() if len(args) > 3 else "free"
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE user_id = %s', (target_id,))
        if not cursor.fetchone():
            bot.reply_to(message, "Ei user ke bot ektuo use koreni ekhono.")
            cursor.close()
            conn.close()
            return
            
        cursor.execute('UPDATE users SET coins = coins + %s, role = %s WHERE user_id = %s', (coins_to_add, new_role, target_id))
        conn.commit()
        cursor.close()
        conn.close()
        
        updated_data = get_user(target_id)
        bot.reply_to(message, f"✅ User {target_id} ke {coins_to_add} coins deya hoyeche. Role: {new_role}.")
        bot.send_message(target_id, f"🎉 Admin apnake {coins_to_add} notun Coins ar '{new_role.capitalize()}' role diyeche! Ekhon apnar total coins: {updated_data[1]}")
    except Exception as e:
        bot.reply_to(message, "Sothik format: /addcoin user_id coin_amount role (e.g., /addcoin 12345678 100 premium)")

if __name__ == "__main__":
    if DATABASE_URL:
        print("🤖 Setup hocche PostgreSQL Database...")
        setup_db()
        print("🤖 Bot is starting up safely...")
        bot.polling(non_stop=True, timeout=60, long_polling_timeout=60)
    else:
        print("❌ ERROR: DATABASE_URL paoa jacche na! Railway te Postgres Database add korun.")