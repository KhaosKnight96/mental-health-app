import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, date

# --- 1. SETTINGS & SESSION ---
st.set_page_config(page_title="Health Bridge Pro", layout="wide", initial_sidebar_state="collapsed")

if "auth" not in st.session_state: 
    st.session_state.auth = {"in": False, "mid": None, "role": "user", "fname": "", "lname": "", "bio": "", "dob": "2000-01-01"}
if "view_mid" not in st.session_state:
    st.session_state.view_mid = None
if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = False

# Custom UI Styling
st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    .chat-bubble { padding: 12px 18px; border-radius: 18px; margin-bottom: 10px; max-width: 85%; }
    .user-bubble { background: #1E40AF; color: white; margin-left: auto; border-bottom-right-radius: 2px; }
    .ai-bubble { background: #334155; color: white; margin-right: auto; border-bottom-left-radius: 2px; }
    .direct-bubble { background: #065F46; color: white; margin-right: auto; border-bottom-left-radius: 2px; border-left: 4px solid #10B981; }
    .feed-card { background: #1E293B; padding: 15px; border-radius: 15px; border: 1px solid #334155; margin-bottom: 10px; }
    .avatar-pulse { width: 60px; height: 60px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 30px; margin: 0 auto 10px; background: linear-gradient(135deg, #38BDF8, #6366F1); }
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

# --- 3. AI ENGINE ---
def get_ai_response(agent, prompt, history):
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"].strip())
        fname = st.session_state.auth['fname']
        u_age = calculate_age(st.session_state.auth['dob'])
        sys = f"You are {agent}, a health companion. User is {fname}, age {u_age}. Be empathetic."
        full_h = [{"role": "system", "content": sys}] + history + [{"role": "user", "content": prompt}]
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=full_h)
        return res.choices[0].message.content
    except Exception as e: return f"AI Error: {e}"

# --- 4. AUTH & SIGNUP ---
USER_COLS = ["memberid", "firstname", "lastname", "password", "role", "bio", "dob"]

if not st.session_state.auth["in"]:
    st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge Pro</h1>", unsafe_allow_html=True)
    t_l, t_s = st.tabs(["Login", "Sign Up"])
    
    with t_l:
        u_in = st.text_input("Member ID", key="l_id").lower().strip()
        p_in = st.text_input("Password", type="password", key="l_pw")
        if st.button("Sign In", use_container_width=True):
            ud = get_data("Users", USER_COLS)
            m = ud[(ud['memberid'].astype(str).str.lower() == u_in) & (ud['password'].astype(str) == p_in)]
            if not m.empty:
                r = m.iloc[0]
                st.session_state.auth.update({"in": True, "mid": u_in, "role": r['role'], "fname": r['firstname'], "lname": r['lastname'], "bio": r['bio'], "dob": r['dob']})
                st.rerun()
            else: st.error("Invalid credentials.")

    with t_s:
        s_id = st.text_input("Choose Member ID", key="s_id").lower().strip()
        s_pw = st.text_input("Create Password", type="password", key="s_pw")
        c1, c2 = st.columns(2)
        with c1: s_fn = st.text_input("First Name", key="s_fn")
        with c2: s_ln = st.text_input("Last Name", key="s_ln")
        s_dob = st.date_input("Date of Birth", min_value=date(1940,1,1), key="s_dob")
        if st.button("Create Account", use_container_width=True):
            ud = get_data("Users", USER_COLS)
            if s_id in ud['memberid'].astype(str).values: st.error("ID taken.")
            else:
                new_u = pd.DataFrame([{"memberid": s_id, "firstname": s_fn, "lastname": s_ln, "password": s_pw, "role": "user", "bio": "New!", "dob": str(s_dob)}])
                sync_data("Users", pd.concat([ud, new_u], ignore_index=True))
                st.success("Account created! Go to Login.")
    st.stop()

# --- 5. TABS ---
tabs = st.tabs(["👤 Profile", "🤝 Cooper", "✨ Clara", "👥 Friends", "📩 Messages", "🛠️ Admin", "🚪 Logout"])
l_df = get_data("ChatLogs", ["timestamp", "memberid", "agent", "role", "content"])
f_df = get_data("Friends", ["sender", "receiver", "status"])

# --- PROFILE TAB ---
with tabs[0]:
    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown('<div class="avatar-pulse">👤</div>', unsafe_allow_html=True)
        if st.session_state.edit_mode:
            en = st.text_input("First Name", value=st.session_state.auth['fname'], key="e_fn")
            el = st.text_input("Last Name", value=st.session_state.auth['lname'], key="e_ln")
            eb = st.text_area("Bio", value=st.session_state.auth['bio'], key="e_bio")
            if st.button("Save Profile"):
                ud = get_data("Users", USER_COLS)
                ud.loc[ud['memberid'] == st.session_state.auth['mid'], ['firstname', 'lastname', 'bio']] = [en, el, eb]
                sync_data("Users", ud)
                st.session_state.auth.update({"fname": en, "lname": el, "bio": eb})
                st.session_state.edit_mode = False; st.rerun()
        else:
            st.subheader(f"{st.session_state.auth['fname']} {st.session_state.auth['lname']}")
            st.caption(f"Age: {calculate_age(st.session_state.auth['dob'])} | @{st.session_state.auth['mid']}")
            st.write(st.session_state.auth['bio'])
            if st.button("Edit Profile"): st.session_state.edit_mode = True; st.rerun()
    with c2:
        txt = st.text_area("What's happening?", key="feed_in")
        if st.button("Post") and txt: save_log("Feed", "user", txt); st.rerun()
        for idx, row in l_df[(l_df['agent']=="Feed")&(l_df['memberid']==st.session_state.auth['mid'])].sort_values('timestamp', ascending=False).iterrows():
            with st.container(border=True):
                st.write(row['content'])
                if st.button("Delete", key=f"del_{idx}"): sync_data("ChatLogs", l_df.drop(idx)); st.rerun()

# --- AI AGENTS ---
for i, name in enumerate(["Cooper", "Clara"]):
    with tabs[i+1]:
        hist = l_df[(l_df['memberid'] == st.session_state.auth['mid']) & (l_df['agent'] == name)].tail(10)
        with st.container(height=400):
            for _, r in hist.iterrows():
                sty = "user-bubble" if r['role'] == "user" else "ai-bubble"
                st.markdown(f'<div class="chat-bubble {sty}">{r["content"]}</div>', unsafe_allow_html=True)
        if prompt := st.chat_input(f"Chat with {name}", key=f"chat_{name}"):
            save_log(name, "user", prompt)
            ans = get_ai_response(name, prompt, [{"role": r.role, "content": r.content} for _, r in hist.iterrows()])
            save_log(name, "assistant", ans); st.rerun()

# --- FRIENDS TAB ---
with tabs[3]:
    if st.session_state.view_mid:
        if st.button("← Back"): st.session_state.view_mid = None; st.rerun()
        u_df = get_data("Users", USER_COLS)
        target = u_df[u_df['memberid'] == st.session_state.view_mid].iloc[0]
        st.header(f"{target['firstname']} {target['lastname']}")
        st.info(target['bio'])
        rel = f_df[((f_df['sender']==st.session_state.auth['mid'])&(f_df['receiver']==st.session_state.view_mid)) | ((f_df['receiver']==st.session_state.auth['mid'])&(f_df['sender']==st.session_state.view_mid))]
        if rel.empty:
            if st.button("Add Friend"): sync_data("Friends", pd.concat([f_df, pd.DataFrame([{"sender":st.session_state.auth['mid'], "receiver":st.session_state.view_mid, "status":"pending"}])])); st.rerun()
        else:
            if st.button("Remove Friend"): sync_data("Friends", f_df.drop(rel.index)); st.rerun()
    else:
        sq = st.text_input("Search Users", key="f_search")
        if sq:
            u_df = get_data("Users", USER_COLS)
            res = u_df[u_df['memberid'].str.contains(sq, na=False)]
            for _, r in res.iterrows():
                if r['memberid'] != st.session_state.auth['mid'] and st.button(f"View @{r['memberid']}", key=f"v_{r['memberid']}"): st.session_state.view_mid = r['memberid']; st.rerun()

# --- MESSAGES TAB ---
with tabs[4]:
    f1 = f_df[(f_df['sender']==st.session_state.auth['mid'])&(f_df['status']=="accepted")]['receiver'].tolist()
    f2 = f_df[(f_df['receiver']==st.session_state.auth['mid'])&(f_df['status']=="accepted")]['sender'].tolist()
    frs = list(set(f1+f2))
    if frs:
        sel = st.selectbox("Select Chat", frs, key="msg_sel")
        h = l_df[((l_df['memberid']==st.session_state.auth['mid'])&(l_df['agent']==f"DM:{sel}")) | ((l_df['memberid']==sel)&(l_df['agent']==f"DM:{st.session_state.auth['mid']}"))].sort_values('timestamp')
        for _, m in h.iterrows():
            sty = "user-bubble" if m['memberid']==st.session_state.auth['mid'] else "direct-bubble"
            st.markdown(f'<div class="chat-bubble {sty}">{m["content"]}</div>', unsafe_allow_html=True)
        if mi := st.chat_input("Message...", key="msg_in"): save_log(f"DM:{sel}", "user", mi); st.rerun()

# --- ADMIN TAB ---
with tabs[5]:
    if st.session_state.auth['role'] == "admin":
        st.subheader("🛡️ Admin Console")
        mode = st.radio("View", ["Users", "Logs"], horizontal=True, key="adm_v")
        if mode == "Users": st.dataframe(get_data("Users", USER_COLS), use_container_width=True)
        else: 
            search = st.text_input("Filter Logs", key="adm_log_f")
            filtered = l_df[l_df['memberid'].str.contains(search, case=False)] if search else l_df
            st.dataframe(filtered.sort_values('timestamp', ascending=False), use_container_width=True)
    else: st.error("Admin Only")

# --- LOGOUT ---
with tabs[6]:
    if st.button("Logout"): st.session_state.clear(); st.rerun()
