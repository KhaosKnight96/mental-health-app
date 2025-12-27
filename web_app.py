import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.graph_objects as go

# --- 1. CONFIG ---
st.set_page_config(page_title="Health Bridge", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    .portal-card { background: #1E293B; padding: 25px; border-radius: 20px; border: 1px solid #334155; margin-bottom: 20px; }
    .stButton>button { border-radius: 12px; font-weight: 600; height: 3.5em; width: 100%; border: none; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    .stTabs [data-baseweb="tab-list"] { gap: 20px; }
    .stTabs [data-baseweb="tab"] { 
        background-color: #1E293B; border-radius: 10px; padding: 10px 20px; color: white; border: 1px solid #334155;
    }
    .stTabs [aria-selected="true"] { background-color: #38BDF8 !important; border: 1px solid #38BDF8 !important; }
</style>
""", unsafe_allow_html=True)

# --- 2. CONNECTIONS ---
conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None, "name": None}
if "cooper_logs" not in st.session_state: st.session_state.cooper_logs = []
if "clara_logs" not in st.session_state: st.session_state.clara_logs = []

def get_data(worksheet_name="Users"):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except: return pd.DataFrame()

def save_high_score(game_name, score):
    try:
        df_hs = get_data("HighScores")
        cid = st.session_state.auth['cid']
        # Check if record exists
        idx = (df_hs['CoupleID'].astype(str) == str(cid)) & (df_hs['Game'] == game_name)
        if not df_hs[idx].empty:
            if score > int(df_hs.loc[idx, 'Score'].values[0]):
                df_hs.loc[idx, 'Score'] = score
                conn.update(worksheet="HighScores", data=df_hs)
        else:
            new_score = pd.DataFrame([{"CoupleID": cid, "Game": game_name, "Score": score}])
            conn.update(worksheet="HighScores", data=pd.concat([df_hs, new_score], ignore_index=True))
    except: pass

# --- 3. LOGIN / SIGNUP ---
if not st.session_state.auth["logged_in"]:
    st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge Portal</h1>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["🔐 Login", "📝 Sign Up"])
    with t1:
        u = st.text_input("Couple ID", key="l_u")
        p = st.text_input("Password", type="password", key="l_p")
        if st.button("Sign In"):
            df = get_data("Users")
            m = df[(df['Username'].astype(str) == u) & (df['Password'].astype(str) == p)]
            if not m.empty:
                st.session_state.auth.update({"logged_in": True, "cid": u, "name": m.iloc[0]['Fullname']})
                st.rerun()
            else: st.error("Invalid Credentials")
    with t2:
        n = st.text_input("Full Name")
        c = st.text_input("Couple ID")
        pw = st.text_input("Password", type="password")
        if st.button("Register"):
            df = get_data("Users")
            new_user = pd.DataFrame([{"Fullname": n, "Username": c, "Password": pw}])
            conn.update(worksheet="Users", data=pd.concat([df, new_user], ignore_index=True))
            st.success("Account created!")
    st.stop()

# --- 4. NAVIGATION ---
st.markdown(f"### Welcome, {st.session_state.auth['name']} ✨")
main_nav = st.tabs(["🏠 Dashboard", "📊 Caregiver Insights", "🎮 Games", "🚪 Logout"])

# --- 5. DASHBOARD TAB ---
with main_nav[0]:
    col1, col2 = st.columns([1, 1.5])
    with col1:
        st.markdown('<div class="portal-card"><h3>⚡ Energy</h3>', unsafe_allow_html=True)
        ev = st.slider("Energy", 1, 11, 6)
        st.markdown(f"<h1 style='text-align:center; font-size:60px;'>{ {1:'🚨', 2:'🪫', 3:'😫', 4:'🥱', 5:'🙁', 6:'😐', 7:'🙂', 8:'😊', 9:'⚡', 10:'🚀', 11:'☀️'}[ev] }</h1>", unsafe_allow_html=True)
        if st.button("💾 Sync"):
            new_row = pd.DataFrame([{"Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), "CoupleID": st.session_state.auth['cid'], "EnergyLog": ev}])
            conn.update(worksheet="Sheet1", data=pd.concat([conn.read(worksheet="Sheet1", ttl=0), new_row], ignore_index=True))
            st.success("Logged!")
        st.markdown('</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="portal-card"><h3>💬 Cooper</h3>', unsafe_allow_html=True)
        for m in st.session_state.cooper_logs:
            with st.chat_message(m["role"]): st.write(m["content"])
        if p := st.chat_input("Chat with Cooper...", key="coop_in"):
            st.session_state.cooper_logs.append({"role": "user", "content": p})
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":"Cooper, a kind friend."}]+st.session_state.cooper_logs[-5:]).choices[0].message.content
            st.session_state.cooper_logs.append({"role": "assistant", "content": res})
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- 6. CAREGIVER TAB ---
with main_nav[1]:
    try:
        df_l = conn.read(worksheet="Sheet1", ttl=0)
        df_p = df_l[df_l['CoupleID'].astype(str) == str(st.session_state.auth['cid'])].copy()
        df_p['Timestamp'] = pd.to_datetime(df_p['Timestamp'])
        df_p = df_p.sort_values('Timestamp')

        if not df_p.empty:
            st.markdown('<div class="portal-card"><h3>📉 Energy Analytics</h3>', unsafe_allow_html=True)
            fig = go.Figure()
            fig.add_shape(type="line", x0=df_p['Timestamp'].min(), y0=6, x1=df_p['Timestamp'].max(), y1=6, line=dict(color="White", width=2, dash="dash"))
            fig.add_trace(go.Scatter(x=df_p['Timestamp'], y=df_p['EnergyLog'], mode='lines+markers', line=dict(color='#38BDF8', width=3), name='Energy', fill='tozeroy', fillcolor='rgba(248, 113, 113, 0.2)'))
            fig.add_trace(go.Scatter(x=df_p['Timestamp'], y=[max(6, y) for y in df_p['EnergyLog']], mode='lines', line=dict(width=0), fill='tonexty', fillcolor='rgba(74, 222, 128, 0.3)', showlegend=False))
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="white"), yaxis=dict(range=[1, 11], gridcolor="#334155"), xaxis=dict(showgrid=False))
            st.plotly_chart(fig, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
    except: st.info("No data yet.")
    
    st.markdown('<div class="portal-card"><h3>🤖 Clara Analyst</h3>', unsafe_allow_html=True)
    for m in st.session_state.clara_logs:
        with st.chat_message(m["role"]): st.write(m["content"])
    if p := st.chat_input("Ask Clara...", key="clar_in"):
        st.session_state.clara_logs.append({"role": "user", "content": p})
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":"Analyst Clara."}]+st.session_state.clara_logs[-5:]).choices[0].message.content
        st.session_state.clara_logs.append({"role": "assistant", "content": res})
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# --- 7. GAMES TAB ---
with main_nav[2]:
    gt = st.radio("Choose Game", ["Modern Snake", "Memory Match"], horizontal=True)
    
    # Fetch Best Score
    try:
        hs_df = get_data("HighScores")
        best = hs_df[(hs_df['CoupleID'].astype(str) == st.session_state.auth['cid']) & (hs_df['Game'] == gt)]['Score'].max()
        st.subheader(f"🏆 Personal Best: {best if pd.notna(best) else 0}")
    except: pass

    if gt == "Modern Snake":
        # Snake logic includes a call to Python to save score on game over via a hidden button or simple check
        # For simplicity in this demo, the JS handles the game and you can use st.query_params to send score back
        SNAKE_HTML = """
        <script src="https://cdnjs.cloudflare.com/ajax/libs/hammer.js/2.0.8/hammer.min.js"></script>
        <div style="display:flex; flex-direction:column; align-items:center; background:#1E293B; padding:20px; border-radius:15px; touch-action:none;">
            <canvas id="s" width="300" height="300" style="border:4px solid #38BDF8; background:#0F172A; border-radius:10px;"></canvas>
            <h2 id="st" style="color:#38BDF8; font-family:sans-serif;">Score: 0</h2>
            <button onclick="location.reload()" style="width:100%; padding:15px; background:#38BDF8; color:white; border:none; border-radius:10px; font-weight:bold;">🔄 Restart</button>
        </div>
        <script>
        const canvas=document.getElementById("s"), ctx=canvas.getContext("2d"), box=15;
        let score=0, d, snake=[{x:10*box, y:10*box}], food={x:Math.floor(Math.random()*19)*box, y:Math.floor(Math.random()*19)*box};
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        function playSound(f, t, d) { const o=audioCtx.createOscillator(); const g=audioCtx.createGain(); o.type=t; o.frequency.setValueAtTime(f, audioCtx.currentTime); g.gain.setValueAtTime(0.1, audioCtx.currentTime); o.connect(g); g.connect(audioCtx.destination); o.start(); o.stop(audioCtx.currentTime+d); }
        window.addEventListener("keydown", e => { if(["ArrowUp","ArrowDown","ArrowLeft","ArrowRight"].includes(e.code)) e.preventDefault(); if(e.code=="ArrowLeft" && d!="RIGHT") d="LEFT"; if(e.code=="ArrowUp" && d!="DOWN") d="UP"; if(e.code=="ArrowRight" && d!="LEFT") d="RIGHT"; if(e.code=="ArrowDown" && d!="UP") d="DOWN"; });
        function draw() {
            ctx.fillStyle="#0F172A"; ctx.fillRect(0,0,300,300);
            ctx.fillStyle = "#F87171"; ctx.beginPath(); ctx.arc(food.x+box/2, food.y+box/2, box/3, 0, Math.PI*2); ctx.fill();
            snake.forEach((p,i)=>{ ctx.fillStyle= i==0 ? "#38BDF8" : "rgba(56, 189, 248, "+(1-i/snake.length)+")"; ctx.beginPath(); ctx.roundRect(p.x, p.y, box-1, box-1, 4); ctx.fill(); });
            let hX=snake[0].x, hY=snake[0].y;
            if(d=="LEFT") hX-=box; if(d=="UP") hY-=box; if(d=="RIGHT") hX+=box; if(d=="DOWN") hY+=box;
            if(hX==food.x && hY==food.y){ score++; document.getElementById("st").innerText="Score: "+score; playSound(600, 'sine', 0.1); food={x:Math.floor(Math.random()*19)*box, y:Math.floor(Math.random()*19)*box}; } else if(d) snake.pop();
            let h={x:hX, y:hY};
            if(hX<0||hX>=300||hY<0||hY>=300||(d && snake.some(z=>z.x==h.x&&z.y==h.y))){
                playSound(150, 'sawtooth', 0.5); ctx.fillStyle="white"; ctx.font="bold 24px Arial"; ctx.textAlign="center"; ctx.fillText("GAME OVER", 150, 150); clearInterval(game);
                window.parent.postMessage({type: 'score_update', game: 'Modern Snake', score: score}, '*');
            }
            if(d) snake.unshift(h);
        }
        let game = setInterval(draw, 100);
        </script>
        """
        st.components.v1.html(SNAKE_HTML, height=520)
    else:
        MEMORY_HTML = """
        <div class="grid" id="g"></div>
        <button onclick="location.reload()" style="width:100%; max-width:320px; display:block; margin:20px auto; padding:15px; background:#38BDF8; color:white; border:none; border-radius:10px; font-weight:bold;">🔄 New Game</button>
        <style> .grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; max-width: 320px; margin: auto; } .card { height: 75px; position: relative; transform-style: preserve-3d; transition: transform 0.5s; cursor: pointer; } .card.flipped { transform: rotateY(180deg); } .face { position: absolute; width: 100%; height: 100%; backface-visibility: hidden; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 25px; border: 2px solid #334155; } .front { background: #1E293B; border-color: #38BDF8; } .back { background: #334155; transform: rotateY(180deg); color: white; } </style>
        <script>
            const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            function playSound(f, t, d) { const o=audioCtx.createOscillator(); const g=audioCtx.createGain(); o.type=t; o.frequency.setValueAtTime(f, audioCtx.currentTime); g.gain.setValueAtTime(0.1, audioCtx.currentTime); o.connect(g); g.connect(audioCtx.destination); o.start(); o.stop(audioCtx.currentTime+d); }
            const icons = ['🍎','🍎','💎','💎','🌟','🌟','🚀','🚀','🌈','🌈','🔥','🔥','🍀','🍀','🎁','🎁'];
            let shuffled = icons.sort(() => 0.5 - Math.random());
            let flipped = [], lock = false, matches = 0;
            const board = document.getElementById('g');
            shuffled.forEach(icon => {
                const card = document.createElement('div'); card.className = 'card';
                card.innerHTML = `<div class="face front"></div><div class="face back">${icon}</div>`;
                card.dataset.icon = icon;
                card.onclick = function() {
                    if(lock || this.classList.contains('flipped')) return;
                    playSound(440, 'sine', 0.1); this.classList.add('flipped'); flipped.push(this);
                    if(flipped.length === 2) {
                        lock = true;
                        if(flipped[0].dataset.icon === flipped[1].dataset.icon) {
                            matches++; playSound(880, 'sine', 0.2); flipped = []; lock = false;
                            if(matches === 8) window.parent.postMessage({type: 'score_update', game: 'Memory Match', score: 100}, '*');
                        } else { setTimeout(() => { playSound(200, 'sine', 0.2); flipped.forEach(c => c.classList.remove('flipped')); flipped = []; lock = false; }, 800); }
                    }
                }; board.appendChild(card);
            });
        </script>
        """
        st.components.v1.html(MEMORY_HTML, height=500)

# --- 8. LOGOUT TAB ---
with main_nav[3]:
    if st.button("Confirm Logout"):
        st.session_state.auth = {"logged_in": False, "cid": None, "name": None}
        st.rerun()
