import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, date

# --- 1. SETTINGS & SESSION ---
st.set_page_config(page_title="Health Bridge Pro", layout="wide", initial_sidebar_state="collapsed")

if "auth" not in st.session_state: 
    st.session_state.auth = {"in": False, "mid": None, "role": "user", "name": "", "bio": "", "dob": ""}
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
    .feed-card { background: #1E293B; padding: 15px; border-radius: 15px; border: 1px solid #334155; margin-bottom: 10px; position: relative; }
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
def get_data(ws, cols=None):
    try:
        df = conn.read(worksheet=ws, ttl=0)
        if df is None or df.empty:
            return pd.DataFrame(columns=[c.lower() for c in cols]) if cols else pd.DataFrame()
        df.columns = [str(c).strip().lower() for c in df.columns]
        if cols:
            for c in cols:
                if c.lower() not in df.columns: df[c.lower()] = None
        return df
    except: return pd.DataFrame(columns=[c.lower() for c in cols]) if cols else pd.DataFrame()

def sync_data(ws_name, df):
    conn.update(worksheet=ws_name, data=df)
    st.cache_data.clear()

def save_log(agent, role, content):
    new_row = pd.DataFrame([{
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "memberid": st.session_state.auth['mid'], 
        "agent": agent, "role": role, "content": content
    }])
    existing = get_data("ChatLogs")
    sync_data("ChatLogs", pd.concat([existing, new_row], ignore_index=True))

# --- 3. AI ENGINE ---
def get_ai_response(agent, prompt, history):
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"].strip())
        u_age = calculate_age(st.session_state.auth['dob'])
        sys = f"You are {agent}. User is {u_age} years old. Be empathetic."
        full_h = [{"role": "system", "content": sys}] + history + [{"role": "user", "content": prompt}]
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=full_h)
        return res.choices[0].message.content
    except Exception as e: return f"AI Error: {e}"

# --- 4. AUTH & SIGNUP ---
if not st.session_state.auth["in"]:
    st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge Pro</h1>", unsafe_allow_html=True)
    tab_l, tab_s = st.tabs(["Login", "Sign Up"])
    
    with tab_l:
        u_in = st.text_input("ID").lower()
        p_in = st.text_input("Password", type="password")
        if st.button("Sign In", use_container_width=True):
            ud = get_data("Users")
            m = ud[(ud['memberid'].astype(str).str.lower() == u_in) & (ud['password'].astype(str) == p_in)]
            if not m.empty:
                r = m.iloc[0]
                st.session_state.auth.update({"in": True, "mid": u_in, "role": r['role'], "name": r['name'], "bio": r['bio'], "dob": r['dob']})
                st.rerun()
            else: st.error("Invalid credentials")

    with tab_s:
        s_id = st.text_input("New Member ID").lower()
        s_nm = st.text_input("Full Name")
        s_pw = st.text_input("New Password", type="password")
        s_dob = st.date_input("Birthday", min_value=date(1940,1,1), max_value=date.today())
        if st.button("Create Account"):
            ud = get_data("Users", ["memberid", "name", "password", "role", "bio", "dob"])
            if s_id in ud['memberid'].values: st.error("ID exists")
            else:
                new_u = pd.DataFrame([{"memberid": s_id, "name": s_nm, "password": s_pw, "role": "user", "bio": "New here!", "dob": str(s_dob)}])
                sync_data("Users", pd.concat([ud, new_u], ignore_index=True))
                st.success("Success! Please Login.")
    st.stop()

# --- 5. TABS ---
tabs = st.tabs(["👤 Profile", "🤝 Cooper", "✨ Clara", "👥 Friends", "📩 Messages", "🎮 Arcade", "🛠️ Admin", "🚪 Logout"])
l_df = get_data("ChatLogs")

# --- PROFILE TAB ---
with tabs[0]:
    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown('<div class="avatar-pulse">👤</div>', unsafe_allow_html=True)
        if st.session_state.edit_mode:
            e_name = st.text_input("Name", value=st.session_state.auth['name'])
            e_bio = st.text_area("Bio", value=st.session_state.auth['bio'])
            if st.button("Save Changes"):
                ud = get_data("Users")
                ud.loc[ud['memberid'] == st.session_state.auth['mid'], ['name', 'bio']] = [e_name, e_bio]
                sync_data("Users", ud)
                st.session_state.auth.update({"name": e_name, "bio": e_bio})
                st.session_state.edit_mode = False
                st.rerun()
        else:
            st.subheader(st.session_state.auth['name'])
            st.caption(f"Age: {calculate_age(st.session_state.auth['dob'])} | ID: @{st.session_state.auth['mid']}")
            st.write(st.session_state.auth['bio'])
            if st.button("Edit Profile"):
                st.session_state.edit_mode = True
                st.rerun()
    with c2:
        st.subheader("📢 Post Update")
        p_txt = st.text_area("What's on your mind?", label_visibility="collapsed")
        if st.button("Post"):
            if p_txt: save_log("Feed", "user", p_txt); st.rerun()
        
        my_feed = l_df[(l_df['agent'] == "Feed") & (l_df['memberid'] == st.session_state.auth['mid'])].sort_values('timestamp', ascending=False)
        for idx, row in my_feed.iterrows():
            with st.container(border=True):
                st.write(row['content'])
                st.caption(row['timestamp'])
                if st.button("Delete Post", key=f"del_{idx}"):
                    l_df = l_df.drop(idx)
                    sync_data("ChatLogs", l_df)
                    st.rerun()

# --- FRIENDS TAB ---
with tabs[3]:
    f_df = get_data("Friends", ["sender", "receiver", "status"])
    u_df = get_data("Users")
    
    if st.session_state.view_mid:
        if st.button("← Back"): st.session_state.view_mid = None; st.rerun()
        target = u_df[u_df['memberid'] == st.session_state.view_mid].iloc[0]
        st.header(f"Profile: {target['name']}")
        cx, cy = st.columns([1, 2])
        with cx:
            st.info(target['bio'])
            st.write(f"Age: {calculate_age(target['dob'])}")
            rel = f_df[((f_df['sender']==st.session_state.auth['mid'])&(f_df['receiver']==st.session_state.view_mid)) | 
                       ((f_df['receiver']==st.session_state.auth['mid'])&(f_df['sender']==st.session_state.view_mid))]
            if rel.empty:
                if st.button("Add Friend"):
                    sync_data("Friends", pd.concat([f_df, pd.DataFrame([{"sender": st.session_state.auth['mid'], "receiver": st.session_state.view_mid, "status": "pending"}])], ignore_index=True))
                    st.rerun()
            else:
                st.warning(f"Connection: {rel.iloc[0]['status']}")
                if st.button("Remove Friend", type="primary"):
                    f_df = f_df.drop(rel.index)
                    sync_data("Friends", f_df)
                    st.rerun()
        with cy:
            st.subheader("Timeline")
            t_feed = l_df[(l_df['agent'] == "Feed") & (l_df['memberid'] == st.session_state.view_mid)].sort_values('timestamp', ascending=False)
            for _, r in t_feed.iterrows():
                st.markdown(f'<div class="feed-card"><small>{r["timestamp"]}</small><p>{r["content"]}</p></div>', unsafe_allow_html=True)
    else:
        c_s, c_f = st.columns(2)
        with c_s:
            search = st.text_input("Search User ID")
            if search:
                res = u_df[u_df['memberid'].str.contains(search, na=False)]
                for _, r in res.iterrows():
                    if r['memberid'] != st.session_state.auth['mid']:
                        if st.button(f"View @{r['memberid']}", key=f"v_{r['memberid']}"):
                            st.session_state.view_mid = r['memberid']; st.rerun()
        with c_f:
            st.subheader("Friends")
            accepted = f_df[((f_df['sender']==st.session_state.auth['mid']) | (f_df['receiver']==st.session_state.auth['mid'])) & (f_df['status']=="accepted")]
            for _, r in accepted.iterrows():
                fr = r['receiver'] if r['sender'] == st.session_state.auth['mid'] else r['sender']
                if st.button(f"👤 {fr}", key=f"list_{fr}"):
                    st.session_state.view_mid = fr; st.rerun()

# --- MESSAGES TAB ---
with tabs[4]:
    # Logic to get accepted friends
    f1 = f_df[(f_df['sender'] == st.session_state.auth['mid']) & (f_df['status'] == "accepted")]['receiver'].tolist()
    f2 = f_df[(f_df['receiver'] == st.session_state.auth['mid']) & (f_df['status'] == "accepted")]['sender'].tolist()
    frnds = list(set(f1+f2))
    if frnds:
        sel = st.selectbox("Chat with", frnds)
        dm_hist = l_df[((l_df['memberid']==st.session_state.auth['mid']) & (l_df['agent']==f"DM:{sel}")) | 
                        ((l_df['memberid']==sel) & (l_df['agent']==f"DM:{st.session_state.auth['mid']}"))].sort_values('timestamp')
        with st.container(height=300):
            for _, m in dm_hist.iterrows():
                sty = "user-bubble" if m['memberid'] == st.session_state.auth['mid'] else "direct-bubble"
                st.markdown(f'<div class="chat-bubble {sty}">{m["content"]}</div>', unsafe_allow_html=True)
        if msg_in := st.chat_input("Message..."):
            save_log(f"DM:{sel}", "user", msg_in); st.rerun()

# --- AI AGENTS LOOP (COOPER & CLARA) ---
for i, name in enumerate(["Cooper", "Clara"]):
    with tabs[i+1]:
        hist = l_df[(l_df['memberid'] == st.session_state.auth['mid']) & (l_df['agent'] == name)].tail(10)
        with st.container(height=400):
            for _, r in hist.iterrows():
                sty = "user-bubble" if r['role'] == "user" else "ai-bubble"
                st.markdown(f'<div class="chat-bubble {sty}">{r["content"]}</div>', unsafe_allow_html=True)
        if prompt := st.chat_input(f"Speak with {name}", key=f"chat_{name}"):
            save_log(name, "user", prompt)
            ans = get_ai_response(name, prompt, [{"role": r.role, "content": r.content} for _, r in hist.iterrows()])
            save_log(name, "assistant", ans); st.rerun()

# --- ARCADE TAB ---
with tabs[5]:
    st.info("Snake Game Active. Click Start to Play!")
    st.components.v1.html("""
    <div id="cont" style="text-align:center; background:#1E293B; padding:20px; border-radius:20px; font-family:sans-serif;">
        <div id="scr" style="color:#38BDF8; font-size:24px; font-weight:bold; margin-bottom:10px;">Score: 0</div>
        <div id="ov" onclick="initG()" style="position:absolute; width:300px; height:300px; background:rgba(0,0,0,0.7); color:white; display:flex; align-items:center; justify-content:center; cursor:pointer; border-radius:10px; z-index:10; left:50%; transform:translateX(-50%);">CLICK TO START</div>
        <canvas id="s" width="300" height="300" style="background:#0F172A; border:2px solid #334155; border-radius:10px;"></canvas>
    </div>
    <script>
        const can=document.getElementById('s'), ctx=can.getContext('2d'), scr=document.getElementById('scr'), ov=document.getElementById('ov');
        let b=15, snk, f, d, sc, gL, act=false;
        function initG(){ ov.style.display='none'; act=true; sc=0; d='R'; snk=[{x:b*5, y:b*5}]; spawnF(); if(gL) clearInterval(gL); gL=setInterval(upd, 120); }
        function spawnF(){ f={x:Math.floor(Math.random()*20)*b, y:Math.floor(Math.random()*20)*b}; }
        window.onkeydown=e=>{ let k=e.key.toLowerCase(); if((k=='a'||k=='arrowleft')&&d!='R') d='L'; if((k=='w'||k=='arrowup')&&d!='D') d='U'; if((k=='d'||k=='arrowright')&&d!='L') d='R'; if((k=='s'||k=='arrowdown')&&d!='U') d='D'; };
        function upd(){
            let h={...snk[0]}; if(d=='L')h.x-=b; if(d=='U')h.y-=b; if(d=='R')h.x+=b; if(d=='D')h.y+=b;
            if(h.x==f.x&&h.y==f.y){ sc++; scr.innerText="Score: "+sc; spawnF(); } else snk.pop();
            if(h.x<0||h.x>=300||h.y<0||h.y>=300||snk.some(s=>s.x==h.x&&s.y==h.y)){ clearInterval(gL); ov.style.display='flex'; ov.innerText="OVER - RESTART"; act=false; return; }
            snk.unshift(h); ctx.fillStyle='#0F172A'; ctx.fillRect(0,0,300,300); ctx.fillStyle='#F87171'; ctx.fillRect(f.x,f.y,b,b); ctx.fillStyle='#38BDF8'; snk.forEach(s=>ctx.fillRect(s.x,s.y,b,b));
        }
    </script>
    """, height=400)

with tabs[6]:
    if st.session_state.auth['role'] == "admin":
        st.dataframe(l_df, use_container_width=True)
    else: st.error("Admin Only")

with tabs[7]:
    if st.button("Logout"): st.session_state.clear(); st.rerun()
