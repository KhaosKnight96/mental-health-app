import streamlit as st
import pandas as pd
import datetime
import random
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# --- 1. SETUP & CONFIG ---
st.set_page_config(page_title="Health Bridge Portal", layout="wide")

# Initialize Session States
if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None, "name": None, "role": "user"}
if "chat_log" not in st.session_state: st.session_state.chat_log = []
if "clara_history" not in st.session_state: st.session_state.clara_history = []

conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# --- 2. HELPER FUNCTIONS ---

def log_to_master(cid, user_type, speaker, message):
    """Logs AI interactions to the master ChatLogs sheet."""
    try:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        try:
            df_logs = conn.read(worksheet="ChatLogs", ttl=0)
        except:
            df_logs = pd.DataFrame(columns=["Timestamp", "CoupleID", "UserType", "Speaker", "Message"])
        
        new_entry = pd.DataFrame([{
            "Timestamp": now, "CoupleID": cid, 
            "UserType": user_type, "Speaker": speaker, "Message": message
        }])
        conn.update(worksheet="ChatLogs", data=pd.concat([df_logs, new_entry], ignore_index=True))
    except:
        pass

def sync_nav():
    """Callback to clear game selection when main navigation is clicked."""
    st.session_state.zen_nav = "--- Choose ---"

# --- 3. LOGIN & SIGN-UP ---
if not st.session_state.auth["logged_in"]:
    st.title("🧠 Health Bridge Portal")
    t1, t2 = st.tabs(["🔐 Login", "📝 Sign Up"])
    now_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # Load User Data
    try:
        udf = conn.read(worksheet="Users", ttl=0)
        udf.columns = [str(c).strip().title() for c in udf.columns] 
    except:
        st.error("Could not connect to the Users database.")
        st.stop()

    with t1:
        u_l = st.text_input("Couple ID", key="l_u")
        p_l = st.text_input("Password", type="password", key="l_p")
        if st.button("Enter Dashboard"):
            m = udf[(udf['Username'].astype(str)==u_l) & (udf['Password'].astype(str)==p_l)]
            if not m.empty:
                udf.loc[udf['Username'].astype(str) == u_l, 'Lastlogin'] = now_ts
                conn.update(worksheet="Users", data=udf)
                u_role = str(m.iloc[0]['Role']).strip().lower() if 'Role' in udf.columns else "user"
                st.session_state.auth = {"logged_in": True, "cid": u_l, "name": m.iloc[0]['Fullname'], "role": u_role}
                st.rerun()
            else:
                st.error("Invalid credentials")

    with t2:
        n_u = st.text_input("New ID")
        n_p = st.text_input("New Pass", type="password")
        n_n = st.text_input("Full Names")
        if st.button("Create Account"):
            if n_u in udf['Username'].astype(str).values:
                st.error("ID taken")
            else:
                new_row = pd.DataFrame([{"Username": n_u, "Password": n_p, "Fullname": n_n, "Lastlogin": now_ts, "Role": "user"}])
                conn.update(worksheet="Users", data=pd.concat([udf, new_row], ignore_index=True))
                st.session_state.auth = {"logged_in": True, "cid": n_u, "name": n_n, "role": "user"}
                st.rerun()
    st.stop()

# --- 4. NAVIGATION ---
cid, cname, role = st.session_state.auth["cid"], st.session_state.auth["name"], st.session_state.auth["role"]

with st.sidebar:
    st.subheader(f"🏠 {cname}")
    
    main_opts = ["Patient Portal", "Caregiver Command"]
    if role == "admin":
        main_opts.append("🛡️ Admin Panel")
    
    # on_change=sync_nav ensures the game closes when you click a main portal
    mode = st.radio("Go to:", main_opts, key="main_nav", on_change=sync_nav)
    
    st.divider()
    st.subheader("🧩 Zen Zone")
    game_choice = st.selectbox("Quick Break:", ["--- Choose ---", "Memory Match", "Breathing Space"], key="zen_nav")
    
    if game_choice != "--- Choose ---":
        mode = game_choice

    st.divider()
    if st.button("🚪 Log Out", use_container_width=True):
        st.session_state.auth = {"logged_in": False, "cid": None, "name": None, "role": "user"}
        st.session_state.chat_log, st.session_state.clara_history = [], []
        if "cards" in st.session_state: del st.session_state.cards
        st.rerun()

# --- 5. PORTAL LOGIC ---

if mode == "Patient Portal":
    st.title("👋 Cooper Support")
    score = st.select_slider("Energy (1-11)", options=range(1,12), value=6)
    
    # Visual Mood Indicator
    v = (score-1)/10.0 
    rgb = f"rgb({int(128*(1-v*2))},0,{int(128+127*v*2)})" if v < 0.5 else f"rgb(0,{int(255*(v-0.5)*2)},{int(255*(1-(v-0.5)*2))})"
    emojis = {1:"😫", 2:"😖", 3:"🙁", 4:"☹️", 5:"😟", 6:"😐", 7:"🙂", 8:"😊", 9:"😁", 10:"😆", 11:"🤩"}
    st.markdown(f'<div style="display:flex;justify-content:center;margin:20px 0;"><div style="width:80px;height:80px;background-color:{rgb};border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:40px;border:3px solid white;box-shadow:0 4px 8px rgba(0,0,0,0.2);">{emojis.get(score, "😐")}</div></div>', unsafe_allow_html=True)

    for m in st.session_state.chat_log:
        with st.chat_message("user" if m["type"]=="P" else "assistant"):
            st.write(m["msg"])
    
    p_in = st.chat_input("Message Cooper...")
    if p_in:
        log_to_master(cid, "Patient", "User", p_in)
        st.session_state.chat_log.append({"type": "P", "msg": p_in})
        msgs = [{"role":"system","content":f"You are Cooper for {cname}."}] + [{"role": "user" if m["type"]=="P" else "assistant", "content": m["msg"]} for m in st.session_state.chat_log[-6:]]
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=msgs).choices[0].message.content
        log_to_master(cid, "Patient", "Cooper", res)
        st.session_state.chat_log.append({"type": "C", "msg": res})
        st.rerun()

    if st.button("Save Daily Score", use_container_width=True):
        df = conn.read(worksheet="Sheet1", ttl=0)
        new = pd.DataFrame([{"Date": datetime.date.today().strftime("%Y-%m-%d"), "Energy": score, "CoupleID": cid}])
        conn.update(worksheet="Sheet1", data=pd.concat([df, new], ignore_index=True))
        st.success("Entry Saved!")

elif mode == "Caregiver Command":
    st.title("👩‍⚕️ Clara Analyst")
    try:
        all_d = conn.read(worksheet="Sheet1", ttl=0)
        f_data = all_d[all_d['CoupleID'].astype(str) == str(cid)]
        if not f_data.empty:
            st.line_chart(f_data.set_index("Date")['Energy'])
    except:
        f_data = pd.DataFrame()
    
    for m in st.session_state.clara_history:
        with st.chat_message(m["role"]):
            st.write(m["content"])
    
    c_in = st.chat_input("Ask Clara...")
    if c_in:
        log_to_master(cid, "Caregiver", "User", c_in)
        prompt = f"You are Clara for {cname}. Data: {f_data.tail(5).to_string()}"
        msgs = [{"role":"system", "content": prompt}] + st.session_state.clara_history[-4:] + [{"role": "user", "content": c_in}]
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=msgs).choices[0].message.content
        log_to_master(cid, "Caregiver", "Clara", res)
        st.session_state.clara_history.append({"role": "user", "content": c_in})
        st.session_state.clara_history.append({"role": "assistant", "content": res})
        st.rerun()

elif mode == "Memory Match":
    st.title("🧩 Zen Memory Match")
    # CSS targets only game pieces in columns to avoid whiting out other buttons
    st.markdown("""
        <style>
        [data-testid="column"] button {
            border-radius: 15px !important;
            height: 100px !important;
            font-size: 35px !important;
            background-color: #ffffff !important;
            border: 2px solid #E0E0E0 !important;
            color: black !important;
            box-shadow: 2px 2px 5px rgba(0,0,0,0.05) !important;
        }
        [data-testid="column"] button:hover {
            border-color: #4A90E2 !important;
            background-color: #F0F7FF !important;
        }
        </style>
    """, unsafe_allow_html=True)

    if "cards" not in st.session_state:
        icons = list("🌟🍀🎈💎🌈🦄🍎🎨") * 2
        random.shuffle(icons); st.session_state.cards = icons
        st.session_state.flipped, st.session_state.matched = [], []

    if len(st.session_state.matched) == len(st.session_state.cards):
        st.balloons()
        st.success("🎉 You matched all the pairs!")

    cols = st.columns(4)
    for i, icon in enumerate(st.session_state.cards):
        with cols[i % 4]:
            if i in st.session_state.matched:
                st.button(icon, key=f"m_{i}", disabled=True)
            elif i in st.session_state.flipped:
                st.button(icon, key=f"f_{i}")
            else:
                if st.button("❓", key=f"c_{i}"):
                    st.session_state.flipped.append(i)
                    if len(st.session_state.flipped) == 2:
                        i1, i2 = st.session_state.flipped
                        if st.session_state.cards[i1] == st.session_state.cards[i2]:
                            st.session_state.matched.extend([i1, i2])
                        st.session_state.flipped = []
                    st.rerun()
    
    if st.button("Reset Game", type="primary"):
        if "cards" in st.session_state: del st.session_state.cards
        st.rerun()

elif mode == "Breathing Space":
    st.title("🌬️ Breathing Space")
    st.markdown("""
        <style>
        .breath-container { display: flex; justify-content: center; align-items: center; height: 350px; }
        .circle { 
            width: 100px; height: 100px; background: #8ECAE6; border-radius: 50%; 
            animation: breathe 8s infinite ease-in-out; border: 4px solid #219EBC; 
        }
        @keyframes breathe { 
            0%, 100% { transform: scale(1); opacity: 0.6; } 
            50% { transform: scale(2.8); opacity: 1; } 
        }
        </style>
        <div class="breath-container"><div class="circle"></div></div>
    """, unsafe_allow_html=True)
    st.info("💡 Follow the circle: Inhale as it grows... Hold... Exhale as it shrinks.")

elif mode == "🛡️ Admin Panel":
    st.title("🛡️ Admin Oversight")
    try:
        logs_df = conn.read(worksheet="ChatLogs", ttl=0)
        id_list = ["All"] + list(logs_df['CoupleID'].unique())
        selected_id = st.selectbox("Filter by Household", id_list)
        view_df = logs_df if selected_id == "All" else logs_df[logs_df['CoupleID'] == selected_id]
        st.dataframe(view_df.sort_values(by="Timestamp", ascending=False), use_container_width=True)
    except:
        st.info("No logs found. Ensure you have a 'ChatLogs' tab in your Google Sheet.")
