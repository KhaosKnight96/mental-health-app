import streamlit as st
import pandas as pd
import datetime
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# --- 1. SETTINGS & APP-WIDE STYLING ---
st.set_page_config(page_title="Health Bridge Portal", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0F172A !important; color: #F8FAFC !important; }
    [data-testid="stSidebar"] { background-color: #1E293B !important; border-right: 1px solid #334155; }
    .portal-card { background: #1E293B; padding: 25px; border-radius: 20px; border: 1px solid #334155; margin-bottom: 20px; }
    h1, h2, h3, p, label { color: #F8FAFC !important; }
    .stButton>button { border-radius: 12px !important; font-weight: 600 !important; }
</style>
""", unsafe_allow_html=True)

# --- 2. CONNECTIONS & STATE ---
conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None, "name": None, "role": None}
if "chat_log" not in st.session_state: st.session_state.chat_log = []
if "current_page" not in st.session_state: st.session_state.current_page = "Dashboard"

# --- 3. PERSISTENT HIGH SCORE SYNC ---
qp = st.query_params
if "last_score" in qp and st.session_state.auth["logged_in"]:
    new_s = int(qp["last_score"])
    udf = conn.read(worksheet="Users", ttl=0)
    user_row_idx = udf.index[udf['Username'].astype(str) == str(st.session_state.auth['cid'])].tolist()
    if user_row_idx:
        current_high = udf.at[user_row_idx[0], 'HighScore']
        if new_s > current_high:
            udf.at[user_row_idx[0], 'HighScore'] = new_s
            conn.update(worksheet="Users", data=udf)
            st.toast(f"🏆 Record Saved: {new_s}!", icon="🔥")
    st.query_params.clear()

# --- 4. LOGIN SYSTEM ---
if not st.session_state.auth["logged_in"]:
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge</h1>", unsafe_allow_html=True)
        u_l = st.text_input("Couple ID", key="l_u")
        p_l = st.text_input("Password", type="password", key="l_p")
        if st.button("Sign In", use_container_width=True, type="primary"):
            udf = conn.read(worksheet="Users", ttl=0)
            udf.columns = [str(c).strip().title() for c in udf.columns]
            m = udf[(udf['Username'].astype(str) == u_l) & (udf['Password'].astype(str) == p_l)]
            if not m.empty:
                st.session_state.auth.update({"logged_in": True, "cid": u_l, "name": m.iloc[0]['Fullname']})
                st.rerun()
            else: st.error("Invalid credentials.")
    st.stop()

if st.session_state.auth["role"] is None:
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown(f"<h2 style='text-align:center;'>Welcome, {st.session_state.auth['name']}</h2>", unsafe_allow_html=True)
        choice = st.radio("Choose your portal:", ["👤 Patient", "👩‍⚕️ Caregiver"], horizontal=True)
        if st.button("Enter Dashboard →", use_container_width=True, type="primary"):
            st.session_state.auth["role"] = "patient" if "Patient" in choice else "caregiver"
            st.rerun()
    st.stop()

cid, cname, role = st.session_state.auth["cid"], st.session_state.auth["name"], st.session_state.auth["role"]

# --- 5. NAVIGATION ---
with st.sidebar:
    st.title("🌉 Health Bridge")
    main_nav = "Dashboard" if role == "patient" else "Analytics"
    side_opt = st.radio("Navigation", [main_nav])
    with st.expander("🧩 Zen Zone", expanded=False):
        game_choice = st.selectbox("Select Break", ["Select a Game", "Memory Match", "Snake"])
    
    st.session_state.current_page = game_choice if game_choice != "Select a Game" else side_opt

    st.divider()
    if st.button("🔄 Switch Role"): st.session_state.auth["role"] = None; st.rerun()
    if st.button("🚪 Logout"): st.session_state.auth = {"logged_in": False}; st.rerun()

# --- 6. PAGE CONTENT ---
if st.session_state.current_page == "Dashboard":
    st.markdown(f'<div style="background: linear-gradient(90deg, #219EBC, #023047); padding: 25px; border-radius: 20px;"><h1>Hi {cname}! ☀️</h1></div>', unsafe_allow_html=True)
    col1, col2 = st.columns([1, 2])
    
    with col1:
        # High Score Card
        udf = conn.read(worksheet="Users", ttl=0)
        pb = udf.loc[udf['Username'].astype(str) == cid, 'HighScore'].values[0]
        st.markdown(f'<div class="portal-card"><h3 style="color:#FFD700;">🏆 Snake Record: {pb}</h3></div>', unsafe_allow_html=True)
        
        # Energy Log Card
        st.markdown('<div class="portal-card"><h3>✨ Energy Log</h3>', unsafe_allow_html=True)
        options = ["Resting", "Low", "Steady", "Good", "Active", "Vibrant", "Radiant"]
        val_map = {"Resting":1, "Low":3, "Steady":5, "Good":7, "Active":9, "Vibrant":10, "Radiant":11}
        score_text = st.select_slider("How are you feeling?", options=options, value="Steady")
        if st.button("Log Energy", use_container_width=True):
            df = conn.read(worksheet="Sheet1", ttl=0)
            new_row = pd.DataFrame([{"Date": datetime.date.today().strftime("%Y-%m-%d"), "Energy": val_map[score_text], "CoupleID": cid}])
            conn.update(worksheet="Sheet1", data=pd.concat([df, new_row], ignore_index=True))
            st.balloons()
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        # Cooper AI Card
        st.markdown('<div class="portal-card"><h3>🤖 Cooper AI</h3>', unsafe_allow_html=True)
        chat_box = st.container(height=350)
        with chat_box:
            for m in st.session_state.chat_log:
                with st.chat_message("user" if m["type"]=="P" else "assistant"): st.write(m["msg"])
        p_in = st.chat_input("Tell Cooper...")
        if p_in:
            st.session_state.chat_log.append({"type": "P", "msg": p_in})
            msgs = [{"role":"system","content":f"You are Cooper, a companion for {cname}."}] + \
                   [{"role": "user" if m["type"]=="P" else "assistant", "content": m["msg"]} for m in st.session_state.chat_log[-6:]]
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=msgs).choices[0].message.content
            st.session_state.chat_log.append({"type": "C", "msg": res}); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.current_page == "Analytics":
    st.title("👩‍⚕️ Caregiver Command")
    try:
        data = conn.read(worksheet="Sheet1", ttl=0)
        f_data = data[data['CoupleID'].astype(str) == str(cid)]
        if not f_data.empty:
            st.markdown('<div class="portal-card"><h3>📈 Patient Energy Trends</h3>', unsafe_allow_html=True)
            st.line_chart(f_data.set_index("Date")['Energy'])
            st.markdown('</div>', unsafe_allow_html=True)
        else: st.info("No energy data logged yet.")
    except: st.error("Could not connect to data.")

elif st.session_state.current_page == "Memory Match":
    # ... (Memory Match HTML and Logic from previous successful version)
    st.title("🧩 3D Memory Match")
    st.components.v1.html(memory_html, height=600) # memory_html defined here in full

elif st.session_state.current_page == "Snake":
    st.title("🐍 Zen Snake")
    st.components.v1.html(snake_html, height=600) # snake_html defined here in full
