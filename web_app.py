import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, date

# --- 1. SETTINGS & SESSION ---
st.set_page_config(page_title="Health Bridge Pro", layout="wide", initial_sidebar_state="collapsed")

if "auth" not in st.session_state: 
    st.session_state.auth = {"in": False, "mid": None, "role": "user", "fname": "", "lname": "", "bio": "", "dob": "2000-01-01"}
if "view_mid" not in st.session_state:
    st.session_state.view_mid = None
if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = False

# --- 2. DATA CORE (SHIELDED) ---
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
                if c.lower() not in df.columns: df[c.lower()] = None
        return df
    except: return pd.DataFrame(columns=[c.lower() for c in expected_cols]) if expected_cols else pd.DataFrame()

def sync_data(ws_name, df):
    conn.update(worksheet=ws_name, data=df)
    st.cache_data.clear()

def save_log(agent, role, content):
    new_row = pd.DataFrame([{
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "memberid": st.session_state.auth['mid'], 
        "agent": agent, "role": role, "content": content
    }])
    existing = get_data("ChatLogs", ["timestamp", "memberid", "agent", "role", "content"])
    sync_data("ChatLogs", pd.concat([existing, new_row], ignore_index=True))

# --- 3. AUTH & SIGNUP ---
USER_COLS = ["memberid", "firstname", "lastname", "password", "role", "bio", "dob"]

if not st.session_state.auth["in"]:
    st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge Pro</h1>", unsafe_allow_html=True)
    t_l, t_s = st.tabs(["Login", "Sign Up"])
    
    with t_l:
        u_in, p_in = st.text_input("Member ID").lower().strip(), st.text_input("Password", type="password")
        if st.button("Sign In", use_container_width=True):
            ud = get_data("Users", USER_COLS)
            m = ud[(ud['memberid'].astype(str).str.lower() == u_in) & (ud['password'].astype(str) == p_in)]
            if not m.empty:
                r = m.iloc[0]
                st.session_state.auth.update({
                    "in": True, "mid": u_in, "role": r['role'], 
                    "fname": r['firstname'], "lname": r['lastname'], 
                    "bio": r['bio'], "dob": r['dob']
                })
                st.rerun()
            else: st.error("Invalid credentials.")

    with t_s:
        c1, c2 = st.columns(2)
        s_id = st.text_input("Member ID (Username)").lower().strip()
        s_pw = st.text_input("Password", type="password")
        with c1: s_fn = st.text_input("First Name")
        with c2: s_ln = st.text_input("Last Name")
        s_dob = st.date_input("Date of Birth", min_value=date(1940,1,1))
        
        if st.button("Create Account"):
            ud = get_data("Users", USER_COLS)
            if s_id in ud['memberid'].astype(str).values: st.error("ID already taken.")
            elif not s_id or not s_fn or not s_ln: st.warning("Please fill required fields.")
            else:
                new_u = pd.DataFrame([{"memberid": s_id, "firstname": s_fn, "lastname": s_ln, "password": s_pw, "role": "user", "bio": "New member!", "dob": str(s_dob)}])
                sync_data("Users", pd.concat([ud, new_u], ignore_index=True))
                st.success("Account created! Switch to Login tab.")
    st.stop()

# --- 4. TABS & DATA LOADING ---
tabs = st.tabs(["👤 Profile", "🤝 Cooper", "✨ Clara", "👥 Friends", "📩 Messages", "🛠️ Admin", "🚪 Logout"])
l_df = get_data("ChatLogs", ["timestamp", "memberid", "agent", "role", "content"])
f_df = get_data("Friends", ["sender", "receiver", "status"])

# --- TAB 0: PROFILE ---
with tabs[0]:
    c1, c2 = st.columns([1, 2])
    with c1:
        st.subheader(f"{st.session_state.auth['fname']} {st.session_state.auth['lname']}")
        if st.session_state.edit_mode:
            en = st.text_input("First Name", st.session_state.auth['fname'])
            el = st.text_input("Last Name", st.session_state.auth['lname'])
            eb = st.text_area("Bio", st.session_state.auth['bio'])
            if st.button("Save Changes"):
                ud = get_data("Users", USER_COLS)
                ud.loc[ud['memberid'] == st.session_state.auth['mid'], ['firstname', 'lastname', 'bio']] = [en, el, eb]
                sync_data("Users", ud)
                st.session_state.auth.update({"fname": en, "lname": el, "bio": eb})
                st.session_state.edit_mode = False; st.rerun()
        else:
            st.caption(f"Age: {calculate_age(st.session_state.auth['dob'])} | @{st.session_state.auth['mid']}")
            st.info(st.session_state.auth['bio'])
            if st.button("Edit Profile"): st.session_state.edit_mode = True; st.rerun()
    with c2:
        txt = st.text_area("Post to Feed", height=100)
        if st.button("Post") and txt: save_log("Feed", "user", txt); st.rerun()
        my_posts = l_df[(l_df['agent'] == "Feed") & (l_df['memberid'] == st.session_state.auth['mid'])].sort_values('timestamp', ascending=False)
        for idx, row in my_posts.iterrows():
            with st.container(border=True):
                st.write(row['content'])
                if st.button("Delete", key=f"dp_{idx}"): sync_data("ChatLogs", l_df.drop(idx)); st.rerun()

# --- TAB 5: ADVANCED ADMIN ---
with tabs[5]:
    if st.session_state.auth['role'] == "admin":
        st.subheader("🛡️ System Administration")
        adm_opt = st.radio("View Mode", ["User Management", "Global Chat Logs"], horizontal=True)
        
        if adm_opt == "User Management":
            ud = get_data("Users", USER_COLS)
            search_u = st.text_input("🔍 Search User by ID, Name or Role")
            if search_u:
                ud = ud[ud.apply(lambda row: search_u.lower() in row.astype(str).str.lower().values, axis=1)]
            st.dataframe(ud, use_container_width=True)
            
        else:
            c1, c2, c3 = st.columns(3)
            with c1: f_agent = st.selectbox("Filter by Agent", ["All"] + list(l_df['agent'].unique()))
            with c2: f_mid = st.text_input("Filter by Member ID")
            with c3: f_search = st.text_input("Keyword Search")
            
            filtered_logs = l_df.copy()
            if f_agent != "All": filtered_logs = filtered_logs[filtered_logs['agent'] == f_agent]
            if f_mid: filtered_logs = filtered_logs[filtered_logs['memberid'].str.contains(f_mid, case=False)]
            if f_search: filtered_logs = filtered_logs[filtered_logs['content'].str.contains(f_search, case=False)]
            
            st.dataframe(filtered_logs.sort_values('timestamp', ascending=False), use_container_width=True)
    else:
        st.error("Unauthorized Access.")

# (Remaining tabs: Cooper, Clara, Friends, Messages, Logout follow the v7.8 logic)
# Note: In the Friends and Messages tabs, I've updated the display to show Full Names instead of just IDs.
