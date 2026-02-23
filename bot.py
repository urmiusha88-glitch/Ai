import telebot
import requests
import psutil
import psycopg2
from openai import OpenAI
from io import BytesIO

# ==========================================
# ⚙️ Configuration (100% Fixed & Direct)
# ==========================================
# os.getenv বাদ দিয়ে সরাসরি টোকেন বসানো হয়েছে। আর কোনো Error আসবে না!
TELEGRAM_BOT_TOKEN = "8718001559:AAEJNbpg2BqFqujbjdVIYQMKa4bHO2b4S4I"
DEEPSEEK_API_KEY = "sk-5da4d6648bbe48158c9dd2ba656ac26d"
DATABASE_URL = "postgresql://postgres:hQKBupovepWPRJyTUCiqYrUfEnoeRYYv@trolley.proxy.rlwy.net:36125/railway"

OWNER_ID = 6198703244  

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

# ==========================================
# 🗄️ Database Setup (PostgreSQL)
# ==========================================
def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def setup_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            name TEXT,
            coins INTEGER,
            role TEXT,
            queries INTEGER
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_stats (
            id INTEGER PRIMARY KEY,
            total_queries INTEGER
        )
    ''')
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
# 🤖 Bot Commands & Updated UI
# ==========================================

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    init_user(message.from_user)
    user_data = get_user(message.from_user.id)
    
    welcome_text = (
        f"🤖 **স্বাগতম, {user_data[0]}!**\n"
        "আমি একটি অত্যাধুনিক AI Bot, যা আপনার দৈনন্দিন কাজকে আরও সহজ করবে।\n\n"
        "⚡ **সার্ভিসসমূহ:**\n"
        "📝 `/script [বিষয়]` - DeepSeek AI দিয়ে চ্যাট, কোডিং বা স্ক্রিপ্ট (১ কয়েন)\n"
        "🎨 `/photo [বর্ণনা]` - AI দিয়ে হাই-কোয়ালিটি ছবি জেনারেট (১ কয়েন)\n\n"
        "📊 **অ্যাকাউন্ট ও অন্যান্য:**\n"
        "👤 `/status` - আপনার প্রোফাইল ও কয়েন দেখুন\n"
        "💎 `/premium` - আরও কয়েন ও প্রিমিয়াম রোল কিনুন\n"
        "👨‍💻 `/developer` - বট ডেভেলপারের তথ্য"
    )
    bot.reply_to(message, welcome_text, parse_mode="Markdown")

@bot.message_handler(commands=['developer', 'dev'])
def developer_info(message):
    dev_text = (
        "👨‍💻 **Developer Information** 👨‍💻\n\n"
        "**Name:** Ononto Hasan\n"
        "**TikTok:** [@AURA MINATO](https://www.tiktok.com/@AURA_MINATO)\n"
        "**Expertise:** Telegram Bot Developer & Freestyle Player\n\n"
        "💡 _যেকোনো প্রয়োজনে বা নিজের জন্য কাস্টম বট বানাতে চাইলে যোগাযোগ করুন।_"
    )
    bot.reply_to(message, dev_text, parse_mode="Markdown", disable_web_page_preview=True)

@bot.message_handler(commands=['status'])
def user_status(message):
    init_user(message.from_user)
    user_data = get_user(message.from_user.id)
    
    role_badge = "🌟 PREMIUM VIP" if user_data[2] == 'premium' else "👤 FREE USER"
    
    status_text = (
        f"🪪 **ডিজিটাল আইডি কার্ড** 🪪\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 **নাম:** {user_data[0]}\n"
        f"🛡️ **রোল:** {role_badge}\n"
        f"🪙 **ব্যালেন্স:** {user_data[1]} Coins\n"
        f"⚡ **মোট ব্যবহার:** {user_data[3]} বার\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 _আরও কয়েন পেতে /premium মেনু দেখুন।_"
    )
    bot.reply_to(message, status_text, parse_mode="Markdown")

@bot.message_handler(commands=['stats'])
def admin_stats(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "❌ এই কমান্ডটি শুধুমাত্র অ্যাডমিন (Ononto Hasan) ব্যবহার করতে পারবেন।")
        return
    
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
        f"👑 **ADMIN DASHBOARD** 👑\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🖥️ **Server Performance:**\n"
        f"🔹 CPU Usage: {cpu_usage}%\n"
        f"🔹 RAM Usage: {ram_usage}%\n\n"
        f"📊 **Bot Database:**\n"
        f"👥 Total Users: {total_users}\n"
        f"🌟 Premium Users: {premium_users}\n"
        f"👤 Free Users: {free_users}\n"
        f"🚀 Total Queries Processed: {total_queries}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    bot.reply_to(message, stats_text, parse_mode="Markdown")

@bot.message_handler(commands=['premium', 'buy'])
def premium_menu(message):
    payment_info = (
        "💎 **PREMIUM SUBSCRIPTION** 💎\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "প্যাকেজসমূহ:\n"
        "🪙 **১০০ কয়েন + প্রিমিয়াম রোল** = ১০০ টাকা\n"
        "🪙 **৫০০ কয়েন + প্রিমিয়াম রোল** = ৪০০ টাকা\n\n"
        "💳 **পেমেন্ট অপশন:**\n"
        "🟢 bKash (Personal): `017XXXXXXXX`\n"
        "🟠 Nagad (Personal): `017XXXXXXXX`\n"
        "🟡 Binance Pay ID: `123456789`\n\n"
        "⚠️ **নিয়মাবলী:** পেমেন্ট সম্পন্ন করার পর ট্রানজেকশন আইডি (TrxID) বা স্ক্রিনশট অ্যাডমিনের কাছে পাঠিয়ে দিন। অ্যাডমিন চেক করে ম্যানুয়ালি আপনার অ্যাকাউন্টে কয়েন যুক্ত করে দেবেন।"
    )
    bot.reply_to(message, payment_info, parse_mode="Markdown")

@bot.message_handler(commands=['script', 'chat', 'code'])
def generate_script(message):
    init_user(message.from_user)
    user_id = message.from_user.id
    prompt = message.text.replace('/script', '').replace('/chat', '').replace('/code', '').strip()
    
    if not prompt:
        bot.reply_to(message, "⚠️ অনুগ্রহ করে টপিক লিখুন।\nউদাহরণ: `/script একটি টেলিগ্রাম বট বানানোর কোড দাও`", parse_mode="Markdown")
        return

    if deduct_coin(user_id):
        processing_msg = bot.send_message(message.chat.id, "⏳ **DeepSeek AI আপনার উত্তর তৈরি করছে...**", parse_mode="Markdown")
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "You are an expert AI assistant and highly skilled developer. Provide clean, efficient, and well-formatted answers."},
                    {"role": "user", "content": prompt}
                ]
            )
            reply_text = response.choices[0].message.content
            current_coins = get_user(user_id)[1]
            bot.edit_message_text(f"{reply_text}\n\n━━━━━━━━━━━━━━━━━━━━\n🪙 **অবশিষ্ট কয়েন:** {current_coins}", chat_id=message.chat.id, message_id=processing_msg.message_id, parse_mode="Markdown")
        except Exception as e:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET coins = coins + 1 WHERE user_id = %s', (user_id,))
            conn.commit()
            cursor.close()
            conn.close()
            bot.edit_message_text(f"❌ **সমস্যা হয়েছে:**\n`{e}`\n\n(আপনার কয়েন ফেরত দেওয়া হয়েছে)", chat_id=message.chat.id, message_id=processing_msg.message_id, parse_mode="Markdown")
    else:
        bot.reply_to(message, "❌ **আপনার ব্যালেন্স শেষ!**\nঅনুগ্রহ করে `/premium` কমান্ড ব্যবহার করে নতুন কয়েন কিনে নিন।", parse_mode="Markdown")

@bot.message_handler(commands=['photo', 'image'])
def generate_photo(message):
    init_user(message.from_user)
    user_id = message.from_user.id
    prompt = message.text.replace('/photo', '').replace('/image', '').strip()
    
    if not prompt:
        bot.reply_to(message, "⚠️ অনুগ্রহ করে ছবির বর্ণনা লিখুন।\nউদাহরণ: `/photo a neon futuristic cyber city`", parse_mode="Markdown")
        return

    if deduct_coin(user_id):
        processing_msg = bot.send_message(message.chat.id, "🎨 **ছবি জেনারেট হচ্ছে, অনুগ্রহ করে কয়েক সেকেন্ড অপেক্ষা করুন...**", parse_mode="Markdown")
        try:
            image_url = f"https://image.pollinations.ai/prompt/{prompt}?width=1024&height=1024&nologo=true"
            response = requests.get(image_url)
            
            if response.status_code == 200:
                image_bytes = BytesIO(response.content)
                current_coins = get_user(user_id)[1]
                bot.delete_message(chat_id=message.chat.id, message_id=processing_msg.message_id)
                bot.send_photo(message.chat.id, image_bytes, caption=f"✨ **আপনার জেনারেট করা ছবি!**\n\n🪙 **অবশিষ্ট কয়েন:** {current_coins}", parse_mode="Markdown")
            else:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('UPDATE users SET coins = coins + 1 WHERE user_id = %s', (user_id,))
                conn.commit()
                cursor.close()
                conn.close()
                bot.edit_message_text("❌ ছবি জেনারেট করতে ব্যর্থ হয়েছি। (কয়েন ফেরত দেওয়া হয়েছে)", chat_id=message.chat.id, message_id=processing_msg.message_id)
        except Exception as e:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET coins = coins + 1 WHERE user_id = %s', (user_id,))
            conn.commit()
            cursor.close()
            conn.close()
            bot.edit_message_text(f"❌ **সমস্যা হয়েছে:** `{e}`\n(কয়েন ফেরত দেওয়া হয়েছে)", chat_id=message.chat.id, message_id=processing_msg.message_id, parse_mode="Markdown")
    else:
        bot.reply_to(message, "❌ **আপনার ব্যালেন্স শেষ!**\nঅনুগ্রহ করে `/premium` কমান্ড ব্যবহার করে নতুন কয়েন কিনে নিন।", parse_mode="Markdown")

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
            bot.reply_to(message, "❌ এই ইউজার এখনও বট স্টার্ট করেনি।")
            cursor.close()
            conn.close()
            return
            
        cursor.execute('UPDATE users SET coins = coins + %s, role = %s WHERE user_id = %s', (coins_to_add, new_role, target_id))
        conn.commit()
        cursor.close()
        conn.close()
        
        updated_data = get_user(target_id)
        bot.reply_to(message, f"✅ **সফলভাবে যুক্ত হয়েছে!**\nইউজার ID: `{target_id}`\nযুক্ত করা কয়েন: {coins_to_add}\nনতুন রোল: {new_role.capitalize()}", parse_mode="Markdown")
        bot.send_message(target_id, f"🎉 **অ্যাডমিন আপনাকে নতুন প্যাকেজ দিয়েছেন!**\n\n🪙 **নতুন যুক্ত হওয়া কয়েন:** {coins_to_add}\n🛡️ **আপনার বর্তমান রোল:** {new_role.capitalize()}\n💰 **মোট ব্যালেন্স:** {updated_data[1]} Coins", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, "⚠️ **সঠিক ফরম্যাট:**\n`/addcoin <user_id> <coin_amount> <role>`\n\nউদাহরণ: `/addcoin 12345678 100 premium`", parse_mode="Markdown")

if __name__ == "__main__":
    if DATABASE_URL:
        print("🤖 Setup hocche PostgreSQL Database...")
        setup_db()
        print("🚀 Bot is successfully running with updated UI!")
        bot.polling(non_stop=True, timeout=60, long_polling_timeout=60)
    else:
        print("❌ ERROR: DATABASE_URL missing!")
