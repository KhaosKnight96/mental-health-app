import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.graph_objects as go

# --- 1. THEME & UI OVERHAUL ---
st.set_page_config(page_title="Health Bridge", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    /* Main App Background */
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    
    /* Premium Glass Cards */
    .glass-panel {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(15px);
        border-radius: 20px;
        padding: 20px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        margin-bottom: 20px;
    }

    /* Chat Bubble Styling */
    .stChatMessage { border-radius: 15px; margin-bottom: 10px; padding: 10px; }
    [data-testid="stChatMessageUser"] { background-color: #1E3A8A !important; border-bottom-right-radius: 2px !important; }
    [data-testid="stChatMessageAssistant"] { background-color: #334155 !important; border-bottom-left-radius: 2px !important; }

    /* Animated Avatar */
    .bot-avatar {
        width: 60px; height: 60px; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: 30px; margin: 0 auto 10px;
        background: linear-gradient(135deg, #38BDF8, #6366F1);
        box-shadow: 0 0 15px rgba(56, 189, 248, 0.5);
    }
    
    /* Utility */
    .stButton>button { border-radius: 10px; font-weight: 600; transition: 0.3s; }
    .stButton>button:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
</style>
""", unsafe_allow_html=True)

# --- 2. DATA & API INITIALIZATION ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    client = Groq(api_key=st.secrets.get("GROQ_API_KEY", "MISSING_KEY"))
except Exception as e:
    st.error(f"Configuration Error: {e}")

# Persistent Session State
if "auth" not in st.session_state: st.session_state.auth = {"in": False, "mid": None, "role": "user"}
if "chats" not in st.session_state: st.session_state.chats = {"Cooper": [], "Clara": []}

def load_sheet(name):
    try:
        df = conn.read(worksheet=name, ttl=0)
        df.columns = [str(c).strip().lower() for c in df.columns]
        return df
    except: return pd.DataFrame()

def log_to_sheet(sheet, data_dict):
    try:
        current_df = load_sheet(sheet)
        new_row = pd.DataFrame([data_dict])
        conn.update(worksheet=sheet, data=pd.concat([current_df, new_row], ignore_index=True))
    except Exception as e: st.toast(f"Sync Error: {e}")

# --- 3. ACCESS CONTROL ---
if not st.session_state.auth["in"]:
    st.markdown("<h1 style='text-align:center;'>Health Bridge</h1>", unsafe_allow_html=True)
    tab_l, tab_r = st.tabs(["Login", "Register"])
    
    with tab_l:
        u = st.text_input("ID", key="login_id")
        p = st.text_input("Pass", type="password", key="login_pw")
        if st.button("Sign In", key="btn_login"):
            users = load_sheet("Users")
            if not users.empty:
                m = users[(users['memberid'].astype(str) == u) & (users['password'].astype(str) == p)]
                if not m.empty:
                    st.session_state.auth.update({"in": True, "mid": u, "role": str(m.iloc[0]['role']).lower()})
                    st.rerun()
                else: st.error("Invalid Credentials")

    with tab_r:
        nu = st.text_input("New ID", key="reg_id")
        np = st.text_input("New Pass", type="password", key="reg_pw")
        if st.button("Create Account", key="btn_reg"):
            log_to_sheet("Users", {"memberid": nu, "password": np, "role": "user"})
            st.success("Registration Complete!")
    st.stop()

# --- 4. MAIN APP LAYOUT ---
tabs = st.tabs(["🏠 Cooper's Corner", "🛋️ Clara's Couch", "🎮 Games Center", "🛡️ Admin"])

# --- 5. COOPER'S CORNER ---
with tabs[0]:
    st.markdown('<div class="glass-panel"><div class="bot-avatar">🤖</div><h3 style="text-align:center;">Cooper</h3></div>', unsafe_allow_html=True)
    
    with st.expander("📊 Log Energy"):
        val = st.select_slider("How's your energy?", options=list(range(1,12)), value=6, key="sl_eng")
        if st.button("Save Entry", key="btn_save_e"):
            log_to_sheet("Sheet1", {"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), "memberid": st.session_state.auth['mid'], "energylog": val})
            st.toast("Energy Logged!")

    for msg in st.session_state.chats["Cooper"]:
        st.chat_message(msg["role"]).write(msg["content"])

    if prompt := st.chat_input("Message Cooper...", key="coop_chat"):
        st.session_state.chats["Cooper"].append({"role": "user", "content": prompt})
        log_to_sheet("ChatLogs", {"timestamp": datetime.now(), "memberid": st.session_state.auth['mid'], "agent": "Cooper", "role": "user", "content": prompt})
        
        try:
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":"You are Cooper."}]+st.session_state.chats["Cooper"][-3:]).choices[0].message.content
            st.session_state.chats["Cooper"].append({"role": "assistant", "content": res})
            log_to_sheet("ChatLogs", {"timestamp": datetime.now(), "memberid": st.session_state.auth['mid'], "agent": "Cooper", "role": "assistant", "content": res})
        except: st.error("AI Unavailable: Check API Key")
        st.rerun()

# --- 6. CLARA'S COUCH ---
with tabs[1]:
    st.markdown('<div class="glass-panel"><div class="bot-avatar" style="background:linear-gradient(135deg,#F472B6,#E11D48);">🛋️</div><h3 style="text-align:center;">Clara</h3></div>', unsafe_allow_html=True)
    
    # Visual Analytics
    logs = load_sheet("Sheet1")
    if not logs.empty:
        p_logs = logs[logs['memberid'].astype(str) == st.session_state.auth['mid']]
        if not p_logs.empty:
            fig = go.Figure(go.Scatter(x=pd.to_datetime(p_logs['timestamp']), y=p_logs['energylog'], fill='tozeroy', line=dict(color='#F472B6')))
            fig.update_layout(height=200, margin=dict(l=0,r=0,t=0,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="white"))
            st.plotly_chart(fig, use_container_width=True)

    for msg in st.session_state.chats["Clara"]:
        st.chat_message(msg["role"]).write(msg["content"])

    if prompt_clara := st.chat_input("Analyze with Clara...", key="clara_chat"):
        st.session_state.chats["Clara"].append({"role": "user", "content": prompt_clara})
        log_to_sheet("ChatLogs", {"timestamp": datetime.now(), "memberid": st.session_state.auth['mid'], "agent": "Clara", "role": "user", "content": prompt_clara})
        try:
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":"You are Clara."}]+st.session_state.chats["Clara"][-3:]).choices[0].message.content
            st.session_state.chats["Clara"].append({"role": "assistant", "content": res})
            log_to_sheet("ChatLogs", {"timestamp": datetime.now(), "memberid": st.session_state.auth['mid'], "agent": "Clara", "role": "assistant", "content": res})
        except: st.error("AI Unavailable")
        st.rerun()

# --- 7. GAMES CENTER (REFACTORED WITH EXIT CONTROLS) ---
with tabs[2]:
    # Use session state to track if a game is active
    if "active_game" not in st.session_state:
        st.session_state.active_game = None

    if st.session_state.active_game is None:
        st.markdown("### 🕹️ Select an Activity")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown('<div class="glass-panel" style="text-align:center;">🐍</div>', unsafe_allow_html=True)
            if st.button("Play Snake", key="sel_snake"):
                st.session_state.active_game = "Snake"
                st.rerun()
                
        with col2:
            st.markdown('<div class="glass-panel" style="text-align:center;">🧩</div>', unsafe_allow_html=True)
            if st.button("Play 2048", key="sel_2048"):
                st.session_state.active_game = "2048"
                st.rerun()

        with col3:
            st.markdown('<div class="glass-panel" style="text-align:center;">🧠</div>', unsafe_allow_html=True)
            if st.button("Memory Match", key="sel_memory"):
                st.session_state.active_game = "Memory"
                st.rerun()
    else:
        # Exit Button at the top
        if st.button("⬅️ Return to Games Menu", key="exit_game"):
            st.session_state.active_game = None
            st.rerun()

        st.info(f"Currently Playing: {st.session_state.active_game}")
        
        # Insert the existing Game HTML logic here based on st.session_state.active_game
        if st.session_state.active_game == "Snake":
            # [Insert the S_CODE HTML here from the previous message]
            st.components.v1.html(S_CODE, height=450)
            
        elif st.session_state.active_game == "Memory":
            # [Insert the M_CODE HTML here from the previous message]
            st.components.v1.html(M_CODE, height=450)
            
        elif st.session_state.active_game == "2048":
            # [Insert the T_CODE HTML here from the previous message]
            st.components.v1.html(T_CODE, height=450)

# --- 8. ADMIN DASHBOARD ---
with tabs[3]:
    if st.session_state.auth['role'] != "admin":
        st.warning("Admin Access Only")
    else:
        st.subheader("🛡️ Global Log Explorer")
        all_logs = load_sheet("ChatLogs")
        if not all_logs.empty:
            c1, c2 = st.columns(2)
            with c1: u_flt = st.multiselect("Users", all_logs['memberid'].unique(), key="ad_u")
            with c2: a_flt = st.multiselect("Agents", all_logs['agent'].unique(), key="ad_a")
            
            f_df = all_logs.copy()
            if u_flt: f_df = f_df[f_df['memberid'].isin(u_flt)]
            if a_flt: f_df = f_df[f_df['agent'].isin(a_flt)]
            st.dataframe(f_df, use_container_width=True, hide_index=True)
            st.download_button("Export Results", f_df.to_csv(index=False), "logs.csv", key="ad_dl")

# --- 9. LOGOUT ---
if st.sidebar.button("Logout", key="btn_logout"):
    st.session_state.clear()
    st.rerun()

