import streamlit as st
import pandas as pd
import datetime
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# --- 1. SETUP ---
st.set_page_config(page_title="Health Bridge", layout="wide")

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None, "name": None}
if "chat_log" not in st.session_state: st.session_state.chat_log = []
if "clara_history" not in st.session_state: st.session_state.clara_history = []

conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# --- 2. LOGIN & SIGN-UP (With LastLogin) ---
if not st.session_state.auth["logged_in"]:
    st.title("🧠 Health Bridge Portal")
    t1, t2 = st.tabs(["🔐 Login", "📝 Sign Up"])
    now_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    with t1:
        u_l = st.text_input("Couple ID", key="l_user")
        p_l = st.text_input("Password", type="password", key="l_pass")
        if st.button("Enter Dashboard"):
            udf = conn.read(worksheet="Users", ttl=0)
            m = udf[(udf['Username'].astype(str)==u_l) & (udf['Password'].astype(str)==p_l)]
            if not m.empty:
                # Update Timestamp
                udf.loc[udf['Username'].astype(str) == u_l, 'LastLogin'] = now_ts
                conn.update(worksheet="Users", data=udf)
                st.session_state.auth = {"logged_in": True, "cid": u_l, "name": m.iloc[0]['FullName']}
                st.rerun()
            else: st.error("Invalid credentials")

    with t2:
        n_u = st.text_input("New Couple ID", key="s_user").strip()
        n_p = st.text_input("New Password", type="password", key="s_pass").strip()
        n_n = st.text_input("Names (e.g. Alice & Bob)", key="s_name").strip()
        if st.button("Create Account"):
            udf = conn.read(worksheet="Users", ttl=0)
            if n_u in udf['Username'].astype(str).values: st.error("ID already taken")
            else:
                new_row = pd.DataFrame([{"Username": n_u, "Password": n_p, "FullName": n_n, "LastLogin": now_ts}])
                conn.update(worksheet="Users", data=pd.concat([udf, new_row], ignore_index=True))
                st.session_state.auth = {"logged_in": True, "cid": n_u, "name": n_n}
                st.rerun()
    st.stop()

# --- 3. DASHBOARD LOGIC ---
cid, cname = st.session_state.auth["cid"], st.session_state.auth["name"]

with st.sidebar:
    st.subheader(f"🏠 {cname}")
    # This defines the "mode" variable correctly
    mode = st.radio("Switch View:", ["Patient Portal", "Caregiver Command"])
    if st.button("Log Out"):
        st.session_state.auth = {"logged_in": False}
        st.rerun()

# --- 4. PORTALS ---
if mode == "Patient Portal":
    st.title("👋 Cooper Support")
    score = st.select_slider("How is your energy?", options=range(1,11), value=5)
    
    # Mood Circle Visual
    v = (score-1)/9.0
    rgb = f"rgb({int(128*(1-v*2))},0,{int(128+127*v*2)})" if v<0.5 else f"rgb(0,{int(255*(v-0.5)*2)},{int(255*(1-(v-0.5)*2))})"
    st.markdown(f'<div style="margin:10px auto; width:60px; height:60px; background-color:{rgb}; border-radius:50%; border:2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.2);"></div>', unsafe_allow_html=True)

    for m in st.session_state.chat_log:
        with st.chat_message("user" if m["type"]=="P" else "assistant"): st.write(m["msg"])
    
    p_in = st.chat_input("Talk to Cooper...")
    if p_in:
        st.session_state.chat_log.append({"type": "P", "msg": p_in})
        msgs = [{"role":"system","content":f"You are Cooper, a warm assistant for {cname}."}]
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
    else:
        st.info("No logs found for your account yet.")
    
    for m in st.session_state.clara_history:
        with st.chat_message(m["role"]): st.write(m["content"])
    
    c_in = st.chat_input("Ask Clara for an analysis...")
    if c_in:
        p_hist = "\n".join([f"Patient: {m['msg']}" for m in st.session_state.chat_log if m['type']=='P'][-5:])
        prompt = f"You are Clara, a health analyst for {cname}. Context: {p_hist}. Logs: {f_data.tail(5).to_string()}"
        msgs = [{"role":"system", "content": prompt}] + st.session_state.clara_history[-4:] + [{"role": "user", "content": c_in}]
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=msgs)
        st.session_state.clara_history.append({"role": "user", "content": c_in})
        st.session_state.clara_history.append({"role": "assistant", "content": res.choices[0].message.content})
        st.rerun()
