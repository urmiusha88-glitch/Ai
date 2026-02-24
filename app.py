import streamlit as st
import requests
import os
import psycopg2
import string
import random
import pandas as pd
import hashlib
from datetime import datetime, timedelta

# ==========================================
# PAGE CONFIGURATION
# ==========================================
st.set_page_config(page_title="Minato AI", page_icon="⚡", layout="wide")

# ==========================================
# CONFIGURATION & DATABASE
# ==========================================
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "sk-5da4d6648bbe48158c9dd2ba656ac26d")
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:hQKBupovepWPRJyTUCiqYrUfEnoeRYYv@trolley.proxy.rlwy.net:36125/railway")
OWNER_ID = 6198703244

def get_bd_time():
    return datetime.utcnow() + timedelta(hours=6)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_db_conn():
    return psycopg2.connect(DATABASE_URL)

def get_user_data_by_id(user_id):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT user_id, credits, role, full_name, expiry_date, is_banned, session_expiry, is_admin FROM users WHERE user_id=%s", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def get_user_data_by_username(username, hashed_pw):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE username=%s AND password=%s", (username, hashed_pw))
    res = c.fetchone()
    conn.close()
    if res:
        return get_user_data_by_id(res[0])
    return None

# ==========================================
# PREMIUM UI & CSS
# ==========================================
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {background: transparent !important;}
    
    .stApp { background-color: #212121; color: #ECECF1; font-family: 'Inter', sans-serif; }
    [data-testid="stSidebar"] { background-color: #171717; border-right: 1px solid #303030; }
    [data-testid="collapsedControl"] svg { color: #ECECF1 !important; }
    
    /* Login & Register Box */
    .auth-container { display: flex; justify-content: center; align-items: center; padding-top: 5vh; }
    .auth-box {
        background: linear-gradient(145deg, #2a2a2a, #242424);
        padding: 40px; border-radius: 16px; border: 1px solid #3d3d3d;
        text-align: center; width: 100%; max-width: 480px; margin: auto;
        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    }
    
    .stChatInputContainer { background-color: #2f2f2f !important; border-radius: 20px !important; border: 1px solid #424242 !important; }
    .stButton>button { width: 100%; border-radius: 8px; border: 1px solid #424242; background-color: #2f2f2f; color: white; transition: all 0.3s ease; }
    .stButton>button:hover { background-color: #10a37f; border-color: #10a37f; }
    
    .stChatMessage { border-radius: 10px; padding: 15px; margin-bottom: 15px; }
    [data-testid="chatAvatarIcon-user"] { background-color: #10a37f; }
    [data-testid="stChatMessageContent"] { color: #FFFFFF !important; font-size: 16px; line-height: 1.6;}
    p {color: #FFFFFF !important;}
    
    /* Contact Buttons */
    .contact-btns { display: flex; justify-content: center; gap: 15px; margin-bottom: 30px; margin-top: 10px;}
    .c-btn {
        text-decoration: none !important; padding: 8px 20px; border-radius: 8px; font-weight: 600; color: white !important; font-size: 14px; transition: 0.3s;
    }
    .fb-btn { background-color: #1877F2; } .fb-btn:hover { background-color: #145DBF; }
    .tg-btn { background-color: #0088cc; } .tg-btn:hover { background-color: #006699; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# STATE INITIALIZATION
# ==========================================
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "user_data" not in st.session_state: st.session_state.user_data = None
if "messages" not in st.session_state: st.session_state.messages = [{"role": "assistant", "content": "Welcome to Minato AI. I am ready to assist you."}]
if "reg_success_user" not in st.session_state: st.session_state.reg_success_user = ""

# ==========================================
# AUTHENTICATION SCREEN (LOGIN & REGISTER)
# ==========================================
if not st.session_state.logged_in:
    st.markdown("<div class='auth-container'><div class='auth-box'>", unsafe_allow_html=True)
    st.markdown("<h1 style='font-size: 2.5rem; color: #10a37f; margin-bottom: 0;'>⚡ Minato AI</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#9CA3AF; margin-bottom: 5px;'>Intelligent • Fast • Secure</p>", unsafe_allow_html=True)
    
    st.markdown("""
        <div class="contact-btns">
            <a href="https://www.facebook.com/yours.ononto" target="_blank" class="c-btn fb-btn">📘 Facebook</a>
            <a href="https://t.me/minato_namikaze143" target="_blank" class="c-btn tg-btn">✈️ Telegram</a>
        </div>
    """, unsafe_allow_html=True)
    
    # 🔴 3 Tabs for better UX
    tab1, tab2, tab3 = st.tabs(["🔐 Web Login", "✈️ Telegram Login", "📝 Register"])
    
    with tab1:
        st.markdown("### Web Account Login")
        l_user = st.text_input("Username", value=st.session_state.reg_success_user, key="login_u")
        l_pass = st.text_input("Password", type="password", key="login_p")
        
        if st.button("Login", key="btn_web_login"):
            if not l_user or not l_pass:
                st.error("Please fill all fields.")
            else:
                user_db = get_user_data_by_username(l_user.strip(), hash_password(l_pass))
                if user_db:
                    if user_db[5] == 1:
                        st.error("❌ You are banned.")
                    else:
                        st.session_state.logged_in = True
                        st.session_state.user_data = user_db
                        st.session_state.reg_success_user = ""
                        st.rerun()
                else:
                    st.error("❌ Invalid Username or Password.")
                    
    with tab2:
        st.markdown("### Bot User Login")
        st.markdown("<p style='color:#9CA3AF; font-size:14px; margin-top:-10px;'>Login directly with your Telegram ID.</p>", unsafe_allow_html=True)
        tg_id_input = st.text_input("Telegram ID", placeholder="e.g. 6198703244", type="password", key="login_tg")
        
        if st.button("Login via Telegram", key="btn_tg_login"):
            if not tg_id_input:
                st.error("Please enter your Telegram ID.")
            else:
                try:
                    user_id = int(tg_id_input.strip())
                    user_db = get_user_data_by_id(user_id)
                    if user_db:
                        if user_db[5] == 1: 
                            st.error("❌ You are banned.")
                        else:
                            st.session_state.logged_in = True
                            st.session_state.user_data = user_db
                            st.rerun()
                    else:
                        st.error("❌ ID not found! Start the Telegram bot first.")
                except ValueError:
                    st.error("❌ Invalid ID format. Must be numbers only.")

    with tab3:
        st.markdown("### Create New Account")
        r_user = st.text_input("Choose Username", key="reg_u")
        r_pass = st.text_input("Password", type="password", key="reg_p")
        r_cpass = st.text_input("Re-enter Password", type="password", key="reg_cp")
        
        if st.button("Register", key="btn_register"):
            if not r_user or not r_pass or not r_cpass:
                st.error("Please fill all fields.")
            elif r_pass != r_cpass:
                st.error("Passwords do not match!")
            else:
                conn = get_db_conn()
                c = conn.cursor()
                c.execute("SELECT user_id FROM users WHERE username=%s", (r_user.strip(),))
                if c.fetchone():
                    st.error("❌ Username already taken! Please choose another.")
                else:
                    new_id = random.randint(1000000000, 9999999999) 
                    now = get_bd_time()
                    hashed_p = hash_password(r_pass)
                    c.execute("INSERT INTO users (user_id, credits, role, generated_count, full_name, expiry_date, is_admin, is_banned, username, password) VALUES (%s, 50, 'Free', 0, %s, %s, 0, 0, %s, %s)", 
                              (new_id, r_user.strip(), now, r_user.strip(), hashed_p))
                    conn.commit()
                    st.session_state.reg_success_user = r_user.strip()
                    st.success("✅ Registration Successful! Please switch to 'Web Login' tab to enter.")
                conn.close()

    st.markdown("</div></div>", unsafe_allow_html=True)
    st.stop()

# ==========================================
# SIDEBAR & DASHBOARD
# ==========================================
user_info = get_user_data_by_id(st.session_state.user_data[0])
is_owner = (user_info[0] == OWNER_ID)
is_admin = (user_info[7] == 1) or is_owner

active_page = "Chat"
with st.sidebar:
    st.markdown(f"<h3 style='text-align: center; color: white;'>👤 {user_info[3]}</h3>", unsafe_allow_html=True)
    st.divider()
    
    if is_owner:
        st.markdown("👑 **Rank:** Owner")
        st.markdown("💎 **Coins:** Unlimited")
    else:
        st.markdown(f"👑 **Rank:** {user_info[2]}")
        st.markdown(f"💎 **Coins:** `{user_info[1]}`")
        now = get_bd_time()
        if user_info[6] and now < user_info[6]:
            time_left = int((user_info[6] - now).total_seconds() / 60)
            st.markdown(f"⏱ **Session:** Active ({time_left} min left)")
        else:
            st.markdown("⏱ **Session:** Inactive")
            
    st.divider()
    
    with st.expander("🎫 Redeem Code"):
        r_code = st.text_input("Enter Code", label_visibility="collapsed", placeholder="CODE-XXXXX")
        if st.button("Claim"):
            if r_code:
                conn = get_db_conn()
                c = conn.cursor()
                c.execute("SELECT credit_amount, role_reward FROM codes WHERE code=%s AND COALESCE(is_redeemed, 0) = 0", (r_code,))
                res = c.fetchone()
                if res:
                    amt, plan = res[0], res[1]
                    new_exp = get_bd_time() + timedelta(days={"BRONZE":3, "SILVER":5, "GOLD":7, "PLATINIAM":15, "DIAMOND":30}.get(plan, 1))
                    c.execute("UPDATE codes SET is_redeemed = 1 WHERE code=%s", (r_code,))
                    c.execute("UPDATE users SET credits=credits+%s, role=%s, expiry_date=%s WHERE user_id=%s", (amt, plan, new_exp, user_info[0]))
                    conn.commit()
                    st.toast(f"🎉 Redeem Successful! {amt} coins added.", icon="✅")
                    st.rerun()
                else:
                    st.error("Invalid or used code.")
                conn.close()
    
    st.divider()
    if is_admin:
        active_page = st.radio("Navigation", ["💬 Chat UI", "⚙️ Admin Dashboard"])
        st.divider()
    
    if st.button("➕ Clear Chat"):
        st.session_state.messages = [{"role": "assistant", "content": "Chat cleared. How can I help?"}]
        st.rerun()
    if st.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.rerun()

# ==========================================
# ADMIN DASHBOARD 
# ==========================================
if is_admin and active_page == "⚙️ Admin Dashboard":
    st.title("⚙️ Admin Dashboard")
    st.markdown("Control your Minato AI Ecosystem from here.")
    
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*), SUM(generated_count) FROM users")
    stats = c.fetchone()
    c.execute("SELECT COUNT(*) FROM users WHERE role != 'Free'")
    prem = c.fetchone()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Users", stats[0] or 0)
    col2.metric("Premium Users", prem[0] or 0)
    col3.metric("Total AI Activities", stats[1] or 0)
    st.divider()
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🎟 Generate Codes")
        plan = st.selectbox("Select Plan", ["BRONZE", "SILVER", "GOLD", "PLATINIAM", "DIAMOND"])
        custom_amt = st.number_input("Custom Coin Amount (Optional)", value=0)
        if st.button("Generate Code"):
            amt = custom_amt if custom_amt > 0 else {"BRONZE":100, "SILVER":500, "GOLD":2000, "PLATINIAM":5000, "DIAMOND":10000}[plan]
            code = "CODE-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=14))
            c.execute("INSERT INTO codes (code, credit_amount, role_reward, is_redeemed) VALUES (%s, %s, %s, 0)", (code, amt, plan))
            conn.commit()
            st.success(f"✅ Generated: `{code}` | {plan} | {amt} Coins")
            
    with c2:
        if is_owner:
            st.subheader("🛡 Add New Admin")
            new_admin_id = st.text_input("Enter User ID to make Admin")
            if st.button("Make Admin"):
                c.execute("UPDATE users SET is_admin=1 WHERE user_id=%s", (int(new_admin_id),))
                conn.commit()
                st.success(f"✅ User is now an Admin!")
    
    st.divider()
    st.subheader("👥 User Database Preview (Top 50)")
    df = pd.read_sql_query("SELECT user_id, username, full_name, credits, role, generated_count FROM users ORDER BY generated_count DESC LIMIT 50", conn)
    st.dataframe(df, use_container_width=True)
    conn.close()
    st.stop()

# ==========================================
# MAIN CHAT INTERFACE
# ==========================================
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.markdown("<h2 style='text-align: center; color: #10a37f; margin-bottom: 0px;'>Minato AI</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #888; margin-bottom: 30px;'>Intelligent • Fast • Secure</p>", unsafe_allow_html=True)

for msg in st.session_state.messages:
    avatar = "🤖" if msg["role"] == "assistant" else "👤"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# ==========================================
# CHAT LOGIC & SESSION
# ==========================================
if user_input := st.chat_input("Ask Minato anything..."):
    now = get_bd_time()
    session_cost = 50
    has_active_session = False
    
    if is_owner: has_active_session = True
    elif user_info[6] and now < user_info[6]: has_active_session = True
        
    if not has_active_session:
        if user_info[1] < session_cost:
            st.error("❌ Not enough Coins for a 10-minute session! (Costs 50 coins). Please claim or buy.")
            st.stop()
        else:
            new_expiry = now + timedelta(minutes=10)
            conn = get_db_conn()
            c = conn.cursor()
            c.execute("UPDATE users SET credits=credits-%s, session_expiry=%s WHERE user_id=%s", (session_cost, new_expiry, user_info[0]))
            conn.commit()
            conn.close()
            st.toast("⏱ Started a new 10-Min Session (-50 Coins)", icon="✅")

    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="👤"):
        st.markdown(user_input)

    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    system_msg = (
        f"You are Minato AI, an advanced AI assistant created by Ononto Hasan. The user's name is {user_info[3]}. "
        "CRITICAL LANGUAGE RULE: Always respond in the proper native script of the detected language. "
        "If Romanized Bengali/Banglish, reply in Bengali script (বাংলা). If English, reply in English."
    )
    
    api_messages = [{"role": "system", "content": system_msg}] + [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
    data = {"model": "deepseek-chat", "messages": api_messages}

    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Minato is thinking..."):
            try:
                response = requests.post("https://api.deepseek.com/chat/completions", headers=headers, json=data)
                if response.status_code == 200:
                    bot_reply = response.json()['choices'][0]['message']['content']
                    conn = get_db_conn()
                    c = conn.cursor()
                    c.execute("UPDATE users SET generated_count=generated_count+1 WHERE user_id=%s", (user_info[0],))
                    conn.commit()
                    conn.close()
                else:
                    bot_reply = "❌ Server error. Please try again."
            except Exception:
                bot_reply = "❌ Network error."
        st.markdown(bot_reply)
    
    st.session_state.messages.append({"role": "assistant", "content": bot_reply})
    st.rerun()
