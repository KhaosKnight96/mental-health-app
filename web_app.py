import streamlit as st
import pandas as pd
import datetime
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIG & SESSION ---
st.set_page_config(page_title="Health Bridge Private", layout="wide")

for key in ["auth", "chat_log", "clara_history"]:
    if key not in st.session_state:
        st.session_state[key] = {"logged_in": False} if key == "auth" else []

# --- 2. CONNECTIONS ---
conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# --- 3. LOGIN ---
if not st.session_state.auth["logged_in"]:
    st.title("🔐 Secure Household Login")
    u_in = st.text_input("Couple ID").strip()
    p_in = st.text_input("Password", type="password").strip()
    
    if st.button("Enter Dashboard", use_container_width=True):
        try:
            udf = conn.read(worksheet="Users", ttl=0)
            m = udf[(udf['Username'].astype(str) == u_in) & (udf['Password'].astype(str) == p_in)]
            if not m.empty:
                st.session_state.auth = {"logged_in": True, "couple_id": u_in, "name": m.iloc[0]['FullName']}
                st.rerun()
            else: st.error("Invalid credentials.")
        except: st.error("Check 'Users' sheet for columns: Username, Password, FullName")
    st.stop()

cid, cname = st.session_state.auth["couple_id"], st.session_state.auth["name"]

# --- 4. CHAT HANDLERS ---
def talk_to_cooper():
    txt = st.session_state.p_in
    if txt:
        st.session_state.chat_log.append({"role": "user", "type": "Patient", "content": txt})
        msgs = [{"role": "system", "content": f"You are Cooper, assistant for {cname}."}]
        for m in st.session_state.chat_log[-6:]:
            msgs.append({"role": "user" if m["type"] == "Patient" else "assistant", "content": m["content"]})
        res = client.chat.completions.create(messages=msgs, model="llama-3.3-70b-versatile")
        st.session_state.chat_log.append({"role": "assistant", "type": "Cooper", "content": res.choices[0].message.content})
        st.session_state.p_in = ""

def talk_to_clara(df):
    txt = st.session_state.c_in
    if txt:
        hist = "\n".join([f"{m.get('type')}: {m['content']}" for m in st.session_state.chat_log][-10:])
        prompt = f"You are Clara for {cname}. Context:\nChats: {hist}\nLogs: {df.tail(5).to_string()}"
        msgs = [{"role": "system", "content": prompt}] + st.session_state.clara_history[-4:] + [{"role": "user", "content": txt}]
        res = client.chat.completions.create(messages=msgs, model="llama-3.3-70b-versatile")
        st.session_state.clara_history.append({"role": "user", "content": txt})
        st.session_state.clara_history.append({"role": "assistant", "content": res.choices[0].message.content})
        st.session_state.c_in = ""

# --- 5. UI ---
with st.sidebar:
    st.subheader(f"🏠 {cname}")
    mode = st.radio("Portal:", ["Patient", "Caregiver"])
    if st.button("Log Out"):
        st.session_state.auth = {"logged_in": False}
        st.rerun()

if mode == "Patient":
    st.title("👋 Cooper Support")
    val = st.select_slider("Energy", options=range(1,11), value=5)
    for m in st.session_state.chat_log:
        with st.chat_message("user" if m["type"]=="Patient" else "assistant"): st.write(m["content"])
    st.text_input("Message Cooper...", key="p_in", on_change=talk_to_cooper)
    if st.button("Save Log"):
        try:
            all_d = conn.read(worksheet="Sheet1", ttl=0)
            row = pd.DataFrame([{"Date": datetime.date.today().strftime("%Y-%m-%d"), "Energy": val, "CoupleID": cid}])
            conn.update(worksheet="Sheet1", data=pd.concat([all_d, row], ignore_index=True))
            st.success("Saved!")
        except Exception as e: st.error(f"Error: {e}")
else:
    st.title("👩‍⚕️ Clara Analyst")
    f_data = pd.DataFrame()
    try:
        all_d = conn.read(worksheet="Sheet1", ttl="1m")
        f_data = all_d[all_d['CoupleID'].astype(str) == str(cid)]
        if not f_data.empty: st.line_chart(f_data.set_index("Date")['Energy'])
    except: st.info("No data yet.")
    for m in st.session_state.clara_history:
        with st.chat_message(m["role"]): st.write(m["content"])
    st.text_input("Ask Clara...", key="c_in", on_change=talk_to_clara, args=(f_data,))
