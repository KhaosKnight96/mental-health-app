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
    
    /* Immersive Glass UI Panels */
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
    st.session_state.auth = {"logged_in": False, "cid": None, "name": None}
if "cooper_logs" not in st.session_state: st.session_state.cooper_logs = []
if "clara_logs" not in st.session_state: st.session_state.clara_logs = []

def get_data(worksheet_name):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except:
        if worksheet_name == "ChatLogs":
            return pd.DataFrame(columns=["Timestamp", "CoupleID", "Agent", "Role", "Content"])
        return pd.DataFrame()

def save_chat_to_sheets(agent, role, content):
    new_entry = pd.DataFrame([{
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "CoupleID": st.session_state.auth['cid'],
        "Agent": agent,
        "Role": role,
        "Content": content
    }])
    existing_df = get_data("ChatLogs")
    updated_df = pd.concat([existing_df, new_entry], ignore_index=True)
    conn.update(worksheet="ChatLogs", data=updated_df)

# --- 3. LOGIN GATE ---
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
                
                # Load History from Sheets
                all_chats = get_data("ChatLogs")
                if not all_chats.empty:
                    user_chats = all_chats[all_chats['CoupleID'].astype(str) == str(u)]
                    
                    cooper_data = user_chats[user_chats['Agent'] == "Cooper"]
                    st.session_state.cooper_logs = [
                        {"role": row["Role"], "content": row["Content"]} 
                        for _, row in cooper_data.iterrows()
                    ]
                    
                    clara_data = user_chats[user_chats['Agent'] == "Clara"]
                    st.session_state.clara_logs = [
                        {"role": row["Role"], "content": row["Content"]} 
                        for _, row in clara_data.iterrows()
                    ]
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
st.markdown(f"### Hello, {st.session_state.auth['name']} ✨")
main_nav = st.tabs(["🏠 Cooper's Corner", "🛋️ Clara's Couch", "🎮 Games", "🚪 Logout"])

# --- 5. COOPER'S CORNER ---
with main_nav[0]:
    col1, col2 = st.columns([1, 1.3])
    with col1:
        st.markdown('<div class="portal-card"><h3>⚡ Energy Status</h3>', unsafe_allow_html=True)
        ev = st.slider("Energy Level", 1, 11, 6)
        emoji_map = {1:'🚨', 2:'🪫', 3:'😫', 4:'🥱', 5:'🙁', 6:'😐', 7:'🙂', 8:'😊', 9:'⚡', 10:'🚀', 11:'☀️'}
        st.markdown(f"<h1 style='text-align:center; font-size:80px;'>{emoji_map[ev]}</h1>", unsafe_allow_html=True)
        if st.button("💾 Sync Data"):
            new_row = pd.DataFrame([{"Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), "CoupleID": st.session_state.auth['cid'], "EnergyLog": ev}])
            conn.update(worksheet="Sheet1", data=pd.concat([get_data("Sheet1"), new_row], ignore_index=True))
            st.success("Logged!")
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
            <div class="glass-panel">
                <div class="avatar-pulse" style="background: linear-gradient(135deg, #38BDF8, #6366F1);">👤</div>
                <h3 style='text-align:center; color:#38BDF8; margin-bottom:0;'>Cooper's Corner</h3>
                <p style='text-align:center; color:#94A3B8; font-size:14px;'>A human companion for reflection</p>
            </div>
        """, unsafe_allow_html=True)
        
        chat_box = st.container(height=380, border=False)
        with chat_box:
            for m in st.session_state.cooper_logs:
                with st.chat_message(m["role"], avatar="👤"): st.write(m["content"])
        
        if p := st.chat_input("Speak with Cooper..."):
            st.session_state.cooper_logs.append({"role": "user", "content": p})
            save_chat_to_sheets("Cooper", "user", p)
            
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":"You are Cooper, a wise and warm human companion. You are empathetic, calm, and professional."}]+st.session_state.cooper_logs[-5:]).choices[0].message.content
            
            st.session_state.cooper_logs.append({"role": "assistant", "content": res})
            save_chat_to_sheets("Cooper", "assistant", res)
            st.rerun()

# --- 6. CLARA'S COUCH ---
with main_nav[1]:
    st.markdown(f"""
        <div class="glass-panel">
            <div class="avatar-pulse" style="background: linear-gradient(135deg, #F472B6, #FB7185);">🧘‍♀️</div>
            <h3 style='text-align:center; color:#F472B6; margin-bottom:0;'>Clara's Couch</h3>
            <p style='text-align:center; color:#94A3B8; font-size:14px;'>Weekly Insights & Clinical Trends</p>
        </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns([1.5, 1])
    with c1:
        try:
            df_l = get_data("Sheet1")
            df_p = df_l[df_l['CoupleID'].astype(str) == str(st.session_state.auth['cid'])].copy()
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
                    insight = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role":"system","content":"You are Clara, a clinical analyst. Summarize the following energy levels into a 3-sentence professional insight."},
                                  {"role":"user","content": f"Data: {data_summary}"}]
                    ).choices[0].message.content
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
    st.markdown('<div class="portal-card">', unsafe_allow_html=True)
    gt = st.radio("Select Activity", ["Modern Snake", "Memory Match", "2048 Logic"], horizontal=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Sound Logic shared across games
    JS_SOUNDS = """
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    function playSound(freq, type, duration, vol=0.1) {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = type; osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
        gain.gain.setValueAtTime(vol, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + duration);
        osc.connect(gain); gain.connect(audioCtx.destination);
        osc.start(); osc.stop(audioCtx.currentTime + duration);
    }
    """

    if gt == "Modern Snake":
        SNAKE_HTML = f"""
        <div style="display:flex; flex-direction:column; align-items:center; background:#1E293B; padding:20px; border-radius:15px;">
            <canvas id="s" width="300" height="300" style="border:4px solid #38BDF8; background:#0F172A; border-radius:10px;"></canvas>
            <h2 id="st" style="color:#38BDF8; font-family:sans-serif;">Score: 0</h2>
        </div>
        <script>
        {JS_SOUNDS}
        const canvas=document.getElementById("s"), ctx=canvas.getContext("2d"), box=15;
        let score=0, d, snake=[{{x:10*box, y:10*box}}], food={{x:Math.floor(Math.random()*19)*box, y:Math.floor(Math.random()*19)*box}};
        
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
                playSound(600, 'sine', 0.1); // Success Beep
                food={{x:Math.floor(Math.random()*19)*box, y:Math.floor(Math.random()*19)*box}};
            }} else if(d) snake.pop();

            let h={{x:hX, y:hY}};
            if(hX<0||hX>=300||hY<0||hY>=300||(d && snake.some(z=>z.x==h.x&&z.y==h.y))){{
                playSound(150, 'sawtooth', 0.5); // Game Over Buzz
                clearInterval(game); alert("Game Over! Score: " + score);
            }}
            if(d) snake.unshift(h);
        }}
        let game = setInterval(draw, 100);
        </script>
        """
        st.components.v1.html(SNAKE_HTML, height=480)

    elif gt == "Memory Match":
        MEMORY_HTML = f"""
        <style>
            .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; max-width: 320px; margin: auto; }}
            .card {{ height: 75px; position: relative; transform-style: preserve-3d; transition: transform 0.5s; cursor: pointer; }}
            .card.flipped {{ transform: rotateY(180deg); }}
            .face {{ position: absolute; width: 100%; height: 100%; backface-visibility: hidden; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 25px; border: 2px solid #334155; }}
            .front {{ background: #1E293B; border-color: #38BDF8; }}
            .back {{ background: #334155; transform: rotateY(180deg); color: white; }}
        </style>
        <div class="grid" id="g"></div>
        <script>
            {JS_SOUNDS}
            const icons = ['🍎','🍎','💎','💎','🌟','🌟','🚀','🚀','🌈','🌈','🔥','🔥','🍀','🍀','🎁','🎁'];
            let shuffled = icons.sort(() => 0.5 - Math.random());
            let flipped = [], lock = false, matches = 0;
            const board = document.getElementById('g');
            shuffled.forEach(icon => {{
                const card = document.createElement('div'); card.className = 'card';
                card.innerHTML = `<div class="face front"></div><div class="face back">${{icon}}</div>`;
                card.dataset.icon = icon;
                card.onclick = function() {{
                    if(lock || this.classList.contains('flipped')) return;
                    playSound(440, 'sine', 0.05); // Flip Click
                    this.classList.add('flipped'); flipped.push(this);
                    if(flipped.length === 2) {{
                        lock = true;
                        if(flipped[0].dataset.icon === flipped[1].dataset.icon) {{
                            matches++; flipped = []; lock = false;
                            setTimeout(() => playSound(880, 'sine', 0.2), 200); // Match Chime
                            if(matches === 8) alert("Match Complete!");
                        }} else {{
                            setTimeout(() => {{ 
                                playSound(220, 'sine', 0.2); // Error Thud
                                flipped.forEach(c => c.classList.remove('flipped')); 
                                flipped = []; lock = false; 
                            }}, 800);
                        }}
                    }}
                }}; board.appendChild(card);
            }});
        </script>
        """
        st.components.v1.html(MEMORY_HTML, height=450)

    elif gt == "2048 Logic":
        T2048_HTML = f"""
        <div style="display:flex; flex-direction:column; align-items:center; background:#1E293B; padding:20px; border-radius:15px; font-family:sans-serif;">
            <div id="grid" style="display:grid; grid-template-columns:repeat(4, 60px); grid-gap:10px; background:#0F172A; padding:10px; border-radius:10px;"></div>
            <h2 id="sc" style="color:#38BDF8; margin-top:15px;">Score: 0</h2>
        </div>
        <script>
            {JS_SOUNDS}
            const gridDisp = document.getElementById('grid');
            let board = Array(16).fill(0), score = 0;

            function init() {{
                addTile(); addTile(); render();
            }}

            function addTile() {{
                let empty = board.map((v, i) => v === 0 ? i : null).filter(v => v !== null);
                if (empty.length) board[empty[Math.floor(Math.random()*empty.length)]] = Math.random() < 0.9 ? 2 : 4;
            }}

            function render() {{
                gridDisp.innerHTML = '';
                board.forEach(v => {{
                    const tile = document.createElement('div');
                    tile.style = `width:60px; height:60px; background:${{v? '#38BDF8' : '#334155'}}; color:white; display:flex; align-items:center; justify-content:center; border-radius:5px; font-weight:bold; font-size:20px;`;
                    tile.innerText = v || '';
                    gridDisp.appendChild(tile);
                }});
                document.getElementById('sc').innerText = "Score: " + score;
            }}

            window.addEventListener('keydown', e => {{
                if(!["ArrowUp","ArrowDown","ArrowLeft","ArrowRight
# --- 8. LOGOUT ---
with main_nav[3]:
    if st.button("Confirm Logout"):
        st.session_state.auth = {"logged_in": False}
        st.rerun()


