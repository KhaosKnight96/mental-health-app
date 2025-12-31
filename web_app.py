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

# Custom CSS for Messaging & Social UI
st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    .chat-bubble { padding: 10px 15px; border-radius: 15px; margin-bottom: 8px; max-width: 80%; line-height: 1.4; }
    .me { background: #2563EB; color: white; margin-left: auto; border-bottom-right-radius: 2px; }
    .them { background: #334155; color: white; border-bottom-left-radius: 2px; border-left: 4px solid #10B981; }
    .sidebar-btn { width: 100%; text-align: left; padding: 10px; border-radius: 5px; margin-bottom: 5px; background: #1E293B; border: 1px solid #334155; color: white; cursor: pointer; }
    .sidebar-btn:hover { background: #334155; }
    .active-chat { border-left: 5px solid #6366F1 !important; background: #334155; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATA CORE ---
conn = st.connection("gsheets", type=GSheetsConnection)

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

def save_log(agent, role, content, custom_mid=None):
    mid = custom_mid if custom_mid else st.session_state.auth['mid']
    new_row = pd.DataFrame([{"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), "memberid": mid, "agent": agent, "role": role, "content": content}])
    existing = get_data("ChatLogs", ["timestamp", "memberid", "agent", "role", "content"])
    sync_data("ChatLogs", pd.concat([existing, new_row], ignore_index=True))

# --- 3. AUTHENTICATION (Full Logic) ---
USER_COLS = ["memberid", "firstname", "lastname", "password", "role", "bio", "dob"]
if not st.session_state.auth["in"]:
    st.title("🧠 Health Bridge Pro")
    t1, t2 = st.tabs(["Login", "Sign Up"])
    with t1:
        u = st.text_input("Member ID").lower().strip()
        p = st.text_input("Password", type="password")
        if st.button("Sign In"):
            ud = get_data("Users", USER_COLS)
            match = ud[(ud['memberid'] == u) & (ud['password'] == p)]
            if not match.empty:
                r = match.iloc[0]
                st.session_state.auth.update({"in":True, "mid":u, "role":r['role'], "fname":r['firstname'], "lname":r['lastname'], "bio":r['bio'], "dob":r['dob']})
                st.rerun()
            else: st.error("Invalid credentials.")
    with t2:
        sid, spw = st.text_input("New ID").lower().strip(), st.text_input("New Password", type="password")
        sfn, sln = st.text_input("First Name"), st.text_input("Last Name")
        if st.button("Register"):
            ud = get_data("Users", USER_COLS)
            if sid in ud['memberid'].values: st.error("ID Taken")
            else:
                new_u = pd.DataFrame([{"memberid":sid, "firstname":sfn, "lastname":sln, "password":spw, "role":"user", "bio":"Hello!", "dob":"2000-01-01"}])
                sync_data("Users", pd.concat([ud, new_u], ignore_index=True)); st.success("Created!")
    st.stop()

# --- 4. APP DATA REFRESH ---
l_df = get_data("ChatLogs", ["timestamp", "memberid", "agent", "role", "content"])
f_df = get_data("Friends", ["sender", "receiver", "status"])
u_df = get_data("Users", USER_COLS)

# Get Accepted Friends List
mid = st.session_state.auth['mid']
f1 = f_df[(f_df['sender']==mid) & (f_df['status']=="accepted")]['receiver'].tolist()
f2 = f_df[(f_df['receiver']==mid) & (f_df['status']=="accepted")]['sender'].tolist()
friends_list = sorted(list(set(f1+f2)))

tabs = st.tabs(["👤 Profile", "🤝 Cooper", "✨ Clara", "👥 Friends", "📩 Messages", "🛠️ Admin", "🚪 Logout"])

# --- PROFILE ---
with tabs[0]:
    c1, c2 = st.columns([1, 2])
    with c1:
        st.header(f"{st.session_state.auth['fname']} {st.session_state.auth['lname']}")
        st.write(st.session_state.auth['bio'])
    with c2:
        st.subheader("Post to Timeline")
        p_in = st.text_area("What's happening?", key="timeline_post")
        if st.button("Post") and p_in:
            save_log("Feed", "user", p_in); st.rerun()

# --- FRIENDS TAB (CLICKABLE NAMES TO PROFILE) ---
with tabs[3]:
    if st.session_state.view_mid:
        if st.button("← Back to Friends"): st.session_state.view_mid = None; st.rerun()
        rows = u_df[u_df['memberid'] == st.session_state.view_mid]
        if not rows.empty:
            t = rows.iloc[0]
            st.title(f"{t['firstname']} {t['lastname']}")
            st.info(t['bio'])
            st.subheader("Posts")
            posts = l_df[(l_df['agent']=="Feed") & (l_df['memberid']==st.session_state.view_mid)].sort_values('timestamp', ascending=False)
            for _, r in posts.iterrows():
                st.markdown(f'<div style="background:#1E293B; padding:10px; border-radius:10px; margin-bottom:10px;"><small>{r["timestamp"]}</small><p>{r["content"]}</p></div>', unsafe_allow_html=True)
    else:
        st.subheader("Your Friends")
        if not friends_list: st.info("No friends added yet.")
        for f in friends_list:
            f_data = u_df[u_df['memberid'] == f]
            label = f"{f_data.iloc[0]['firstname']} {f_data.iloc[0]['lastname']} (@{f})" if not f_data.empty else f
            if st.button(label, key=f"f_list_{f}"):
                st.session_state.view_mid = f; st.rerun()

# --- MESSAGES TAB (CLICKABLE BUTTONS / REAL CHAT) ---
with tabs[4]:
    mc1, mc2 = st.columns([1, 3])
    with mc1:
        st.subheader("Chats")
        for f in friends_list:
            f_data = u_df[u_df['memberid'] == f]
            f_name = f_data.iloc[0]['firstname'] if not f_data.empty else f
            is_active = "active-chat" if st.session_state.active_chat_mid == f else ""
            if st.button(f"💬 {f_name}", key=f"msg_btn_{f}"):
                st.session_state.active_chat_mid = f
                st.rerun()
    
    with mc2:
        target = st.session_state.active_chat_mid
        if target:
            f_data = u_df[u_df['memberid'] == target]
            st.subheader(f"Chat with {f_data.iloc[0]['firstname'] if not f_data.empty else target}")
            
            # Show DM History
            dm_h = l_df[
                ((l_df['memberid'] == mid) & (l_df['agent'] == f"DM:{target}")) |
                ((l_df['memberid'] == target) & (l_df['agent'] == f"DM:{mid}"))
            ].sort_values('timestamp')
            
            with st.container(height=400):
                for _, m in dm_h.iterrows():
                    cls = "me" if m['memberid'] == mid else "them"
                    st.markdown(f'<div class="chat-bubble {cls}">{m["content"]}</div>', unsafe_allow_html=True)
            
            if msg_in := st.chat_input("Send message..."):
                save_log(f"DM:{target}", "user", msg_in)
                st.rerun()
        else:
            st.info("Select a friend from the left to start messaging.")

# --- ADMIN PANEL (DEEP FILTERS & DELETE) ---
with tabs[5]:
    if st.session_state.auth['role'] == "admin":
        st.subheader("🛠️ Admin Command Center")
        with st.expander("🗑️ Delete User History"):
            target_del = st.text_input("Enter ID to wipe:")
            if st.button("Confirm Wipe", type="primary"):
                sync_data("ChatLogs", l_df[l_df['memberid'] != target_del]); st.success("Logs Purged")
        
        st.divider()
        st.write("Advanced Log Search")
        c1, c2, c3 = st.columns(3)
        with c1: q_agent = st.multiselect("Agents", l_df['agent'].unique(), default=l_df['agent'].unique())
        with c2: q_mid = st.text_input("Member ID")
        with c3: q_key = st.text_input("Keyword")
        
        res = l_df[l_df['agent'].isin(q_agent)]
        if q_mid: res = res[res['memberid'].str.contains(q_mid, case=False)]
        if q_key: res = res[res['content'].str.contains(q_key, case=False)]
        st.dataframe(res.sort_values('timestamp', ascending=False), use_container_width=True)
    else: st.error("Admin Restricted")

# --- AI AGENTS (v8.9) ---
for i, name in enumerate(["Cooper", "Clara"]):
    with tabs[i+1]:
        hist = l_df[(l_df['memberid'] == mid) & (l_df['agent'] == name)].tail(15)
        for _, r in hist.iterrows():
            st.chat_message(r['role']).write(r['content'])
        if p := st.chat_input(f"Talk to {name}..."):
            save_log(name, "user", p)
            client = Groq(api_key=st.secrets["GROQ_API_KEY"].strip())
            msgs = [{"role": "system", "content": f"You are {name}, friend to {st.session_state.auth['fname']}."}] + \
                   [{"role": r.role, "content": r.content} for _, r in hist.iterrows()] + [{"role": "user", "content": p}]
            ans = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=msgs).choices[0].message.content
            save_log(name, "assistant", ans); st.rerun()

# --- LOGOUT ---
with tabs[6]:
    if st.button("Logout"): st.session_state.clear(); st.rerun()
