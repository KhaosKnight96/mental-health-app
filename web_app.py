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

    .stButton>button { border-radius: 12px; font-weight: 600; height: 3.5em; width: 100%; border: none; }
    .stTabs [data-baseweb="tab-list"] { gap: 20px; }
    .stTabs [data-baseweb="tab"] { background-color: #1E293B; border-radius: 10px; padding: 10px 20px; color: white; }
    .stTabs [aria-selected="true"] { background-color: #38BDF8 !important; }
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
st.markdown(f"### Hello, {st.session_state.auth['name']} ✨")
# RENAMED TABS
main_nav = st.tabs(["🏠 Cooper's Corner", "🛋️ Clara's Couch", "🎮 Games", "🚪 Logout"])

# --- 5. COOPER'S CORNER ---
with main_nav[0]:
    col1, col2 = st.columns([1, 1.3])
    with col1:
        st.markdown('<div class="portal-card"><h3>⚡ Energy Status</h3>', unsafe_allow_html=True)
        ev = st.slider("Energy Level", 1, 11, 6)
        emoji_map = {1:'🚨', 2:'🪫', 3:'😫', 4:'🥱', 5:'🙁', 6:'😐', 7:'🙂', 8:'😊', 9:'⚡', 10:'🚀', 11:'☀️'}
        st.markdown(f"<h1 style='text-align:center; font-size:80px;'>{emoji_map[ev]}</h1>", unsafe_allow_html=True)
        if st.button("💾 Sync Data"):
            new_row = pd.DataFrame([{"Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), "CoupleID": st.session_state.auth['cid'], "EnergyLog": ev}])
            conn.update(worksheet="Sheet1", data=pd.concat([conn.read(worksheet="Sheet1", ttl=0), new_row], ignore_index=True))
            st.success("Logged!")
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
            <div class="glass-panel">
                <div class="avatar-pulse" style="background: linear-gradient(135deg, #38BDF8, #6366F1);">👤</div>
                <h3 style='text-align:center; color:#38BDF8; margin-bottom:0;'>Cooper's Corner</h3>
                <p style='text-align:center; color:#94A3B8; font-size:14px;'>Your personal space for reflection</p>
            </div>
        """, unsafe_allow_html=True)
        
        chat_box = st.container(height=380, border=False)
        with chat_box:
            for m in st.session_state.cooper_logs:
                with st.chat_message(m["role"], avatar="👤"): st.write(m["content"])
        
        if p := st.chat_input("Speak with Cooper..."):
            st.session_state.cooper_logs.append({"role": "user", "content": p})
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":"You are Cooper, a wise and warm human companion. You are empathetic, calm, and professional."}]+st.session_state.cooper_logs[-5:]).choices[0].message.content
            st.session_state.cooper_logs.append({"role": "assistant", "content": res})
            st.rerun()

# --- 6. CLARA'S COUCH (CAREGIVER ANALYTICS) ---
with main_nav[1]:
    st.markdown(f"""
        <div class="glass-panel">
            <div class="avatar-pulse" style="background: linear-gradient(135deg, #F472B6, #FB7185);">🧘‍♀️</div>
            <h3 style='text-align:center; color:#F472B6; margin-bottom:0;'>Clara's Couch</h3>
            <p style='text-align:center; color:#94A3B8; font-size:14px;'>Weekly Insights & Clinical Trends</p>
        </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns([1.5, 1])
    
    with c1:
        try:
            df_l = conn.read(worksheet="Sheet1", ttl=0)
            df_p = df_l[df_l['CoupleID'].astype(str) == str(st.session_state.auth['cid'])].copy()
            df_p['Timestamp'] = pd.to_datetime(df_p['Timestamp'])
            df_p = df_p.sort_values('Timestamp')
            
            if not df_p.empty:
                # LINE CHART
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df_p['Timestamp'], y=df_p['EnergyLog'], fill='tozeroy', 
                                         line=dict(color='#F472B6', width=4), name="Energy"))
                fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', 
                                  font=dict(color="white"), height=300, margin=dict(l=0,r=0,t=0,b=0))
                st.plotly_chart(fig, use_container_width=True)
                
                # WEEKLY SUMMARY LOGIC
                if st.button("✨ Generate Clara's Weekly Insight"):
                    last_week = df_p[df_p['Timestamp'] > (datetime.now() - timedelta(days=7))]
                    data_summary = last_week['EnergyLog'].to_list()
                    
                    with st.spinner("Analyzing patterns..."):
                        insight = client.chat.completions.create(
                            model="llama-3.3-70b-versatile",
                            messages=[{"role":"system","content":"You are Clara, a clinical analyst. Summarize the following energy levels (1-11) from the past week into a 3-sentence professional insight for a caregiver. Focus on stability and burnout risk."},
                                      {"role":"user","content": f"Data: {data_summary}"}]
                        ).choices[0].message.content
                        st.info(insight)
        except: st.info("Recording history needed for Clara to analyze trends.")

    with c2:
        clara_chat = st.container(height=400, border=False)
        with clara_chat:
            for m in st.session_state.clara_logs:
                with st.chat_message(m["role"], avatar="🧘‍♀️"): st.write(m["content"])
        if cp := st.chat_input("Analyze trends with Clara..."):
            st.session_state.clara_logs.append({"role": "user", "content": cp})
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":"You are Clara, a clinical analyst and caregiver support AI. You focus on data-driven insights and mental health patterns."}]+st.session_state.clara_logs[-5:]).choices[0].message.content
            st.session_state.clara_logs.append({"role": "assistant", "content": res})
            st.rerun()

# --- 7. GAMES ---
with main_nav[2]:
    st.markdown('<div class="portal-card">', unsafe_allow_html=True)
    gt = st.radio("Select Activity", ["Modern Snake", "Memory Match"], horizontal=True)
    st.markdown('</div>', unsafe_allow_html=True)
    # Your snake/memory logic here
    st.info(f"{gt} initialized. Play to boost your energy score!")

with main_nav[3]:
    if st.button("Logout"):
        st.session_state.auth = {"logged_in": False}
        st.rerun()
