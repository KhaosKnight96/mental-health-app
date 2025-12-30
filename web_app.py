import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, date

# --- 1. SETTINGS & SESSION ---
st.set_page_config(page_title="Health Bridge Pro", layout="wide", initial_sidebar_state="collapsed")

if "auth" not in st.session_state: 
    st.session_state.auth = {"in": False, "mid": None, "role": "user", "name": "", "bio": "", "dob": "2000-01-01"}
if "view_mid" not in st.session_state:
    st.session_state.view_mid = None
if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = False

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

# --- 3. AI ---
def get_ai_response(agent, prompt, history):
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"].strip())
        sys = f"You are {agent}. User is {calculate_age(st.session_state.auth['dob'])}yo."
        full_h = [{"role": "system", "content": sys}] + history + [{"role": "user", "content": prompt}]
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=full_h)
        return res.choices[0].message.content
    except Exception as e: return f"AI Error: {e}"

# --- 4. AUTH & LOGIN ---
USER_COLS = ["memberid", "name", "password", "role", "bio", "dob"]
if not st.session_state.auth["in"]:
    st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge Pro</h1>", unsafe_allow_html=True)
    t_l, t_s = st.tabs(["Login", "Sign Up"])
    with t_l:
        u_in, p_in = st.text_input("ID").lower().strip(), st.text_input("Pass", type="password")
        if st.button("Sign In", use_container_width=True):
            ud = get_data("Users", USER_COLS)
            m = ud[(ud['memberid'].astype(str).str.lower() == u_in) & (ud['password'].astype(str) == p_in)]
            if not m.empty:
                st.session_state.auth.update({"in": True, "mid": u_in, "role": m.iloc[0]['role'], "name": m.iloc[0]['name'], "bio": m.iloc[0]['bio'], "dob": m.iloc[0]['dob']})
                st.rerun()
    with t_s:
        s_id, s_nm, s_pw = st.text_input("New ID").lower().strip(), st.text_input("Name"), st.text_input("New Pass", type="password")
        s_dob = st.date_input("DOB", min_value=date(1940,1,1))
        if st.button("Join"):
            ud = get_data("Users", USER_COLS)
            if s_id in ud['memberid'].values: st.error("ID Taken")
            else:
                sync_data("Users", pd.concat([ud, pd.DataFrame([{"memberid": s_id, "name": s_nm, "password": s_pw, "role": "user", "bio": "Hi!", "dob": str(s_dob)}])]))
                st.success("Created! Log in.")
    st.stop()

# --- 5. MAIN APP ---
tabs = st.tabs(["👤 Profile", "🤝 Cooper", "✨ Clara", "👥 Friends", "📩 Messages", "🎮 Arcade", "🛠️ Admin", "🚪 Logout"])
l_df = get_data("ChatLogs", ["timestamp", "memberid", "agent", "role", "content"])
f_df = get_data("Friends", ["sender", "receiver", "status"])

# PROFILE
with tabs[0]:
    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown('<div class="avatar-pulse">👤</div>', unsafe_allow_html=True)
        if st.session_state.edit_mode:
            en, eb = st.text_input("Name", st.session_state.auth['name']), st.text_area("Bio", st.session_state.auth['bio'])
            if st.button("Save"):
                ud = get_data("Users", USER_COLS)
                ud.loc[ud['memberid']==st.session_state.auth['mid'], ['name', 'bio']] = [en, eb]
                sync_data("Users", ud); st.session_state.auth.update({"name": en, "bio": eb}); st.session_state.edit_mode = False; st.rerun()
        else:
            st.subheader(st.session_state.auth['name'])
            st.caption(f"Age: {calculate_age(st.session_state.auth['dob'])} | ID: @{st.session_state.auth['mid']}")
            st.write(st.session_state.auth['bio'])
            if st.button("Edit"): st.session_state.edit_mode = True; st.rerun()
    with c2:
        txt = st.text_area("Post Update", label_visibility="collapsed")
        if st.button("Post") and txt: save_log("Feed", "user", txt); st.rerun()
        for idx, row in l_df[(l_df['agent']=="Feed")&(l_df['memberid']==st.session_state.auth['mid'])].sort_values('timestamp', ascending=False).iterrows():
            with st.container(border=True):
                st.write(row['content'])
                if st.button("🗑️", key=f"d_{idx}"): sync_data("ChatLogs", l_df.drop(idx)); st.rerun()

# FRIENDS
with tabs[3]:
    if st.session_state.view_mid:
        if st.button("←"): st.session_state.view_mid = None; st.rerun()
        u_df = get_data("Users", USER_COLS)
        target = u_df[u_df['memberid'] == st.session_state.view_mid].iloc[0]
        st.header(target['name'])
        st.info(target['bio'])
        rel = f_df[((f_df['sender']==st.session_state.auth['mid'])&(f_df['receiver']==st.session_state.view_mid)) | ((f_df['receiver']==st.session_state.auth['mid'])&(f_df['sender']==st.session_state.view_mid))]
        if rel.empty:
            if st.button("Add"): sync_data("Friends", pd.concat([f_df, pd.DataFrame([{"sender":st.session_state.auth['mid'], "receiver":st.session_state.view_mid, "status":"pending"}])])); st.rerun()
        else:
            st.write(f"Status: {rel.iloc[0]['status']}")
            if st.button("Remove Friend"): sync_data("Friends", f_df.drop(rel.index)); st.rerun()
    else:
        sq = st.text_input("Search ID")
        if sq:
            u_df = get_data("Users", USER_COLS)
            res = u_df[u_df['memberid'].str.contains(sq, na=False)]
            for _, r in res.iterrows():
                if r['memberid'] != st.session_state.auth['mid'] and st.button(f"View @{r['memberid']}"): st.session_state.view_mid = r['memberid']; st.rerun()
        st.subheader("Current Friends")
        acc = f_df[((f_df['sender']==st.session_state.auth['mid'])|(f_df['receiver']==st.session_state.auth['mid']))&(f_df['status']=="accepted")]
        for _, r in acc.iterrows():
            f = r['receiver'] if r['sender']==st.session_state.auth['mid'] else r['sender']
            if st.button(f"👤 {f}"): st.session_state.view_mid = f; st.rerun()

# MESSAGES
with tabs[4]:
    f1 = f_df[(f_df['sender']==st.session_state.auth['mid'])&(f_df['status']=="accepted")]['receiver'].tolist()
    f2 = f_df[(f_df['receiver']==st.session_state.auth['mid'])&(f_df['status']=="accepted")]['sender'].tolist()
    frs = list(set(f1+f2))
    if frs:
        s = st.selectbox("Chat", frs)
        h = l_df[((l_df['memberid']==st.session_state.auth['mid'])&(l_df['agent']==f"DM:{s}")) | ((l_df['memberid']==s)&(l_df['agent']==f"DM:{st.session_state.auth['mid']}"))].sort_values('timestamp')
        with st.container(height=300):
            for _, m in h.iterrows():
                sty = "user-bubble" if m['memberid']==st.session_state.auth['mid'] else "direct-bubble"
                st.markdown(f'<div class="chat-bubble {sty}">{m["content"]}</div>', unsafe_allow_html=True)
        if mi := st.chat_input("Hi"): save_log(f"DM:{s}", "user", mi); st.rerun()

# AGENTS (COOPER & CLARA)
for i, n in enumerate(["Cooper", "Clara"]):
    with tabs[i+1]:
        hi = l_df[(l_df['memberid']==st.session_state.auth['mid'])&(l_df['agent']==n)].tail(10)
        with st.container(height=350):
            for _, r in hi.iterrows():
                st.markdown(f'<div class="chat-bubble {"user-bubble" if r["role"]=="user" else "ai-bubble"}">{r["content"]}</div>', unsafe_allow_html=True)
        if p := st.chat_input(f"Chat {n}", key=f"c_{n}"):
            save_log(n, "user", p)
            save_log(n, "assistant", get_ai_response(n, p, [{"role": r.role, "content": r.content} for _, r in hi.iterrows()])); st.rerun()

# ARCADE & ADMIN & LOGOUT
with tabs[5]: st.components.v1.html("""<div style="text-align:center;"><canvas id="s" width="300" height="300" style="background:#000;"></canvas></div><script>/* Existing Snake JS */</script>""", height=400)
with tabs[6]:
    if st.session_state.auth['role']=="admin": st.dataframe(l_df)
    else: st.error("Denied")
with tabs[7]:
    if st.button("Logout"): st.session_state.clear(); st.rerun()
