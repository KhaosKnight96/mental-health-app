import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, date

# --- 1. SETTINGS & SESSION ---
st.set_page_config(page_title="Health Bridge Pro", layout="wide", initial_sidebar_state="collapsed")

if "auth" not in st.session_state: 
    st.session_state.auth = {"in": False, "mid": None, "role": "user", "name": "", "bio": "", "age": ""}
if "view_mid" not in st.session_state:
    st.session_state.view_mid = None

st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    .chat-bubble { padding: 12px 18px; border-radius: 18px; margin-bottom: 10px; max-width: 85%; line-height: 1.5; font-family: sans-serif; }
    .user-bubble { background: #1E40AF; color: white; margin-left: auto; border-bottom-right-radius: 2px; }
    .ai-bubble { background: #334155; color: white; margin-right: auto; border-bottom-left-radius: 2px; }
    .direct-bubble { background: #065F46; color: white; margin-right: auto; border-bottom-left-radius: 2px; border-left: 4px solid #10B981; }
    .feed-card { background: #1E293B; padding: 15px; border-radius: 15px; border: 1px solid #334155; margin-bottom: 10px; }
    .avatar-pulse { width: 60px; height: 60px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 30px; margin: 0 auto 10px; background: linear-gradient(135deg, #38BDF8, #6366F1); }
</style>
""", unsafe_allow_html=True)

# --- 2. DATA CORE (FIXED FOR KEYERROR) ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=1)
def get_data(ws, cols=None):
    try:
        df = conn.read(worksheet=ws, ttl=0)
        if df.empty and cols:
            return pd.DataFrame(columns=[c.lower() for c in cols])
        df.columns = [str(c).strip().lower() for c in df.columns]
        return df
    except: 
        return pd.DataFrame(columns=[c.lower() for c in cols]) if cols else pd.DataFrame()

def save_to_sheet(ws_name, df_to_add):
    try:
        existing = conn.read(worksheet=ws_name, ttl=0)
        updated = pd.concat([existing, df_to_add], ignore_index=True)
        conn.update(worksheet=ws_name, data=updated)
        st.cache_data.clear()
    except Exception as e: st.error(f"Save Error: {e}")

def save_log(agent, role, content):
    new_row = pd.DataFrame([{
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "memberid": st.session_state.auth['mid'], 
        "agent": agent, "role": role, "content": content
    }])
    save_to_sheet("ChatLogs", new_row)

# --- 3. AI LOGIC ---
def get_ai_response(agent, prompt, history):
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"].strip())
        sys = f"You are {agent}. Be empathetic and helpful."
        full_history = [{"role": "system", "content": sys}] + history[-5:] + [{"role": "user", "content": prompt}]
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=full_history, temperature=0.8)
        return res.choices[0].message.content
    except Exception as e: return f"AI Error: {e}"

# --- 4. AUTH ---
if not st.session_state.auth["in"]:
    st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge</h1>", unsafe_allow_html=True)
    with st.container(border=True):
        u = st.text_input("Member ID").strip().lower()
        p = st.text_input("Password", type="password")
        if st.button("Sign In", use_container_width=True):
            users = get_data("Users", ["memberid", "password", "role", "name", "bio", "age"])
            if not users.empty:
                m = users[(users['memberid'].astype(str).str.lower() == u) & (users['password'].astype(str) == p)]
                if not m.empty:
                    ur = m.iloc[0]
                    st.session_state.auth.update({
                        "in": True, "mid": u, "role": str(ur.get('role', 'user')).lower(),
                        "name": str(ur.get('name', 'User')), 
                        "bio": str(ur.get('bio', 'No bio.')), "age": str(ur.get('age', 'N/A'))
                    })
                    st.rerun()
                else: st.error("Incorrect credentials.")
    st.stop()

# --- 5. INTERFACE ---
tabs = st.tabs(["👤 Profile", "🤝 Cooper", "✨ Clara", "👥 Friends", "📩 Messages", "🎮 Arcade", "🛠️ Admin", "🚪 Logout"])

# --- TAB 0: PERSONAL PROFILE ---
with tabs[0]:
    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown('<div class="avatar-pulse">👤</div>', unsafe_allow_html=True)
        st.subheader(st.session_state.auth['name'])
        st.write(f"**ID:** {st.session_state.auth['mid']}")
        st.info(f"**Bio:** {st.session_state.auth['bio']}")
    with c2:
        st.subheader("📢 My Timeline")
        post = st.text_area("Post to your timeline...", label_visibility="collapsed")
        if st.button("Post"):
            if post: save_log("Feed", "user", post); st.rerun()
        l_df = get_data("ChatLogs", ["timestamp", "memberid", "agent", "role", "content"])
        if not l_df.empty:
            my_feed = l_df[(l_df['agent'] == "Feed") & (l_df['memberid'] == st.session_state.auth['mid'])].sort_values('timestamp', ascending=False).head(10)
            for _, p in my_feed.iterrows():
                st.markdown(f'<div class="feed-card"><small>{p["timestamp"]}</small><p>{p["content"]}</p></div>', unsafe_allow_html=True)

# --- TAB 3: FRIENDS & EXTERNAL PROFILES (KEYERROR PROTECTION) ---
with tabs[3]:
    f_df = get_data("Friends", ["sender", "receiver", "status"])
    u_df = get_data("Users", ["memberid", "name", "bio"])
    l_df = get_data("ChatLogs", ["timestamp", "memberid", "agent", "content"])
    
    if st.session_state.view_mid:
        if st.button("← Back to Friends"):
            st.session_state.view_mid = None
            st.rerun()
        
        target_u = u_df[u_df['memberid'].astype(str).str.lower() == st.session_state.view_mid]
        if not target_u.empty:
            t = target_u.iloc[0]
            st.markdown(f"## 👤 {t['name']}'s Profile")
            cx, cy = st.columns([1, 2])
            with cx:
                st.info(f"**Bio:** {t.get('bio', 'No bio.')}")
                st.write(f"**Member ID:** @{t['memberid']}")
                # Request Logic
                status_check = f_df[((f_df['sender'] == st.session_state.auth['mid']) & (f_df['receiver'] == st.session_state.view_mid)) | 
                                    ((f_df['receiver'] == st.session_state.auth['mid']) & (f_df['sender'] == st.session_state.view_mid))]
                if status_check.empty:
                    if st.button("➕ Add Friend", use_container_width=True):
                        save_to_sheet("Friends", pd.DataFrame([{"sender": st.session_state.auth['mid'], "receiver": st.session_state.view_mid, "status": "pending"}]))
                        st.success("Request Sent!"); st.rerun()
                else:
                    st.info(f"Status: {status_check.iloc[0]['status'].capitalize()}")
            with cy:
                st.subheader("📜 Timeline")
                u_feed = l_df[(l_df['agent'] == "Feed") & (l_df['memberid'] == st.session_state.view_mid)].sort_values('timestamp', ascending=False)
                for _, p in u_feed.iterrows():
                    st.markdown(f'<div class="feed-card"><small>{p["timestamp"]}</small><p>{p["content"]}</p></div>', unsafe_allow_html=True)
        st.stop()

    # Friends List Logic
    f1 = f_df[(f_df['sender'] == st.session_state.auth['mid']) & (f_df['status'] == "accepted")]['receiver'].tolist()
    f2 = f_df[(f_df['receiver'] == st.session_state.auth['mid']) & (f_df['status'] == "accepted")]['sender'].tolist()
    accepted_friends = list(set(f1 + f2))

    cl, cr = st.columns(2)
    with cl:
        st.subheader("🔍 Find People")
        sq = st.text_input("Search ID or Name:").strip().lower()
        if sq:
            res = u_df[(u_df['name'].str.contains(sq, case=False, na=False)) | (u_df['memberid'].astype(str).str.lower() == sq)]
            res = res[res['memberid'].astype(str).str.lower() != st.session_state.auth['mid']]
            for _, r in res.iterrows():
                if st.button(f"📄 Preview @{r['memberid']}", key=f"p_{r['memberid']}"):
                    st.session_state.view_mid = str(r['memberid'])
                    st.rerun()
    with cr:
        st.subheader("✅ My Friends")
        for f_id in accepted_friends:
            if st.button(f"👤 {f_id}", key=f"f_{f_id}", use_container_width=True):
                st.session_state.view_mid = f_id
                st.rerun()
        st.subheader("📥 Requests")
        inbound = f_df[(f_df['receiver'] == st.session_state.auth['mid']) & (f_df['status'] == "pending")]
        for _, r in inbound.iterrows():
            if st.button(f"✅ Accept {r['sender']}", key=f"acc_{r['sender']}"):
                f_df.loc[(f_df['sender'] == r['sender']) & (f_df['receiver'] == st.session_state.auth['mid']), 'status'] = "accepted"
                conn.update(worksheet="Friends", data=f_df); st.rerun()

# --- TAB 4: DIRECT MESSAGES ---
with tabs[4]:
    st.subheader("📩 Direct Messages")
    f_df = get_data("Friends", ["sender", "receiver", "status"])
    l_df = get_data("ChatLogs", ["timestamp", "memberid", "agent", "content"])
    f1 = f_df[(f_df['sender'] == st.session_state.auth['mid']) & (f_df['status'] == "accepted")]['receiver'].tolist()
    f2 = f_df[(f_df['receiver'] == st.session_state.auth['mid']) & (f_df['status'] == "accepted")]['sender'].tolist()
    friends = list(set(f1 + f2))
    if friends:
        sel = st.selectbox("Select Conversation:", friends)
        history = l_df[((l_df['memberid'] == st.session_state.auth['mid']) & (l_df['agent'] == f"DM:{sel}")) |
                        ((l_df['memberid'] == sel) & (l_df['agent'] == f"DM:{st.session_state.auth['mid']}"))].sort_values('timestamp')
        with st.container(height=300):
            for _, m in history.iterrows():
                sty = "user-bubble" if m['memberid'] == st.session_state.auth['mid'] else "direct-bubble"
                st.markdown(f'<div class="chat-bubble {sty}">{m["content"]}</div>', unsafe_allow_html=True)
        if msg := st.chat_input(f"Message {sel}"):
            save_log(f"DM:{sel}", "user", msg); st.rerun()
    else: st.info("Add friends to start chatting.")

# --- TAB 5: ARCADE (SAME GAMES) ---
with tabs[5]:
    gm = st.radio("Library", ["Snake", "Memory", "Simon Says"], horizontal=True)
    if gm == "Snake":
        st.components.v1.html("""
        <div style="text-align:center; background:#1E293B; padding:15px; border-radius:20px;">
            <div id="scr" style="color:#38BDF8; font-size:20px;">Score: 0</div>
            <canvas id="snk" width="300" height="300" style="background:#0F172A; border:3px solid #334155; margin-top:10px;"></canvas>
        </div>
        <script>
            const c=document.getElementById('snk'), x=c.getContext('2d');
            let sn=[{x:150,y:150}], f={x:75,y:75}, d='R', sc=0, tsX=null, tsY=null;
            window.onkeydown=e=>{ let k=e.key.toLowerCase(); if(k=='arrowleft'||k=='a') d='L'; if(k=='arrowright'||k=='d') d='R'; if(k=='arrowup'||k=='w') d='U'; if(k=='arrowdown'||k=='s') d='D'; };
            c.addEventListener('touchstart', e=>{ tsX=e.touches[0].clientX; tsY=e.touches[0].clientY; });
            c.addEventListener('touchmove', e=>{ if(!tsX||!tsY) return; let dx=tsX-e.touches[0].clientX, dy=tsY-e.touches[0].clientY; if(Math.abs(dx)>Math.abs(dy)) d=dx>0?'L':'R'; else d=dy>0?'U':'D'; tsX=null; tsY=null; e.preventDefault(); }, {passive:false});
            setInterval(()=>{
                x.fillStyle='#0F172A'; x.fillRect(0,0,300,300); x.fillStyle='#F87171'; x.fillRect(f.x,f.y,15,15);
                x.fillStyle='#38BDF8'; sn.forEach(p=>x.fillRect(p.x,p.y,15,15));
                let h={...sn[0]}; if(d=='L')h.x-=15; if(d=='R')h.x+=15; if(d=='U')h.y-=15; if(d=='D')h.y+=15;
                if(h.x==f.x&&h.y==f.y){sc++; f={x:Math.floor(Math.random()*19)*15,y:Math.floor(Math.random()*19)*15}} else sn.pop();
                if(h.x<0||h.x>=300||h.y<0||h.y>=300||sn.some(s=>s.x==h.x&&s.y==h.y)){sn=[{x:150,y:150}]; sc=0; d='R';}
                sn.unshift(h); document.getElementById('scr').innerText="Score: "+sc;
            }, 130);
        </script>
        """, height=400)
    elif gm == "Memory":
        st.components.v1.html("""
        <div style="text-align:center; background:#1E293B; padding:15px; border-radius:15px;">
            <div id="msg" style="color:#38BDF8; font-size:18px;">Memory</div>
            <div id="grid" style="display:grid; gap:8px; margin:auto; max-width:320px; margin-top:10px;"></div>
        </div>
        <script>
            let cards=[], flipped=[], matched=0; const icons=['❤️','⭐','🍀','💎','🎈','🎨','⚡','🔥','🍄','🌈'];
            function start(n){
                matched=0; flipped=[]; const g=document.getElementById('grid'); g.innerHTML=''; g.style.gridTemplateColumns=`repeat(${n}, 1fr)`;
                let count=(n*n)/2; let items=[...icons.slice(0,count), ...icons.slice(0,count)].sort(()=>Math.random()-0.5);
                items.forEach(icon=>{
                    let c=document.createElement('div'); c.style="height:65px; background:#334155; border-radius:10px; display:flex; align-items:center; justify-content:center; font-size:24px; cursor:pointer;";
                    c.onclick=()=>{ if(flipped.length<2 && c.innerText==''){
                        c.innerText=icon; flipped.push({c,icon});
                        if(flipped.length==2){ if(flipped[0].icon==flipped[1].icon){ matched++; flipped=[]; if(matched==(n*n)/2) setTimeout(()=>start(n+2),600); }
                        else { setTimeout(()=>{ flipped.forEach(f=>f.c.innerText=''); flipped=[]; }, 500); } } }}; g.appendChild(c);
                });
            } start(2);
        </script>
        """, height=450)
    else:
        st.components.v1.html("""
        <div style="text-align:center; background:#1E293B; padding:20px; border-radius:15px;">
            <div id="stat" style="color:white; font-size:20px; margin-bottom:15px;">Level 1</div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; max-width:240px; margin:auto;">
                <div id="0" onclick="tp(0)" style="height:100px; background:#EF4444; opacity:0.3; border-radius:10px; cursor:pointer;"></div>
                <div id="1" onclick="tp(1)" style="height:100px; background:#3B82F6; opacity:0.3; border-radius:10px; cursor:pointer;"></div>
                <div id="2" onclick="tp(2)" style="height:100px; background:#EAB308; opacity:0.3; border-radius:10px; cursor:pointer;"></div>
                <div id="3" onclick="tp(3)" style="height:100px; background:#22C55E; opacity:0.3; border-radius:10px; cursor:pointer;"></div>
            </div>
            <button onclick="sq=[];lv=1;nxt()" style="margin-top:20px; width:100%; padding:15px; background:#38BDF8; color:white; border-radius:10px; border:none; cursor:pointer; font-weight:bold;">START</button>
        </div>
        <script>
            let sq=[], u=[], lv=1; window.onkeydown=e=>{ if(['1','2','3','4'].includes(e.key)) tp(parseInt(e.key)-1); };
            function nxt(){ u=[]; sq.push(Math.floor(Math.random()*4)); ply(); }
            function ply(){ let i=0; let t=setInterval(()=>{ fl(sq[i]); i++; if(i>=sq.length)clearInterval(t); }, 600); }
            function fl(id){ let e=document.getElementById(id); e.style.opacity='1'; setTimeout(()=>e.style.opacity='0.3', 300); }
            function tp(id){ fl(id); u.push(id); if(u[u.length-1]!==sq[u.length-1]){ alert('Game Over!'); sq=[]; lv=1; document.getElementById('stat').innerText='Level 1'; } 
            else if(u.length==sq.length){ lv++; document.getElementById('stat').innerText='Level '+lv; setTimeout(nxt, 800); } }
        </script>
        """, height=480)

# --- TAB 6: ADMIN ---
with tabs[6]:
    if st.session_state.auth["role"] == "admin":
        st.subheader("🛡️ Admin Logs")
        all_l = get_data("ChatLogs", ["timestamp", "memberid", "agent", "content"])
        if not all_l.empty:
            all_l['dt'] = pd.to_datetime(all_l['timestamp'], format='mixed')
            c1, c2 = st.columns(2)
            u_f = c1.selectbox("User", ["All"] + list(all_l['memberid'].unique()))
            d_r = c2.date_input("Range", value=(all_l['dt'].min().date(), date.today()))
            if isinstance(d_r, tuple) and len(d_r) == 2:
                s_ts, e_ts = pd.Timestamp(d_r[0]), pd.Timestamp(d_r[1]) + pd.Timedelta(days=1)
                filt = all_l[(all_l['dt'] >= s_ts) & (all_l['dt'] < e_ts)]
                if u_f != "All": filt = filt[filt['memberid'] == u_f]
                st.dataframe(filt.drop(columns=['dt']).sort_values('timestamp', ascending=False), use_container_width=True)
    else: st.error("Restricted")

# --- AGENTS & LOGOUT ---
for i, agent in enumerate(["Cooper", "Clara"]):
    with tabs[i+1]:
        all_logs = get_data("ChatLogs", ["memberid", "agent", "role", "content"])
        ul = all_logs[(all_logs['memberid'] == st.session_state.auth['mid']) & (all_logs['agent'] == agent)].tail(15)
        with st.container(height=300):
            for _, r in ul.iterrows():
                sty = "user-bubble" if r['role'] == "user" else "ai-bubble"
                st.markdown(f'<div class="chat-bubble {sty}">{r["content"]}</div>', unsafe_allow_html=True)
        if pr := st.chat_input(f"Chat with {agent}"):
            save_log(agent, "user", pr)
            res = get_ai_response(agent, pr, [{"role": r.role, "content": r.content} for _, r in ul.iterrows()])
            save_log(agent, "assistant", res); st.rerun()

with tabs[7]:
    if st.button("Logout"): st.session_state.clear(); st.rerun()
