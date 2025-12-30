import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, date

# --- 1. SETTINGS & SESSION ---
st.set_page_config(page_title="Health Bridge Pro", layout="wide", initial_sidebar_state="collapsed")

# Initialize Session States
if "auth" not in st.session_state: 
    st.session_state.auth = {"in": False, "mid": None, "role": "user", "name": "", "bio": "", "age": ""}
if "view_mid" not in st.session_state:
    st.session_state.view_mid = None

# Custom CSS for Modern UI
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

# --- 2. DATA CORE (PROTECTED) ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=1)
def get_data(ws, cols=None):
    """Fetches data and ensures column existence to prevent KeyErrors."""
    try:
        df = conn.read(worksheet=ws, ttl=0)
        if df is None or df.empty:
            return pd.DataFrame(columns=[c.lower() for c in cols]) if cols else pd.DataFrame()
        df.columns = [str(c).strip().lower() for c in df.columns]
        # Verify specific columns exist, add if missing
        if cols:
            for c in cols:
                if c.lower() not in df.columns:
                    df[c.lower()] = None
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
        sys = f"You are {agent}, a helpful and empathetic partner on Health Bridge Pro."
        full_history = [{"role": "system", "content": sys}] + history[-5:] + [{"role": "user", "content": prompt}]
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=full_history, temperature=0.8)
        return res.choices[0].message.content
    except Exception as e: return f"AI Error: {e}"

# --- 4. AUTHENTICATION ---
if not st.session_state.auth["in"]:
    st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge</h1>", unsafe_allow_html=True)
    with st.container(border=True):
        u = st.text_input("Member ID").strip().lower()
        p = st.text_input("Password", type="password")
        if st.button("Sign In", use_container_width=True):
            users = get_data("Users", ["memberid", "password", "role", "name", "bio"])
            if not users.empty:
                m = users[(users['memberid'].astype(str).str.lower() == u) & (users['password'].astype(str) == p)]
                if not m.empty:
                    ur = m.iloc[0]
                    st.session_state.auth.update({
                        "in": True, "mid": u, "role": str(ur.get('role', 'user')).lower(),
                        "name": str(ur.get('name', 'User')), 
                        "bio": str(ur.get('bio', 'No bio.'))
                    })
                    st.rerun()
                else: st.error("Invalid credentials.")
    st.stop()

# --- 5. TABS INTERFACE ---
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
        st.subheader("📢 Post an Update")
        post = st.text_area("What's on your mind?", label_visibility="collapsed")
        if st.button("Post"):
            if post: save_log("Feed", "user", post); st.rerun()
        
        l_df = get_data("ChatLogs", ["timestamp", "memberid", "agent", "content"])
        my_feed = l_df[(l_df['agent'] == "Feed") & (l_df['memberid'] == st.session_state.auth['mid'])].sort_values('timestamp', ascending=False).head(5)
        for _, p in my_feed.iterrows():
            st.markdown(f'<div class="feed-card"><small>{p["timestamp"]}</small><p>{p["content"]}</p></div>', unsafe_allow_html=True)

# --- TAB 3: FRIENDS & PROFILE VIEWING ---
with tabs[3]:
    f_df = get_data("Friends", ["sender", "receiver", "status"])
    u_df = get_data("Users", ["memberid", "name", "bio"])
    l_df = get_data("ChatLogs", ["timestamp", "memberid", "agent", "content"])

    # View Specific Profile Mode
    if st.session_state.view_mid:
        if st.button("← Back to Friends List"):
            st.session_state.view_mid = None
            st.rerun()
        
        target = u_df[u_df['memberid'].astype(str).str.lower() == st.session_state.view_mid]
        if not target.empty:
            t = target.iloc[0]
            st.markdown(f"## 👤 Profile: {t['name']}")
            cx, cy = st.columns([1, 2])
            with cx:
                st.info(f"**Bio:** {t.get('bio', 'No bio.')}")
                st.write(f"**Member ID:** @{t['memberid']}")
                # Connection Check
                status = f_df[((f_df['sender'] == st.session_state.auth['mid']) & (f_df['receiver'] == st.session_state.view_mid)) | 
                               ((f_df['receiver'] == st.session_state.auth['mid']) & (f_df['sender'] == st.session_state.view_mid))]
                if status.empty:
                    if st.button("➕ Add Friend", use_container_width=True):
                        save_to_sheet("Friends", pd.DataFrame([{"sender": st.session_state.auth['mid'], "receiver": st.session_state.view_mid, "status": "pending"}]))
                        st.success("Request Sent!"); st.rerun()
                else:
                    st.info(f"Connection: {status.iloc[0]['status'].capitalize()}")
            with cy:
                st.subheader(f"{t['name']}'s Timeline")
                t_feed = l_df[(l_df['agent'] == "Feed") & (l_df['memberid'] == st.session_state.view_mid)].sort_values('timestamp', ascending=False)
                for _, p in t_feed.iterrows():
                    st.markdown(f'<div class="feed-card"><small>{p["timestamp"]}</small><p>{p["content"]}</p></div>', unsafe_allow_html=True)
        st.stop()

    # Friends Management Mode
    f1 = f_df[(f_df['sender'] == st.session_state.auth['mid']) & (f_df['status'] == "accepted")]['receiver'].tolist()
    f2 = f_df[(f_df['receiver'] == st.session_state.auth['mid']) & (f_df['status'] == "accepted")]['sender'].tolist()
    accepted = list(set(f1 + f2))

    c_search, c_list = st.columns(2)
    with c_search:
        st.subheader("🔍 Search")
        sq = st.text_input("Find User by ID or Name:").strip().lower()
        if sq:
            res = u_df[(u_df['name'].str.contains(sq, case=False, na=False)) | (u_df['memberid'].astype(str).str.lower() == sq)]
            res = res[res['memberid'].astype(str).str.lower() != st.session_state.auth['mid']]
            for _, r in res.iterrows():
                if st.button(f"📄 View @{r['memberid']}", key=f"src_{r['memberid']}"):
                    st.session_state.view_mid = str(r['memberid'])
                    st.rerun()
    with c_list:
        st.subheader("✅ Friends")
        for f_id in accepted:
            if st.button(f"👤 {f_id}", key=f"fbtn_{f_id}", use_container_width=True):
                st.session_state.view_mid = f_id
                st.rerun()
        
        st.subheader("📥 Requests")
        reqs = f_df[(f_df['receiver'] == st.session_state.auth['mid']) & (f_df['status'] == "pending")]
        for _, r in reqs.iterrows():
            if st.button(f"✅ Accept {r['sender']}", key=f"acc_{r['sender']}"):
                f_df.loc[(f_df['sender'] == r['sender']) & (f_df['receiver'] == st.session_state.auth['mid']), 'status'] = "accepted"
                conn.update(worksheet="Friends", data=f_df); st.rerun()

# --- TAB 4: DIRECT MESSAGING ---
with tabs[4]:
    st.subheader("📩 Messaging")
    f_df = get_data("Friends", ["sender", "receiver", "status"])
    f1 = f_df[(f_df['sender'] == st.session_state.auth['mid']) & (f_df['status'] == "accepted")]['receiver'].tolist()
    f2 = f_df[(f_df['receiver'] == st.session_state.auth['mid']) & (f_df['status'] == "accepted")]['sender'].tolist()
    friends = list(set(f1 + f2))
    if friends:
        sel = st.selectbox("Chat with:", friends)
        history = l_df[((l_df['memberid'] == st.session_state.auth['mid']) & (l_df['agent'] == f"DM:{sel}")) |
                        ((l_df['memberid'] == sel) & (l_df['agent'] == f"DM:{st.session_state.auth['mid']}"))].sort_values('timestamp')
        with st.container(height=300):
            for _, m in history.iterrows():
                sty = "user-bubble" if m['memberid'] == st.session_state.auth['mid'] else "direct-bubble"
                st.markdown(f'<div class="chat-bubble {sty}">{m["content"]}</div>', unsafe_allow_html=True)
        if msg := st.chat_input("Send message..."):
            save_log(f"DM:{sel}", "user", msg); st.rerun()
    else: st.info("Connect with friends to start a chat.")

# --- TAB 5: ARCADE (FIXED SNAKE) ---
with tabs[5]:
    gm = st.radio("Choose Game", ["Snake", "Memory", "Simon"], horizontal=True)
    if gm == "Snake":
        st.components.v1.html("""
        <div id="cont" style="text-align:center; background:#1E293B; padding:20px; border-radius:20px; font-family:sans-serif;">
            <div id="scr" style="color:#38BDF8; font-size:24px; font-weight:bold; margin-bottom:10px;">Score: 0</div>
            <div id="ov" onclick="initG()" style="position:absolute; width:300px; height:300px; background:rgba(0,0,0,0.7); color:white; display:flex; align-items:center; justify-content:center; cursor:pointer; border-radius:10px; z-index:10; left:50%; transform:translateX(-50%);">CLICK TO START</div>
            <canvas id="s" width="300" height="300" style="background:#0F172A; border:2px solid #334155; border-radius:10px;"></canvas>
            <div style="margin-top:10px; color:#94A3B8; font-size:12px;">ARROWS / WASD / SWIPE</div>
        </div>
        <script>
            const can=document.getElementById('s'), ctx=can.getContext('2d'), scr=document.getElementById('scr'), ov=document.getElementById('ov');
            let b=15, snk, f, d, sc, gL, act=false;
            function initG(){
                ov.style.display='none'; act=true; sc=0; d='R'; snk=[{x:b*5, y:b*5}];
                spawnF(); if(gL) clearInterval(gL); gL=setInterval(upd, 120);
            }
            function spawnF(){ f={x:Math.floor(Math.random()*20)*b, y:Math.floor(Math.random()*20)*b}; }
            window.onkeydown=e=>{
                let k=e.key.toLowerCase();
                if((k=='a'||k=='arrowleft')&&d!='R') d='L';
                if((k=='w'||k=='arrowup')&&d!='D') d='U';
                if((k=='d'||k=='arrowright')&&d!='L') d='R';
                if((k=='s'||k=='arrowdown')&&d!='U') d='D';
            };
            // Swipe
            let tX, tY; can.addEventListener('touchstart', e=>{ tX=e.touches[0].clientX; tY=e.touches[0].clientY; });
            can.addEventListener('touchmove', e=>{
                if(!tX||!tY) return; let dX=tX-e.touches[0].clientX, dY=tY-e.touches[0].clientY;
                if(Math.abs(dX)>Math.abs(dY)){ if(dX>0&&d!='R')d='L'; else if(dX<0&&d!='L')d='R'; }
                else { if(dY>0&&d!='D')d='U'; else if(dY<0&&d!='U')d='D'; }
                tX=null; tY=null; e.preventDefault();
            }, {passive:false});
            function upd(){
                let h={...snk[0]}; if(d=='L')h.x-=b; if(d=='U')h.y-=b; if(d=='R')h.x+=b; if(d=='D')h.y+=b;
                if(h.x==f.x&&h.y==f.y){ sc++; scr.innerText="Score: "+sc; spawnF(); } else snk.pop();
                if(h.x<0||h.x>=300||h.y<0||h.y>=300||snk.some(s=>s.x==h.x&&s.y==h.y)){ clearInterval(gL); ov.style.display='flex'; ov.innerText="GAME OVER - RESTART"; act=false; return; }
                snk.unshift(h); ctx.fillStyle='#0F172A'; ctx.fillRect(0,0,300,300);
                ctx.fillStyle='#F87171'; ctx.fillRect(f.x,f.y,b,b);
                ctx.fillStyle='#38BDF8'; snk.forEach(s=>ctx.fillRect(s.x,s.y,b,b));
            }
        </script>
        """, height=440)
    elif gm == "Memory":
        st.components.v1.html("""
        <div style="text-align:center; background:#1E293B; padding:15px; border-radius:15px;">
            <div id="grid" style="display:grid; gap:8px; grid-template-columns:repeat(4,1fr); max-width:300px; margin:auto;"></div>
        </div>
        <script>
            const icons=['❤️','⭐','🍀','💎','🎈','🎨','⚡','🔥'];
            let cards=[...icons, ...icons].sort(()=>Math.random()-0.5), flip=[], match=0;
            const g=document.getElementById('grid');
            cards.forEach((icon, i)=>{
                let c=document.createElement('div');
                c.style="height:60px; background:#334155; border-radius:8px; display:flex; align-items:center; justify-content:center; font-size:24px; cursor:pointer;";
                c.onclick=()=>{
                    if(flip.length<2 && c.innerText==''){
                        c.innerText=icon; flip.push({c,icon});
                        if(flip.length==2){
                            if(flip[0].icon==flip[1].icon){ match++; flip=[]; if(match==8) alert('Win!'); }
                            else { setTimeout(()=>{ flip.forEach(f=>f.c.innerText=''); flip=[]; }, 500); }
                        }
                    }
                }; g.appendChild(c);
            });
        </script>
        """, height=350)
    else:
        st.components.v1.html("""
        <div style="text-align:center; background:#1E293B; padding:20px; border-radius:15px;">
            <div id="st" style="color:white; font-size:20px; margin-bottom:10px;">Simon Says</div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; max-width:200px; margin:auto;">
                <div id="0" onclick="tp(0)" style="height:80px; background:#EF4444; opacity:0.3; border-radius:8px;"></div>
                <div id="1" onclick="tp(1)" style="height:80px; background:#3B82F6; opacity:0.3; border-radius:8px;"></div>
                <div id="2" onclick="tp(2)" style="height:80px; background:#EAB308; opacity:0.3; border-radius:8px;"></div>
                <div id="3" onclick="tp(3)" style="height:80px; background:#22C55E; opacity:0.3; border-radius:8px;"></div>
            </div>
            <button onclick="sq=[];lv=1;nx()" style="margin-top:15px; width:100%; padding:10px; background:#38BDF8; color:white; border:none; border-radius:5px;">START</button>
        </div>
        <script>
            let sq=[], u=[], lv=1;
            function nx(){ u=[]; sq.push(Math.floor(Math.random()*4)); ply(); }
            function ply(){ let i=0; let t=setInterval(()=>{ fl(sq[i]); i++; if(i>=sq.length)clearInterval(t); }, 600); }
            function fl(id){ let e=document.getElementById(id); e.style.opacity='1'; setTimeout(()=>e.style.opacity='0.3', 300); }
            function tp(id){ fl(id); u.push(id); if(u[u.length-1]!==sq[u.length-1]){ alert('Over!'); sq=[]; } else if(u.length==sq.length) setTimeout(nx, 800); }
        </script>
        """, height=400)

# --- TAB 6: ADMIN & AGENTS ---
with tabs[6]:
    if st.session_state.auth["role"] == "admin":
        st.subheader("🛡️ Global Logs")
        all_l = get_data("ChatLogs", ["timestamp", "memberid", "agent", "content"])
        if not all_l.empty:
            all_l['dt'] = pd.to_datetime(all_l['timestamp'], format='mixed')
            st.dataframe(all_l.sort_values('dt', ascending=False), use_container_width=True)
    else: st.error("Access Restricted.")

for i, agent in enumerate(["Cooper", "Clara"]):
    with tabs[i+1]:
        all_logs = get_data("ChatLogs", ["memberid", "agent", "role", "content"])
        ul = all_logs[(all_logs['memberid'] == st.session_state.auth['mid']) & (all_logs['agent'] == agent)].tail(10)
        with st.container(height=300):
            for _, r in ul.iterrows():
                sty = "user-bubble" if r['role'] == "user" else "ai-bubble"
                st.markdown(f'<div class="chat-bubble {sty}">{r["content"]}</div>', unsafe_allow_html=True)
        if pr := st.chat_input(f"Message {agent}"):
            save_log(agent, "user", pr)
            res = get_ai_response(agent, pr, [{"role": r.role, "content": r.content} for _, r in ul.iterrows()])
            save_log(agent, "assistant", res); st.rerun()

with tabs[7]:
    if st.button("Log out"): st.session_state.clear(); st.rerun()
