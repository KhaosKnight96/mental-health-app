import streamlit as st
import pandas as pd
import datetime
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIG & SESSION ---
st.set_page_config(page_title="Health Bridge", page_icon="🧠", layout="wide")

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None, "name": None}
if "chat_log" not in st.session_state:
    st.session_state.chat_log = []
if "clara_history" not in st.session_state:
    st.session_state.clara_history = []

# --- 2. CONNECTIONS ---
conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# --- 3. LOGIN & SIGN-UP GATE ---
if not st.session_state.auth["logged_in"]:
    st.title("🧠 Health Bridge Portal")
    
    # Toggle between Login and Sign Up
    tab1, tab2 = st.tabs(["🔐 Login", "📝 Create New Account"])
    
    with tab1:
        u_in = st.text_input("Couple ID", key="login_u").strip()
        p_in = st.text_input("Password", type="password", key="login_p").strip()
        
        if st.button("Enter Dashboard", use_container_width=True):
            try:
                udf = conn.read(worksheet="Users", ttl=0)
                m = udf[(udf['Username'].astype(str) == u_in) & (udf['Password'].astype(str) == p_in)]
                if not m.empty:
                    st.session_state.auth = {"logged_in": True, "cid": u_in, "name": m.iloc[0]['FullName']}
                    st.rerun()
                else: st.error("Invalid Username or Password")
            except: st.error("Database connection error. Ensure 'Users' tab exists.")

    with tab2:
        st.subheader("Register your Household")
        new_u = st.text_input("Choose a Couple ID (e.g., AB1)", key="reg_u").strip()
        new_p = st.text_input("Choose a Password", type="password", key="reg_p").strip()
        new_name = st.text_input("Your Names (e.g., Alice & Bob)", key="reg_n").strip()
        
        if st.button("Register & Login", use_container_width=True):
            if new_u and new_p and new_name:
                try:
                    udf = conn.read(worksheet="Users", ttl=0)
                    if new_u in udf['Username'].astype(str).values:
                        st.error("This Couple ID is already taken. Please choose another.")
                    else:
                        # Append new user to the Google Sheet
                        new_user = pd.DataFrame([{"Username": new_u, "Password": new_p, "FullName": new_name}])
                        updated_udf = pd.concat([udf, new_user], ignore_index=True)
                        conn.update(worksheet="Users", data=updated_udf)
                        
                        # Auto-login after registration
                        st.session_state.auth = {"logged_in": True, "cid": new_u, "name": new_name}
                        st.success("Account created successfully!")
                        st.rerun()
                except Exception as e:
                    st.error(f"Registration failed: {e}")
            else:
                st.warning("Please fill in all fields.")
    st.stop()

# --- 4. DASHBOARD LOGIC (Same as before) ---
cid = st.session_state.auth.get("cid")
cname = st.session_state.auth.get("name")

with st.sidebar:
    st.subheader(f"🏠 {cname}")
    mode = st.radio("Switch View:", ["Patient Portal", "Caregiver Command"])
    if st.button("Logout"):
        st.session_state.auth = {"logged_in": False}
        st.session_state.chat_log = []
        st.session_state.clara_history = []
        st.rerun()

# --- 5. PORTALS (Cooper & Clara logic remains identical) ---
if mode == "Patient Portal":
    st.title("👋 Cooper Support")
    score = st.select_slider("Energy Level", options=range(1,11), value=5)
    
    # Mood Circle Visual
    def get_live_color(s):
        val = (s - 1) / 9.0
        r, g, b = (int(128 * (1 - val * 2)), 0, int(128 + (127 * val * 2))) if val < 0.5 else (0, int(255 * (val - 0.5) * 2), int(255 * (1 - (val - 0.5) * 2)))
        emojis = {1:"😫", 2:"😖", 3:"🙁", 4:"☹️", 5:"😐", 6:"🙂", 7:"😊", 8:"😁", 9:"😆", 10:"🤩"}
        return f"rgb({r}, {g}, {b})", emojis.get(s, "😶")

    rgb, emo = get_live_color(score)
    st.markdown(f'<div style="margin:10px auto; width:80px; height:80px; background-color:{rgb}; border-radius:50%; display:flex; justify-content:center; align-items:center; border:3px solid white; box-shadow: 0 2px 5px rgba(0,0,0,0.2);"><span style="font-size:40px;">{emo}</span></div>', unsafe_allow_html=True)

    for m in st.session_state.chat_log:
        with st.chat_message("user" if m["type"]=="P" else "assistant"): st.write(m["msg"])
    msg = st.chat_input("Talk to Cooper...")
    if msg:
        st.session_state.chat_log.append({"type": "P", "msg": msg})
        msgs = [{"role":"system","content":f"Your name is Cooper. Assistant for {cname}."}]
        for m in st.session_state.chat_log[-6:]: msgs.append({"role": "user" if m["type"]=="P" else "assistant", "content": m["msg"]})
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=msgs)
        st.session_state.chat_log.append({"type": "C", "msg": res.choices[0].message.content})
        st.rerun()

    if st.button("Save Daily Score"):
        df = conn.read(worksheet="Sheet1", ttl=0)
        new = pd.DataFrame([{"Date": datetime.date.today().strftime("%Y-%m-%d"), "Energy": score, "CoupleID": cid}])
        conn.update(worksheet="Sheet1", data=pd.concat([df, new], ignore_index=True))
        st.success("Successfully Saved!")

else:
    st.title("👩‍⚕️ Clara Analyst")
    all_d = conn.read(worksheet="Sheet1", ttl=0)
    f_data = all_d[all_d['CoupleID'].astype(str) == str(cid)]
    if not f_data.empty: st.line_chart(f_data.set_index("Date")['Energy'])
    
    for m in st.session_state.clara_history:
        with st.chat_message(m["role"]): st.write(m["content"])
    c_msg = st.chat_input("Ask Clara...")
    if c_msg:
        p_history = "\n".join([f"Patient: {m['msg']}" for m in st.session_state.chat_log if m['type']=='P'][-5:])
        prompt = f"You are Clara, health analyst for {
