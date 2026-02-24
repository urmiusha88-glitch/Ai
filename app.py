import streamlit as st
import requests
import os

# ==========================================
# PAGE CONFIGURATION (Must be the first Streamlit command)
# ==========================================
st.set_page_config(page_title="Minato AI", page_icon="⚡", layout="centered")

# ==========================================
# CUSTOM CSS FOR CHATGPT/PREMIUM LOOK
# ==========================================
st.markdown("""
<style>
    /* Hide default Streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Main background and text colors */
    .stApp {
        background-color: #343541;
        color: #D1D5DB;
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #202123;
        border-right: 1px solid #4D4D4F;
    }
    
    /* Chat Input Box styling */
    .stChatInputContainer {
        background-color: #40414F !important;
        border-radius: 12px !important;
        border: 1px solid #565869 !important;
        padding: 5px;
    }
    
    /* Custom Title */
    .main-title {
        text-align: center;
        font-size: 2.5rem;
        font-weight: 700;
        color: #F9FAFB;
        margin-bottom: 5px;
        margin-top: -40px;
    }
    .sub-title {
        text-align: center;
        color: #9CA3AF;
        font-size: 1rem;
        margin-bottom: 30px;
    }
    
    /* Style for buttons in sidebar */
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        border: 1px solid #565869;
        background-color: transparent;
        color: white;
        transition: 0.3s;
    }
    .stButton>button:hover {
        background-color: #2A2B32;
        border-color: #ececf1;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# SIDEBAR (SETTINGS & NEW CHAT)
# ==========================================
with st.sidebar:
    st.markdown("<h2 style='text-align: center; color: white;'>⚡ Minato AI</h2>", unsafe_allow_html=True)
    
    # New Chat Button
    if st.button("➕ New Chat"):
        st.session_state.messages = [{"role": "assistant", "content": "Hello! I am Minato AI. How can I assist you today?"}]
        st.rerun()
        
    st.divider()
    st.markdown("### 👑 Creator")
    st.markdown("**Ononto Hasan**")
    st.markdown("[🔗 Facebook Profile](https://www.facebook.com/yours.ononto)")
    st.divider()
    st.markdown("🔹 **Model:** DeepSeek-V3")
    st.markdown("🔹 **Status:** Online 🟢")

# ==========================================
# MAIN CHAT INTERFACE
# ==========================================
st.markdown("<div class='main-title'>Minato AI</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>Advanced AI Assistant • Multi-Language Supported</div>", unsafe_allow_html=True)

# Configuration
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "sk-5da4d6648bbe48158c9dd2ba656ac26d")

# Chat History Initialize (First message from bot)
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Hello! I am Minato AI. How can I assist you today?"}]

# Display chat messages from history
for msg in st.session_state.messages:
    avatar = "🤖" if msg["role"] == "assistant" else "👤"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# ==========================================
# CHAT INPUT & AI RESPONSE
# ==========================================
if user_input := st.chat_input("Message Minato AI..."):
    # Add user message to chat
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="👤"):
        st.markdown(user_input)

    # Prepare AI Request
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    
    system_msg = (
        "You are Minato AI, an advanced AI assistant created by Ononto Hasan. "
        "CRITICAL LANGUAGE RULE: Always detect the underlying language of any Romanized input and ALWAYS respond in the proper native script of that language. "
        "If Romanized Bengali/Banglish (e.g., 'kemon aso'), reply in Bengali script (বাংলা). "
        "If Romanized Hindi/Hinglish, reply in Hindi script (हिंदी). "
        "If English, reply in English."
    )
    
    api_messages = [{"role": "system", "content": system_msg}] + [
        {"role": m["role"], "content": m["content"]} for m in st.session_state.messages
    ]

    data = {
        "model": "deepseek-chat",
        "messages": api_messages
    }

    # Loading animation and AI response
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Minato is thinking..."):
            try:
                response = requests.post("https://api.deepseek.com/chat/completions", headers=headers, json=data)
                if response.status_code == 200:
                    bot_reply = response.json()['choices'][0]['message']['content']
                else:
                    bot_reply = "❌ Server Busy. Please try again later."
            except Exception as e:
                bot_reply = "❌ Network Error. Please check your connection."
        
        st.markdown(bot_reply)
    
    # Save bot response to history
    st.session_state.messages.append({"role": "assistant", "content": bot_reply})