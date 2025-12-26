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

# --- 2. LOGIN & SIGN-UP ---
if not st.session_state.auth["logged_in"]:
    st.title("🧠 Health Bridge Portal")
    t1, t2 = st.tabs(["🔐 Login", "📝 Sign Up"])
    now_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    with t1:
        u_l, p_l = st.text_input("Couple ID", key="l_u"), st.text_input("Password", type="password", key="l_p")
        if st.button("Enter Dashboard"):
            udf = conn.read(worksheet="Users", ttl=0)
            m = udf[(udf['Username'].astype(str)==u_l) & (udf['Password'].astype(str)==p_l)]
            if not m.empty:
                udf.loc[udf['Username'].astype(str) == u_l, 'LastLogin'] = now_ts
                conn.update(worksheet="Users", data=udf)
                st.session_state.auth = {"logged_in": True, "cid": u_l, "name": m.iloc[0]['FullName']}
                st.rerun()
            else: st.error("Invalid credentials")

    with t2:
        n_u, n_p, n_n = st.text_input("New ID"), st.text_input("New Pass", type="password"), st.text_input("Names")
        if st.button("Create Account"):
            udf = conn.read(worksheet="Users", ttl=0)
            if n_u in udf['Username'].astype(str).values: st.error("ID taken")
            else:
                new_row = pd.DataFrame([{"Username": n_u, "Password": n_p, "FullName": n_n, "LastLogin": now_ts}])
                conn.update(worksheet="Users", data=pd.concat([udf, new_row], ignore_index=True))
                st.session_state.auth = {"logged_in": True, "cid": n_u, "name": n_n}
                st.rerun()
    st.stop()

# --- 3. HELPERS ---
cid, cname = st.session_state.auth["cid"], st.session_state.auth["name"]

def get_mood_assets(score):
    # Adjusted for 11 points (1-11)
    v = (score-1)/10.0 
    if v < 0.5: 
        rgb = f"rgb({int(128*(1-v*2))},0,{int(128+127*v*2)})"
    else: 
        rgb = f"rgb(0,{int(255*(v-0.5)*2)},{int(255*(1-(v-0.5)*2))})"
    
    # Expanded Emojis for 11 digits
    emojis = {
        1:"😫", 2:"😖", 3:"🙁", 4:"☹️", 5:"😟", 
        6:"😐", # Exact Middle
        7:"🙂", 8:"😊", 9:"😁", 10:"😆", 11:"🤩"
    }
    return rgb, emojis.get(score, "😐")

# --- 4. UI ---
with st.sidebar:
    st.subheader(f"🏠 {cname}")
    mode = st.radio("Portal:", ["Patient", "Caregiver"])
    if st.button("Log Out"):
        st.session_state.auth = {"logged_in": False}
        st.rerun()

if mode == "Patient":
    st.title("👋 Cooper Support")
    # Slider now ranges from 1 to 11
    score = st.select_slider("How is your energy? (6 is neutral)", options=range(1,12), value=6)
    
    color, smiley = get_mood_assets(score)
    st.markdown(f'''
        <div style="display: flex; justify-content: center; margin: 20px 0;">
            <div style="width: 100px; height: 100px; background-color: {color}; 
            border-radius: 50%; display: flex; align-items: center; justify-content: center; 
            font-size: 50px; border: 4px solid white; box-shadow: 0 4px 8px rgba(0,0,0,0.2);">
                {smiley}
            </div>
        </div>
    ''', unsafe_allow_html=True)

    for m in st.session_state.chat_log:
        with st.chat_message("user" if m["type"]=="P" else "assistant"): st.write(m["msg"])
    
    p_in = st.chat_input("Message Cooper...")
    if p_in:
        st.session_state.chat_log.append({"type": "P", "msg": p_in})
        msgs = [{"role":"system","content":f"You are Cooper, assistant for {cname}."}]
        for m in st.session_state.chat_log[-6:]:
            msgs.append({"role": "user" if m["type"]=="P" else "assistant", "content": m["msg"]})
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=msgs)
        st.session_state.chat_log.append({"type": "C", "msg": res.choices[0].message.content})
        st.rerun()

    if st.button("Save Daily Score", use_container_width=True):
        df = conn.read(worksheet="Sheet1", ttl=0)
        new = pd.DataFrame([{"Date": datetime.date.today().strftime("%Y-%m-%d"), "Energy": score, "CoupleID": cid}])
        conn.update(worksheet="Sheet1", data=pd.concat([df, new], ignore_index=True))
        st.success("Entry Saved!")

else:
    st.title("👩‍⚕️ Clara Analyst")
    all_d = conn.read(worksheet="Sheet1", ttl=0)
    f_data = all_d[all_d['CoupleID'].astype(str) == str(cid)]
    
    if not f_data.empty:
        # Chart will now reflect the 1-11 scale
        st.line_chart(f_data.set_index("Date")['Energy'])
    else:
        st.info("No logs found.")
    
    for m in st.session_state.clara_history:
        with st.chat_message(m["role"]): st.write(m["content"])
    c_in = st.chat_input("Ask Clara...")
    if c_in:
        hist = "\n".join([f"Patient: {m['msg']}" for m in st.session_state.chat_log if m['type']=='P'][-5:])
        prompt = f"You are Clara for {cname}. Chat: {hist}. Logs: {f_data.tail(5).to_string()}"
        msgs = [{"role":"system", "content": prompt}] + st.session_state.clara_history[-4:] + [{"role": "user", "content": c_in}]
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=msgs)
        st.session_state.clara_history.append({"role": "user", "content": c_in})
        st.session_state.clara_history.append({"role": "assistant", "content": res.choices[0].message.content})
        st.rerun()
