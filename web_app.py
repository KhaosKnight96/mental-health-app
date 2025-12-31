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
    "edit_mode": False
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# Custom CSS for Professional UI
st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    .msg-bubble { padding: 12px 18px; border-radius: 18px; margin-bottom: 10px; max-width: 85%; }
    .user-bubble { background: #1E40AF; color: white; margin-left: auto; border-bottom-right-radius: 2px; }
    .ai-bubble { background: #334155; color: white; border-bottom-left-radius: 2px; border-left: 4px solid #6366F1; }
    .feed-card { background: #1E293B; padding: 15px; border-radius: 15px; border: 1px solid #334155; margin-bottom: 10px; }
    .friend-sidebar-item { padding: 10px; background: #1E293B; border-radius: 8px; margin-bottom: 8px; border-left: 4px solid #6366F1; }
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

# --- 3. UI HELPERS ---
def render_clickable_friends(f_df, u_df, key_prefix):
    mid = st.session_state.auth['mid']
    acc = f_df[((f_df['sender']==mid) | (f_df['receiver']==mid)) & (f_df['status']=="accepted")]
    if acc.empty:
        st.caption("No friends yet.")
    else:
        for _, r in acc.iterrows():
            fid = r['receiver'] if r['sender'] == mid else r['sender']
            f_row = u_df[u_df['memberid'] == fid]
            if not f_row.empty:
                name = f"{f_row.iloc[0]['firstname']} {f_row.iloc[0]['lastname']}"
                if st.button(f"👤 {name}", key=f"{key_prefix}_{fid}", use_container_width=True):
                    st.session_state.view_mid = fid
                    st.rerun()

# --- 4. AUTHENTICATION SECTION (RESTORED) ---
USER_COLS = ["memberid", "firstname", "lastname", "password", "role", "bio", "dob"]

if not st.session_state.auth["in"]:
    st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge Pro</h1>", unsafe_allow_html=True)
    t_login, t_signup = st.tabs(["Login", "Sign Up"])
    
    with t_login:
        u_in = st.text_input("Member ID", key="l_u").lower().strip()
        p_in = st.text_input("Password", type="password", key="l_p")
        if st.button("Sign In", use_container_width=True):
            ud = get_data("Users", USER_COLS)
            match = ud[(ud['memberid'].astype(str).str.lower() == u_in) & (ud['password'].astype(str) == p_in)]
            if not match.empty:
                r = match.iloc[0]
                st.session_state.auth.update({
                    "in": True, "mid": u_in, "role": r['role'], 
                    "fname": r['firstname'], "lname": r['lastname'], 
                    "bio": r['bio'], "dob": r['dob']
                })
                st.rerun()
            else: st.error("Invalid ID or Password.")

    with t_signup:
        s_id = st.text_input("Choose Member ID", key="s_id").lower().strip()
        s_pw = st.text_input("Create Password", type="password", key="s_pw")
        c1, c2 = st.columns(2)
        with c1: s_fn = st.text_input("First Name", key="s_fn")
        with c2: s_ln = st.text_input("Last Name", key="s_ln")
        s_dob = st.date_input("Date of Birth", min_value=date(1940,1,1), key="s_dob")
        
        if st.button("Register Account", use_container_width=True):
            ud = get_data("Users", USER_COLS)
            if s_id in ud['memberid'].astype(str).values:
                st.error("This Member ID is already taken.")
            elif not (s_id and s_fn and s_ln and s_pw):
                st.warning("Please fill in all fields.")
            else:
                new_user = pd.DataFrame([{
                    "memberid": s_id, "firstname": s_fn, "lastname": s_ln, 
                    "password": s_pw, "role": "user", "bio": "New member!", "dob": str(s_dob)
                }])
                sync_data("Users", pd.concat([ud, new_user], ignore_index=True))
                st.success("Account created! You can now login.")
    st.stop()

# --- 5. MAIN APP DATA ---
l_df = get_data("ChatLogs", ["timestamp", "memberid", "agent", "role", "content"])
f_df = get_data("Friends", ["sender", "receiver", "status"])
u_df = get_data("Users", USER_COLS)

tabs = st.tabs(["👤 Profile", "🤝 Cooper", "✨ Clara", "👥 Friends", "📩 Messages", "🛠️ Admin", "🚪 Logout"])

# --- TAB 0: PROFILE ---
with tabs[0]:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        st.subheader("My Profile")
        st.markdown(f"### {st.session_state.auth['fname']} {st.session_state.auth['lname']}")
        st.caption(f"Age: {calculate_age(st.session_state.auth['dob'])} | @{st.session_state.auth['mid']}")
        st.write(st.session_state.auth['bio'])
    
    with c2:
        st.subheader("Timeline")
        with st.container(border=True):
            post_txt = st.text_area("Create a new post...", key="new_post_in", label_visibility="collapsed")
            if st.button("Post with Timestamp", use_container_width=True):
                if post_txt:
                    save_log("Feed", "user", post_txt); st.rerun()
        
        my_posts = l_df[(l_df['agent']=="Feed") & (l_df['memberid']==st.session_state.auth['mid'])].sort_values('timestamp', ascending=False)
        for idx, row in my_posts.iterrows():
            with st.container(border=True):
                st.caption(f"🕒 {row['timestamp']}")
                st.write(row['content'])
                if st.button("Delete Post", key=f"del_p_{idx}"):
                    sync_data("ChatLogs", l_df.drop(idx)); st.rerun()

    with c3:
        st.subheader("My Friends")
        render_clickable_friends(f_df, u_df, "side_f")

# --- TAB 1 & 2: AI AGENTS ---
for i, name in enumerate(["Cooper", "Clara"]):
    with tabs[i+1]:
        hist = l_df[(l_df['memberid'] == st.session_state.auth['mid']) & (l_df['agent'] == name)].tail(15)
        for _, r in hist.iterrows():
            st.chat_message(r['role']).write(r['content'])
        
        if prompt := st.chat_input(f"Talk to {name}...", key=f"chat_{name}"):
            save_log(name, "user", prompt)
            try:
                client = Groq(api_key=st.secrets["GROQ_API_KEY"].strip())
                role_desc = "empathetic health friend" if name == "Cooper" else "bright wellness coach"
                sys_msg = f"You are {name}, a {role_desc}. User is {st.session_state.auth['fname']}."
                msgs = [{"role": "system", "content": sys_msg}] + [{"role": r.role, "content": r.content} for _, r in hist.iterrows()] + [{"role": "user", "content": prompt}]
                res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=msgs)
                save_log(name, "assistant", res.choices[0].message.content); st.rerun()
            except Exception as e: st.error("Connection Error. Check API Key.")

# --- TAB 3: FRIENDS (CLICKABLE) ---
with tabs[3]:
    if st.session_state.view_mid:
        if st.button("← Back to List"): st.session_state.view_mid = None; st.rerun()
        target = u_df[u_df['memberid'] == st.session_state.view_mid]
        if not target.empty:
            t = target.iloc[0]
            st.header(f"{t['firstname']} {t['lastname']}")
            st.info(t['bio'])
            st.subheader("Recent Posts")
            t_posts = l_df[(l_df['agent']=="Feed") & (l_df['memberid']==st.session_state.view_mid)].sort_values('timestamp', ascending=False)
            for _, r in t_posts.iterrows():
                st.markdown(f'<div class="feed-card"><small>{r["timestamp"]}</small><br>{r["content"]}</div>', unsafe_allow_html=True)
    else:
        st.subheader("Find Connections")
        search_f = st.text_input("Search by ID", key="search_f_in")
        if search_f:
            res = u_df[u_df['memberid'].str.contains(search_f, case=False)]
            for _, r in res.iterrows():
                if st.button(f"View Profile: @{r['memberid']}", key=f"src_{r['memberid']}"):
                    st.session_state.view_mid = r['memberid']; st.rerun()

# --- TAB 5: ADMIN (DEEP FILTERS) ---
with tabs[5]:
    if st.session_state.auth['role'] == "admin":
        st.subheader("🛡️ Global Log Audit")
        with st.expander("🚨 Danger Zone: Delete Logs"):
            d_id = st.text_input("ID to Wipe", key="admin_wipe_id")
            if st.button("Delete All Logs for this ID", type="primary"):
                sync_data("ChatLogs", l_df[l_df['memberid'] != d_id]); st.success("Purged.")
        
        st.divider()
        c1, c2, c3 = st.columns(3)
        with c1: a_agent = st.multiselect("Agents", l_df['agent'].unique(), default=l_df['agent'].unique())
        with c2: a_mid = st.text_input("Search Member ID", key="a_mid_search")
        with c3: a_key = st.text_input("Keyword Search", key="a_key_search")
        
        filtered = l_df[l_df['agent'].isin(a_agent)]
        if a_mid: filtered = filtered[filtered['memberid'].str.contains(a_mid, case=False)]
        if a_key: filtered = filtered[filtered['content'].str.contains(a_key, case=False)]
        st.dataframe(filtered.sort_values('timestamp', ascending=False), use_container_width=True)
    else: st.error("Admin Only")

# --- TAB 6: LOGOUT ---
with tabs[6]:
    if st.button("Sign Out"): st.session_state.clear(); st.rerun()
