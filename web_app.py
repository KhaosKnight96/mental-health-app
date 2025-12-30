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
    if key not in st.session_state: 
        st.session_state[key] = val

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

def save_log(agent, role, content):
    new_row = pd.DataFrame([{
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "memberid": st.session_state.auth['mid'], 
        "agent": agent, "role": role, "content": content
    }])
    existing = get_data("ChatLogs", ["timestamp", "memberid", "agent", "role", "content"])
    sync_data("ChatLogs", pd.concat([existing, new_row], ignore_index=True))

# --- 3. AUTHENTICATION ---
USER_COLS = ["memberid", "firstname", "lastname", "password", "role", "bio", "dob"]

if not st.session_state.auth["in"]:
    st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge Pro</h1>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["Login", "Sign Up"])
    
    with t1:
        u_in = st.text_input("Member ID", key="l_u").lower().strip()
        p_in = st.text_input("Password", type="password", key="l_p")
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

    with t2:
        s_id = st.text_input("Choose ID", key="s_id").lower().strip()
        s_pw = st.text_input("Create Password", type="password", key="s_pw")
        c1, c2 = st.columns(2)
        with c1: s_fn = st.text_input("First Name", key="s_fn")
        with c2: s_ln = st.text_input("Last Name", key="s_ln")
        s_dob = st.date_input("Birthday", min_value=date(1940,1,1), key="s_dob")
        if st.button("Register", use_container_width=True):
            ud = get_data("Users", USER_COLS)
            if s_id in ud['memberid'].astype(str).values: st.error("ID Taken")
            else:
                new_u = pd.DataFrame([{"memberid":s_id, "firstname":s_fn, "lastname":s_ln, "password":s_pw, "role":"user", "bio":"Hi!", "dob":str(s_dob)}])
                sync_data("Users", pd.concat([ud, new_u], ignore_index=True))
                st.success("Created! Please Login.")
    st.stop()

# --- 4. TABS & DATA ---
tabs = st.tabs(["👤 Profile", "🤝 Cooper", "✨ Clara", "👥 Friends", "📩 Messages", "🛠️ Admin", "🚪 Logout"])
l_df = get_data("ChatLogs", ["timestamp", "memberid", "agent", "role", "content"])
f_df = get_data("Friends", ["sender", "receiver", "status"])
u_df = get_data("Users", USER_COLS)

# --- PROFILE TAB ---
with tabs[0]:
    c1, c2 = st.columns([1, 2])
    with c1:
        st.subheader(f"{st.session_state.auth['fname']} {st.session_state.auth['lname']}")
        st.caption(f"Age: {calculate_age(st.session_state.auth['dob'])}")
        if st.button("🗑️ Delete My Chat History"):
            new_logs = l_df[l_df['memberid'] != st.session_state.auth['mid']]
            sync_data("ChatLogs", new_logs)
            st.success("History Deleted"); st.rerun()
    with c2:
        st.write("Post to Feed")
        p_txt = st.text_area("Update", key="p_txt", label_visibility="collapsed")
        if st.button("Post") and p_txt:
            save_log("Feed", "user", p_txt); st.rerun()

# --- AI AGENTS ---
for i, name in enumerate(["Cooper", "Clara"]):
    with tabs[i+1]:
        hist = l_df[(l_df['memberid'] == st.session_state.auth['mid']) & (l_df['agent'] == name)].tail(15)
        for _, r in hist.iterrows():
            st.chat_message(r['role']).write(r['content'])
        
        if prompt := st.chat_input(f"Talk to {name}", key=f"chat_{name}"):
            save_log(name, "user", prompt)
            try:
                client = Groq(api_key=st.secrets["GROQ_API_KEY"].strip())
                sys = f"You are {name}. User is {st.session_state.auth['fname']}."
                msgs = [{"role": "system", "content": sys}] + [{"role": r.role, "content": r.content} for _, r in hist.iterrows()] + [{"role": "user", "content": prompt}]
                res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=msgs)
                save_log(name, "assistant", res.choices[0].message.content)
                st.rerun()
            except Exception as e: st.error(f"AI Error: {e}")

# --- FRIENDS TAB (FIXED IndexError) ---
with tabs[3]:
    if st.session_state.view_mid:
        if st.button("← Back"): st.session_state.view_mid = None; st.rerun()
        rows = u_df[u_df['memberid'] == st.session_state.view_mid]
        if not rows.empty:
            t = rows.iloc[0]
            st.header(f"{t['firstname']} {t['lastname']}")
            st.info(t['bio'])
        else: st.error("User not found."); st.session_state.view_mid = None
    else:
        sq = st.text_input("Search ID", key="f_sq")
        if sq:
            res = u_df[u_df['memberid'].str.contains(sq, na=False)]
            for _, r in res.iterrows():
                if st.button(f"View {r['memberid']}", key=f"v_{r['memberid']}"):
                    st.session_state.view_mid = r['memberid']; st.rerun()

# --- ADMIN PANEL (DEEP SEARCH) ---
with tabs[5]:
    if st.session_state.auth['role'] == "admin":
        st.subheader("🛡️ Admin Log Search")
        c1, c2, c3 = st.columns(3)
        with c1: a_agent = st.multiselect("Agents", l_df['agent'].unique(), default=l_df['agent'].unique())
        with c2: a_mid = st.text_input("Member ID Search")
        with c3: a_key = st.text_input("Keyword Search")
        
        filt = l_df[l_df['agent'].isin(a_agent)]
        if a_mid: filt = filt[filt['memberid'].str.contains(a_mid, case=False)]
        if a_key: filt = filt[filt['content'].str.contains(a_key, case=False)]
        
        st.dataframe(filt.sort_values('timestamp', ascending=False), use_container_width=True)
    else: st.error("Admin Only")

# --- LOGOUT ---
with tabs[6]:
    if st.button("Logout"): st.session_state.clear(); st.rerun()
