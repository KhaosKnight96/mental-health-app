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

# Custom CSS for Modern Social Interface
st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    .msg-bubble { padding: 12px 18px; border-radius: 18px; margin-bottom: 10px; max-width: 85%; }
    .user-bubble { background: #1E40AF; color: white; margin-left: auto; border-bottom-right-radius: 2px; }
    .friend-bubble { background: #334155; color: white; border-bottom-left-radius: 2px; border-left: 4px solid #10B981; }
    .ai-bubble { background: #475569; color: white; border-bottom-left-radius: 2px; border-left: 4px solid #6366F1; }
    .feed-card { background: #1E293B; padding: 15px; border-radius: 15px; border: 1px solid #334155; margin-bottom: 10px; }
    .friend-btn { text-align: left; background: #1E293B; border: 1px solid #334155; margin-bottom: 5px; }
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

# --- 3. UI HELPERS ---
def render_clickable_friends(f_df, u_df, key_prefix):
    mid = st.session_state.auth['mid']
    acc = f_df[((f_df['sender']==mid) | (f_df['receiver']==mid)) & (f_df['status']=="accepted")]
    if acc.empty:
        st.caption("No connections yet.")
    else:
        for _, r in acc.iterrows():
            fid = r['receiver'] if r['sender'] == mid else r['sender']
            f_row = u_df[u_df['memberid'] == fid]
            name = f"{f_row.iloc[0]['firstname']} {f_row.iloc[0]['lastname']}" if not f_row.empty else fid
            if st.button(f"👤 {name}", key=f"{key_prefix}_{fid}", use_container_width=True):
                st.session_state.view_mid = fid
                st.rerun()

# --- 4. AUTHENTICATION (Omitted details for space, same as v8.6) ---
# ... [Standard Auth Logic here] ...
USER_COLS = ["memberid", "firstname", "lastname", "password", "role", "bio", "dob"]
if not st.session_state.auth["in"]:
    # Login/Signup logic
    st.stop()

# --- 5. MAIN DATA REFRESH ---
l_df = get_data("ChatLogs", ["timestamp", "memberid", "agent", "role", "content"])
f_df = get_data("Friends", ["sender", "receiver", "status"])
u_df = get_data("Users", USER_COLS)

tabs = st.tabs(["👤 Profile", "🤝 Cooper", "✨ Clara", "👥 Friends", "📩 Messages", "🛠️ Admin", "🚪 Logout"])

# --- TAB 0: PROFILE (WITH SIDEBAR & NEW POST) ---
with tabs[0]:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1: # Personal Info
        st.subheader("My Details")
        st.markdown(f"### {st.session_state.auth['fname']} {st.session_state.auth['lname']}")
        st.caption(f"Age: {calculate_age(st.session_state.auth['dob'])} | @{st.session_state.auth['mid']}")
        st.info(st.session_state.auth['bio'])
        if st.button("Edit Profile"): st.session_state.edit_mode = True; st.rerun()

    with c2: # Timeline & Post Section
        st.subheader("Create a Post")
        with st.container(border=True):
            p_txt = st.text_area("What's on your mind?", key="prof_post_input", label_visibility="collapsed")
            if st.button("Post Update", use_container_width=True):
                if p_txt:
                    new_row = pd.DataFrame([{"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), "memberid": st.session_state.auth['mid'], "agent": "Feed", "role": "user", "content": p_txt}])
                    sync_data("ChatLogs", pd.concat([l_df, new_row], ignore_index=True)); st.rerun()
        
        st.subheader("My Timeline")
        my_p = l_df[(l_df['agent']=="Feed") & (l_df['memberid']==st.session_state.auth['mid'])].sort_values('timestamp', ascending=False)
        for idx, row in my_p.iterrows():
            with st.container(border=True):
                st.caption(f"📅 {row['timestamp']}")
                st.write(row['content'])
                if st.button("Delete", key=f"p_del_{idx}"): sync_data("ChatLogs", l_df.drop(idx)); st.rerun()

    with c3: # Clickable Friends List
        st.subheader("My Friends")
        render_clickable_friends(f_df, u_df, "prof_side")

# --- TAB 3: FRIENDS (CLICK TO VIEW PROFILE) ---
with tabs[3]:
    if st.session_state.view_mid: # READ-ONLY PROFILE
        if st.button("← Back to Social"): st.session_state.view_mid = None; st.rerun()
        rows = u_df[u_df['memberid'] == st.session_state.view_mid]
        if not rows.empty:
            t = rows.iloc[0]
            st.divider()
            cx, cy = st.columns([1, 2])
            with cx:
                st.header(f"{t['firstname']} {t['lastname']}")
                st.caption(f"Age: {calculate_age(t['dob'])} | @{t['memberid']}")
                st.info(t['bio'])
            with cy:
                st.subheader("Posts")
                for _, r in l_df[(l_df['agent']=="Feed") & (l_df['memberid']==st.session_state.view_mid)].sort_values('timestamp', ascending=False).iterrows():
                    st.markdown(f'<div class="feed-card"><small>{r["timestamp"]}</small><p>{r["content"]}</p></div>', unsafe_allow_html=True)
        else: st.error("Profile not found."); st.session_state.view_mid = None
    else:
        s1, s2 = st.tabs(["Find Friends", "Friend List"])
        with s1:
            sq = st.text_input("Search ID or Name", key="f_src")
            if sq:
                res = u_df[(u_df['memberid'].str.contains(sq, case=False)) | (u_df['firstname'].str.contains(sq, case=False))]
                for _, r in res.iterrows():
                    if r['memberid'] != st.session_state.auth['mid']:
                        if st.button(f"View Profile: {r['firstname']} (@{r['memberid']})", key=f"f_v_{r['memberid']}"):
                            st.session_state.view_mid = r['memberid']; st.rerun()
        with s2:
            st.subheader("Connected Friends")
            render_clickable_friends(f_df, u_df, "f_list_tab")

# --- TAB 5: ADMIN (IN-DEPTH FILTERS & DELETE) ---
with tabs[5]:
    if st.session_state.auth['role'] == "admin":
        st.subheader("🛡️ Administrative Dashboard")
        
        # 1. DELETE CHAT HISTORY TOOL
        with st.expander("🚨 Wipe User Data"):
            del_id = st.text_input("Target Member ID to delete logs for:", key="adm_del_id")
            if st.button("PERMANENTLY DELETE ALL LOGS", type="primary"):
                if del_id:
                    sync_data("ChatLogs", l_df[l_df['memberid'] != del_id]); st.success(f"History purged for {del_id}")
                else: st.error("Enter an ID")

        # 2. IN-DEPTH FILTERS
        st.subheader("Log Audit Tool")
        c1, c2, c3, c4 = st.columns(4)
        with c1: f_agent = st.multiselect("Filter Agents", l_df['agent'].unique(), default=l_df['agent'].unique())
        with c2: f_mid = st.text_input("Filter by Member ID")
        with c3: f_key = st.text_input("Search Content Keywords")
        with c4: f_role = st.selectbox("Filter Role", ["All", "user", "assistant"])

        filt = l_df[l_df['agent'].isin(f_agent)]
        if f_mid: filt = filt[filt['memberid'].str.contains(f_mid, case=False)]
        if f_key: filt = filt[filt['content'].str.contains(f_key, case=False)]
        if f_role != "All": filt = filt[filt['role'] == f_role]

        st.dataframe(filt.sort_values('timestamp', ascending=False), use_container_width=True)
    else: st.error("Admin Only")

# (Cooper/Clara/Messages logic following v8.6)
# ... [Rest of code] ...
