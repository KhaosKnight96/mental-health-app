import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta
import plotly.graph_objects as go

# --- 1. CONFIG ---
st.set_page_config(page_title="Health Bridge", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    .portal-card { background: #1E293B; padding: 25px; border-radius: 20px; border: 1px solid #334155; margin-bottom: 20px; }
    .glass-panel {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(15px);
        border-radius: 25px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 25px;
        margin-bottom: 20px;
    }
    .avatar-pulse {
        width: 70px; height: 70px;
        border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: 35px; margin: 0 auto 15px;
        animation: pulse 3s infinite;
    }
    @keyframes pulse {
        0% { transform: scale(1); opacity: 1; }
        70% { transform: scale(1.05); opacity: 0.8; }
        100% { transform: scale(1); opacity: 1; }
    }
</style>
""", unsafe_allow_html=True)

# --- 2. CONNECTIONS & DATA HELPERS ---
conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None, "name": None}

def get_data(worksheet_name):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except:
        # Create empty DF if sheet doesn't exist/is empty
        if worksheet_name == "ChatLogs":
            return pd.DataFrame(columns=["Timestamp", "CoupleID", "Agent", "Role", "Content"])
        return pd.DataFrame()

def save_chat_to_sheets(agent, role, content):
    """Saves a single message to the Google Sheet."""
    new_entry = pd.DataFrame([{
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "CoupleID": st.session_state.auth['cid'],
        "Agent": agent, # "Cooper" or "Clara"
        "Role": role,   # "user" or "assistant"
        "Content": content
    }])
    existing_df = get_data("ChatLogs")
    updated_df = pd.concat([existing_df, new_entry], ignore_index=True)
    conn.update(worksheet="ChatLogs", data=updated_df)

# --- 3. LOGIN ---
if not st.session_state.auth["logged_in"]:
    st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge Portal</h1>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["🔐 Login", "📝 Sign Up"])
    with t1:
        u = st.text_input("Couple ID", key="l_u")
        p = st.text_input("Password", type="password", key="l_p")
        if st.button("Sign In"):
            df = get_data("Users")
            m = df[(df['Username'].astype(str) == u) & (df['Password'].astype(str) == p)]
            if not m.empty:
                st.session_state.auth.update({"logged_in": True, "cid": u, "name": m.iloc[0]['Fullname']})
                
                # LOAD CHAT HISTORY FROM SHEETS ON LOGIN
                all_chats = get_data("ChatLogs")
                user_chats = all_chats[all_chats['CoupleID'].astype(str) == str(u)]
                st.session_state.cooper_logs = user_chats[user_chats['Agent'] == "Cooper"][["role", "content"]].to_dict('records')
                st.session_state.clara_logs = user_chats[user_chats['Agent'] == "Clara"][["role", "content"]].to_dict('records')
                
                st.rerun()
            else: st.error("Invalid Credentials")
    st.stop()

# --- 4. NAVIGATION ---
main_nav = st.tabs(["🏠 Cooper's Corner", " Couch", "🎮 Games", "🚪 Logout"])

# --- 5. COOPER'S CORNER ---
with main_nav[0]:
    col1, col2 = st.columns([1, 1.3])
    with col1:
        st.markdown('<div class="portal-card"><h3>⚡ Energy Status</h3>', unsafe_allow_html=True)
        ev = st.slider("Energy Level", 1, 11, 6)
        if st.button("💾 Sync Data"):
            new_row = pd.DataFrame([{"Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), "CoupleID": st.session_state.auth['cid'], "EnergyLog": ev}])
            conn.update(worksheet="Sheet1", data=pd.concat([get_data("Sheet1"), new_row], ignore_index=True))
            st.success("Logged!")
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="glass-panel"><div class="avatar-pulse" style="background:linear-gradient(135deg,#38BDF8,#6366F1);">👤</div><h3 style="text-align:center; color:#38BDF8;">Cooper\'s Corner</h3></div>', unsafe_allow_html=True)
        
        chat_box = st.container(height=380, border=False)
        with chat_box:
            for m in st.session_state.cooper_logs:
                with st.chat_message(m["role"], avatar="👤"): st.write(m["content"])
        
        if p := st.chat_input("Speak with Cooper..."):
            # 1. Save and Show User Message
            st.session_state.cooper_logs.append({"role": "user", "content": p})
            save_chat_to_sheets("Cooper", "user", p)
            
            # 2. Get AI Response
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":"You are Cooper, a wise and warm human companion."}]+st.session_state.cooper_logs[-5:]).choices[0].message.content
            
            # 3. Save and Show AI Message
            st.session_state.cooper_logs.append({"role": "assistant", "content": res})
            save_chat_to_sheets("Cooper", "assistant", res)
            st.rerun()

# --- 6. CLARA'S COUCH ---
with main_nav[1]:
    st.markdown('<div class="glass-panel"><div class="avatar-pulse" style="background:linear-gradient(135deg,#F472B6,#FB7185);">🧘‍♀️</div><h3 style="text-align:center; color:#F472B6;">Clara\'s Couch</h3></div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1.5, 1])
    
    with c2:
        clara_chat = st.container(height=400, border=False)
        with clara_chat:
            for m in st.session_state.clara_logs:
                with st.chat_message(m["role"], avatar="🧘‍♀️"): st.write(m["content"])
        if cp := st.chat_input("Analyze with Clara..."):
            st.session_state.clara_logs.append({"role": "user", "content": cp})
            save_chat_to_sheets("Clara", "user", cp)
            
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":"You are Clara, a clinical analyst."}]+st.session_state.clara_logs[-5:]).choices[0].message.content
            
            st.session_state.clara_logs.append({"role": "assistant", "content": res})
            save_chat_to_sheets("Clara", "assistant", res)
            st.rerun()
