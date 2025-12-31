import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, date

# --- 1. CONFIG & SESSION ---
st.set_page_config(page_title="Health Bridge Pro", layout="wide", initial_sidebar_state="collapsed")

if "auth" not in st.session_state:
    st.session_state.auth = {"in": False, "mid": None, "role": "user", "fname": "", "lname": "", "bio": "", "dob": "2000-01-01"}
if "view_mid" not in st.session_state:
    st.session_state.view_mid = None
if "active_chat_mid" not in st.session_state:
    st.session_state.active_chat_mid = None

# Professional Social CSS
st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    .msg-bubble { padding: 12px 18px; border-radius: 18px; margin-bottom: 10px; max-width: 80%; line-height: 1.4; display: block; }
    .me { background: #2563EB; color: white; margin-left: auto; border-bottom-right-radius: 2px; text-align: right; }
    .them { background: #334155; color: white; border-bottom-left-radius: 2px; border-left: 4px solid #10B981; }
    .feed-card { background: #1E293B; padding: 20px; border-radius: 12px; border: 1px solid #334155; margin-bottom: 15px; }
    .request-box { background: #1E293B; padding: 15px; border-radius: 10px; border: 1px solid #10B981; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATA ENGINE ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=1)
def get_data(ws):
    try:
        df = conn.read(worksheet=ws, ttl=0)
        if df is None or df.empty: return pd.DataFrame()
        df.columns = [str(c).strip().lower() for c in df.columns]
        return df
    except: return pd.DataFrame()

def sync_data(ws_name, df):
    conn.update(worksheet=ws_name, data=df)
    st.cache_data.clear()

def save_log(agent, role, content, custom_mid=None):
    target_mid = custom_mid if custom_mid else st.session_state.auth['mid']
    new_row = pd.DataFrame([{"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), "memberid": str(target_mid), "agent": agent, "role": role, "content": content}])
    existing = get_data("ChatLogs")
    sync_data("ChatLogs", pd.concat([existing, new_row], ignore_index=True))

# --- 3. LOGIN / SIGNUP (FIXED UNIQUE KEYS) ---
if not st.session_state.auth["in"]:
    st.title("🧠 Health Bridge Pro")
    t1, t2 = st.tabs(["Login", "Sign Up"])
    with t1:
        u_in = st.text_input("Member ID", key="login_mid").strip().lower()
        p_in = st.text_input("Password", type="password", key="login_pw").strip()
        if st.button("Sign In", use_container_width=True, key="btn_signin"):
            ud = get_data("Users")
            if not ud.empty:
                ud['mid_c'] = ud['memberid'].astype(str).str.strip().str.lower()
                match = ud[(ud['mid_c'] == u_in) & (ud['password'].astype(str) == p_in)]
                if not match.empty:
                    r = match.iloc[0]
                    st.session_state.auth.update({"in":True, "mid":str(r['memberid']), "role":r['role'], "fname":r['firstname'], "lname":r['lastname'], "bio":r['bio'], "dob":r['dob']})
                    st.rerun()
            st.error("Login failed.")
    with t2:
        sid = st.text_input("Choose Member ID", key="signup_mid").lower().strip()
        spw = st.text_input("Choose Password", type="password", key="signup_pw")
        sfn = st.text_input("First Name", key="signup_fn")
        sln = st.text_input("Last Name", key="signup_ln")
        sdob = st.date_input("DOB", min_value=date(1940,1,1), key="signup_dob")
        if st.button("Create Account", key="btn_register"):
            ud = get_data("Users")
            if not ud.empty and sid in ud['memberid'].astype(str).values: st.error("ID Taken")
            else:
                new_u = pd.DataFrame([{"memberid":sid, "firstname":sfn, "lastname":sln, "password":spw, "role":"user", "bio":"New member!", "dob":str(sdob)}])
                sync_data("Users", pd.concat([ud, new_u], ignore_index=True))
                save_log("Cooper", "assistant", f"Welcome {sfn}! I'm Cooper.", custom_mid=sid)
                st.success("Success! Please Login.")
    st.stop()

# --- 4. LOAD DATA ---
u_df = get_data("Users")
l_df = get_data("ChatLogs")
f_df = get_data("Friends")
mid = st.session_state.auth['mid']

# Friends Logic
friends_ids = []
pending = []
if not f_df.empty:
    f_acc = f_df[((f_df['sender'].astype(str)==mid) | (f_df['receiver'].astype(str)==mid)) & (f_df['status']=="accepted")]
    friends_ids = [str(r['receiver']) if str(r['sender']) == mid else str(r['sender']) for _, r in f_acc.iterrows()]
    pending = f_df[(f_df['receiver'].astype(str)==mid) & (f_df['status']=="pending")]

tabs = st.tabs(["👤 Profile", "🤝 Cooper", "✨ Clara", "👥 Social", "📩 Messages", "🛠️ Admin", "🚪 Logout"])

# --- TAB: PROFILE ---
with tabs[0]:
    v_id = st.session_state.view_mid if st.session_state.view_mid else mid
    u_lookup = u_df[u_df['memberid'].astype(str) == str(v_id)] if not u_df.empty else pd.DataFrame()
    if not u_lookup.empty:
        user = u_lookup.iloc[0]
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            if v_id != mid:
                if st.button("← Back Home", key="back_home"): st.session_state.view_mid = None; st.rerun()
            st.header(user['firstname'])
            st.caption(f"@{user['memberid']}")
            st.info(user['bio'])
        with c2:
            st.subheader("Timeline")
            if v_id == mid:
                post_box = st.text_area("What's on your mind?", key="prof_post_input")
                if st.button("Share Post", key="btn_share"):
                    if post_box: save_log("Feed", "user", post_box); st.rerun()
            feed = l_df[(l_df['agent']=="Feed") & (l_df['memberid']==str(v_id))].sort_values('timestamp', ascending=False)
            for _, r in feed.iterrows():
                st.markdown(f'<div class="feed-card"><small>{r["timestamp"]}</small><br>{r["content"]}</div>', unsafe_allow_html=True)
        with c3:
            st.subheader("Friends")
            for fid in friends_ids:
                if st.button(f"👤 {fid}", key=f"p_nav_{fid}", use_container_width=True):
                    st.session_state.view_mid = fid; st.rerun()

# --- TAB: SOCIAL (FIXED KEYS) ---
with tabs[3]:
    sc1, sc2 = st.columns(2)
    with sc1:
        st.subheader("Explore")
        search_q = st.text_input("Find User by ID", key="search_user_input").lower().strip()
        if search_q:
            s_res = u_df[u_df['memberid'].astype(str).str.contains(search_q)]
            for _, row in s_res.iterrows():
                if str(row['memberid']) != mid:
                    col1, col2 = st.columns([3, 1])
                    col1.write(f"**{row['firstname']}** (@{row['memberid']})")
                    if col2.button("Add", key=f"add_user_{row['memberid']}"):
                        new_req = pd.DataFrame([{"sender":mid, "receiver":row['memberid'], "status":"pending"}])
                        sync_data("Friends", pd.concat([f_df, new_req], ignore_index=True))
                        st.success("Sent!")
    with sc2:
        st.subheader("Requests")
        for _, req in pending.iterrows():
            st.markdown(f'<div class="request-box">From: <b>{req["sender"]}</b></div>', unsafe_allow_html=True)
            ca, cb = st.columns(2)
            if ca.button("Accept", key=f"acc_{req['sender']}"):
                f_df.loc[(f_df['sender']==req['sender']) & (f_df['receiver']==mid), 'status'] = "accepted"
                sync_data("Friends", f_df); st.rerun()
            if cb.button("Decline", key=f"dec_{req['sender']}"):
                f_df = f_df.drop(req.name)
                sync_data("Friends", f_df); st.rerun()

# --- TAB: MESSAGES (FIXED KEYS) ---
with tabs[4]:
    m1, m2 = st.columns([1, 3])
    with m1:
        for fid in friends_ids:
            if st.button(f"💬 {fid}", key=f"chat_list_{fid}", use_container_width=True):
                st.session_state.active_chat_mid = fid; st.rerun()
    with m2:
        target = st.session_state.active_chat_mid
        if target:
            st.subheader(f"Chat: {target}")
            hist = l_df[((l_df['memberid']==mid)&(l_df['agent']==f"DM:{target}")) | ((l_df['memberid']==str(target))&(l_df['agent']==f"DM:{mid}"))].sort_values('timestamp')
            with st.container(height=350):
                for _, m in hist.iterrows():
                    cls = "me" if m['memberid'] == mid else "them"
                    st.markdown(f'<div class="msg-bubble {cls}">{m["content"]}</div>', unsafe_allow_html=True)
            if dmin := st.chat_input("Type a message...", key="dm_input_field"):
                save_log(f"DM:{target}", "user", dmin); st.rerun()

# --- AI AGENTS ---
for i, name in enumerate(["Cooper", "Clara"]):
    with tabs[i+1]:
        st.subheader(f"Chat with {name}")
        hist = l_df[(l_df['memberid'] == mid) & (l_df['agent'] == name)].tail(15)
        for _, r in hist.iterrows():
            st.chat_message(r['role']).write(r['content'])
        if p := st.chat_input(f"Talk to {name}...", key=f"ai_input_{name}"):
            save_log(name, "user", p)
            client = Groq(api_key=st.secrets["GROQ_API_KEY"])
            ans = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":f"You are {name}."}] + [{"role":"user","content":p}]).choices[0].message.content
            save_log(name, "assistant", ans); st.rerun()

# --- LOGOUT ---
with tabs[6]:
    if st.button("Confirm Logout", key="btn_logout"):
        st.session_state.clear(); st.rerun()
