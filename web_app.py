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

# --- 3. HELPER: LIVE COLOR CIRCLE ---
def get_live_color(score):
    val = (score - 1) / 9.0
    if val < 0.5:
        r, g, b = int(128 * (1 - val * 2)), 0, int(128 + (127 * val * 2))
    else:
        adj_val = (val - 0.5) * 2
        r, g, b = 0, int(255 * adj_val), int(255 * (1 - adj_val))
    emojis = {1:"😫", 2:"😖", 3:"🙁", 4:"☹️", 5:"😐", 6:"🙂", 7:"😊", 8:"😁", 9:"😆", 10:"🤩"}
    return f"rgb({r}, {g}, {b})", emojis.get(score, "😶")

# --- 4. LOGIN GATE ---
if not st.session_state.auth["logged_in"]:
    st.title("🔐 Secure Login")
    u_in = st.text_input("Couple ID").strip()
    p_in = st.text_input("Password", type="password").strip()
    
    if st.button("Enter Dashboard", use_container_width=True):
        try:
            udf = conn.read(worksheet="Users", ttl=0)
            m = udf[(udf['Username'].astype(str) == u_in) & (udf['Password'].astype(str) == p_in)]
            if not m.empty:
                st.session_state.auth = {"logged_in": True, "cid": u_in, "name": m.iloc[0]['FullName']}
                st.rerun()
            else: st.error("Invalid Username or Password")
        except: st.error("Spreadsheet connection error.")
    st.stop()

# --- 5. DASHBOARD VARIABLES ---
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

# --- 6. PORTALS ---
if mode == "Patient Portal":
    st.title("👋 Cooper Support")
    score = st.select_slider("How is your energy?", options=range(1,11), value=5)
    
    # Mood Circle Visual
    rgb, emo = get_live_color(score)
    st.markdown(f'<div style="margin:10px auto; width:80px; height:80px; background-color:{rgb}; border-radius:50%; display:flex; justify-content:center; align-items:center; border:3px solid white; box-shadow: 0 2px 5px rgba(0,0,0,0.2);"><span style="font-size:40px;">{emo}</span></div>', unsafe_allow_html=True)

    # Chat with Memory
    for m in st.session_state.chat_log:
        with st.chat_message("user" if m["type"]=="P" else "assistant"): st.write(m["msg"])
            
    msg = st.chat_input("Talk to Cooper...")
    if msg:
        st.session_state.chat_log.append({"type": "P", "msg": msg})
        # Cooper's Identity
        msgs = [{"role":"system","content":f"Your name is Cooper. You are a warm, compassionate assistant for {cname}. Focus on empathy."}]
        for m in st.session_state.chat_log[-6:]:
            msgs.append({"role": "user" if m["type"]=="P" else "assistant", "content": m["msg"]})
        
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
    
    if not f_data.empty:
        st.line_chart(f_data.set_index("Date")['Energy'])
    
    # Clara's Chat
    for m in st.session_state.clara_history:
        with st.chat_message(m["role"]): st.write(m["content"])
            
    c_msg = st.chat_input("Ask Clara for an analysis...")
    if c_msg:
        # Context building
        p_history = "\n".join([f"Patient: {m['msg']}" for m in st.session_state.chat_log if m['type']=='P'][-5:])
        e_history = f_data.tail(5).to_string()
        
        clara_prompt = f"You are Clara, a health analyst for {cname}. Patient Chat History: {p_history}. Energy Logs: {e_history}. Goal: Analyze trends for the caregiver."
        
        msgs = [{"role":"system", "content": clara_prompt}]
        for m in st.session_state.clara_history[-4:]: msgs.append(m)
        msgs.append({"role": "user", "content": c_msg})
        
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=msgs)
        st.session_state.clara_history.append({"role": "user", "content": c_msg})
        st.session_state.clara_history.append({"role": "assistant", "content": res.choices[0].message.content})
        st.rerun()
