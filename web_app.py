import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, date

# --- 1. SETTINGS & SESSION ---
st.set_page_config(page_title="Health Bridge Pro", layout="wide", initial_sidebar_state="collapsed")

# Initialize Session States
defaults = {
    "auth": {"in": False, "mid": None, "role": "user", "fname": "", "lname": "", "bio": "", "dob": "2000-01-01"},
    "view_mid": None,
    "active_chat_mid": None,
    "edit_mode": False
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# Custom CSS for Professional UI
st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    .msg-bubble { padding: 12px 18px; border-radius: 18px; margin-bottom: 10px; max-width: 80%; line-height: 1.4; }
    .me { background: #2563EB; color: white; margin-left: auto; border-bottom-right-radius: 2px; }
    .them { background: #334155; color: white; border-bottom-left-radius: 2px; border-left: 4px solid #10B981; }
    .ai-bubble { background: #475569; color: white; border-bottom-left-radius: 2px; border-left: 4px solid #6366F1; }
    .feed-card { background: #1E293B; padding: 15px; border-radius: 15px; border: 1px solid #334155; margin-bottom: 15px; }
    .active-chat-btn { border-left: 5px solid #6366F1 !important; background: #334155 !important; }
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

# --- 3. FIXED AUTHENTICATION (STR Accessor Fix) ---
USER_COLS = ["memberid", "firstname", "lastname", "password", "role", "bio", "dob"]

if not st.session_state.auth["in"]:
    st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge Pro</h1>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["Login", "Sign Up"])
    
    with t1:
        u_in = st.text_input("Member ID").strip().lower()
        p_in = st.text_input("Password", type="password").strip()
        if st.button("Sign In", use_container_width=True):
            ud = get_data("Users", USER_COLS)
            # FIXED: Added .str accessor to perform lower() and strip() on the Series
            ud['mid_check'] = ud['memberid'].astype(str).str.strip().str.lower()
            ud['pw_check'] = ud['password'].astype(str).str.strip()
            
            match = ud[(ud['mid_check'] == u_in) & (ud['pw_check'] == p_in)]
            
            if not match.empty:
                r = match.iloc[0]
                st.session_state.auth.update({
                    "in": True, "mid": str(r['memberid']), "role": r['role'], 
                    "fname": r['firstname'], "lname": r['lastname'], 
                    "bio": r['bio'], "dob": r['dob']
                })
                st.rerun()
            else: st.error("Login failed. Check ID/Password.")

    with t2:
        sid = st.text_input("Choose ID").lower().strip()
        spw = st.text_input("Create Password", type="password")
        c1, c2 = st.columns(2)
        with c1: sfn = st.text_input("First Name")
        with c2: sln = st.text_input("Last Name")
        sdob = st.date_input("Birthday", min_value=date(1940,1,1))
        if st.button("Register Account"):
            ud = get_data("Users", USER_COLS)
            # FIXED: Added .str accessor here as well
            if sid in ud['memberid'].astype(str).str.lower().values: 
                st.error("ID Taken")
            else:
                new_u = pd.DataFrame([{"memberid":sid, "firstname":sfn, "lastname":sln, "password":spw, "role":"user", "bio":"Hello!", "dob":str(sdob)}])
                sync_data("Users", pd.concat([ud, new_u], ignore_index=True)); st.success("Account created!")
    st.stop()

# --- 4. DATA REFRESH ---
l_df = get_data("ChatLogs", ["timestamp", "memberid", "agent", "role", "content"])
f_df = get_data("Friends", ["sender", "receiver", "status"])
u_df = get_data("Users", USER_COLS)

# Get Accepted Friends
mid = st.session_state.auth['mid']
f_acc = f_df[((f_df['sender']==mid) | (f_df['receiver']==mid)) & (f_df['status']=="accepted")]
friends_ids = [r['receiver'] if r['sender'] == mid else r['sender'] for _, r in f_acc.iterrows()]

tabs = st.tabs(["👤 Profile", "🤝 Cooper", "✨ Clara", "👥 Friends", "📩 Messages", "🛠️ Admin", "🚪 Logout"])

# --- TAB 0: PROFILE ---
with tabs[0]:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        st.subheader("My Info")
        st.markdown(f"**{st.session_state.auth['fname']} {st.session_state.auth['lname']}**")
        st.caption(f"Age: {calculate_age(st.session_state.auth['dob'])}")
        st.write(st.session_state.auth['bio'])
    with c2:
        st.subheader("Timeline")
        p_txt = st.text_area("Write something...", key="profile_p_in")
        if st.button("Post Update"):
            if p_txt: save_log("Feed", "user", p_txt); st.rerun()
        for _, r in l_df[(l_df['agent']=="Feed") & (l_df['memberid']==mid)].sort_values('timestamp', ascending=False).iterrows():
            st.markdown(f'<div class="feed-card"><small>{r["timestamp"]}</small><br>{r["content"]}</div>', unsafe_allow_html=True)
    with c3:
        st.subheader("My Friends")
        for fid in friends_ids:
            f_row = u_df[u_df['memberid'].astype(str) == str(fid)]
            name = f"{f_row.iloc[0]['firstname']}" if not f_row.empty else fid
            if st.button(f"👤 {name}", key=f"p_side_{fid}", use_container_width=True):
                st.session_state.view_mid = fid; st.rerun()

# --- TAB 3: FRIENDS ---
with tabs[3]:
    if st.session_state.view_mid:
        if st.button("← Back"): st.session_state.view_mid = None; st.rerun()
        t_row = u_df[u_df['memberid'].astype(str) == str(st.session_state.view_mid)]
        if not t_row.empty:
            t = t_row.iloc[0]
            st.title(f"{t['firstname']} {t['lastname']}")
            st.write(t['bio'])
            st.subheader("Timeline")
            for _, r in l_df[(l_df['agent']=="Feed") & (l_df['memberid']==str(st.session_state.view_mid))].sort_values('timestamp', ascending=False).iterrows():
                st.markdown(f'<div class="feed-card"><small>{r["timestamp"]}</small><p>{r["content"]}</p></div>', unsafe_allow_html=True)
    else:
        st.subheader("Connections")
        for fid in friends_ids:
            f_row = u_df[u_df['memberid'].astype(str) == str(fid)]
            name = f"{f_row.iloc[0]['firstname']} {f_row.iloc[0]['lastname']}" if not f_row.empty else fid
            if st.button(f"View Profile: {name}", key=f"f_tab_{fid}"):
                st.session_state.view_mid = fid; st.rerun()

# --- TAB 4: MESSAGES ---
with tabs[4]:
    mc1, mc2 = st.columns([1, 3])
    with mc1:
        st.subheader("Chats")
        for fid in friends_ids:
            f_row = u_df[u_df['memberid'].astype(str) == str(fid)]
            f_name = f_row.iloc[0]['firstname'] if not f_row.empty else fid
            btn_style = "active-chat-btn" if st.session_state.active_chat_mid == fid else ""
            if st.button(f"💬 {f_name}", key=f"m_list_{fid}", use_container_width=True):
                st.session_state.active_chat_mid = fid; st.rerun()
    with mc2:
        target = st.session_state.active_chat_mid
        if target:
            dm_hist = l_df[((l_df['memberid']==mid)&(l_df['agent']==f"DM:{target}")) | ((l_df['memberid']==str(target))&(l_df['agent']==f"DM:{mid}"))].sort_values('timestamp')
            with st.container(height=450):
                for _, m in dm_hist.iterrows():
                    cls = "me" if m['memberid'] == mid else "them"
                    st.markdown(f'<div class="msg-bubble {cls}">{m["content"]}</div>', unsafe_allow_html=True)
            if msg_in := st.chat_input("Message..."):
                save_log(f"DM:{target}", "user", msg_in); st.rerun()
        else: st.info("Select a chat to begin.")

# --- TAB 5: ADMIN PANEL ---
with tabs[5]:
    if st.session_state.auth['role'] == "admin":
        st.subheader("🛡️ Admin Panel")
        with st.expander("🗑️ Delete History"):
            d_id = st.text_input("Member ID to Wipe")
            if st.button("Purge All Records", type="primary"):
                sync_data("ChatLogs", l_df[l_df['memberid'].astype(str) != d_id]); st.success("Deleted.")
        
        st.divider()
        st.write("Advanced Search")
        c1, c2, c3 = st.columns(3)
        with c1: a_agents = st.multiselect("Agents", l_df['agent'].unique(), default=l_df['agent'].unique())
        with c2: a_mid = st.text_input("Member ID Search")
        with c3: a_key = st.text_input("Keyword Search")
        
        res = l_df[l_df['agent'].isin(a_agents)]
        if a_mid: res = res[res['memberid'].astype(str).str.contains(a_mid, case=False)]
        if a_key: res = res[res['content'].str.contains(a_key, case=False)]
        st.dataframe(res.sort_values('timestamp', ascending=False), use_container_width=True)
    else: st.error("Admin Only")

# --- AI AGENTS ---
for i, name in enumerate(["Cooper", "Clara"]):
    with tabs[i+1]:
        hist = l_df[(l_df['memberid'] == mid) & (l_df['agent'] == name)].tail(15)
        for _, r in hist.iterrows():
            st.chat_message(r['role']).write(r['content'])
        if p := st.chat_input(f"Consult {name}..."):
            save_log(name, "user", p)
            client = Groq(api_key=st.secrets["GROQ_API_KEY"].strip())
            sys_prompt = f"You are {name}, friend to {st.session_state.auth['fname']}."
            msgs = [{"role": "system", "content": sys_prompt}] + [{"role": r.role, "content": r.content} for _, r in hist.iterrows()] + [{"role": "user", "content": p}]
            ans = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=msgs).choices[0].message.content
            save_log(name, "assistant", ans); st.rerun()

# --- LOGOUT ---
with tabs[6]:
    if st.button("Logout"): st.session_state.clear(); st.rerun()
