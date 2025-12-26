import streamlit as st
import pandas as pd
import datetime
import random
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# --- 1. SETUP ---
st.set_page_config(page_title="Health Bridge", layout="wide")

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None, "name": None, "role": "user"}
if "chat_log" not in st.session_state: st.session_state.chat_log = []
if "clara_history" not in st.session_state: st.session_state.clara_history = []

conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# --- 2. LOGGING ENGINE ---
def log_to_master(cid, user_type, speaker, message):
    try:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        try:
            df_logs = conn.read(worksheet="ChatLogs", ttl=0)
        except:
            df_logs = pd.DataFrame(columns=["Timestamp", "CoupleID", "UserType", "Speaker", "Message"])
        
        new_entry = pd.DataFrame([{"Timestamp": now, "CoupleID": cid, "UserType": user_type, "Speaker": speaker, "Message": message}])
        conn.update(worksheet="ChatLogs", data=pd.concat([df_logs, new_entry], ignore_index=True))
    except: pass

# --- 3. LOGIN & SIGN-UP ---
if not st.session_state.auth["logged_in"]:
    st.title("🧠 Health Bridge Portal")
    t1, t2 = st.tabs(["🔐 Login", "📝 Sign Up"])
    now_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    udf = conn.read(worksheet="Users", ttl=0)
    udf.columns = [str(c).strip().title() for c in udf.columns] 

    with t1:
        u_l, p_l = st.text_input("Couple ID", key="l_u"), st.text_input("Password", type="password", key="l_p")
        if st.button("Enter Dashboard"):
            m = udf[(udf['Username'].astype(str)==u_l) & (udf['Password'].astype(str)==p_l)]
            if not m.empty:
                udf.loc[udf['Username'].astype(str) == u_l, 'Lastlogin'] = now_ts
                conn.update(worksheet="Users", data=udf)
                u_role = str(m.iloc[0]['Role']).strip().lower() if 'Role' in udf.columns else "user"
                st.session_state.auth = {"logged_in": True, "cid": u_l, "name": m.iloc[0]['Fullname'], "role": u_role}
                st.rerun()
            else: st.error("Invalid credentials")
    with t2:
        n_u, n_p, n_n = st.text_input("New ID"), st.text_input("New Pass", type="password"), st.text_input("Names")
        if st.button("Create Account"):
            if n_u in udf['Username'].astype(str).values: st.error("ID taken")
            else:
                new_row = pd.DataFrame([{"Username": n_u, "Password": n_p, "Fullname": n_n, "Lastlogin": now_ts, "Role": "user"}])
                conn.update(worksheet="Users", data=pd.concat([udf, new_row], ignore_index=True))
                st.session_state.auth = {"logged_in": True, "cid": n_u, "name": n_n, "role": "user"}
                st.rerun()
    st.stop()

# --- 4. NAVIGATION & ZEN DROPDOWN ---
cid, cname, role = st.session_state.auth["cid"], st.session_state.auth["name"], st.session_state.auth["role"]

with st.sidebar:
    st.subheader(f"🏠 {cname}")
    
    # Primary Portals
    main_options = ["Patient Portal", "Caregiver Command"]
    if role == "admin": 
        main_options.append("🛡️ Admin Panel")
    
    mode = st.radio("Go to:", main_options)
    
    st.divider()
    
    # THE ZEN ZONE PULLDOWN
    st.subheader("🧩 Zen Zone")
    game_choice = st.selectbox("Select a Activity:", ["--- Choose ---", "Memory Match", "Breathing Space"])
    
    # If a game is selected, we override the 'mode'
    if game_choice != "--- Choose ---":
        mode = game_choice

    st.divider()
    if st.button("🚪 Log Out", use_container_width=True):
        st.session_state.auth = {"logged_in": False, "cid": None, "name": None, "role": "user"}
        st.session_state.chat_log, st.session_state.clara_history = [], []
        if "cards" in st.session_state: del st.session_state.cards
        st.rerun()

# --- 5. PORTALS & GAMES ---

# A. PATIENT PORTAL
if mode == "Patient Portal":
    st.title("👋 Cooper Support")
    # ... (Your existing Cooper/Slider code goes here)

# B. CAREGIVER PORTAL
elif mode == "Caregiver Command":
    st.title("👩‍⚕️ Clara Analyst")
    # ... (Your existing Clara/Graph code goes here)

# C. ADMIN PANEL
elif mode == "🛡️ Admin Panel":
    st.title("🛡️ Admin Oversight")
    # ... (Your existing Admin log code goes here)

# D. THE GAMES (Triggered by the Sidebar Pulldown)
elif mode == "Memory Match":
    st.title("🧩 Zen Memory Match")
    if "cards" not in st.session_state:
        icons = list("🌟🍀🎈💎🌈🦄🍎🎨") * 2
        random.shuffle(icons)
        st.session_state.cards = icons
        st.session_state.flipped = []
        st.session_state.matched = []

    cols = st.columns(4)
    for i, icon in enumerate(st.session_state.cards):
        with cols[i % 4]:
            if i in st.session_state.matched: st.button(icon, key=f"m_{i}", disabled=True)
            elif i in st.session_state.flipped: st.button(icon, key=f"f_{i}")
            else:
                if st.button("❓", key=f"c_{i}"):
                    st.session_state.flipped.append(i)
                    if len(st.session_state.flipped) == 2:
                        idx1, idx2 = st.session_state.flipped
                        if st.session_state.cards[idx1] == st.session_state.cards[idx2]: 
                            st.session_state.matched.extend([idx1, idx2])
                        st.session_state.flipped = []
                    st.rerun()
    if st.button("Reset Game"): 
        del st.session_state.cards
        st.rerun()

elif mode == "Breathing Space":
    st.title("🌬️ Breathing Space")
    st.write("Follow the circle to find your center.")
    st.info("Inhale for 4 seconds... Hold for 7... Exhale for 8.")
    # You can add a simple CSS animation here later!
