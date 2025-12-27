import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.graph_objects as go

# --- 1. CONFIG ---
st.set_page_config(page_title="Health Bridge", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    .portal-card { background: #1E293B; padding: 25px; border-radius: 20px; border: 1px solid #334155; margin-bottom: 20px; }
    
    /* Cooper's Corner Specific Styling */
    .cooper-glass {
        background: rgba(30, 41, 59, 0.6);
        backdrop-filter: blur(12px);
        border-radius: 30px;
        border: 1px solid rgba(56, 189, 248, 0.2);
        padding: 30px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.4);
    }
    
    .avatar-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        margin-bottom: 20px;
    }

    .avatar-pulse {
        width: 80px;
        height: 80px;
        background: linear-gradient(135deg, #38BDF8, #818CF8);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 40px;
        box-shadow: 0 0 0 0 rgba(56, 189, 248, 0.7);
        animation: pulse 2.5s infinite;
    }

    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(56, 189, 248, 0.6); }
        70% { box-shadow: 0 0 0 20px rgba(56, 189, 248, 0); }
        100% { box-shadow: 0 0 0 0 rgba(56, 189, 248, 0); }
    }

    .stButton>button { border-radius: 12px; font-weight: 600; height: 3.5em; width: 100%; border: none; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    .stTabs [data-baseweb="tab-list"] { gap: 20px; }
    .stTabs [data-baseweb="tab"] { background-color: #1E293B; border-radius: 10px; padding: 10px 20px; color: white; border: 1px solid #334155; }
    .stTabs [aria-selected="true"] { background-color: #38BDF8 !important; border: 1px solid #38BDF8 !important; }
</style>
""", unsafe_allow_html=True)

# --- 2. CONNECTIONS ---
conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None, "name": None}
if "cooper_logs" not in st.session_state: st.session_state.cooper_logs = []
if "clara_logs" not in st.session_state: st.session_state.clara_logs = []

def get_data(worksheet_name="Users"):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except: return pd.DataFrame()

# --- 3. LOGIN GATE ---
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
                st.rerun()
            else: st.error("Invalid Credentials")
    with t2:
        n = st.text_input("Full Name")
        c = st.text_input("Couple ID")
        pw = st.text_input("Password", type="password")
        if st.button("Register"):
            df = get_data("Users")
            new_user = pd.DataFrame([{"Fullname": n, "Username": c, "Password": pw}])
            conn.update(worksheet="Users", data=pd.concat([df, new_user], ignore_index=True))
            st.success("Account created!")
    st.stop()

# --- 4. NAVIGATION ---
st.markdown(f"### Welcome back, {st.session_state.auth['name']} ✨")
main_nav = st.tabs(["🏠 Dashboard", "📊 Caregiver Insights", "🎮 Games", "🚪 Logout"])

# --- 5. DASHBOARD (FEATURING COOPER'S CORNER) ---
with main_nav[0]:
    col1, col2 = st.columns([1, 1.2])
    
    with col1:
        st.markdown('<div class="portal-card"><h3>⚡ Energy Status</h3>', unsafe_allow_html=True)
        ev = st.slider("How are you feeling?", 1, 11, 6)
        emoji_map = {1:'🚨', 2:'🪫', 3:'😫', 4:'🥱', 5:'🙁', 6:'😐', 7:'🙂', 8:'😊', 9:'⚡', 10:'🚀', 11:'☀️'}
        st.markdown(f"<h1 style='text-align:center; font-size:80px; margin: 20px 0;'>{emoji_map[ev]}</h1>", unsafe_allow_html=True)
        if st.button("💾 Sync Energy"):
            new_row = pd.DataFrame([{"Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), "CoupleID": st.session_state.auth['cid'], "EnergyLog": ev}])
            conn.update(worksheet="Sheet1", data=pd.concat([conn.read(worksheet="Sheet1", ttl=0), new_row], ignore_index=True))
            st.success("Energy synced to the cloud!")
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        # COOPER'S CORNER GLASS UI
        st.markdown(f"""
            <div class="cooper-glass">
                <div class="avatar-container">
                    <div class="avatar-pulse">🐶</div>
                    <h2 style='color:#38BDF8; margin:10px 0 0 0; font-family:sans-serif;'>Cooper's Corner</h2>
                    <p style='color:#94A3B8; font-style: italic;'>Warm, empathetic, and always listening.</p>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        # Chat Display
        chat_container = st.container(height=350, border=False)
        with chat_container:
            for m in st.session_state.cooper_logs:
                with st.chat_message(m["role"], avatar="👤" if m["role"] == "user" else "🐶"):
                    st.write(m["content"])

        # Chat Input
        if p := st.chat_input("Talk to Cooper...", key="coop_in"):
            st.session_state.cooper_logs.append({"role": "user", "content": p})
            
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role":"system","content":"You are Cooper, a very warm and kind AI friend for a mental health portal. You are empathetic, use dog emojis occasionally, and focus on being a supportive listener. Keep responses relatively concise."}] + st.session_state.cooper_logs[-5:]
            ).choices[0].message.content
            
            st.session_state.cooper_logs.append({"role": "assistant", "content": response})
            st.rerun()

# (Caregiver Insights, Games, and Logout remain in their tabs as per your building block)
