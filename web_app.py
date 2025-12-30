import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, date

# --- 1. SETTINGS & SESSION ---
st.set_page_config(page_title="Health Bridge Pro", layout="wide", initial_sidebar_state="collapsed")

# Initialize Session States with safe defaults
states = {
    "auth": {"in": False, "mid": None, "role": "user", "fname": "", "lname": "", "bio": "", "dob": "2000-01-01"},
    "view_mid": None,
    "edit_mode": False
}
for key, val in states.items():
    if key not in st.session_state:
        st.session_state[key] = val

# Custom CSS for a professional social feel
st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    .chat-bubble { padding: 12px 18px; border-radius: 18px; margin-bottom: 10px; max-width: 85%; line-height: 1.5; }
    .user-bubble { background: #1E40AF; color: white; margin-left: auto; border-bottom-right-radius: 2px; }
    .ai-bubble { background: #334155; color: white; margin-right: auto; border-bottom-left-radius: 2px; }
    .direct-bubble { background: #065F46; color: white; margin-right: auto; border-bottom-left-radius: 2px; border-left: 4px solid #10B981; }
    .feed-card { background: #1E293B; padding: 15px; border-radius: 15px; border: 1px solid #334155; margin-bottom: 10px; }
    .sidebar-box { background: #1E293B; padding: 10px; border-radius: 10px; border-left: 3px solid #6366F1; margin-bottom: 5px; }
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
                if c.lower() not in df.columns: df[c.lower()] = None
        return df
    except: return pd.DataFrame(columns=[c.lower() for c in expected_cols]) if expected_cols else pd.DataFrame()

def sync_data(ws_name, df):
    conn.update(worksheet=ws_name, data=df)
    st.cache_data.clear()

def save_log(agent, role, content):
    new_row = pd.DataFrame([{"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), "memberid": st.session_state.auth['mid'], "agent": agent, "role": role, "content": content}])
    existing = get_data("ChatLogs", ["timestamp", "memberid", "agent", "role", "content"])
    sync_data("ChatLogs", pd.concat([existing, new_row], ignore_index=True))

# --- 3. UI HELPERS ---
def render_friends_list(f_df, u_df, key_prefix):
    mid = st.session_state.auth['mid']
    acc = f_df[((f_df['sender']==mid) | (f_df['receiver']==mid)) & (f_df['status']=="accepted")]
    if acc.empty:
        st.caption("No friends found.")
    else:
        for _, r in acc.iterrows():
            fid = r['receiver'] if r['sender'] == mid else r['sender']
            f_row = u_df[u_df['memberid'] == fid]
            name = f"{f_row.iloc[0]['firstname']} {f_row.iloc[0]['lastname']}" if not f_row.empty else fid
            if st.button(f"👤 {name}", key=f"{key_prefix}_{fid}", use_container_width=True):
                st.session_state.view_mid = fid
                st.rerun()

# --- 4. AUTHENTICATION ---
USER_COLS = ["memberid", "firstname", "lastname", "password", "role", "bio", "dob"]

if not st.session_state.auth["in"]:
    st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge Pro</h1>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["Login", "Create Account"])
    
    with t1:
        u = st.text_input("Member ID", key="l_id").lower().strip()
        p = st.text_input("Password", type="password", key="l_pw")
        if st.button("Sign In", use_container_width=True):
            ud = get_data("Users", USER_COLS)
            m = ud[(ud['memberid'].astype(str).str.lower() == u) & (ud['password'].astype(str) == p)]
            if not m.empty:
                r = m.iloc[0]
                st.session_state.auth.update({"in": True, "mid": u, "role": r['role'], "fname": r.get('firstname', ''), "lname": r.get('lastname', ''), "bio": r.get('bio', ''), "dob": r.get('dob', '2000-01-01')})
                st.rerun()
            else: st.error("Access denied. Please check your credentials.")

    with t2:
        sid = st.text_input("Desired ID", key="s_id").lower().strip()
        spw = st.text_input("Password", type="password", key="s_pw")
        c1, c2 = st.columns(2)
        with c1: sfn = st.text_input("First Name", key="s_fn")
        with c2: sln = st.text_input("Last Name", key="s_ln")
        sdob = st.date_input("Birthday", min_value=date(1940,1,1), key="s_dob")
        if st.button("Register"):
            ud = get_data("Users", USER_COLS)
            if sid in ud['memberid'].values: st.error("This ID is already taken.")
            elif not (sid and sfn and sln and spw): st.warning("Please fill in all fields.")
            else:
                new_user = pd.DataFrame([{"memberid": sid, "firstname": sfn, "lastname": sln, "password": spw, "role": "user", "bio": "New member!", "dob": str(sdob)}])
                sync_data("Users", pd.concat([ud, new_user], ignore_index=True))
                st.success("Account created! You can now login.")
    st.stop()

# --- 5. MAIN INTERFACE ---
tabs = st.tabs(["👤 Profile", "🤝 Cooper", "✨ Clara", "👥 Friends", "📩 Messages", "🛠️ Admin", "🚪 Logout"])
l_df = get_data("ChatLogs", ["timestamp", "memberid", "agent", "role", "content"])
f_df = get_data("Friends", ["sender", "receiver", "status"])
u_df = get_data("Users", USER_COLS)

# --- PROFILE TAB ---
with tabs[0]:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1: # User Info
        st.subheader("Profile")
        if st.session_state.edit_mode:
            en = st.text_input("First Name", st.session_state.auth['fname'], key="e_fn")
            el = st.text_input("Last Name", st.session_state.auth['lname'], key="e_ln")
            eb = st.text_area("Bio", st.session_state.auth['bio'], key="e_bio")
            if st.button("Save Changes"):
                u_df.loc[u_df['memberid'] == st.session_state.auth['mid'], ['firstname', 'lastname', 'bio']] = [en, el, eb]
                sync_data("Users", u_df)
                st.session_state.auth.update({"fname": en, "lname": el, "bio": eb})
                st.session_state.edit_mode = False; st.rerun()
        else:
            st.markdown(f"### {st.session_state.auth['fname']} {st.session_state.auth['lname']}")
            st.caption(f"Age: {calculate_age(st.session_state.auth['dob'])} | @{st.session_state.auth['mid']}")
            st.write(st.session_state.auth['bio'])
            if st.button("Edit Profile"): st.session_state.edit_mode = True; st.rerun()
    
    with c2: # Personal Feed
        st.subheader("Timeline")
        txt = st.text_area("What's on your mind?", key="feed_post", placeholder="Type here...")
        if st.button("Post", key="post_btn") and txt:
            save_log("Feed", "user", txt); st.rerun()
        my_p = l_df[(l_df['agent']=="Feed") & (l_df['memberid']==st.session_state.auth['mid'])].sort_values('timestamp', ascending=False)
        for idx, row in my_p.iterrows():
            with st.container(border=True):
                st.write(row['content'])
                st.caption(row['timestamp'])
                if st.button("Delete", key=f"del_{idx}"): sync_data("ChatLogs", l_df.drop(idx)); st.rerun()

    with c3: # Sidebar Friends
        st.subheader("Friends")
        render_friends_list(f_df, u_df, "prof_side")

# --- FRIENDS & SOCIAL TAB ---
with tabs[3]:
    if st.session_state.view_mid: # THE "READ-ONLY" VIEWER
        if st.button("← Back to Social"): st.session_state.view_mid = None; st.rerun()
        target = u_df[u_df['memberid'] == st.session_state.view_mid].iloc[0]
        st.divider()
        cx, cy = st.columns([1, 2])
        with cx:
            st.header(f"{target['firstname']} {target['lastname']}")
            st.caption(f"Age: {calculate_age(target['dob'])} | @{target['memberid']}")
            st.info(target['bio'])
            rel = f_df[((f_df['sender']==st.session_state.auth['mid'])&(f_df['receiver']==st.session_state.view_mid)) | ((f_df['receiver']==st.session_state.auth['mid'])&(f_df['sender']==st.session_state.view_mid))]
            if rel.empty:
                if st.button("Add Friend", use_container_width=True):
                    sync_data("Friends", pd.concat([f_df, pd.DataFrame([{"sender":st.session_state.auth['mid'], "receiver":st.session_state.view_mid, "status":"pending"}])])); st.rerun()
            else:
                st.caption(f"Status: {rel.iloc[0]['status']}")
                if st.button("Remove Friend", type="primary"): sync_data("Friends", f_df.drop(rel.index)); st.rerun()
        with cy:
            st.subheader("Posts")
            for _, r in l_df[(l_df['agent']=="Feed") & (l_df['memberid']==st.session_state.view_mid)].sort_values('timestamp', ascending=False).iterrows():
                st.markdown(f'<div class="feed-card"><p>{r["content"]}</p><small>{r["timestamp"]}</small></div>', unsafe_allow_html=True)
    else:
        st1, st2 = st.tabs(["Find New Friends", "Relationship Requests"])
        with st1:
            sq = st.text_input("Search Users (ID or Name)", key="find_f")
            if sq:
                res = u_df[(u_df['memberid'].str.contains(sq, case=False)) | (u_df['firstname'].str.contains(sq, case=False))]
                for _, r in res.iterrows():
                    if r['memberid'] != st.session_state.auth['mid']:
                        if st.button(f"View {r['firstname']} {r['lastname']} (@{r['memberid']})", key=f"src_{r['memberid']}"):
                            st.session_state.view_mid = r['memberid']; st.rerun()
        with st2:
            st.subheader("Pending Requests")
            reqs = f_df[(f_df['receiver'] == st.session_state.auth['mid']) & (f_df['status'] == "pending")]
            for idx, r in reqs.iterrows():
                st.write(f"Request from: {r['sender']}")
                if st.button("Accept", key=f"acc_{idx}"):
                    f_df.at[idx, 'status'] = "accepted"
                    sync_data("Friends", f_df); st.rerun()

# --- MESSAGES TAB ---
with tabs[4]:
    # Filter only for accepted friends
    f1 = f_df[(f_df['sender']==st.session_state.auth['mid'])&(f_df['status']=="accepted")]['receiver'].tolist()
    f2 = f_df[(f_df['receiver']==st.session_state.auth['mid'])&(f_df['status']=="accepted")]['sender'].tolist()
    all_f = list(set(f1+f2))
    if all_f:
        sel_chat = st.selectbox("Direct Message", all_f, key="msg_sel")
        chat_h = l_df[((l_df['memberid']==st.session_state.auth['mid'])&(l_df['agent']==f"DM:{sel_chat}")) | ((l_df['memberid']==sel_chat)&(l_df['agent']==f"DM:{st.session_state.auth['mid']}"))].sort_values('timestamp')
        with st.container(height=300):
            for _, m in chat_h.iterrows():
                sty = "user-bubble" if m['memberid']==st.session_state.auth['mid'] else "direct-bubble"
                st.markdown(f'<div class="chat-bubble {sty}">{m["content"]}</div>', unsafe_allow_html=True)
        if dm_in := st.chat_input("Send a message..."):
            save_log(f"DM:{sel_chat}", "user", dm_in); st.rerun()
    else: st.info("Add friends to start messaging.")

# --- ADMIN PANEL ---
with tabs[5]:
    if st.session_state.auth['role'] == "admin":
        st.subheader("🛡️ Administrative Dashboard")
        amode = st.radio("Tool", ["Users DB", "Log Viewer"], horizontal=True)
        if amode == "Users DB": st.dataframe(u_df, use_container_width=True)
        else:
            asrc = st.text_input("Search Logs by ID", key="adm_log_src")
            filtered = l_df[l_df['memberid'].str.contains(asrc, case=False)] if asrc else l_df
            st.dataframe(filtered.sort_values('timestamp', ascending=False), use_container_width=True)
    else: st.error("Access restricted to Administrators.")

# --- COOPER & CLARA (Standard Logic) ---
for i, name in enumerate(["Cooper", "Clara"]):
    with tabs[i+1]:
        hist = l_df[(l_df['memberid'] == st.session_state.auth['mid']) & (l_df['agent'] == name)].tail(10)
        with st.container(height=400):
            for _, r in hist.iterrows():
                sty = "user-bubble" if r['role'] == "user" else "ai-bubble"
                st.markdown(f'<div class="chat-bubble {sty}">{r["content"]}</div>', unsafe_allow_html=True)
        if prompt := st.chat_input(f"Consult {name}", key=f"chat_input_{name}"):
            save_log(name, "user", prompt)
            client = Groq(api_key=st.secrets["GROQ_API_KEY"].strip())
            sys_msg = f"You are {name}. User: {st.session_state.auth['fname']}, Age: {calculate_age(st.session_state.auth['dob'])}."
            full_msgs = [{"role": "system", "content": sys_msg}] + [{"role": r.role, "content": r.content} for _, r in hist.iterrows()] + [{"role": "user", "content": prompt}]
            ans = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=full_msgs).choices[0].message.content
            save_log(name, "assistant", ans); st.rerun()

# --- LOGOUT ---
with tabs[6]:
    if st.button("Log Out of System"):
        st.session_state.clear()
        st.rerun()
