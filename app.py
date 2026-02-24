import streamlit as st
import requests
import os
import psycopg2
from datetime import datetime

# ==========================================
# PAGE CONFIGURATION
# ==========================================
st.set_page_config(page_title="Minato AI", page_icon="⚡", layout="centered")

# ==========================================
# CONFIGURATION & DATABASE
# ==========================================
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "sk-5da4d6648bbe48158c9dd2ba656ac26d")
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:hQKBupovepWPRJyTUCiqYrUfEnoeRYYv@trolley.proxy.rlwy.net:36125/railway")
OWNER_ID = 6198703244

def get_db_conn():
    return psycopg2.connect(DATABASE_URL)

def get_user_data(user_id):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT user_id, credits, role, full_name, expiry_date, is_banned FROM users WHERE user_id=%s", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def deduct_credits(user_id, cost=2):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET credits=credits-%s, generated_count=generated_count+1 WHERE user_id=%s", (cost, user_id))
    conn.commit()
    conn.close()

# ==========================================
# PREMIUM CUSTOM CSS
# ==========================================
st.markdown("""
<style>
    /* Hide Streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Global Colors (ChatGPT Theme) */
    .stApp {
        background-color: #343541;
        color: #ECECF1;
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #202123;
        border-right: 1px solid #4D4D4F;
    }
    
    /* Login Box */
    .login-box {
        background-color: #202123;
        padding: 30px;
        border-radius: 10px;
        border: 1px solid #4D4D4F;
        text-align: center;
        margin-top: 10%;
    }
    
    /* Chat Input styling */
    .stChatInputContainer {
        background-color: #40414F !important;
        border-radius: 12px !important;
        border: 1px solid #565869 !important;
    }
    
    /* Title Customization */
    .main-title {
        text-align: center;
        font-size: 2.2rem;
        font-weight: 700;
        color: #F9FAFB;
        margin-top: -30px;
    }
    
    /* Sidebar Buttons */
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        border: 1px solid #565869;
        background-color: #40414F;
        color: white;
        transition: 0.3s;
    }
    .stButton>button:hover {
        background-color: #565869;
        border-color: #ececf1;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# SESSION STATE INITIALIZATION
# ==========================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_data = None
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Hello! I am Minato AI. How can I assist you today?"}]

# ==========================================
# LOGIN SCREEN
# ==========================================
if not st.session_state.logged_in:
    st.markdown("<div class='main-title'>⚡ Minato AI Web</div>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color:#9CA3AF;'>Welcome! Please log in to continue.</p>", unsafe_allow_html=True)
    
    st.markdown("<div class='login-box'>", unsafe_allow_html=True)
    st.markdown("### 🔐 User Login")
    
    telegram_id_input = st.text_input("Enter your Telegram ID", placeholder="e.g. 6198703244", type="password")
    
    if st.button("Login"):
        if telegram_id_input.strip() == "":
            st.error("Please enter a valid Telegram ID.")
        else:
            try:
                user_id = int(telegram_id_input.strip())
                user_db = get_user_data(user_id)
                
                if user_db:
                    if user_db[5] == 1: # is_banned check
                        st.error("❌ You are banned from using this service.")
                    else:
                        st.session_state.logged_in = True
                        st.session_state.user_data = user_db
                        st.success("✅ Login Successful!")
                        st.rerun()
                else:
                    st.error("❌ ID not found! Please start the Minato Telegram bot first to create an account.")
            except ValueError:
                st.error("❌ Invalid ID format. Must be numbers only.")
    
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop() # Stops the rest of the app from running if not logged in

# ==========================================
# SIDEBAR (PROFILE & SETTINGS)
# ==========================================
user_info = get_user_data(st.session_state.user_data[0]) # Refresh data
is_owner = (user_info[0] == OWNER_ID)

with st.sidebar:
    st.markdown(f"<h3 style='text-align: center;'>👤 {user_info[3]}</h3>", unsafe_allow_html=True)
    st.divider()
    
    if is_owner:
        st.markdown("👑 **Rank:** Owner")
        st.markdown("💎 **Coins:** Unlimited ♾️")
    else:
        st.markdown(f"👑 **Rank:** {user_info[2]}")
        st.markdown(f"💎 **Coins:** `{user_info[1]}`")
    
    st.divider()
    
    if st.button("➕ New Chat"):
        st.session_state.messages = [{"role": "assistant", "content": "Hello! I am Minato AI. How can I assist you today?"}]
        st.rerun()
        
    if st.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.session_state.user_data = None
        st.session_state.messages = [{"role": "assistant", "content": "Hello! I am Minato AI. How can I assist you today?"}]
        st.rerun()

    st.divider()
    st.markdown("<p style='text-align:center; color:#9CA3AF; font-size:12px;'>Created by Ononto Hasan</p>", unsafe_allow_html=True)

# ==========================================
# MAIN CHAT INTERFACE
# ==========================================
st.markdown("<div class='main-title'>Minato AI</div>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #9CA3AF; margin-bottom: 30px;'>Advanced AI Assistant • Multi-Language Supported</p>", unsafe_allow_html=True)

# Display chat messages
for msg in st.session_state.messages:
    avatar = "🤖" if msg["role"] == "assistant" else "👤"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# ==========================================
# CHAT INPUT & AI LOGIC
# ==========================================
if user_input := st.chat_input("Message Minato AI..."):
    # Credit Check for normal users
    cost = 2
    if not is_owner and user_info[1] < cost:
        st.error("❌ Not enough Coins to chat! Please buy more credits or claim daily reward via Telegram.")
        st.stop()

    # User message
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="👤"):
        st.markdown(user_input)

    # API Prep
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    system_msg = (
        f"You are Minato AI, an advanced AI assistant created by Ononto Hasan. "
        f"The user's name is {user_info[3]}. "
        "CRITICAL LANGUAGE RULE: Always detect the underlying language of any Romanized input and ALWAYS respond in the proper native script of that language. "
        "If Romanized Bengali/Banglish (e.g., 'kemon aso'), reply in Bengali script (বাংলা). "
        "If Romanized Hindi/Hinglish, reply in Hindi script (हिंदी). "
        "If English, reply in English."
    )
    
    api_messages = [{"role": "system", "content": system_msg}] + [
        {"role": m["role"], "content": m["content"]} for m in st.session_state.messages
    ]

    data = {"model": "deepseek-chat", "messages": api_messages}

    # AI Response
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Thinking..."):
            try:
                response = requests.post("https://api.deepseek.com/chat/completions", headers=headers, json=data)
                if response.status_code == 200:
                    bot_reply = response.json()['choices'][0]['message']['content']
                    # Deduct coins if not owner
                    if not is_owner:
                        deduct_credits(user_info[0], cost)
                else:
                    bot_reply = "❌ Server Busy. Please try again later."
            except Exception as e:
                bot_reply = "❌ Network Error. Please check your connection."
        
        st.markdown(bot_reply)
    
    st.session_state.messages.append({"role": "assistant", "content": bot_reply})
    st.rerun() # Refresh page to update coin balance in sidebar
