import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, date, timedelta

# --- 1. SETTINGS & SESSION ---
st.set_page_config(page_title="Health Bridge Pro", layout="wide", initial_sidebar_state="collapsed")

if "auth" not in st.session_state: 
    st.session_state.auth = {"in": False, "mid": None, "role": "user", "name": "", "bio": "", "age": ""}
if "selected_search_id" not in st.session_state:
    st.session_state.selected_search_id = None

# Custom CSS for Chat Bubbles, Feed Cards, and Touch-Friendly Arcade
st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    .chat-bubble { padding: 12px 18px; border-radius: 18px; margin-bottom: 10px; max-width: 85%; line-height: 1.5; font-family: sans-serif; }
    .user-bubble { background: #1E40AF; color: white; margin-left: auto; border-bottom-right-radius: 2px; }
    .ai-bubble { background: #334155; color: white; margin-right: auto; border-bottom-left-radius: 2px; }
    .direct-bubble { background: #065F46; color: white; margin-right: auto; border-bottom-left-radius: 2px; border-left: 4px solid #10B981; }
    .feed-card { background: #1E293B; padding: 20px; border-radius: 15px; border: 1px solid #334155; margin-bottom: 15px; }
    .avatar-pulse { width: 60px; height: 60px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 30px; margin: 0 auto 10px; background: linear-gradient(135deg, #38BDF8, #6366F1); box-shadow: 0 0 15px rgba(56, 189, 248, 0.4); }
    .game-container { touch-action: none; user-select: none; -webkit-tap-highlight-color: transparent; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATA CORE ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=1)
def get_data(ws):
    try:
        df = conn.read(worksheet=ws, ttl=0)
        df.columns = [str(c).strip().lower() for c in df.columns]
        return df
    except: return pd.DataFrame()

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
        sys = f"You are {agent}. Speak like a real human friend, fluid and empathetic."
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
            users = get_data("Users")
            m = users[(users['memberid'].astype(str).str.lower() == u) & (users['password'].astype(str) == p)]
            if not m.empty:
                st.session_state.auth.update({
                    "in": True, "mid": u, "role": str(m.iloc[0]['role']).lower(),
                    "name": str(m.iloc[0].get('name', 'User')), 
                    "bio": str(m.iloc[0].get('bio', 'No bio yet.')),
                    "age": str(m.iloc[0].get('age', 'N/A'))
                })
                st.rerun()
            else: st.error("Invalid Credentials")
    st.stop()

# --- 5. MAIN INTERFACE ---
tabs = st.tabs(["👤 Profile", "🤝 Cooper", "✨ Clara", "👥 Friends", "📩 Messages", "🎮 Arcade", "🛠️ Admin", "🚪 Logout"])

# --- TAB 0: PROFILE & FEED ---
with tabs[0]:
    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown('<div class="avatar-pulse">👤</div>', unsafe_allow_html=True)
        st.subheader(st.session_state.auth['name'])
        st.write(f"**ID:** {st.session_state.auth['mid']} | **Age:** {st.session_state.auth['age']}")
        st.info(f"**Bio:** {st.session_state.auth['bio']}")
    with c2:
        st.subheader("📢 Community Feed")
        post_txt = st.text_area("Share an update...", label_visibility="collapsed")
        if st.button("Post to Feed"):
            if post_txt: save_log("Feed", "user", post_txt); st.rerun()
        l_df = get_data("ChatLogs")
        if not l_df.empty:
            feed = l_df[l_df['agent'] == "Feed"].sort_values('timestamp', ascending=False).head(10)
            for _, p in feed.iterrows():
                st.markdown(f'<div class="feed-card"><b>@{p["memberid"]}</b><br><small>{p["timestamp"]}</small><p>{p["content"]}</p></div>', unsafe_allow_html=True)

# --- TAB 3: FRIENDS (VERIFIED PROFILE SEARCH) ---
with tabs[3]:
    f_df, u_df = get_data("Friends"), get_data("Users")
    l_df = get_data("ChatLogs")
    col_a, col_b = st.columns(2)
    with col_a:
        st.write("### 🔍 Find People")
        sq = st.text_input("Search Name/ID:").strip().lower()
        if sq:
            results = u_df[(u_df['name'].str.contains(sq, case=False, na=False)) | (u_df['memberid'].astype(str).str.lower() == sq)]
            results = results[results['memberid'].astype(str).str.lower() != st.session_state.auth['mid']]
            for _, r in results.iterrows():
                if st.button(f"👤 View {r['name']}", key=f"search_{r['memberid']}"):
                    st.session_state.selected_search_id = str(r['memberid'])
        
        if st.session_state.selected_search_id:
            with st.container(border=True):
                target = u_df[u_df['memberid'].astype(str).str.lower() == st.session_state.selected_search_id].iloc[0]
                st.write(f"**Name:** {target['name']}")
                st.write(f"**Bio:** {target.get('bio', 'No bio.')}")
                if st.button("✅ Send Friend Request"):
                    save_to_sheet("Friends", pd.DataFrame([{"sender": st.session_state.auth['mid'], "receiver": st.session_state.selected_search_id, "status": "pending"}]))
                    st.success("Request Sent!"); st.session_state.selected_search_id = None; st.rerun()
                if st.button("Cancel"): st.session_state.selected_search_id = None; st.rerun()
    with col_b:
        st.write("### 👥 My Circle")
        inbox = f_df[(f_df['receiver'] == st.session_state.auth['mid']) & (f_df['status'] == "pending")]
        for _, r in inbox.iterrows():
            if st.button(f"✅ Accept {r['sender']}"):
                f_df.loc[(f_df['sender'] == r['sender']) & (f_df['receiver'] == st.session_state.auth['mid']), 'status'] = "accepted"
                conn.update(worksheet="Friends", data=f_df); st.rerun()
        
        f1 = f_df[(f_df['sender'] == st.session_state.auth['mid']) & (f_df['status'] == "accepted")]['receiver'].tolist()
        f2 = f_df[(f_df['receiver'] == st.session_state.auth['mid']) & (f_df['status'] == "accepted")]['sender'].tolist()
        friends = list(set(f1 + f2))
        if friends:
            sel_f = st.selectbox("Quick View Friend:", ["-- Select --"] + friends)
            if sel_f != "-- Select --":
                f_posts = l_df[(l_df['memberid'] == sel_f) & (l_df['agent'] == "Feed")].head(3)
                for _, p in f_posts.iterrows(): st.caption(f"{p['timestamp']}: {p['content']}")

# --- TAB 5: ARCADE (TOUCH/SWIPE/KEYBOARD ENGINE) ---
with tabs[5]:
    game_mode = st.segmented_control("Arcade Mode", ["Snake (Swipe/Keys)", "Memory Match (Auto Level)", "Simon Says"], default="Snake (Swipe/Keys)")
    
    if game_mode == "Snake (Swipe/Keys)":
        st.components.v1.html("""
        <div class="game-container" style="text-align:center; background:#1E293B; padding:15px; border-radius:20px;">
            <div id="scr" style="color:#38BDF8; font-size:20px; font-weight:bold;">Score: 0</div>
            <canvas id="snk" width="300" height="300" style="background:#0F172A; border:3px solid #334155; border-radius:10px; margin-top:10px;"></canvas>
        </div>
        <script>
            const c=document.getElementById('snk'), x=c.getContext('2d');
            let sn=[{x:150,y:150}], f={x:75,y:75}, d='R', sc=0, tsX=null, tsY=null;
            window.onkeydown=e=>{
                if(e.key=='ArrowUp'&&d!='D')d='U'; if(e.key=='ArrowDown'&&d!='U')d='D';
                if(e.key=='ArrowLeft'&&d!='R')d='L'; if(e.key=='ArrowRight'&&d!='L')d='R';
            };
            c.addEventListener('touchstart', e=>{ tsX=e.touches[0].clientX; tsY=e.touches[0].clientY; }, false);
            c.addEventListener('touchmove', e=>{
                if(!tsX||!tsY) return;
                let tdX=tsX-e.touches[0].clientX, tdY=tsY-e.touches[0].clientY;
                if(Math.abs(tdX)>Math.abs(tdY)){ if(tdX>0 && d!='R')d='L'; else if(d!='L') d='R'; }
                else { if(tdY>0 && d!='D')d='U'; else if(d!='U') d='D'; }
                tsX=null; tsY=null; e.preventDefault();
            }, {passive: false});
            setInterval(()=>{
                x.fillStyle='#0F172A'; x.fillRect(0,0,300,300);
                x.fillStyle='#F87171'; x.fillRect(f.x,f.y,15,15);
                x.fillStyle='#38BDF8'; sn.forEach(p=>x.fillRect(p.x,p.y,15,15));
                let h={...sn[0]};
                if(d=='L')h.x-=15; if(d=='U')h.y-=15; if(d=='R')h.x+=15; if(d=='D')h.y+=15;
                if(h.x==f.x&&h.y==f.y){sc++; f={x:Math.floor(Math.random()*19)*15,y:Math.floor(Math.random()*19)*15}} else sn.pop();
                if(h.x<0||h.x>=300||h.y<0||h.y>=300||sn.some(s=>s.x==h.x&&s.y==h.y)){sn=[{x:150,y:150}]; sc=0; d='R';}
                sn.unshift(h); document.getElementById('scr').innerText="Score: "+sc;
            }, 130);
        </script>
        """, height=420)

    elif game_mode == "Memory Match (Auto Level)":
        st.components.v1.html("""
        <div class="game-container" style="text-align:center; background:#1E293B; padding:15px; border-radius:15px;">
            <div id="msg" style="color:#38BDF8; font-size:18px; margin-bottom:10px;">Level 1 (2x2)</div>
            <div id="grid" style="display:grid; gap:8px; margin:auto; max-width:320px;"></div>
        </div>
        <script>
            let cards=[], flipped=[], matched=0, sz=2;
            const icons=['❤️','⭐','🍀','💎','🎈','🎨','⚡','🔥','🍄','🌈','🌊','🍕'];
            function start(n){
                sz=n; matched=0; flipped=[];
                const g=document.getElementById('grid'); g.innerHTML='';
                g.style.gridTemplateColumns=`repeat(${n}, 1fr)`;
                document.getElementById('msg').innerText=`Level ${n-1} (${n}x${n})`;
                let count=(n*n)/2;
                let items=[...icons.slice(0,count), ...icons.slice(0,count)].sort(()=>Math.random()-0.5);
                items.forEach(icon=>{
                    let c=document.createElement('div');
                    c.style="height:65px; background:#334155; border-radius:10px; display:flex; align-items:center; justify-content:center; font-size:24px; cursor:pointer;";
                    c.onclick=()=>{ if(flipped.length<2 && c.innerText==''){
                        c.innerText=icon; flipped.push({c,icon});
                        if(flipped.length==2){
                            if(flipped[0].icon==flipped[1].icon){ matched++; flipped=[]; if(matched==(n*n)/2) setTimeout(()=>start(n+2),600); }
                            else { setTimeout(()=>{ flipped.forEach(f=>f.c.innerText=''); flipped=[]; }, 500); }
                        }
                    }}; g.appendChild(c);
                });
            } start(2);
        </script>
        """, height=450)

    elif game_mode == "Simon Says":
        st.components.v1.html("""
        <div class="game-container" style="text-align:center; background:#1E293B; padding:20px; border-radius:15px;">
            <div id="stat" style="color:white; font-size:20px; margin-bottom:15px;">Level 1</div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; max-width:240px; margin:auto;">
                <div id="0" onclick="tp(0)" style="height:100px; background:#EF4444; opacity:0.3; border-radius:10px; cursor:pointer;"></div>
                <div id="1" onclick="tp(1)" style="height:100px; background:#3B82F6; opacity:0.3; border-radius:10px; cursor:pointer;"></div>
                <div id="2" onclick="tp(2)" style="height:100px; background:#EAB308; opacity:0.3; border-radius:10px; cursor:pointer;"></div>
                <div id="3" onclick="tp(3)" style="height:100px; background:#22C55E; opacity:0.3; border-radius:10px; cursor:pointer;"></div>
            </div>
            <button onclick="sq=[];lv=1;nxt()" style="margin-top:20px; width:100%; padding:15px; background:#38BDF8; color:white; border:none; border-radius:10px; font-weight:bold;">START GAME</button>
        </div>
        <script>
            let sq=[], u=[], lv=1;
            function nxt(){ u=[]; sq.push(Math.floor(Math.random()*4)); ply(); }
            function ply(){ let i=0; let t=setInterval(()=>{ fl(sq[i]); i++; if(i>=sq.length)clearInterval(t); }, 600); }
            function fl(id){ let e=document.getElementById(id); e.style.opacity='1'; setTimeout(()=>e.style.opacity='0.3', 300); }
            function tp(id){ fl(id); u.push(id); if(u[u.length-1]!==sq[u.length-1]){ alert('Sequence Error!'); sq=[]; lv=1; document.getElementById('stat').innerText='Level 1'; } 
            else if(u.length==sq.length){ lv++; document.getElementById('stat').innerText='Level '+lv; setTimeout(nxt, 800); } }
        </script>
        """, height=450)

# --- TAB 6: ADMIN (STRICT PD.TIMESTAMP FIX) ---
with tabs[6]:
    if st.session_state.auth["role"] == "admin":
        st.subheader("🛡️ Activity Explorer")
        all_l = get_data("ChatLogs")
        if not all_l.empty:
            all_l['dt'] = pd.to_datetime(all_l['timestamp'])
            c1, c2 = st.columns(2)
            u_f = c1.selectbox("User Filter", ["All"] + list(all_l['memberid'].unique()))
            d_r = c2.date_input("Filter Range", value=(all_l['dt'].min().date(), date.today()))
            
            # THE FIX: Explicit conversion to pd.Timestamp for valid comparison
            if isinstance(d_r, tuple) and len(d_r) == 2:
                start_ts = pd.Timestamp(d_r[0])
                end_ts = pd.Timestamp(d_r[1]) + pd.Timedelta(days=1)
                filt = all_l[(all_l['dt'] >= start_ts) & (all_l['dt'] < end_ts)]
                if u_f != "All": filt = filt[filt['memberid'] == u_f]
                st.dataframe(filt.drop(columns=['dt']).sort_values('timestamp', ascending=False), use_container_width=True)
    else: st.error("Admin Access Required")

# --- AI AGENTS & LOGOUT ---
for i, agent in enumerate(["Cooper", "Clara"]):
    with tabs[i+1]:
        st.markdown(f'<div class="avatar-pulse">{"🤝" if agent=="Cooper" else "✨"}</div>', unsafe_allow_html=True)
        logs = get_data("ChatLogs")
        ulogs = logs[(logs['memberid'] == st.session_state.auth['mid']) & (logs['agent'] == agent)].tail(20)
        with st.container(height=350):
            for _, r in ulogs.iterrows():
                sty = "user-bubble" if r['role'] == "user" else "ai-bubble"
                st.markdown(f'<div class="chat-bubble {sty}">{r["content"]}</div>', unsafe_allow_html=True)
        if prompt := st.chat_input(f"Chat with {agent}...", key=f"chat_{agent}"):
            save_log(agent, "user", prompt)
            response = get_ai_response(agent, prompt, [{"role": r.role, "content": r.content} for _, r in ulogs.iterrows()])
            save_log(agent, "assistant", response); st.rerun()

with tabs[7]:
    if st.button("Confirm Logout"): st.session_state.clear(); st.rerun()
