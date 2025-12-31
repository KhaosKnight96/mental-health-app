import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, date

# --- 1. CONFIG & SESSION ---
st.set_page_config(page_title="Health Bridge Pro", layout="wide", initial_sidebar_state="collapsed")

# Initialize Session States
if "auth" not in st.session_state:
    st.session_state.auth = {"in": False, "mid": None, "role": "user", "fname": "", "lname": "", "bio": "", "dob": "2000-01-01"}
if "view_target" not in st.session_state:
    st.session_state.view_target = None
if "active_chat_mid" not in st.session_state:
    st.session_state.active_chat_mid = None

# Custom CSS for Social Media Look
st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    .profile-header { background: linear-gradient(135deg, #1E293B, #0F172A); padding: 40px; border-radius: 20px; border: 1px solid #334155; margin-bottom: 25px; }
    .feed-card { background: #1E293B; padding: 20px; border-radius: 12px; border: 1px solid #334155; margin-bottom: 15px; }
    .msg-bubble { padding: 12px 18px; border-radius: 18px; margin-bottom: 10px; max-width: 80%; line-height: 1.4; display: block; }
    .me { background: #2563EB; color: white; margin-left: auto; border-bottom-right-radius: 2px; text-align: right; }
    .them { background: #334155; color: white; border-bottom-left-radius: 2px; border-left: 4px solid #10B981; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATA ENGINE ---
conn = st.connection("gsheets", type=GSheetsConnection)

def calculate_age(dob_str):
    try:
        b_day = datetime.strptime(str(dob_str), "%Y-%m-%d").date()
        return date.today().year - b_day.year - ((date.today().month, date.today().day) < (b_day.month, b_day.day))
    except: return "N/A"

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
    sync_data("ChatLogs", pd.concat([get_data("ChatLogs"), new_row], ignore_index=True))

# --- 3. THE FULL PROFILE PAGE (ROUTER) ---
def render_full_profile(target_mid):
    u_df = get_data("Users")
    l_df = get_data("ChatLogs")
    u_lookup = u_df[u_df['memberid'].astype(str) == str(target_mid)]
    
    if not u_lookup.empty:
        u = u_lookup.iloc[0]
        if st.button("← Back to My Home", key="exit_profile"):
            st.session_state.view_target = None
            st.rerun()
            
        st.markdown(f"""<div class="profile-header">
            <h1>{u['firstname']} {u['lastname']}</h1>
            <p>@{u['memberid']} | Age: {calculate_age(u['dob'])}</p>
            <p><i>{u['bio']}</i></p>
        </div>""", unsafe_allow_html=True)
        
        c1, c2 = st.columns([2, 1])
        with c1:
            st.subheader("User Timeline")
            posts = l_df[(l_df['agent']=="Feed") & (l_df['memberid']==str(target_mid))].sort_values('timestamp', ascending=False)
            if posts.empty: st.caption("No posts yet.")
            for _, p in posts.iterrows():
                st.markdown(f'<div class="feed-card"><small>{p["timestamp"]}</small><br>{p["content"]}</div>', unsafe_allow_html=True)
        with c2:
            st.subheader("Interact")
            if st.button(f"Send DM to {u['firstname']}", key=f"dm_btn_{target_mid}"):
                st.session_state.active_chat_mid = target_mid
                st.session_state.view_target = None
                st.rerun()
    else:
        st.error("User not found.")
        if st.button("Go Back"): st.session_state.view_target = None; st.rerun()

# --- 4. AUTHENTICATION ---
if not st.session_state.auth["in"]:
    st.title("🧠 Health Bridge Pro")
    t1, t2 = st.tabs(["Login", "Sign Up"])
    with t1:
        u_in = st.text_input("Member ID", key="l_mid").strip().lower()
        p_in = st.text_input("Password", type="password", key="l_pw").strip()
        if st.button("Sign In", use_container_width=True, key="btn_l"):
            ud = get_data("Users")
            if not ud.empty:
                ud['mid_c'] = ud['memberid'].astype(str).str.strip().str.lower()
                match = ud[(ud['mid_c'] == u_in) & (ud['password'].astype(str) == p_in)]
                if not match.empty:
                    r = match.iloc[0]
                    st.session_state.auth.update({"in":True, "mid":str(r['memberid']), "role":r['role'], "fname":r['firstname'], "lname":r['lastname'], "bio":r['bio'], "dob":r['dob']})
                    st.rerun()
            st.error("Login failed. Check ID and Password.")
    with t2:
        sid = st.text_input("New Member ID", key="s_mid").lower().strip()
        spw = st.text_input("Password", type="password", key="s_pw")
        sfn = st.text_input("First Name", key="s_fn")
        sln = st.text_input("Last Name", key="s_ln")
        sdob = st.date_input("DOB", key="s_dob", min_value=date(1940,1,1))
        if st.button("Create Account", key="btn_s"):
            ud = get_data("Users")
            if not ud.empty and sid in ud['memberid'].astype(str).values: st.error("ID Taken")
            else:
                new_u = pd.DataFrame([{"memberid":sid, "firstname":sfn, "lastname":sln, "password":spw, "role":"user", "bio":"Hello!", "dob":str(sdob)}])
                sync_data("Users", pd.concat([ud, new_u], ignore_index=True))
                save_log("Cooper", "assistant", f"Welcome {sfn}! Ask me anything.", custom_mid=sid)
                st.success("Account Created! Use Login tab.")
    st.stop()

# --- 5. APP CORE NAVIGATION ---
# Check for "Full Profile" redirect first
if st.session_state.view_target:
    render_full_profile(st.session_state.view_target)
    st.stop()

# Load App Data
u_df = get_data("Users")
l_df = get_data("ChatLogs")
f_df = get_data("Friends")
mid = st.session_state.auth['mid']

# Tab Structure
tabs = st.tabs(["👤 My Home", "🤝 Cooper", "👥 Social Explorer", "📩 Messages", "🛠️ Admin", "🚪 Logout"])

with tabs[0]: # MY HOME
    st.header(f"Welcome, {st.session_state.auth['fname']}")
    c1, c2 = st.columns([1, 2])
    with c1:
        st.info(f"**Bio:** {st.session_state.auth['bio']}")
        st.markdown(f"**Age:** {calculate_age(st.session_state.auth['dob'])}")
    with c2:
        st.subheader("My Private Timeline")
        p_txt = st.text_area("Write an update...", key="my_post_box")
        if st.button("Post", key="my_post_btn"):
            save_log("Feed", "user", p_txt); st.rerun()
        my_feed = l_df[(l_df['agent']=="Feed") & (l_df['memberid']==mid)].sort_values('timestamp', ascending=False)
        for _, r in my_feed.iterrows():
            st.markdown(f'<div class="feed-card"><small>{r["timestamp"]}</small><br>{r["content"]}</div>', unsafe_allow_html=True)

with tabs[2]: # SOCIAL EXPLORER
    st.subheader("Search the Network")
    search_q = st.text_input("Find User by Member ID", key="search_bar").lower().strip()
    if search_q:
        results = u_df[u_df['memberid'].astype(str).str.contains(search_q)]
        for _, row in results.iterrows():
            if str(row['memberid']) != mid:
                with st.container(border=True):
                    col_a, col_b = st.columns([3, 1])
                    col_a.write(f"**{row['firstname']}** (@{row['memberid']})")
                    if col_b.button("View Full Profile", key=f"view_{row['memberid']}"):
                        st.session_state.view_target = row['memberid']
                        st.rerun()

with tabs[3]: # MESSAGES
    mc1, mc2 = st.columns([1, 3])
    with mc1:
        st.subheader("Inbox")
        # Simplified: for demo, shows all users. Usually would filter by "Friends"
        for _, u_row in u_df.iterrows():
            if str(u_row['memberid']) != mid:
                if st.button(f"💬 {u_row['firstname']}", key=f"msg_to_{u_row['memberid']}", use_container_width=True):
                    st.session_state.active_chat_mid = u_row['memberid']; st.rerun()
    with mc2:
        target = st.session_state.active_chat_mid
        if target:
            st.subheader(f"Chatting with @{target}")
            hist = l_df[((l_df['memberid']==mid)&(l_df['agent']==f"DM:{target}")) | ((l_df['memberid']==str(target))&(l_df['agent']==f"DM:{mid}"))].sort_values('timestamp')
            with st.container(height=350):
                for _, m in hist.iterrows():
                    cls = "me" if m['memberid'] == mid else "them"
                    st.markdown(f'<div class="msg-bubble {cls}">{m["content"]}</div>', unsafe_allow_html=True)
            if dm_in := st.chat_input("Send a message...", key="dm_box"):
                save_log(f"DM:{target}", "user", dm_in); st.rerun()

with tabs[1]: # COOPER AI
    st.subheader("Consult with Cooper")
    ai_hist = l_df[(l_df['memberid'] == mid) & (l_df['agent'] == "Cooper")].tail(10)
    for _, r in ai_hist.iterrows():
        st.chat_message(r['role']).write(r['content'])
    if ai_p := st.chat_input("Ask Cooper..."):
        save_log("Cooper", "user", ai_p)
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":ai_p}]).choices[0].message.content
        save_log("Cooper", "assistant", res); st.rerun()

with tabs[4]: # ADMIN
    if st.session_state.auth['role'] == "admin":
        st.dataframe(l_df, use_container_width=True)
    else: st.error("Admin Access Only")

with tabs[5]: # LOGOUT
    if st.button("Logout", key="logout_btn"):
        st.session_state.clear(); st.rerun()
