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

# Custom Styling for Message Bubbles
st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    .chat-container { padding: 20px; border-radius: 15px; background: #1E293B; margin-bottom: 20px; border: 1px solid #334155; }
    .msg-bubble { padding: 12px 16px; border-radius: 15px; margin: 5px 0; max-width: 80%; line-height: 1.4; }
    .msg-user { background: #2563EB; color: white; margin-left: auto; border-bottom-right-radius: 2px; }
    .msg-friend { background: #334155; color: white; border-bottom-left-radius: 2px; border-left: 4px solid #10B981; }
    .msg-ai { background: #475569; color: white; border-bottom-left-radius: 2px; border-left: 4px solid #6366F1; }
    .admin-card { background: #450A0A; border: 1px solid #991B1B; padding: 15px; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

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
                st.session_state.auth.update({"in": True, "mid": u_in, "role": r['role'], "fname": r['firstname'], "lname": r['lastname'], "bio": r['bio'], "dob": r['dob']})
                st.rerun()
            else: st.error("Incorrect credentials.")
    with t2:
        s_id = st.text_input("Choose ID", key="s_id").lower().strip()
        s_pw = st.text_input("Password", type="password", key="s_pw")
        c1, c2 = st.columns(2)
        with c1: s_fn = st.text_input("First Name", key="s_fn")
        with c2: s_ln = st.text_input("Last Name", key="s_ln")
        s_dob = st.date_input("Birthday", min_value=date(1940,1,1), key="s_dob")
        if st.button("Create Account", use_container_width=True):
            ud = get_data("Users", USER_COLS)
            if s_id in ud['memberid'].astype(str).values: st.error("ID Taken")
            else:
                new_u = pd.DataFrame([{"memberid":s_id, "firstname":s_fn, "lastname":s_ln, "password":s_pw, "role":"user", "bio":"New member", "dob":str(s_dob)}])
                sync_data("Users", pd.concat([ud, new_u], ignore_index=True))
                st.success("Registered! Go to Login.")
    st.stop()

# --- 4. DATA REFRESH ---
l_df = get_data("ChatLogs", ["timestamp", "memberid", "agent", "role", "content"])
f_df = get_data("Friends", ["sender", "receiver", "status"])
u_df = get_data("Users", USER_COLS)

tabs = st.tabs(["👤 Profile", "🤝 Cooper", "✨ Clara", "👥 Friends", "📩 Messages", "🛠️ Admin", "🚪 Logout"])

# --- COOPER & CLARA (THE BRAINS) ---

for i, name in enumerate(["Cooper", "Clara"]):
    with tabs[i+1]:
        persona = "a empathetic health-conscious best friend" if name == "Cooper" else "a bright, energetic wellness coach and friend"
        hist = l_df[(l_df['memberid'] == st.session_state.auth['mid']) & (l_df['agent'] == name)].tail(15)
        
        with st.container(height=450):
            for _, r in hist.iterrows():
                cls = "msg-user" if r['role'] == "user" else "msg-ai"
                st.markdown(f'<div class="msg-bubble {cls}">{r["content"]}</div>', unsafe_allow_html=True)
        
        if prompt := st.chat_input(f"Chat with {name}...", key=f"ai_{name}"):
            save_log(name, "user", prompt)
            try:
                client = Groq(api_key=st.secrets["GROQ_API_KEY"].strip())
                sys_prompt = f"You are {name}, {persona}. The user is your close friend {st.session_state.auth['fname']}. Use a warm, friendly tone. Age: {calculate_age(st.session_state.auth['dob'])}."
                msgs = [{"role": "system", "content": sys_prompt}] + [{"role": r.role, "content": r.content} for _, r in hist.iterrows()] + [{"role": "user", "content": prompt}]
                res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=msgs)
                save_log(name, "assistant", res.choices[0].message.content)
                st.rerun()
            except Exception as e: st.error(f"Brain Error: {e}")

# --- MESSAGES TAB (BETTER UI) ---
with tabs[4]:
    f1 = f_df[(f_df['sender']==st.session_state.auth['mid'])&(f_df['status']=="accepted")]['receiver'].tolist()
    f2 = f_df[(f_df['receiver']==st.session_state.auth['mid'])&(f_df['status']=="accepted")]['sender'].tolist()
    friends_list = list(set(f1+f2))
    
    if friends_list:
        selected_friend = st.selectbox("Select a friend to message", friends_list, key="dm_select")
        st.markdown(f"### Chat with @{selected_friend}")
        
        dm_hist = l_df[
            ((l_df['memberid']==st.session_state.auth['mid']) & (l_df['agent']==f"DM:{selected_friend}")) | 
            ((l_df['memberid']==selected_friend) & (l_df['agent']==f"DM:{st.session_state.auth['mid']}"))
        ].sort_values('timestamp')
        
        with st.container(height=400, border=True):
            for _, m in dm_hist.iterrows():
                is_me = m['memberid'] == st.session_state.auth['mid']
                cls = "msg-user" if is_me else "msg-friend"
                st.markdown(f'<div class="msg-bubble {cls}">{m["content"]}</div>', unsafe_allow_html=True)
        
        if dm_msg := st.chat_input("Write a message...", key="dm_input"):
            save_log(f"DM:{selected_friend}", "user", dm_msg)
            st.rerun()
    else:
        st.info("You haven't added any friends yet. Head to the Friends tab to find people!")

# --- ADMIN PANEL (MOVED DELETE FUNCTION) ---
with tabs[5]:
    if st.session_state.auth['role'] == "admin":
        st.subheader("🛠️ System Administration")
        
        with st.expander("🚨 Danger Zone - Data Management", expanded=False):
            st.markdown('<div class="admin-card">', unsafe_allow_html=True)
            target_del = st.text_input("Enter Member ID to wipe history for:", key="admin_del_id")
            if st.button("Confirm: Wipe Entire Chat History", type="primary"):
                if target_del:
                    new_logs = l_df[l_df['memberid'] != target_del]
                    sync_data("ChatLogs", new_logs)
                    st.success(f"Successfully purged all logs for {target_del}")
                else: st.warning("Please enter a Member ID")
            st.markdown('</div>', unsafe_allow_html=True)
        
        st.divider()
        st.subheader("Log Auditor")
        c1, c2 = st.columns(2)
        with c1: a_mid = st.text_input("Filter by Member ID", key="adm_f1")
        with c2: a_key = st.text_input("Filter by Keyword", key="adm_f2")
        
        filt = l_df.copy()
        if a_mid: filt = filt[filt['memberid'].str.contains(a_mid, case=False)]
        if a_key: filt = filt[filt['content'].str.contains(a_key, case=False)]
        st.dataframe(filt.sort_values('timestamp', ascending=False), use_container_width=True)
    else:
        st.error("Admin Access Required")

# (Remaining tabs: Profile, Friends, Logout following v8.5 logic)
with tabs[0]:
    st.header(f"Welcome, {st.session_state.auth['fname']}!")
    st.write(f"ID: @{st.session_state.auth['mid']} | Bio: {st.session_state.auth['bio']}")

with tabs[3]:
    if st.session_state.view_mid:
        if st.button("← Back"): st.session_state.view_mid = None; st.rerun()
        rows = u_df[u_df['memberid'] == st.session_state.view_mid]
        if not rows.empty:
            t = rows.iloc[0]
            st.subheader(f"{t['firstname']} {t['lastname']}")
            st.info(t['bio'])
    else:
        search = st.text_input("Search for friends by ID", key="f_search")
        if search:
            res = u_df[u_df['memberid'].str.contains(search, case=False)]
            for _, r in res.iterrows():
                if st.button(f"View Profile: @{r['memberid']}", key=f"btn_{r['memberid']}"):
                    st.session_state.view_mid = r['memberid']; st.rerun()

with tabs[6]:
    if st.button("Sign Out"): st.session_state.clear(); st.rerun()
