import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, date

# --- 1. SETTINGS & SESSION ---
st.set_page_config(page_title="Health Bridge Pro", layout="wide", initial_sidebar_state="collapsed")

for key, val in {
    "auth": {"in": False, "mid": None, "role": "user", "fname": "", "lname": "", "bio": "", "dob": "2000-01-01"},
    "view_mid": None, "edit_mode": False
}.items():
    if key not in st.session_state: st.session_state[key] = val

# --- 2. DATA CORE ---
conn = st.connection("gsheets", type=GSheetsConnection)

def calculate_age(dob_str):
    try:
        b_day = datetime.strptime(str(dob_str), "%Y-%m-%d").date()
        today = date.today()
        return today.year - b_day.year - ((today.month, today.day) < (b_day.month, b_day.day))
    except: return "N/A"

@st.cache_data(ttl=1)
def get_data(ws, expected_cols=None):
    try:
        df = conn.read(worksheet=ws, ttl=0)
        if df is None or df.empty:
            return pd.DataFrame(columns=[c.lower() for c in expected_cols]) if expected_cols else pd.DataFrame()
        df.columns = [str(c).strip().lower() for c in df.columns]
        if expected_cols:
            for c in expected_cols:
                if c.lower() not in df.columns: df[c.lower()] = ""
        return df
    except: return pd.DataFrame(columns=[c.lower() for c in expected_cols]) if expected_cols else pd.DataFrame()

def sync_data(ws_name, df):
    conn.update(worksheet=ws_name, data=df)
    st.cache_data.clear()

# --- 3. AUTH LOGIC (SAFEGUARDED) ---
USER_COLS = ["memberid", "firstname", "lastname", "password", "role", "bio", "dob"]

if not st.session_state.auth["in"]:
    st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge Pro</h1>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["Login", "Sign Up"])
    with t1:
        u, p = st.text_input("ID", key="l_u").lower().strip(), st.text_input("Pass", type="password", key="l_p")
        if st.button("Sign In"):
            ud = get_data("Users", USER_COLS)
            m = ud[(ud['memberid'].astype(str).str.lower() == u) & (ud['password'].astype(str) == p)]
            if not m.empty:
                r = m.iloc[0]
                st.session_state.auth.update({"in":True, "mid":u, "role":r['role'], "fname":r['firstname'], "lname":r['lastname'], "bio":r['bio'], "dob":r['dob']})
                st.rerun()
            else: st.error("Account not found or password incorrect.")
    # (Signup logic remains same as v8.3)
    st.stop()

# --- 4. TABS & DATA ---
tabs = st.tabs(["👤 Profile", "🤝 Cooper", "✨ Clara", "👥 Friends", "📩 Messages", "🛠️ Admin", "🚪 Logout"])
l_df = get_data("ChatLogs", ["timestamp", "memberid", "agent", "role", "content"])
f_df = get_data("Friends", ["sender", "receiver", "status"])
u_df = get_data("Users", USER_COLS)

# --- PROFILE & DELETE CHAT HISTORY ---
with tabs[0]:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        st.subheader("Settings")
        if st.button("🗑️ Delete All My Chat History", type="secondary"):
            # Deletes all logs (Cooper, Clara, DMs) associated with this MemberID
            new_l_df = l_df[l_df['memberid'] != st.session_state.auth['mid']]
            sync_data("ChatLogs", new_l_df)
            st.success("Chat history wiped."); st.rerun()
    # (Profile display logic here...)

# --- ADMIN: IN-DEPTH SEARCH ---
with tabs[5]:
    if st.session_state.auth['role'] == "admin":
        st.header("🔍 Global Log Auditor")
        
        # Multi-Filter Sidebar or Top Bar
        c1, c2, c3, c4 = st.columns(4)
        with c1: f_agent = st.multiselect("Agents", l_df['agent'].unique(), default=l_df['agent'].unique())
        with c2: f_mid = st.text_input("Search Member ID")
        with c3: f_content = st.text_input("Keyword Search")
        with c4: f_role = st.selectbox("Role", ["All", "user", "assistant"])

        # Apply Filters
        query_df = l_df[l_df['agent'].isin(f_agent)]
        if f_mid: query_df = query_df[query_df['memberid'].str.contains(f_mid, case=False)]
        if f_content: query_df = query_df[query_df['content'].str.contains(f_content, case=False)]
        if f_role != "All": query_df = query_df[query_df['role'] == f_role]

        st.dataframe(query_df.sort_values('timestamp', ascending=False), use_container_width=True)
        st.write(f"Total Results: {len(query_df)}")
    else: st.error("Access Denied")

# --- FRIENDS: SAFEGUARDED (Fixes IndexError) ---
with tabs[3]:
    if st.session_state.view_mid:
        if st.button("← Back"): st.session_state.view_mid = None; st.rerun()
        
        target_rows = u_df[u_df['memberid'] == st.session_state.view_mid]
        if not target_rows.empty: # THE FIX
            target = target_rows.iloc[0]
            st.header(f"{target['firstname']} {target['lastname']}")
            # (Render Profile...)
        else:
            st.error("Profile not found."); st.session_state.view_mid = None
    # (Search/List logic here...)

# --- COOPER/CLARA AI ---
for i, name in enumerate(["Cooper", "Clara"]):
    with tabs[i+1]:
        hist = l_df[(l_df['memberid'] == st.session_state.auth['mid']) & (l_df['agent'] == name)].tail(15)
        # (Chat rendering...)
        if p := st.chat_input(f"Chat with {name}", key=f"chat_{name}"):
            # (Groq API logic...)
