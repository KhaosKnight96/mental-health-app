import streamlit as st
import pandas as pd
import datetime
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIG & SESSION ---
st.set_page_config(page_title="Health Bridge Private", layout="wide")

# This ensures all memory slots exist before the app runs
if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None, "name": None}
if "chat_log" not in st.session_state:
    st.session_state.chat_log = []

# --- 2. CONNECTIONS ---
conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# --- 3. LOGIN GATE ---
if not st.session_state.auth["logged_in"]:
    st.title("🔐 Secure Login")
    u_in = st.text_input("Couple ID").strip()
    p_in = st.text_input("Password", type="password").strip()
    
    if st.button("Enter Dashboard", use_container_width=True):
        try:
            udf = conn.read(worksheet="Users", ttl=0)
            # Match credentials
            m = udf[(udf['Username'].astype(str) == u_in) & (udf['Password'].astype(str) == p_in)]
            
            if not m.empty:
                st.session_state.auth = {
                    "logged_in": True, 
                    "cid": u_in, 
                    "name": m.iloc[0]['FullName']
                }
                st.rerun()
            else:
                st.error("Invalid Username or Password")
        except Exception as e:
            st.error(f"Sheet Error: Ensure your 'Users' tab has headers: Username, Password, FullName")
    st.stop()

# --- 4. DASHBOARD (Only runs if logged in) ---
# Retrieve variables safely
cid = st.session_state.auth.get("cid")
cname = st.session_state.auth.get("name")

with st.sidebar:
    st.subheader(f"🏠 {cname}")
    mode = st.radio("Switch View:", ["Patient Portal", "Caregiver Command"])
    if st.button("Logout"):
        st.session_state.auth = {"logged_in": False, "cid": None, "name": None}
        st.session_state.chat_log = []
        st.rerun()

# --- 5. PORTALS ---
if mode == "Patient Portal":
    st.title("🙋‍♂️ Patient Portal")
    val = st.slider("How is your energy?", 1, 10, 5)
    
    # Simple Chat UI
    for m in st.session_state.chat_log:
        with st.chat_message("user" if m["type"]=="P" else "assistant"): 
            st.write(m["msg"])
            
    msg = st.chat_input("Talk to Cooper...")
    if msg:
        st.session_state.chat_log.append({"type": "P", "msg": msg})
        res = client.chat.completions.create(
            model="llama-3.3-70b-versatile", 
            messages=[{"role":"system","content":f"You are Cooper, helping {cname}"},{"role":"user","content":msg}]
        )
        st.session_state.chat_log.append({"type": "C", "msg": res.choices[0].message.content})
        st.rerun()

    if st.button("Save Daily Score"):
        try:
            df = conn.read(worksheet="Sheet1", ttl=0)
            new_row = pd.DataFrame([{"Date": datetime.date.today().strftime("%Y-%m-%d"), "Energy": val, "CoupleID": cid}])
            conn.update(worksheet="Sheet1", data=pd.concat([df, new_row], ignore_index=True))
            st.success("Successfully Saved!")
        except Exception as e:
            st.error(f"Save failed: {e}")

else:
    st.title("👩‍⚕️ Caregiver Command")
    try:
        all_data = conn.read(worksheet="Sheet1", ttl=0)
        # Filter for this specific couple
        f_data = all_data[all_data['CoupleID'].astype(str) == str(cid)]
        
        if not f_data.empty:
            st.line_chart(f_data.set_index("Date")['Energy'])
            st.write(f"Displaying logs for account: {cid}")
        else:
            st.info("No logs have been saved for this account yet.")
    except:
        st.warning("Waiting for the first data entry to build the chart...")
