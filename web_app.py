import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, date

# --- 1. SETTINGS & SESSION ---
st.set_page_config(page_title="Health Bridge Pro", layout="wide", initial_sidebar_state="collapsed")

# Initialize Session States
if "auth" not in st.session_state:
    st.session_state.auth = {"in": False, "mid": None, "role": "user", "fname": "", "lname": "", "bio": "", "dob": "2000-01-01"}
if "view_mid" not in st.session_state:
    st.session_state.view_mid = None
if "active_chat_mid" not in st.session_state:
    st.session_state.active_chat_mid = None

# Custom CSS
st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    .msg-bubble { padding: 12px 18px; border-radius: 18px; margin-bottom: 10px; max-width: 80%; line-height: 1.4; display: block; }
    .me { background: #2563EB; color: white; margin-left: auto; border-bottom-right-radius: 2px; text-align: right; }
    .them { background: #334155; color: white; border-bottom-left-radius: 2px; border-left: 4px solid #10B981; }
    .feed-card { background: #1E293B; padding: 15px; border-radius: 15px; border: 1px solid #334155; margin-bottom: 15px; }
    .sidebar-friend { background: #1E293B; padding: 10px; border-radius: 8px; margin-bottom: 5px; border-left: 3px solid #6366F1; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATA CORE ---
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

# --- 3. LOGIN / SIGNUP ---
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
            st.error("Invalid Credentials")
    with t2:
        sid = st.text_input("New ID").lower().strip()
        spw = st.text_input("Password (New)")
        sfn = st.text_input("First Name")
        sln = st.text_input("Last Name")
        sdob = st.date_input("DOB")
        if st.button("Register"):
            ud = get_data("Users")
            if sid in ud['memberid'].astype(str).values: st.error("ID Taken")
            else:
                new_u = pd.DataFrame([{"memberid":sid, "firstname":sfn, "lastname":sln, "password":spw, "role":"user", "bio":"Hello!", "dob":str(sdob)}])
                sync_data("Users", pd.concat([ud, new_u], ignore_index=True))
                save_log("Cooper", "assistant", f"Welcome {sfn}! I'm Cooper, your health AI.", custom_mid=sid)
                st.success("Registered! Go to Login tab.")
    st.stop()

# --- 4. APP DATA ---
l_df = get_data("ChatLogs")
f_df = get_data("Friends")
u_df = get_data("Users")
mid = st.session_state.auth['mid']

# Get Friends List
f_acc = f_df[((f_df['sender']==mid) | (f_df['receiver']==mid)) & (f_df['status']=="accepted")]
friends_ids = [str(r['receiver']) if str(r['sender']) == mid else str(r['sender']) for _, r in f_acc.iterrows()]

tabs = st.tabs(["👤 Profile", "🤝 Cooper", "✨ Clara", "👥 Friends", "📩 Messages", "🛠️ Admin", "🚪 Logout"])

# --- TAB 0: PROFILE (THE ROUTER) ---
with tabs[0]:
    # Determine who we are looking at
    curr_view = st.session_state.view_mid if st.session_state.view_mid else mid
    u_info = u_df[u_df['memberid'].astype(str) == str(curr_view)]
    
    if not u_info.empty:
        user = u_info.iloc[0]
        c1, c2, c3 = st.columns([1, 2, 1])
        
        with c1:
            if st.session_state.view_mid:
                if st.button("← My Profile"): 
                    st.session_state.view_mid = None
                    st.rerun()
            st.header(f"{user['firstname']}")
            st.caption(f"@{user['memberid']} | Age: {calculate_age(user['dob'])}")
            st.write(user['bio'])
        
        with c2:
            st.subheader("Timeline")
            if not st.session_state.view_mid: # Only post on your own profile
                p_txt = st.text_area("What's up?", key="post_area")
                if st.button("Post"):
                    save_log("Feed", "user", p_txt); st.rerun()
            
            feed = l_df[(l_df['agent']=="Feed") & (l_df['memberid']==str(curr_view))].sort_values('timestamp', ascending=False)
            for _, r in feed.iterrows():
                st.markdown(f'<div class="feed-card"><small>{r["timestamp"]}</small><br>{r["content"]}</div>', unsafe_allow_html=True)
        
        with c3:
            st.subheader("Friends")
            for fid in friends_ids:
                fname = u_df[u_df['memberid'].astype(str)==fid]['firstname'].iloc[0]
                if st.button(f"👤 {fname}", key=f"side_{fid}", use_container_width=True):
                    st.session_state.view_mid = fid
                    st.rerun()

# --- TAB 3: FRIENDS DIRECTORY ---
with tabs[3]:
    st.subheader("Your Connections")
    if not friends_ids:
        st.info("No friends yet! Add some in the sheet.")
    for fid in friends_ids:
        f_data = u_df[u_df['memberid'].astype(str) == fid].iloc[0]
        with st.container(border=True):
            col_a, col_b = st.columns([3, 1])
            col_a.write(f"**{f_data['firstname']} {f_data['lastname']}** (@{fid})")
            if col_b.button("View Profile", key=f"dir_btn_{fid}"):
                st.session_state.view_mid = fid
                st.info(f"Viewing @{fid}. Switch to the 'Profile' tab to see them!")

# --- TAB 4: MESSAGES ---
with tabs[4]:
    m1, m2 = st.columns([1, 3])
    with m1:
        st.subheader("Inbox")
        for fid in friends_ids:
            fname = u_df[u_df['memberid'].astype(str)==fid]['firstname'].iloc[0]
            if st.button(f"💬 {fname}", key=f"msg_nav_{fid}", use_container_width=True):
                st.session_state.active_chat_mid = fid
                st.rerun()
    with m2:
        target = st.session_state.active_chat_mid
        if target:
            st.subheader(f"Chat: {target}")
            msgs = l_df[((l_df['memberid']==mid)&(l_df['agent']==f"DM:{target}")) | ((l_df['memberid']==str(target))&(l_df['agent']==f"DM:{mid}"))].sort_values('timestamp')
            for _, m in msgs.iterrows():
                cls = "me" if m['memberid'] == mid else "them"
                st.markdown(f'<div class="msg-bubble {cls}">{m["content"]}</div>', unsafe_allow_html=True)
            if dmin := st.chat_input("Type message..."):
                save_log(f"DM:{target}", "user", dmin); st.rerun()
        else:
            st.info("Select a friend to message.")

# --- ADMIN PANEL ---
with tabs[5]:
    if st.session_state.auth['role'] == "admin":
        st.subheader("🛡️ Admin Log Audit")
        search = st.text_input("Search Logs")
        if search:
            st.dataframe(l_df[l_df['content'].str.contains(search, case=False)])
        else:
            st.dataframe(l_df)
    else:
        st.error("Admin Only")

# --- AI AGENTS ---
for i, name in enumerate(["Cooper", "Clara"]):
    with tabs[i+1]:
        hist = l_df[(l_df['memberid'] == mid) & (l_df['agent'] == name)].tail(10)
        for _, r in hist.iterrows():
            st.chat_message(r['role']).write(r['content'])
        if p := st.chat_input(f"Talk to {name}", key=f"ai_{name}"):
            save_log(name, "user", p)
            client = Groq(api_key=st.secrets["GROQ_API_KEY"])
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":f"You are {name}."}] + [{"role":m.role, "content":m.content} for _,m in hist.iterrows()] + [{"role":"user","content":p}])
            save_log(name, "assistant", res.choices[0].message.content); st.rerun()

# --- LOGOUT ---
with tabs[6]:
    if st.button("Logout Now"):
        st.session_state.clear()
        st.rerun()
