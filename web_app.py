import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, date

# --- 1. CONFIG & SESSION ---
st.set_page_config(page_title="Health Bridge Pro", layout="wide", initial_sidebar_state="collapsed")

# Initialize Session States for Social Navigation
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
    .profile-stat { background: #334155; padding: 10px; border-radius: 8px; text-align: center; }
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

def calculate_age(dob_str):
    try:
        b_day = datetime.strptime(str(dob_str), "%Y-%m-%d").date()
        return date.today().year - b_day.year - ((date.today().month, date.today().day) < (b_day.month, b_day.day))
    except: return "N/A"

# --- 3. AUTHENTICATION FLOW ---
if not st.session_state.auth["in"]:
    st.title("🧠 Health Bridge Pro")
    t1, t2 = st.tabs(["Login", "Sign Up"])
    
    with t1:
        u_in = st.text_input("Member ID").strip().lower()
        p_in = st.text_input("Password", type="password").strip()
        if st.button("Sign In", use_container_width=True):
            ud = get_data("Users")
            if not ud.empty:
                ud['mid_c'] = ud['memberid'].astype(str).str.strip().str.lower()
                match = ud[(ud['mid_c'] == u_in) & (ud['password'].astype(str) == p_in)]
                if not match.empty:
                    r = match.iloc[0]
                    st.session_state.auth.update({"in":True, "mid":str(r['memberid']), "role":r['role'], "fname":r['firstname'], "lname":r['lastname'], "bio":r['bio'], "dob":r['dob']})
                    st.rerun()
            st.error("Login failed. Check your ID and Password.")

    with t2:
        sid = st.text_input("Username / Member ID").lower().strip()
        spw = st.text_input("Choose Password", type="password")
        c1, c2 = st.columns(2)
        with c1: sfn = st.text_input("First Name")
        with c2: sln = st.text_input("Last Name")
        sdob = st.date_input("Date of Birth", min_value=date(1940,1,1))
        if st.button("Create Account", use_container_width=True):
            ud = get_data("Users")
            if not ud.empty and sid in ud['memberid'].astype(str).values: st.error("ID Already Taken")
            else:
                new_u = pd.DataFrame([{"memberid":sid, "firstname":sfn, "lastname":sln, "password":spw, "role":"user", "bio":"I'm new here!", "dob":str(sdob)}])
                sync_data("Users", pd.concat([ud, new_u], ignore_index=True))
                save_log("Cooper", "assistant", f"Hi {sfn}! Welcome to Health Bridge. I'm Cooper, your personal health AI. How are you feeling today?", custom_mid=sid)
                st.success("Account Created! You can now Login.")
    st.stop()

# --- 4. APP DATA LOADING ---
u_df = get_data("Users")
l_df = get_data("ChatLogs")
f_df = get_data("Friends")
mid = st.session_state.auth['mid']

# Get Verified Friends
friends_ids = []
if not f_df.empty:
    f_acc = f_df[((f_df['sender'].astype(str)==mid) | (f_df['receiver'].astype(str)==mid)) & (f_df['status']=="accepted")]
    friends_ids = [str(r['receiver']) if str(r['sender']) == mid else str(r['sender']) for _, r in f_acc.iterrows()]

# --- 5. SOCIAL APP NAVIGATION ---
tabs = st.tabs(["👤 Profile", "🤝 Cooper", "✨ Clara", "👥 Friends", "📩 Messages", "🛠️ Admin", "🚪 Logout"])

# --- TAB: PROFILE (DYNAMIC ROUTER) ---
with tabs[0]:
    # Determine which profile to show
    viewing_id = st.session_state.view_mid if st.session_state.view_mid else mid
    is_my_profile = (viewing_id == mid)
    
    u_lookup = u_df[u_df['memberid'].astype(str) == str(viewing_id)] if not u_df.empty else pd.DataFrame()
    
    if not u_lookup.empty:
        u_record = u_lookup.iloc[0]
        c1, c2, c3 = st.columns([1, 2, 1])
        
        with c1: # Sidebar Info
            if not is_my_profile:
                if st.button("← Back to My Home"):
                    st.session_state.view_mid = None; st.rerun()
            st.header(f"{u_record['firstname']} {u_record['lastname']}")
            st.caption(f"Member: @{u_record['memberid']}")
            st.markdown(f"**Age:** {calculate_age(u_record['dob'])}")
            st.info(u_record['bio'])
            
        with c2: # Central Feed
            st.subheader("Timeline")
            if is_my_profile:
                with st.expander("Post an Update", expanded=True):
                    post_input = st.text_area("What's on your mind?", key="main_post", height=100)
                    if st.button("Share Post"):
                        if post_input: save_log("Feed", "user", post_input); st.rerun()
            
            # Show Feed for current viewed user
            if not l_df.empty:
                posts = l_df[(l_df['agent']=="Feed") & (l_df['memberid']==str(viewing_id))].sort_values('timestamp', ascending=False)
                if posts.empty: st.write("No posts to show yet.")
                for _, p in posts.iterrows():
                    st.markdown(f'<div class="feed-card"><small>{p["timestamp"]}</small><p>{p["content"]}</p></div>', unsafe_allow_html=True)
                    
        with c3: # Friends List Sidebar
            st.subheader("Connections")
            for fid in friends_ids:
                f_data = u_df[u_df['memberid'].astype(str)==fid]
                if not f_data.empty:
                    name = f_data.iloc[0]['firstname']
                    if st.button(f"👤 {name}", key=f"prof_nav_{fid}", use_container_width=True):
                        st.session_state.view_mid = fid; st.rerun()
    else:
        st.error("Profile not found.")

# --- TAB: AI AGENTS ---
for i, name in enumerate(["Cooper", "Clara"]):
    with tabs[i+1]:
        st.subheader(f"Consulting with {name}")
        if not l_df.empty:
            chat_hist = l_df[(l_df['memberid'] == mid) & (l_df['agent'] == name)].tail(15)
            for _, msg in chat_hist.iterrows():
                st.chat_message(msg['role']).write(msg['content'])
        
        if prompt := st.chat_input(f"Ask {name} anything..."):
            save_log(name, "user", prompt)
            client = Groq(api_key=st.secrets["GROQ_API_KEY"])
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role":"system","content":f"You are {name}, an empathetic health assistant."}] + [{"role":"user","content":prompt}]
            )
            save_log(name, "assistant", response.choices[0].message.content)
            st.rerun()

# --- TAB: FRIENDS DIRECTORY ---
with tabs[3]:
    st.subheader("Your Friends")
    if not friends_ids:
        st.info("You haven't added any friends yet.")
    for fid in friends_ids:
        f_row = u_df[u_df['memberid'].astype(str) == fid]
        if not f_row.empty:
            f_dat = f_row.iloc[0]
            with st.container(border=True):
                ca, cb = st.columns([3, 1])
                ca.write(f"**{f_dat['firstname']} {f_dat['lastname']}** (@{fid})")
                if cb.button("View Profile", key=f"dir_v_{fid}"):
                    st.session_state.view_mid = fid; st.rerun()

# --- TAB: MESSAGES ---
with tabs[4]:
    mc1, mc2 = st.columns([1, 3])
    with mc1:
        st.subheader("Chats")
        for fid in friends_ids:
            f_row = u_df[u_df['memberid'].astype(str)==fid]
            if not f_row.empty:
                fname = f_row.iloc[0]['firstname']
                if st.button(f"💬 {fname}", key=f"msg_l_{fid}", use_container_width=True):
                    st.session_state.active_chat_mid = fid; st.rerun()
    with mc2:
        target = st.session_state.active_chat_mid
        if target:
            st.subheader(f"Chat with {target}")
            if st.button("View Their Profile", use_container_width=True):
                st.session_state.view_mid = target; st.rerun()
            
            if not l_df.empty:
                dm_msgs = l_df[((l_df['memberid']==mid)&(l_df['agent']==f"DM:{target}")) | ((l_df['memberid']==str(target))&(l_df['agent']==f"DM:{mid}"))].sort_values('timestamp')
                with st.container(height=400):
                    for _, m in dm_msgs.iterrows():
                        cls = "me" if m['memberid'] == mid else "them"
                        st.markdown(f'<div class="msg-bubble {cls}">{m["content"]}</div>', unsafe_allow_html=True)
            
            if dmin := st.chat_input("Send message..."):
                save_log(f"DM:{target}", "user", dmin); st.rerun()
        else:
            st.info("Select a friend to message.")

# --- TAB: ADMIN & LOGOUT ---
with tabs[5]:
    if st.session_state.auth['role'] == "admin":
        st.subheader("System Logs")
        st.dataframe(l_df, use_container_width=True)
    else: st.error("Admin Access Required")

with tabs[6]:
    if st.button("Confirm Logout"):
        st.session_state.clear(); st.rerun()
