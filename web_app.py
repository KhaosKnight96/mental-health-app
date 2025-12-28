import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.graph_objects as go

# --- 1. SETTINGS & CSS ---
st.set_page_config(page_title="Health Bridge Pro", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    .glass-panel {
        background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(15px);
        border-radius: 20px; border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 20px; margin-bottom: 20px;
    }
    /* WhatsApp Bubble Styling */
    .chat-bubble { padding: 12px 18px; border-radius: 18px; margin-bottom: 10px; max-width: 80%; line-height: 1.5; font-family: sans-serif; }
    .user-bubble { background: #1E40AF; color: white; margin-left: auto; border-bottom-right-radius: 2px; }
    .ai-bubble { background: #334155; color: white; margin-right: auto; border-bottom-left-radius: 2px; }
    .avatar-pulse {
        width: 60px; height: 60px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
        font-size: 30px; margin: 0 auto 10px; background: linear-gradient(135deg, #38BDF8, #6366F1);
        box-shadow: 0 0 15px rgba(56, 189, 248, 0.4);
    }
</style>
""", unsafe_allow_html=True)

# --- 2. CORE LOGIC & CONNECTIONS ---
conn = st.connection("gsheets", type=GSheetsConnection)

if "auth" not in st.session_state: st.session_state.auth = {"in": False, "mid": None, "role": "user"}
if "cooper_logs" not in st.session_state: st.session_state.cooper_logs = []
if "clara_logs" not in st.session_state: st.session_state.clara_logs = []

def get_data(ws):
    try:
        df = conn.read(worksheet=ws, ttl=0)
        df.columns = [str(c).strip().lower() for c in df.columns]
        return df
    except: return pd.DataFrame()

def save_log(agent, role, content):
    try:
        new_row = pd.DataFrame([{
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "memberid": st.session_state.auth['mid'],
            "agent": agent, "role": role, "content": content
        }])
        conn.update(worksheet="ChatLogs", data=pd.concat([get_data("ChatLogs"), new_row], ignore_index=True))
    except: pass

def get_ai_response(agent, prompt, history):
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"].strip())
        if agent == "Cooper":
            sys = "You are Cooper, a warm, empathetic friend. Listen and support deeply."
        else:
            energy_data = get_data("Sheet1")
            user_data = energy_data[energy_data['memberid'] == st.session_state.auth['mid']].tail(5).to_string()
            sys = f"You are Clara, a logical data analyst. Analyze user energy: {user_data}"
        
        full_history = [{"role": "system", "content": sys}] + history[-5:] + [{"role": "user", "content": prompt}]
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=full_history)
        return res.choices[0].message.content
    except Exception as e: return f"AI Error: {e}"

# --- 3. LOGIN GATE ---
if not st.session_state.auth["in"]:
    st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge</h1>", unsafe_allow_html=True)
    with st.container(border=True):
        u = st.text_input("Member ID").strip().lower()
        p = st.text_input("Password", type="password")
        if st.button("Sign In", use_container_width=True):
            users = get_data("Users")
            m = users[(users['memberid'].astype(str).str.lower() == u) & (users['password'].astype(str) == p)]
            if not m.empty:
                st.session_state.auth.update({"in": True, "mid": u, "role": str(m.iloc[0]['role']).lower()})
                # Load persistent history
                all_logs = get_data("ChatLogs")
                if not all_logs.empty:
                    user_logs = all_logs[all_logs['memberid'].astype(str).str.lower() == u]
                    st.session_state.cooper_logs = [{"role": r.role, "content": r.content} for _,r in user_logs[user_logs.agent == "Cooper"].iterrows()]
                    st.session_state.clara_logs = [{"role": r.role, "content": r.content} for _,r in user_logs[user_logs.agent == "Clara"].iterrows()]
                st.rerun()
            else: st.error("Invalid Credentials")
    st.stop()

# --- 4. NAVIGATION ---
tabs = st.tabs(["🏠 Cooper", "🛋️ Clara", "🎮 Games", "🛡️ Admin", "🚪 Logout"])

# --- COOPER & CLARA (WHATSAPP STYLE) ---
for i, agent in enumerate(["Cooper", "Clara"]):
    with tabs[i]:
        st.markdown(f'<div class="avatar-pulse">{"🤝" if agent=="Cooper" else "📊"}</div>', unsafe_allow_html=True)
        logs = st.session_state.cooper_logs if agent == "Cooper" else st.session_state.clara_logs
        
        chat_box = st.container(height=450, border=False)
        with chat_box:
            for m in logs:
                div_class = "user-bubble" if m["role"] == "user" else "ai-bubble"
                st.markdown(f'<div class="chat-bubble {div_class}">{m["content"]}</div>', unsafe_allow_html=True)
        
        if p := st.chat_input(f"Speak with {agent}...", key=f"chat_{agent}"):
            logs.append({"role": "user", "content": p})
            save_log(agent, "user", p)
            with st.spinner("Thinking..."):
                res = get_ai_response(agent, p, logs)
            logs.append({"role": "assistant", "content": res})
            save_log(agent, "assistant", res)
            st.rerun()

# --- 5. IMMERSIVE GAMES (TOUCH & SCROLL-LOCKED) ---
with tabs[2]:
    game_mode = st.radio("Select Activity", ["Snake", "2048", "Memory Pattern", "Flash Match"], horizontal=True)
    
    # Unified Sound Library
    JS_LIBS = """
    const actx=new(window.AudioContext||window.webkitAudioContext)();
    function snd(f,t,d){const o=actx.createOscillator(),g=actx.createGain();o.type=t;o.frequency.value=f;g.gain.exponentialRampToValueAtTime(0.01,actx.currentTime+d);o.connect(g);g.connect(actx.destination);o.start();o.stop(actx.currentTime+d);}
    """
    
    if game_mode == "2048":
        st.components.v1.html(f"<script>{JS_LIBS}</script>" + """
        <div id="p2048" style="text-align:center; background:#1E293B; padding:20px; border-radius:20px; touch-action:none; font-family:sans-serif;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                <h2 style="color:#38BDF8; margin:0;">2048</h2>
                <div style="background:#0F172A; padding:5px 15px; border-radius:8px; color:white;">Score: <span id="s2048">0</span></div>
            </div>
            
            <div id="grid2048" style="display:grid; grid-template-columns:repeat(4,1fr); gap:10px; background:#0F172A; padding:10px; border-radius:10px; position:relative;">
                </div>
            
            <button id="start2048" onclick="init2048()" style="margin-top:15px; padding:10px 20px; background:#38BDF8; border:none; border-radius:8px; color:white; cursor:pointer; font-weight:bold;">New Game</button>
            <p style="color:#94A3B8; font-size:12px; margin-top:10px;">Swipe or use Arrows to slide tiles</p>
        </div>

        <script>
            let board, score, running=false;
            const grid = document.getElementById("grid2048");
            
            function init2048() {
                board = Array(16).fill(0);
                score = 0;
                running = true;
                addTile(); addTile();
                draw2048();
                document.getElementById("start2048").innerText = "Reset Game";
            }

            function addTile() {
                let empty = board.map((v, i) => v === 0 ? i : null).filter(v => v !== null);
                if (empty.length) board[empty[Math.floor(Math.random() * empty.length)]] = Math.random() < 0.9 ? 2 : 4;
            }

            function draw2048() {
                grid.innerHTML = "";
                board.forEach(v => {
                    const tile = document.createElement("div");
                    tile.style = `height:60px; display:flex; align-items:center; justify-content:center; border-radius:5px; font-weight:bold; font-size:20px; transition: all 0.1s; background:${getCol(v)}; color:${v>4?"#fff":"#0F172A"}`;
                    tile.innerText = v === 0 ? "" : v;
                    grid.appendChild(tile);
                });
                document.getElementById("s2048").innerText = score;
            }

            function getCol(v) {
                const colors = {0:"#334155", 2:"#eee4da", 4:"#ede0c8", 8:"#f2b179", 16:"#f59563", 32:"#f67c5f", 64:"#f65e3b", 128:"#edcf72", 256:"#edcc61", 512:"#edc850", 1024:"#edc53f", 2048:"#edc22e"};
                return colors[v] || "#3c3a32";
            }

            function slide(row) {
                let arr = row.filter(v => v);
                for (let i = 0; i < arr.length - 1; i++) {
                    if (arr[i] === arr[i+1]) { arr[i] *= 2; score += arr[i]; arr[i+1] = 0; snd(440, "sine", 0.05); }
                }
                arr = arr.filter(v => v);
                while (arr.length < 4) arr.push(0);
                return arr;
            }

            function move(dir) {
                if(!running) return;
                let prev = JSON.stringify(board);
                for (let i = 0; i < 4; i++) {
                    let row = [];
                    for (let j = 0; j < 4; j++) {
                        if (dir === "L" || dir === "R") row.push(board[i * 4 + j]);
                        else row.push(board[j * 4 + i]);
                    }
                    if (dir === "R" || dir === "D") row.reverse();
                    row = slide(row);
                    if (dir === "R" || dir === "D") row.reverse();
                    for (let j = 0; j < 4; j++) {
                        if (dir === "L" || dir === "R") board[i * 4 + j] = row[j];
                        else board[j * 4 + i] = row[j];
                    }
                }
                if (prev !== JSON.stringify(board)) { addTile(); draw2048(); if(isGameOver()) { running=false; alert("Game Over!"); } }
            }

            function isGameOver() { return !board.includes(0); }

            // Controls & Scroll-Lock
            window.addEventListener("keydown", e => {
                if(["ArrowUp","ArrowDown","ArrowLeft","ArrowRight"].includes(e.key)) { e.preventDefault(); }
                if(e.key=="ArrowLeft") move("L"); if(e.key=="ArrowRight") move("R");
                if(e.key=="ArrowUp") move("U"); if(e.key=="ArrowDown") move("D");
            });

            let tx, ty;
            grid.ontouchstart = e => { tx = e.touches[0].clientX; ty = e.touches[0].clientY; };
            grid.ontouchmove = e => e.preventDefault();
            grid.ontouchend = e => {
                let dx = e.changedTouches[0].clientX - tx, dy = e.changedTouches[0].clientY - ty;
                if (Math.abs(dx) > Math.abs(dy)) { move(dx > 0 ? "R" : "L"); }
                else { move(dy > 0 ? "D" : "U"); }
            };
            init2048(); // Initialize empty board
        </script>
        """, height=500)
    
    if game_mode == "Snake":
        st.components.v1.html(f"<script>{JS_LIBS}</script>" + """
<div id="p" style="text-align:center; background:#1E293B; padding:20px; border-radius:20px; touch-action:none; position:relative;">
    <canvas id="s" width="300" height="300" style="background:#0F172A; border:2px solid #38BDF8; border-radius:10px;"></canvas>
    <h2 id="sc" style="color:#38BDF8; margin:10px 0;">Score: 0</h2>
    
    <div id="ui-overlay">
        <button id="startBtn" onclick="initGame()" style="padding:10px 20px; font-size:18px; background:#38BDF8; border:none; border-radius:8px; color:white; cursor:pointer;">Start Game</button>
    </div>
    
    <div id="go" style="display:none; color:#F87171; position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); background:rgba(15,23,42,0.9); padding:20px; border-radius:15px; width:80%;">
        <h1>GAME OVER</h1>
        <button onclick="initGame()" style="padding:10px 20px; background:#F87171; border:none; border-radius:8px; color:white;">Try Again</button>
    </div>
</div>

<script>
    const c=document.getElementById("s"), x=c.getContext("2d"), b=15;
    let sn, f, d, g, s, running = false;

    // KEYBOARD: Prevent Scroll
    window.onkeydown = e => {
        if(["ArrowUp","ArrowDown","ArrowLeft","ArrowRight"].includes(e.key)) {
            e.preventDefault(); // STOPS SCREEN SCROLL
        }
        if(!running) return;
        if(e.key=="ArrowLeft"&&d!="R") d="L";
        if(e.key=="ArrowUp"&&d!="D") d="U";
        if(e.key=="ArrowRight"&&d!="L") d="R";
        if(e.key=="ArrowDown"&&d!="U") d="D";
    };

    // TOUCH: Prevent Scroll
    let tx, ty;
    c.ontouchstart = e => { 
        tx = e.touches[0].clientX; 
        ty = e.touches[0].clientY; 
    };
    c.ontouchmove = e => { e.preventDefault(); }; // STOPS SCROLL ON SWIPE
    c.ontouchend = e => {
        if(!running) return;
        let dx = e.changedTouches[0].clientX - tx, dy = e.changedTouches[0].clientY - ty;
        if(Math.abs(dx) > Math.abs(dy)){
            if(dx > 0 && d != "L") d = "R"; else if(dx < 0 && d != "R") d = "L";
        } else {
            if(dy > 0 && d != "U") d = "D"; else if(dy < 0 && d != "D") d = "U";
        }
    };

    function initGame(){
        sn = [{x:150,y:150}];
        f = {x:Math.floor(Math.random()*19)*b, y:Math.floor(Math.random()*19)*b};
        d = "R"; s = 0;
        running = true;
        document.getElementById("go").style.display = "none";
        document.getElementById("startBtn").style.display = "none";
        document.getElementById("sc").innerText = "Score: 0";
        clearInterval(g);
        g = setInterval(upd, 120);
    }

    function upd(){
        if(!running) return;
        x.fillStyle="#0F172A"; x.fillRect(0,0,300,300);
        x.fillStyle="#F87171"; x.fillRect(f.x,f.y,b,b);
        sn.forEach((p,i)=>{ x.fillStyle=i==0?"#38BDF8":"#334155"; x.fillRect(p.x,p.y,b,b); });
        
        let h={...sn[0]}; 
        if(d=="L")h.x-=b; if(d=="U")h.y-=b; if(d=="R")h.x+=b; if(d=="D")h.y+=b;
        
        if(h.x==f.x && h.y==f.y){
            s++; snd(600,"sine",0.1);
            f={x:Math.floor(Math.random()*19)*b, y:Math.floor(Math.random()*19)*b};
        } else { sn.pop(); }
        
        if(h.x<0||h.x>=300||h.y<0||h.y>=300||sn.some(z=>z.x==h.x&&z.y==h.y)){
            running = false;
            clearInterval(g);
            snd(100,"sawtooth",0.5);
            document.getElementById("go").style.display = "block";
        }
        if(running) sn.unshift(h);
        document.getElementById("sc").innerText = "Score: " + s;
    }
</script>
""", height=520)
    elif game_mode == "Memory Pattern":
        st.components.v1.html(f"<script>{JS_LIBS}</script>" + """
        <div style="text-align:center; background:#1E293B; padding:20px; border-radius:20px;">
            <div id="board" style="display:grid; grid-template-columns:repeat(2,100px); gap:10px; justify-content:center;">
                <div onclick="p(0)" id="b0" style="height:100px; background:#ef4444; opacity:0.6; border-radius:10px;"></div>
                <div onclick="p(1)" id="b1" style="height:100px; background:#3b82f6; opacity:0.6; border-radius:10px;"></div>
                <div onclick="p(2)" id="b2" style="height:100px; background:#22c55e; opacity:0.6; border-radius:10px;"></div>
                <div onclick="p(3)" id="b3" style="height:100px; background:#eab308; opacity:0.6; border-radius:10px;"></div>
            </div>
            <h3 id="lvl" style="color:#38BDF8;">Level: 1</h3>
            <button onclick="start()">Start Game</button>
        </div>
        <script>
            let seq=[], user=[], lv=1, wait=true;
            const f=[261,329,392,523];
            function start(){ seq=[]; next(); }
            function next(){ user=[]; wait=true; seq.push(Math.floor(Math.random()*4)); show(); }
            async function show(){
                for(let i of seq){ await new Promise(r=>setTimeout(r,600)); flash(i); }
                wait=false;
            }
            function flash(i){ snd(f[i],"triangle",0.3); document.getElementById("b"+i).style.opacity="1"; setTimeout(()=>document.getElementById("b"+i).style.opacity="0.6",300); }
            function p(i){ if(wait)return; flash(i); user.push(i); if(user[user.length-1]!==seq[user.length-1]){ alert("Game Over!"); lv=1; start(); } else if(user.length===seq.length){ lv++; document.getElementById("lvl").innerText="Level: "+lv; setTimeout(next,800); } }
        </script>""", height=400)

    elif game_mode == "Flash Match":
        st.components.v1.html(f"<script>{JS_LIBS}</script>" + """
        <div style="text-align:center; background:#1E293B; padding:20px; border-radius:20px;">
            <div id="mgrid" style="display:grid; grid-template-columns:repeat(4,1fr); gap:10px;"></div>
            <h3 id="mlvl" style="color:#38BDF8;">Matches: 0</h3>
        </div>
        <script>
            let pairs=2, matched=0, flip=[];
            const icons=['🍎','🚀','💎','🌟','🔥','🌈','🍕','⚽'];
            function init(){
                matched=0; flip=[]; const grid=document.getElementById("mgrid"); grid.innerHTML="";
                let deck=[...icons.slice(0,pairs), ...icons.slice(0,pairs)].sort(()=>Math.random()-0.5);
                deck.forEach(icon=>{
                    const c=document.createElement("div"); c.style="height:60px; background:#334155; border-radius:8px; display:flex; align-items:center; justify-content:center; font-size:24px; cursor:pointer";
                    c.onclick=()=>{
                        if(flip.length<2 && !c.innerText){
                            c.innerText=icon; c.style.background="#38BDF8"; snd(400,"sine",0.1); flip.push({c,icon});
                            if(flip.length==2){
                                if(flip[0].icon==flip[1].icon){ matched++; flip=[]; if(matched==pairs){ pairs++; if(pairs>8)pairs=2; setTimeout(init,1000); } }
                                else{ setTimeout(()=>{ flip.forEach(f=>{f.c.innerText=""; f.c.style.background="#334155"}); flip=[]; },500); }
                            }
                        }
                    }; grid.appendChild(c);
                });
            } init();
        </script>""", height=400)

# --- 6. ADMIN (FIXED FOR DATETIME ERRORS) ---
with tabs[3]:
    if st.session_state.auth["role"] == "admin":
        st.subheader("🛡️ Admin Control Center")
        
        # Load Data
        logs_df = get_data("ChatLogs")
        
        if not logs_df.empty:
            # Persistent search bar
            search_query = st.text_input("🔍 Search conversation content...", placeholder="Type to filter logs...")

            # Filter Controls Row
            col1, col2, col3, col4 = st.columns([1.5, 1, 1, 1])
            
            with col1:
                # "Filter By" Sort Order
                sort_order = st.selectbox("📅 Sort By", ["Most Recent", "Oldest First"])
            
            with col2:
                # Filter by User
                user_list = ["All Users"] + sorted(logs_df['memberid'].unique().tolist())
                selected_user = st.selectbox("👤 User", user_list)
            
            with col3:
                # Filter by Agent
                agent_list = ["All Agents"] + sorted(logs_df['agent'].unique().tolist())
                selected_agent = st.selectbox("🤖 Agent", agent_list)
            
            with col4:
                # Extra Filter: By Role
                role_list = ["All Roles", "user", "assistant"]
                selected_role = st.selectbox("💬 Role", role_list)

            # --- Data Processing Logic ---
            f_df = logs_df.copy()

            # THE FIX: Handle mixed date formats (seconds vs no seconds)
            f_df['timestamp'] = pd.to_datetime(f_df['timestamp'], errors='coerce', format='mixed')

            # 1. Search Filter
            if search_query:
                f_df = f_df[f_df['content'].str.contains(search_query, case=False, na=False)]
            
            # 2. User Filter
            if selected_user != "All Users":
                f_df = f_df[f_df['memberid'] == selected_user]
            
            # 3. Agent Filter
            if selected_agent != "All Agents":
                f_df = f_df[f_df['agent'] == selected_agent]
            
            # 4. Role Filter
            if selected_role != "All Roles":
                f_df = f_df[f_df['role'] == selected_role]

            # 5. Sorting Logic
            if sort_order == "Most Recent":
                f_df = f_df.sort_values(by='timestamp', ascending=False)
            else:
                f_df = f_df.sort_values(by='timestamp', ascending=True)

            # Display Results
            st.write(f"Showing **{len(f_df)}** entries:")
            st.dataframe(
                f_df, 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "timestamp": st.column_config.DatetimeColumn("Time", format="D MMM, h:mm a"),
                    "content": st.column_config.TextColumn("Message Content", width="large")
                }
            )
            
            # Download Button
            csv = f_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Export CSV", data=csv, file_name="health_bridge_logs.csv", mime="text/csv")
            
    else:
        st.warning("⛔ Access Denied. Admin privileges required.")
# --- 7. LOGOUT ---
with tabs[4]:
    if st.button("Confirm Logout"):
        st.session_state.clear()
        st.rerun()




