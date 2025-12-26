import streamlit as st
import pandas as pd
import datetime
from groq import Groq
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Health Bridge", layout="wide")

# Persistent state
for k in ["auth", "chat_log", "clara_history"]:
    if k not in st.session_state:
        st.session_state[k] = {"logged_in": False} if k == "auth" else []

conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

if not st.session_state.auth["logged_in"]:
    st.title("🔐 Login")
    u_in, p_in = st.text_input("Couple ID"), st.text_input("Password", type="password")
    if st.button("Enter"):
        try:
            udf = conn.read(worksheet="Users", ttl=0)
            # Debug check: st.write(udf.columns) # Uncomment this line to see actual column names
            m = udf[(udf['Username'].astype(str) == u_in) & (udf['Password'].astype(str) == p_in)]
            if not m.empty:
                st.session_state.auth = {"logged_in": True, "cid": u_in, "name": m.iloc[0]['FullName']}
                st.rerun()
            else: st.error("Wrong ID or Password")
        except Exception as e: st.error(f"Sheet Error: Make sure columns are 'Username', 'Password', 'FullName'. Details: {e}")
    st.stop()

# Dashboard logic
cid, cname = st.session_state.auth["cid"], st.session_state.auth["name"]
with st.sidebar:
    st.write(f"Logged in: **{cname}**")
    mode = st.radio("Switch View:", ["Patient", "Caregiver"])
    if st.button("Logout"):
        st.session_state.auth = {"logged_in": False}
        st.rerun()

if mode == "Patient":
    st.title("🙋‍♂️ Patient Portal")
    val = st.slider("Energy", 1, 10, 5)
    # Simple Chat
    for m in st.session_state.chat_log:
        with st.chat_message("user" if m["type"]=="P" else "assistant"): st.write(m["msg"])
    msg = st.chat_input("Talk to Cooper...")
    if msg:
        st.session_state.chat_log.append({"type": "P", "msg": msg})
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":msg}])
        st.session_state.chat_log.append({"type": "C", "msg": res.choices[0].message.content})
        st.rerun()
    if st.button("Save Daily Score"):
        df = conn.read(worksheet="Sheet1", ttl=0)
        new = pd.DataFrame([{"Date": datetime.date.today().strftime("%Y-%m-%d"), "Energy": val, "CoupleID": cid}])
        conn.update(worksheet="Sheet1", data=pd.concat([df, new]))
        st.success("Saved!")
else:
    st.title("👩‍⚕️ Caregiver Command")
    try:
        data = conn.read(worksheet="Sheet1", ttl=0)
        f_data = data[data['CoupleID'] == cid]
        if not f_data.empty: st.line_chart(f_data.set_index("Date")['Energy'])
        else: st.info("No data yet for this couple.")
    except: st.warning("Ready for first entry.")
