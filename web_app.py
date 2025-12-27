import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta
import plotly.graph_objects as go

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Health Bridge", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    .portal-card { background: #1E293B; padding: 25px; border-radius: 20px; border: 1px solid #334155; margin-bottom: 20px; }
    
    .glass-panel {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(15px);
        border-radius: 25px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 25px;
        margin-bottom: 20px;
    }
    
    .avatar-pulse {
        width: 70px; height: 70px;
        border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: 35px; margin: 0 auto 15px;
        animation: pulse 3s infinite;
    }

    @keyframes pulse {
        0% { transform: scale(1); opacity: 1; }
        70% { transform: scale(1.05); opacity: 0.8; }
        100% { transform: scale(1); opacity: 1; }
    }

    .stButton>button { border-radius: 12px; font-weight: 600; height: 3.5em; width: 100%; border: none; }
    .stTabs [data-baseweb="tab-list"] { gap: 20px; }
    .stTabs [data-baseweb="tab"] { background-color: #1E293B; border-radius: 10px; padding: 10px 20px; color: white; }
    .stTabs [aria-selected="true"] { background-color: #38BDF8 !important; }
</style>
""", unsafe_allow_html=True)

# --- 2. CONNECTIONS & DATA HELPERS ---
conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "mid": None, "name": None, "role": "user"}

def get_data(worksheet_name):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        # CASE INSENSITIVE FIX: Convert all column names to lowercase and strip spaces
        df.columns = [str(c).strip().lower() for c in df.columns]
        return df
    except:
        if worksheet_name == "chatlogs":
            return pd.DataFrame(columns=["timestamp", "memberid", "agent", "role", "content"])
        return pd.DataFrame()

def save_chat_to_sheets(agent, role, content):
    # Map the data to lowercase keys to match the normalized sheet
    new_entry = pd.DataFrame([{
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "memberid": st.session_state.auth['mid'],
        "agent": agent,
        "role": role,
        "content": content
    }])
    existing_df = get_data("ChatLogs")
    updated_df = pd.concat([existing_df, new_entry], ignore_index=True)
    conn.update(worksheet="ChatLogs", data=updated_df)

# --- 3. LOGIN GATE ---
if not st.session_state.auth["logged_in"]:
    st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge Portal</h1>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["🔐 Login", "📝 Sign Up"])
    with t1:
        u = st.text_input("Member ID", key="l_u").strip().lower() # Input is now lowercase
        p = st.text_input("Password", type="password", key="l_p")
        if st.button("Sign In"):
            df = get_data("Users")
            # Logic now checks against lowercase 'memberid' and 'password'
            if 'memberid' in df.columns and 'password' in df.columns:
                m = df[(df['memberid'].astype(str).str.lower() == u) & 
                       (df['password'].astype(str) == p)]
                
                if not m.empty:
                    user_role = m.iloc[0]['role'] if 'role' in m.columns else 'user'
                    st.session_state.auth.update({
                        "logged_in": True, 
                        "mid": u, 
                        "name": m.iloc[0]['fullname'] if 'fullname' in m.columns else u,
                        "role": str(user_role).lower()
                    })
                    st.rerun()
                else: st.error("Invalid Credentials")
            else:
                st.error(f"Sheet missing required columns. Found: {df.columns.tolist()}")
    
    with t2:
        n = st.text_input("Full Name")
        c = st.text_input("Member ID (Create)").strip().lower()
        pw = st.text_input("Create Password", type="password")
        if st.button("Register"):
            df = get_data("Users")
            new_user = pd.DataFrame([{"fullname": n, "memberid": c, "password": pw, "role": "user"}])
            conn.update(worksheet="Users", data=pd.concat([df, new_user], ignore_index=True))
            st.success("Account created!")
    st.stop()
# --- 4. NAVIGATION ---
nav_options = ["🏠 Cooper's Corner", "🛋️ Clara's Couch", "🎮 Games"]
if st.session_state.auth.get("role") == "admin":
    nav_options.append("🛡️ Admin Portal")
nav_options.append("🚪 Logout")

main_nav = st.tabs(nav_options)

# --- 5. COOPER'S CORNER ---
with main_nav[0]:
    col1, col2 = st.columns([1, 1.3])
    with col1:
        st.markdown('<div class="portal-card"><h3>⚡ Energy Status</h3>', unsafe_allow_html=True)
        ev = st.slider("Energy Level", 1, 11, 6)
        emoji_map = {1:'🚨', 2:'🪫', 3:'😫', 4:'🥱', 5:'🙁', 6:'😐', 7:'🙂', 8:'😊', 9:'⚡', 10:'🚀', 11:'☀️'}
        st.markdown(f"<h1 style='text-align:center; font-size:80px;'>{emoji_map[ev]}</h1>", unsafe_allow_html=True)
        if st.button("💾 Sync Data"):
            new_row = pd.DataFrame([{"Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), "MemberId": st.session_state.auth['mid'], "EnergyLog": ev}])
            conn.update(worksheet="Sheet1", data=pd.concat([get_data("Sheet1"), new_row], ignore_index=True))
            st.success("Logged!")
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="glass-panel"><div class="avatar-pulse" style="background:linear-gradient(135deg,#38BDF8,#6366F1);">👤</div><h3 style="text-align:center; color:#38BDF8; margin-bottom:0;">Cooper\'s Corner</h3><p style="text-align:center; color:#94A3B8; font-size:14px;">A human companion for reflection</p></div>', unsafe_allow_html=True)
        chat_box = st.container(height=380, border=False)
        with chat_box:
            for m in st.session_state.cooper_logs:
                with st.chat_message(m["role"], avatar="👤"): st.write(m["content"])
        if p := st.chat_input("Speak with Cooper..."):
            st.session_state.cooper_logs.append({"role": "user", "content": p})
            save_chat_to_sheets("Cooper", "user", p)
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":"You are Cooper, a wise and warm human companion."}]+st.session_state.cooper_logs[-5:]).choices[0].message.content
            st.session_state.cooper_logs.append({"role": "assistant", "content": res})
            save_chat_to_sheets("Cooper", "assistant", res)
            st.rerun()

# --- 6. CLARA'S COUCH ---
with main_nav[1]:
    st.markdown('<div class="glass-panel"><div class="avatar-pulse" style="background:linear-gradient(135deg,#F472B6,#FB7185);">🧘‍♀️</div><h3 style="text-align:center; color:#F472B6; margin-bottom:0;">Clara\'s Couch</h3><p style="text-align:center; color:#94A3B8; font-size:14px;">Weekly Insights & Clinical Trends</p></div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1.5, 1])
    with c1:
        try:
            df_l = get_data("Sheet1")
            df_p = df_l[df_l['MemberId'].astype(str) == str(st.session_state.auth['mid'])].copy()
            df_p['Timestamp'] = pd.to_datetime(df_p['Timestamp'])
            df_p = df_p.sort_values('Timestamp')
            if not df_p.empty:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df_p['Timestamp'], y=df_p['EnergyLog'], fill='tozeroy', line=dict(color='#F472B6', width=4)))
                fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="white"), height=300)
                st.plotly_chart(fig, use_container_width=True)
                if st.button("✨ Generate Clara's Weekly Insight"):
                    last_week = df_p[df_p['Timestamp'] > (datetime.now() - timedelta(days=7))]
                    data_summary = last_week['EnergyLog'].to_list()
                    insight = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":"You are Clara, a clinical analyst. Summarize data professionally."} ,{"role":"user","content": f"Data: {data_summary}"}]).choices[0].message.content
                    st.info(insight)
        except: st.info("Recording history needed.")
    with c2:
        clara_chat = st.container(height=400, border=False)
        with clara_chat:
            for m in st.session_state.clara_logs:
                with st.chat_message(m["role"], avatar="🧘‍♀️"): st.write(m["content"])
        if cp := st.chat_input("Analyze with Clara..."):
            st.session_state.clara_logs.append({"role": "user", "content": cp})
            save_chat_to_sheets("Clara", "user", cp)
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":"You are Clara, a clinical analyst."}]+st.session_state.clara_logs[-5:]).choices[0].message.content
            st.session_state.clara_logs.append({"role": "assistant", "content": res})
            save_chat_to_sheets("Clara", "assistant", res)
            st.rerun()

# --- 7. GAMES ---
with main_nav[2]:
    gt = st.radio("Select Activity", ["Modern Snake", "Memory Match", "2048 Logic"], horizontal=True)
    
    JS_SOUNDS = """
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    function playSound(freq, type, duration, vol=0.1) {
        const osc = audioCtx.createOscillator(); const gain = audioCtx.createGain();
        osc.type = type; osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
        gain.gain.setValueAtTime(vol, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + duration);
        osc.connect(gain); gain.connect(audioCtx.destination);
        osc.start(); osc.stop(audioCtx.currentTime + duration);
    }
    """

    if gt == "Modern Snake":
        SNAKE_HTML = f"""
        <div style="display:flex; flex-direction:column; align-items:center; background:#1E293B; padding:20px; border-radius:15px; position:relative;">
            <canvas id="s" width="300" height="300" style="border:4px solid #38BDF8; background:#0F172A; border-radius:10px;"></canvas>
            <h2 id="st" style="color:#38BDF8; font-family:sans-serif;">Score: 0</h2>
            <div id="over" style="display:none; position:absolute; top:0; left:0; width:100%; height:100%; background:rgba(15,23,42,0.85); border-radius:15px; flex-direction:column; align-items:center; justify-content:center; z-index:10;">
                <h1 style="color:#F87171; font-family:sans-serif; margin-bottom:5px;">GAME OVER</h1>
                <p id="finalScore" style="color:white; font-family:sans-serif; font-size:1.2em; margin-bottom:20px;">Score: 0</p>
                <button onclick="resetSnake()" style="background:#38BDF8; color:white; border:none; padding:10px 20px; border-radius:8px; cursor:pointer; font-weight:bold;">Try Again</button>
            </div>
        </div>
        <script>
        {{
        {JS_SOUNDS}
        const canvas=document.getElementById("s"), ctx=canvas.getContext("2d"), box=15;
        let score=0, d, game, snake, food;
        function resetSnake() {{
            document.getElementById("over").style.display = "none";
            score=0; d=undefined; snake=[{{x:10*box, y:10*box}}];
            food={{x:Math.floor(Math.random()*19)*box, y:Math.floor(Math.random()*19)*box}};
            document.getElementById("st").innerText="Score: 0";
            if(game) clearInterval(game); game = setInterval(draw, 100);
        }}
        window.addEventListener("keydown", e => {{ 
            if(["ArrowUp","ArrowDown","ArrowLeft","ArrowRight"].includes(e.code)) e.preventDefault();
            if(e.code=="ArrowLeft" && d!="RIGHT") d="LEFT"; if(e.code=="ArrowUp" && d!="DOWN") d="UP";
            if(e.code=="ArrowRight" && d!="LEFT") d="RIGHT"; if(e.code=="ArrowDown" && d!="UP") d="DOWN"; 
        }});
        function draw() {{
            ctx.fillStyle="#0F172A"; ctx.fillRect(0,0,300,300);
            ctx.fillStyle = "#F87171"; ctx.beginPath(); ctx.arc(food.x+box/2, food.y+box/2, box/3, 0, Math.PI*2); ctx.fill();
            snake.forEach((p,i)=>{{ ctx.fillStyle= i==0 ? "#38BDF8" : "rgba(56, 189, 248, "+(1-i/snake.length)+")"; ctx.fillRect(p.x, p.y, box-1, box-1); }});
            let hX=snake[0].x, hY=snake[0].y;
            if(d=="LEFT") hX-=box; if(d=="UP") hY-=box; if(d=="RIGHT") hX+=box; if(d=="DOWN") hY+=box;
            if(hX==food.x && hY==food.y){{
                score++; document.getElementById("st").innerText="Score: "+score;
                playSound(600, 'sine', 0.1); food={{x:Math.floor(Math.random()*19)*box, y:Math.floor(Math.random()*19)*box}};
            }} else if(d) snake.pop();
            let h={{x:hX, y:hY}};
            if(hX<0||hX>=300||hY<0||hY>=300||(d && snake.some(z=>z.x==h.x&&z.y==h.y))){{
                playSound(150, 'sawtooth', 0.5); clearInterval(game);
                document.getElementById("finalScore").innerText = "Final Score: " + score;
                document.getElementById("over").style.display = "flex";
            }}
            if(d) snake.unshift(h);
        }}
        resetSnake();
        }}
        </script>
        """
        st.components.v1.html(SNAKE_HTML, height=480)

    elif gt == "Memory Match":
        MEMORY_HTML = f"""
        <div style="display:flex; flex-direction:column; align-items:center; background:#1E293B; padding:20px; border-radius:15px; position:relative; min-height:480px;">
            <div style="text-align: center; color: #38BDF8; font-family: sans-serif; margin-bottom: 15px;">
                <span id="lvl" style="font-weight:bold; font-size:1.2em;">Level 1</span> | Matches: <span id="mtch">0</span>
            </div>
            <div id="g" style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; width: 100%; max-width: 400px;"></div>
            <div id="overMem" style="display:none; position:absolute; top:0; left:0; width:100%; height:100%; background:rgba(15,23,42,0.9); border-radius:15px; flex-direction:column; align-items:center; justify-content:center; z-index:10; text-align:center;">
                <h1 id="memTitle" style="color:#38BDF8; font-family:sans-serif;">LEVEL CLEAR!</h1>
                <p id="memDesc" style="color:white; font-family:sans-serif; margin-bottom:20px;">Ready for more?</p>
                <button id="memBtn" onclick="nextLevel()" style="background:#38BDF8; color:white; border:none; padding:12px 24px; border-radius:8px; cursor:pointer; font-weight:bold;">Next Level</button>
            </div>
        </div>
        <script>
            {{
            {JS_SOUNDS}
            const allIcons = ['🍎','💎','🌟','🚀','🌈','🔥','🍀','🎁','🦄','🐲','🍕','🎸','🪐','⚽','🍦','🍭','🎲','⚡'];
            let currentLevel = 1, flipped = [], lock = false, matches = 0, totalPairs = 8;
            window.nextLevel = function() {{ if (currentLevel < 3) {{ currentLevel++; loadLevel(currentLevel); }} else {{ currentLevel = 1; loadLevel(1); }} }};
            window.loadLevel = function(level) {{
                document.getElementById("overMem").style.display = "none";
                const board = document.getElementById('g'); board.innerHTML = ''; matches = 0; flipped = [];
                totalPairs = level === 1 ? 8 : (level === 2 ? 12 : 18);
                document.getElementById('lvl').innerText = "Level " + level;
                document.getElementById('mtch').innerText = "0 / " + totalPairs;
                board.style.gridTemplateColumns = (level === 1) ? "repeat(4, 1fr)" : "repeat(6, 1fr)";
                let levelIcons = allIcons.slice(0, totalPairs);
                let gameIcons = [...levelIcons, ...levelIcons].sort(() => 0.5 - Math.random());
                gameIcons.forEach(icon => {{
                    const card = document.createElement('div'); card.style.height = "70px"; card.style.position = "relative";
                    card.style.transformStyle = "preserve-3d"; card.style.transition = "transform 0.5s"; card.style.cursor = "pointer";
                    card.innerHTML = `<div style="position:absolute; width:100%; height:100%; backface-visibility:hidden; border-radius:8px; background:#1E293B; border:2px solid #38BDF8;"></div>
                                      <div style="position:absolute; width:100%; height:100%; backface-visibility:hidden; border-radius:8px; background:#334155; transform:rotateY(180deg); display:flex; align-items:center; justify-content:center; font-size:25px; color:white;">${{icon}}</div>`;
                    card.dataset.icon = icon;
                    card.onclick = function() {{
                        if(lock || this.style.transform === "rotateY(180deg)") return;
                        playSound(440, 'sine', 0.05); this.style.transform = "rotateY(180deg)"; flipped.push(this);
                        if(flipped.length === 2) {{
                            lock = true;
                            if(flipped[0].dataset.icon === flipped[1].dataset.icon) {{
                                matches++; document.getElementById('mtch').innerText = matches + " / " + totalPairs;
                                flipped = []; lock = false; setTimeout(() => playSound(880, 'sine', 0.2), 200);
                                if(matches === totalPairs) setTimeout(showWinOverlay, 600);
                            }} else {{
                                setTimeout(() => {{ playSound(220, 'sine', 0.2); flipped.forEach(c => c.style.transform = "rotateY(0deg)"); flipped = []; lock = false; }}, 800);
                            }}
                        }}
                    }}; board.appendChild(card);
                }});
            }};
            function showWinOverlay() {{
                const overlay = document.getElementById("overMem");
                document.getElementById("memTitle").innerText = currentLevel < 3 ? "LEVEL CLEAR!" : "GRANDMASTER!";
                document.getElementById("memBtn").innerText = currentLevel < 3 ? "Next Level" : "Restart";
                overlay.style.display = "flex";
            }}
            loadLevel(1);
            }}
        </script>
        """
        st.components.v1.html(MEMORY_HTML, height=580)

    elif gt == "2048 Logic":
        T2048_HTML = f"""
        <div style="display:flex; flex-direction:column; align-items:center; background:#1E293B; padding:20px; border-radius:15px; position:relative;">
            <div id="grid" style="display:grid; grid-template-columns:repeat(4, 60px); grid-gap:10px; background:#0F172A; padding:10px; border-radius:10px;"></div>
            <h2 id="sc" style="color:#38BDF8; margin-top:15px;">Score: 0</h2>
            <div id="over2048" style="display:none; position:absolute; top:0; left:0; width:100%; height:100%; background:rgba(15,23,42,0.9); border-radius:15px; flex-direction:column; align-items:center; justify-content:center; z-index:10;">
                <h1 style="color:#38BDF8;">OUT OF MOVES</h1>
                <p id="finalScore2048" style="color:white; font-size:1.2em; margin-bottom:20px;">Score: 0</p>
                <button onclick="init()" style="background:#38BDF8; color:white; border:none; padding:10px 20px; border-radius:8px; font-weight:bold;">Restart</button>
            </div>
        </div>
        <script>
            {{
            {JS_SOUNDS}
            const gridDisp = document.getElementById('grid');
            let board = Array(16).fill(0), score = 0;
            window.init = function() {{ document.getElementById("over2048").style.display = "none"; board = Array(16).fill(0); score = 0; addTile(); addTile(); render(); }};
            function addTile() {{ let empty = board.map((v, i) => v === 0 ? i : null).filter(v => v !== null); if (empty.length) board[empty[Math.floor(Math.random()*empty.length)]] = Math.random() < 0.9 ? 2 : 4; }}
            function render() {{
                gridDisp.innerHTML = '';
                board.forEach(v => {{
                    const t = document.createElement('div'); t.style.width='60px'; t.style.height='60px'; t.style.background=v?'#38BDF8':'#334155';
                    t.style.color='white'; t.style.display='flex'; t.style.alignItems='center'; t.style.justifyContent='center';
                    t.style.borderRadius='5px'; t.style.fontWeight='bold'; t.innerText=v||''; gridDisp.appendChild(t);
                }});
                document.getElementById('sc').innerText = "Score: " + score; checkGameOver();
            }}
            function checkGameOver() {{
                if (board.includes(0)) return;
                for (let i=0; i<4; i++) for (let j=0; j<4; j++) {{
                    let c = board[i*4+j]; if (j<3 && c===board[i*4+j+1]) return; if (i<3 && c===board[(i+1)*4+j]) return;
                }}
                document.getElementById("finalScore2048").innerText = "Final Score: " + score; document.getElementById("over2048").style.display = "flex";
            }}
            window.addEventListener('keydown', e => {{
                if(!["ArrowUp","ArrowDown","ArrowLeft","ArrowRight"].includes(e.code)) return; e.preventDefault();
                let old = [...board]; if(e.code==="ArrowLeft") move(0,1,4); if(e.code==="ArrowRight") move(3,-1,4);
                if(e.code==="ArrowUp") move(0,4,1); if(e.code==="ArrowDown") move(12,-4,1);
                if (JSON.stringify(old)!==JSON.stringify(board)) {{ playSound(523,'sine',0.05); addTile(); render(); }}
            }});
            function move(s,st,sd) {{
                for (let i=0; i<4; i++) {{
                    let l = []; for (let j=0; j<4; j++) l.push(board[s+i*sd+j*st]);
                    let f = l.filter(v=>v); for (let j=0; j<f.length-1; j++) if (f[j]===f[j+1]) {{ f[j]*=2; score+=f[j]; f.splice(j+1,1); playSound(1046,'sine',0.1); }}
                    while (f.length<4) f.push(0); for (let j=0; j<4; j++) board[s+i*sd+j*st] = f[j];
                }}
            }}
            init();
            }}
        </script>
        """
        st.components.v1.html(T2048_HTML, height=480)

# --- 8. ADMIN PORTAL ---
if st.session_state.auth.get("role") == "admin":
    with main_nav[-2]:
        st.header("🛡️ Admin Chat Explorer")
        logs_df = get_data("ChatLogs")
        if not logs_df.empty:
            c1, c2, c3 = st.columns(3)
            with c1: u_f = st.multiselect("Member ID", options=logs_df['MemberId'].unique())
            with c2: a_f = st.multiselect("Agent", options=logs_df['Agent'].unique())
            with c3: r_f = st.multiselect("Role", options=logs_df['Role'].unique())
            f_df = logs_df.copy()
            if u_f: f_df = f_df[f_df['MemberId'].isin(u_f)]
            if a_f: f_df = f_df[f_df['Agent'].isin(a_f)]
            if r_f: f_df = f_df[f_df['Role'].isin(r_f)]
            st.dataframe(f_df[['Timestamp', 'MemberId', 'Agent', 'Role', 'Content']], use_container_width=True, hide_index=True)
            st.download_button("📥 Export CSV", f_df.to_csv(index=False), "logs.csv", "text/csv")
        else: st.info("No logs found.")

# --- 9. LOGOUT ---
with main_nav[-1]:
    if st.button("Confirm Logout"):
        st.session_state.auth = {"logged_in": False}
        st.rerun()

