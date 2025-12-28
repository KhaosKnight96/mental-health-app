import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.graph_objects as go

# --- 1. CONFIGURATION & STYLING ---
st.set_page_config(page_title="Health Bridge Pro", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    .glass-panel {
        background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(15px);
        border-radius: 20px; border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 25px; margin-bottom: 20px;
    }
    .stChatMessage { border-radius: 15px; margin-bottom: 10px; border: 1px solid rgba(255,255,255,0.05); }
    [data-testid="stChatMessageUser"] { background-color: #1E40AF !important; }
    [data-testid="stChatMessageAssistant"] { background-color: #1E293B !important; }
    .avatar-pulse {
        width: 60px; height: 60px; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: 30px; margin: 0 auto 10px;
        background: linear-gradient(135deg, #38BDF8, #6366F1);
        box-shadow: 0 0 15px rgba(56, 189, 248, 0.4);
    }
</style>
""", unsafe_allow_html=True)

# --- 2. CONNECTIONS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# Initialize Session State
if "auth" not in st.session_state: st.session_state.auth = {"in": False, "mid": None, "role": "user"}
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

# --- 3. AI ENGINE (SECURELY FETCHING FROM SECRETS) ---
def talk_to_ai(agent_name, prompt):
    try:
        # Pulls the fresh key you just added to Secrets
        client = Groq(api_key=st.secrets["GROQ_API_KEY"].strip())
        
        system_map = {
            "Cooper": "You are Cooper, a high-energy fitness coach. Be concise and motivating.",
            "Clara": "You are Clara, a calm health data analyst. Focus on patterns and wellness."
        }
        
        # Build history for context
        history = [{"role": "system", "content": system_map[agent_name]}]
        history.extend(st.session_state.chats[agent_name][-4:])
        history.append({"role": "user", "content": prompt})

        res = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=history
        )
        return res.choices[0].message.content
    except Exception as e:
        return f"⚠️ Connection Error: {str(e)}"

# --- 4. LOGIN GATE ---
if not st.session_state.auth["in"]:
    st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge</h1>", unsafe_allow_html=True)
    with st.container(border=True):
        u = st.text_input("Member ID").strip().lower()
        p = st.text_input("Password", type="password")
        if st.button("Sign In", use_container_width=True):
            users = get_data("Users")
            if not users.empty:
                m = users[(users['memberid'].astype(str).str.lower() == u) & (users['password'].astype(str) == p)]
                if not m.empty:
                    st.session_state.auth.update({"in": True, "mid": u, "role": str(m.iloc[0]['role']).lower()})
                    st.rerun()
            st.error("Access Denied")
    st.stop()

# --- 5. MAIN NAVIGATION ---
main_nav = st.tabs(["🏠 Cooper", "🛋️ Clara", "📊 Tracker", "🎮 Games", "🛡️ Admin"])

# --- 6. COOPER & CLARA CHAT ---
for i, agent in enumerate(["Cooper", "Clara"]):
    with main_nav[i]:
        st.markdown(f'<div class="glass-panel"><div class="avatar-pulse">{"🤖" if agent=="Cooper" else "🧘‍♀️"}</div><h3 style="text-align:center;">{agent}</h3></div>', unsafe_allow_html=True)
        
        # Chat container
        chat_container = st.container(height=400, border=False)
        with chat_container:
            for m in st.session_state.chats[agent]:
                with st.chat_message(m["role"]): st.write(m["content"])
        
        if p := st.chat_input(f"Message {agent}...", key=f"chat_{agent}"):
            st.session_state.chats[agent].append({"role": "user", "content": p})
            save_log(agent, "user", p)
            
            with chat_container:
                with st.chat_message("user"): st.write(p)
                with st.chat_message("assistant"):
                    with st.spinner(f"{agent} is typing..."):
                        response = talk_to_ai(agent, p)
                        st.write(response)
            
            st.session_state.chats[agent].append({"role": "assistant", "content": response})
            save_log(agent, "assistant", response)
            st.rerun()

# --- 7. TRACKER ---
with main_nav[2]:
    st.subheader("⚡ Energy & Mood Tracker")
    ev = st.select_slider("Current Energy Level", options=range(1,12), value=6)
    if st.button("Log Energy"):
        new_log = pd.DataFrame([{"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), "memberid": st.session_state.auth['mid'], "energylog": ev}])
        conn.update(worksheet="Sheet1", data=pd.concat([get_data("Sheet1"), new_log], ignore_index=True))
        st.success("Level Sync'd!")

# --- 8. GAMES ---
with main_nav[3]:
    game_choice = st.radio("Choose Activity", ["Snake", "Memory Match"], horizontal=True)
    if game_choice == "Snake":
        st.components.v1.html("""<div style="text-align:center;"><canvas id="s" width="300" height="300" style="border:2px solid #38BDF8; background:#0F172A;"></canvas></div><script>/* Snake logic here */</script>""", height=400)
    else:
        st.info("Memory Match Loading...")

# --- 9. ADMIN & LOGOUT ---
with main_nav[4]:
    if st.session_state.auth["role"] == "admin":
        st.write("Current User Logs")
        st.dataframe(get_data("ChatLogs"))
    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()
