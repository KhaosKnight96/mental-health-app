import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.graph_objects as go

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Health Bridge Pro", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    .glass-panel {
        background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(15px);
        border-radius: 20px; border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 25px; margin-bottom: 20px;
    }
    .stChatMessage { border-radius: 15px; margin-bottom: 10px; }
    .avatar-pulse {
        width: 60px; height: 60px; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: 30px; margin: 0 auto 10px;
        background: linear-gradient(135deg, #38BDF8, #6366F1);
    }
</style>
""", unsafe_allow_html=True)

# --- 2. CONNECTIONS & DATA ---
conn = st.connection("gsheets", type=GSheetsConnection)

if "auth" not in st.session_state: st.session_state.auth = {"in": False, "mid": None}
if "chats" not in st.session_state: st.session_state.chats = {"Cooper": [], "Clara": []}

def get_data(ws):
    try:
        df = conn.read(worksheet=ws, ttl=0)
        df.columns = [str(c).strip().lower() for c in df.columns]
        return df
    except: return pd.DataFrame()

def save_log(agent, role, content):
    try:
        new_row = pd.DataFrame([{
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "memberid": st.session_state.auth['mid'],
            "agent": agent, "role": role, "content": content
        }])
        conn.update(worksheet="ChatLogs", data=pd.concat([get_data("ChatLogs"), new_row], ignore_index=True))
    except: pass

# --- 3. THE AI ENGINES ---
def talk_to_cooper(prompt):
    """Cooper: The Empathetic Friend"""
    client = Groq(api_key=st.secrets["GROQ_API_KEY"].strip())
    system_msg = (
        "You are Cooper, a warm, friendly, and deeply empathetic friend. "
        "Your goal is to listen, provide emotional support, and be a safe space for the user. "
        "Keep your tone conversational, kind, and supportive. Avoid being overly clinical."
    )
    history = [{"role": "system", "content": system_msg}] + st.session_state.chats["Cooper"][-5:]
    res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=history)
    return res.choices[0].message.content

def talk_to_clara(prompt):
    """Clara: The Data Analyst"""
    client = Groq(api_key=st.secrets["GROQ_API_KEY"].strip())
    
    # Fetch Data for Clara to analyze
    energy_df = get_data("Sheet1")
    user_energy = energy_df[energy_df['memberid'] == st.session_state.auth['mid']].tail(10).to_string()
    
    system_msg = (
        "You are Clara, a logical health data analyst. You have access to the user's recent energy logs and chat history. "
        f"USER ENERGY DATA (Recent): {user_energy}. "
        "Analyze the connection between their reported energy and their conversations with Cooper. "
        "Provide insights on patterns, potential burnout, or improvements. Be professional yet empathetic."
    )
    history = [{"role": "system", "content": system_msg}] + st.session_state.chats["Clara"][-3:]
    history.append({"role": "user", "content": prompt})
    
    res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=history)
    return res.choices[0].message.content

# --- 4. LOGIN ---
if not st.session_state.auth["in"]:
    st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge</h1>", unsafe_allow_html=True)
    u = st.text_input("Member ID").strip().lower()
    p = st.text_input("Password", type="password")
    if st.button("Sign In"):
        users = get_data("Users")
        if not users.empty and u in users['memberid'].values:
            st.session_state.auth.update({"in": True, "mid": u})
            st.rerun()
    st.stop()

# --- 5. TABS ---
t1, t2, t3 = st.tabs(["🏠 Cooper's Corner", "🛋️ Clara's Couch", "🚪 Logout"])

with t1:
    st.markdown('<div class="glass-panel"><div class="avatar-pulse">🤝</div><h3 style="text-align:center;">Cooper</h3><p style="text-align:center;font-style:italic;">"I am here to listen."</p></div>', unsafe_allow_html=True)
    for m in st.session_state.chats["Cooper"]:
        with st.chat_message(m["role"]): st.write(m["content"])
    
    if p := st.chat_input("Talk to Cooper..."):
        st.session_state.chats["Cooper"].append({"role": "user", "content": p})
        save_log("Cooper", "user", p)
        with st.chat_message("user"): st.write(p)
        with st.chat_message("assistant"):
            with st.spinner("Cooper is listening..."):
                res = talk_to_cooper(p)
                st.write(res)
        st.session_state.chats["Cooper"].append({"role": "assistant", "content": res})
        save_log("Cooper", "assistant", res)

with t2:
    st.markdown('<div class="glass-panel"><div class="avatar-pulse" style="background:linear-gradient(135deg,#F472B6,#FB7185);">📊</div><h3 style="text-align:center;">Clara</h3><p style="text-align:center;font-style:italic;">"Analyzing patterns in your wellness data..."</p></div>', unsafe_allow_html=True)
    for m in st.session_state.chats["Clara"]:
        with st.chat_message(m["role"]): st.write(m["content"])
        
    if cp := st.chat_input("Ask Clara for insights..."):
        st.session_state.chats["Clara"].append({"role": "user", "content": cp})
        with st.chat_message("user"): st.write(cp)
        with st.chat_message("assistant"):
            with st.spinner("Clara is calculating..."):
                res = talk_to_clara(cp)
                st.write(res)
        st.session_state.chats["Clara"].append({"role": "assistant", "content": res})
        save_log("Clara", "assistant", res)

with t3:
    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()
