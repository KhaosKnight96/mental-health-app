import streamlit as st
import pandas as pd
import datetime
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# --- 1. SETUP ---
st.set_page_config(page_title="Health Bridge Admin", layout="wide")

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None, "name": None, "role": "user"}
if "chat_log" not in st.session_state: st.session_state.chat_log = []
if "clara_history" not in st.session_state: st.session_state.clara_history = []

conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# --- 2. THE LOGGING ENGINE ---
def log_to_master(cid, user_type, speaker, message):
    """Saves every chat message to the 'ChatLogs' worksheet."""
    try:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        # Try to read existing logs to append
        try:
            df_logs = conn.read(worksheet="ChatLogs", ttl=0)
        except:
            # Create dataframe if sheet is empty/missing headers
            df_logs = pd.DataFrame(columns=["Timestamp", "CoupleID", "UserType", "Speaker", "Message"])
        
        new_entry = pd.DataFrame([{
            "Timestamp": now, "CoupleID": cid, 
            "UserType": user_type, "Speaker": speaker, "Message": message
        }])
        conn.update(worksheet="ChatLogs", data=pd.concat([df_logs, new_entry], ignore_index=True))
    except Exception as e:
        print(f"Logging failed: {e}")

# --- 3. LOGIN & SIGN-UP (Robust) ---
if not st.session_state.auth["logged_in"]:
    st.title("🧠 Health Bridge Portal")
    t1, t2 = st.tabs(["🔐 Login", "📝 Sign Up"])
    now_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # Standardize column headers to prevent KeyErrors
    udf = conn.read(worksheet="Users", ttl=0)
    udf.columns = [c.strip().title() for c in udf.columns] # Username, Password, Fullname, Role

    with t1:
        u_l, p_l = st.text_input("Couple ID", key="l_u"), st.text_input("Password", type="password", key="l_p")
        if st.button("Enter Dashboard"):
            m = udf[(udf['Username'].astype(str)==u_l) & (udf['Password'].astype(str)==p_l)]
            if not m.empty:
                # Update LastLogin
                udf.loc[udf['Username'].astype(str) == u_l, 'Lastlogin'] = now_ts
                conn.update(worksheet="Users", data=udf)
                # Assign Role
                u_role = str(m.iloc[0]['Role']).lower() if 'Role' in m.columns else "user"
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

# --- 4. NAVIGATION ---
cid, cname, role = st.session_state.auth["cid"], st.session_state.auth["name"], st.session_state.auth["role"]

with st.sidebar:
    st.subheader(f"🏠 {cname}")
    options = ["Patient Portal", "Caregiver Command"]
    if role == "admin":
        options.append("🛡️ Admin Panel")
    
    mode = st.radio("Go to:", options)
    if st.button("Log Out"):
        st.session_state.auth = {"logged_in": False}
        st.rerun()

# --- 5. PORTALS ---
if mode == "Patient Portal":
    st.title("👋 Cooper Support")
    score = st.select_slider("Energy (1-11)", options=range(1,12), value=6)
    
    for m in st.session_state.chat_log:
        with st.chat_message("user" if m["type"]=="P" else "assistant"): st.write(m["msg"])
    
    p_in = st.chat_input("Message Cooper...")
    if p_in:
        log_to_master(cid, "Patient", "User", p_in) # LOGGING
        st.session_state.chat_log.append({"type": "P", "msg": p_in})
        msgs = [{"role":"system","content":f"You are Cooper for {cname}."}] + [{"role": "user" if m["type"]=="P" else "assistant", "content": m["msg"]} for m in st.session_state.chat_log[-6:]]
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=msgs).choices[0].message.content
        log_to_master(cid, "Patient", "Cooper", res) # LOGGING
        st.session_state.chat_log.append({"type": "C", "msg": res})
        st.rerun()

elif mode == "Caregiver Command":
    st.title("👩‍⚕️ Clara Analyst")
    all_d = conn.read(worksheet="Sheet1", ttl=0)
    f_data = all_d[all_d['CoupleID'].astype(str) == str(cid)]
    if not f_data.empty: st.line_chart(f_data.set_index("Date")['Energy'])
    
    c_in = st.chat_input("Ask Clara...")
    if c_in:
        log_to_master(cid, "Caregiver", "User", c_in) # LOGGING
        prompt = f"You are Clara for {cname}. Logs: {f_data.tail(5).to_string()}"
        msgs = [{"role":"system", "content": prompt}] + st.session_state.clara_history[-4:] + [{"role": "user", "content": c_in}]
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=msgs).choices[0].message.content
        log_to_master(cid, "Caregiver", "Clara", res) # LOGGING
        st.session_state.clara_history.append({"role": "user", "content": c_in})
        st.session_state.clara_history.append({"role": "assistant", "content": res})
        st.rerun()

# --- 6. THE ADMIN PANEL ---
elif mode == "🛡️ Admin Panel":
    st.title("🛡️ System Administration")
    
    try:
        master_logs = conn.read(worksheet="ChatLogs", ttl=0)
        
        st.subheader("Global Chat History")
        selected_couple = st.selectbox("Filter by Household", ["All Households"] + list(master_logs['CoupleID'].unique()))
        
        view_logs = master_logs if selected_couple == "All Households" else master_logs[master_logs['CoupleID'] == selected_couple]
        
        st.dataframe(view_logs.sort_values(by="Timestamp", ascending=False), use_container_width=True)
        
        if st.button("Refresh Logs"):
            st.rerun()
            
    except:
        st.info("No chat logs found yet. Ensure you have a 'ChatLogs' tab in your Google Sheet.")
