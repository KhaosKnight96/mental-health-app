import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime

# --- 1. CONFIG & MOBILE OPTIMIZATION ---
st.set_page_config(page_title="Health Bridge", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    [data-testid="stSidebar"] { background-color: #1E293B; border-right: 1px solid #334155; }
    .portal-card { background: #1E293B; padding: 25px; border-radius: 20px; border: 1px solid #334155; margin-bottom: 20px; }
    .stButton>button { border-radius: 12px; font-weight: 600; height: 3.5em; width: 100%; border: none; }
    .stSlider [data-baseweb="slider"] div { background-color: #38BDF8; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
</style>
<head>
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
</head>
""", unsafe_allow_html=True)

# --- 2. CONNECTIONS ---
conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None, "name": None}
if "cooper_logs" not in st.session_state: st.session_state.cooper_logs = []
if "clara_logs" not in st.session_state: st.session_state.clara_logs = []

def get_data(worksheet_name="Users"):
    df = conn.read(worksheet=worksheet_name, ttl=0)
    df.columns = [str(c).strip() for c in df.columns]
    return df

# --- 3. LOGIN GATE ---
if not st.session_state.auth["logged_in"]:
    st.markdown("<h1 style='text-align:center; margin-top:50px;'>🧠 Health Bridge</h1>", unsafe_allow_html=True)
    with st.container():
        _, login_col, _ = st.columns([1, 2, 1])
        with login_col:
            u = st.text_input("Couple ID")
            p = st.text_input("Password", type="password")
            if st.button("Sign In", type="primary"):
                df = get_data("Users")
                m = df[(df['Username'].astype(str) == u) & (df['Password'].astype(str) == p)]
                if not m.empty:
                    st.session_state.auth.update({"logged_in": True, "cid": u, "name": m.iloc[0]['Fullname']})
                    st.rerun()
                else: st.error("Access Denied.")
    st.stop()

# --- 4. NAVIGATION ---
with st.sidebar:
    st.title("🌉 Menu")
    nav = st.selectbox("Navigation", ["Dashboard", "Caregiver Insights", "Games"])
    st.divider()
    if st.button("Logout"):
        st.session_state.auth = {"logged_in": False, "cid": None}
        st.rerun()

# --- 5. DASHBOARD (COOPER + 11-POINT ENERGY SCALE) ---
if nav == "Dashboard":
    st.title(f"Hi {st.session_state.auth['name']}! 👋")
    col_vibe, col_chat = st.columns([1, 1.5])
    
    with col_vibe:
        st.markdown('<div class="portal-card"><h3>⚡ Energy Status</h3>', unsafe_allow_html=True)
        # 11-point system (1 to 11)
        energy_val = st.slider("Energy Scale (1=Worst, 6=Neutral, 11=Best)", 1, 11, 6)
        
        energy_emojis = {
            1: "🚨", 2: "🪫", 3: "😫", 4: "🥱", 5: "🙁", 
            6: "😐", 
            7: "🙂", 8: "😊", 9: "⚡", 10: "🚀", 11: "☀️"
        }
        current_emoji = energy_emojis.get(energy_val, "😐")
        
        st.markdown(f"<h1 style='text-align:center; font-size:80px; margin: 10px 0;'>{current_emoji}</h1>", unsafe_allow_html=True)
        status_text = "Neutral" if energy_val == 6 else ("Optimal" if energy_val > 6 else "Low")
        st.markdown(f"<p style='text-align:center; color:#38BDF8; font-weight:bold;'>Level {energy_val}: {status_text}</p>", unsafe_allow_html=True)
        
        if st.button("💾 Sync Energy"):
            try:
                # 1. Prepare data with exact header "EnergyLog"
                new_row = pd.DataFrame([{
                    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), 
                    "CoupleID": st.session_state.auth['cid'], 
                    "EnergyLog": energy_val, 
                    "Emoji": current_emoji
                }])
                
                # 2. Read from "Sheet1"
                existing_data = conn.read(worksheet="Sheet1", ttl=0)
                existing_data.columns = [str(c).strip() for c in existing_data.columns]
                
                # 3. Append and Update "Sheet1"
                updated_data = pd.concat([existing_data, new_row], ignore_index=True)
                conn.update(worksheet="Sheet1", data=updated_data)
                
                st.success("Energy synced to Sheet1!")
                st.balloons()
            except Exception as e:
                st.error(f"Sync Error: Ensure 'Sheet1' has a header named 'EnergyLog'. ({e})")
        st.markdown('</div>', unsafe_allow_html=True)

    with col_chat:
        st.markdown('<div class="portal-card"><h3>💬 Chat with Cooper</h3>', unsafe_allow_html=True)
        container = st.container(height=350)
        for m in st.session_state.cooper_logs:
            with container.chat_message(m["role"]): st.write(m["content"])
        if p := st.chat_input("Hey Cooper..."):
            st.session_state.cooper_logs.append({"role": "user", "content": p})
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":"You are Cooper, a warm friend."}]+st.session_state.cooper_logs[-5:]).choices[0].message.content
            st.session_state.cooper_logs.append({"role": "assistant", "content": res})
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- 6. CAREGIVER SECTION ---
elif nav == "Caregiver Insights":
    st.title("📊 Clara Analysis")
    df_users = get_data("Users")
    user_row = df_users[df_users['Username'].astype(str) == str(st.session_state.auth['cid'])]
    
    col_data, col_clara = st.columns([1, 1.5])
    with col_data:
        st.markdown('<div class="portal-card"><h3>📋 User Profile</h3>', unsafe_allow_html=True)
        if not user_row.empty: st.table(user_row.drop(columns=['Password', 'Username']).T)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_clara:
        st.markdown('<div class="portal-card"><h3>🤖 Clara Analyst</h3>', unsafe_allow_html=True)
        container = st.container(height=400)
        for m in st.session_state.clara_logs:
            with container.chat_message(m["role"]): st.write(m["content"])
        if p := st.chat_input("Analyze energy trends..."):
            st.session_state.clara_logs.append({"role": "user", "content": p})
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":"You are Clara, a precise analyst."}]+st.session_state.clara_logs[-5:]).choices[0].message.content
            st.session_state.clara_logs.append({"role": "assistant", "content": res})
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- 7. GAMES SECTION ---
elif nav == "Games":
    if st.button("⬅️ Back to Dashboard"): st.rerun()
    game_type = st.radio("Select Game", ["Zen Snake", "Memory Match"], horizontal=True)

    if game_type == "Zen Snake":
        SNAKE_HTML = """
        <script src="https://cdnjs.cloudflare.com/ajax/libs/hammer.js/2.0.8/hammer.min.js"></script>
        <div style="display:flex; flex-direction:column; align-items:center; background:#1E293B; padding:20px; border-radius:15px; touch-action:none;">
            <canvas id="s" width="320" height="320" style="border:4px solid #38BDF8; background:black; border-radius:10px;"></canvas>
            <h2 id="st" style="color:#38BDF8; font-family:sans-serif;">Score: 0</h2>
            <button onclick="location.reload()" style="width:100%; padding:15px; background:#38BDF8; color:white; border:none; border-radius:10px; font-weight:bold; font-size:18px;">🔄 Restart Game</button>
        </div>
        <script>
        const c=document.getElementById("s"), ctx=c.getContext("2d"), box=16;
        let score=0, d, snake=[{x:9*box, y:10*box}], food={x:5*box, y:5*box};
        const mc = new Hammer(c);
        mc.get('swipe').set({ direction: Hammer.DIRECTION_ALL });
        mc.on("swipeleft", () => { if(d!="RIGHT") d="LEFT" }); mc.on("swiperight", () => { if(d!="LEFT") d="RIGHT" });
        mc.on("swipeup", () => { if(d!="DOWN") d="UP" }); mc.on("swipedown", () => { if(d!="UP") d="DOWN" });
        function draw() {
            ctx.fillStyle="black"; ctx.fillRect(0,0,320,320);
            ctx.fillStyle="#F87171"; ctx.fillRect(food.x, food.y, box, box);
            snake.forEach((p,i)=>{ ctx.fillStyle=i==0?"#38BDF8":"white"; ctx.fillRect(p.x,p.y,box,box); });
            let hX=snake[0].x, hY=snake[0].y;
            if(d=="LEFT") hX-=box; if(d=="UP") hY-=box; if(d=="RIGHT") hX+=box; if(d=="DOWN") hY+=box;
            if(hX==food.x && hY==food.y){ score++; document.getElementById("st").innerText="Score: "+score; food={x:Math.floor(Math.random()*19)*box, y:Math.floor(Math.random()*19)*box};}
            else if(d) snake.pop();
            let h={x:hX, y:hY};
            if(hX<0||hX>=320||hY<0||hY>=320||(d && snake.some(z=>z.x==h.x&&z.y==h.y))){
                ctx.fillStyle="white"; ctx.font="20px Arial"; ctx.fillText("GAME OVER", 110, 160); clearInterval(g);
            }
            if(d) snake.unshift(h);
        }
        let g = setInterval(draw, 120);
        </script>
        """
        st.components.v1.html(SNAKE_HTML, height=550)

    elif game_type == "Memory Match":
        MEMORY_HTML = """
        <style>
            .grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; max-width: 320px; margin: auto; perspective: 1000px; }
            .card { height: 75px; position: relative; transform-style: preserve-3d; transition: transform 0.5s; cursor: pointer; }
            .card.flipped { transform: rotateY(180deg); }
            .card.wrong { animation: flash 0.4s; }
            @keyframes flash { 0% { background: #1E293B; } 50% { background: #EF4444; } 100% { background: #1E293B; } }
            .face { position: absolute; width: 100%; height: 100%; backface-visibility: hidden; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 25px; border: 2px solid #38BDF8; }
            .front { background: #1E293B; }
            .back { background: #334155; transform: rotateY(180deg); color: white; }
        </style>
        <div class="grid" id="g"></div>
        <button onclick="location.reload()" style="width:100%; max-width:320px; display:block; margin:20px auto; padding:15px; background:#38BDF8; color:white; border:none; border-radius:10px; font-weight:bold;">🔄 New Game</button>
        <script>
            const icons = ['🍎','🍎','💎','💎','🌟','🌟','🚀','🚀','🌈','🌈','🔥','🔥','🍀','🍀','🎁','🎁'];
            let shuffled = icons.sort(() => 0.5 - Math.random());
            let flipped = [], lock = false;
            const board = document.getElementById('g');
            shuffled.forEach(icon => {
                const card = document.createElement('div'); card.className = 'card';
                card.innerHTML = `<div class="face front"></div><div class="face back">${icon}</div>`;
                card.dataset.icon = icon;
                card.onclick = function() {
                    if(lock || this.classList.contains('flipped')) return;
                    this.classList.add('flipped'); flipped.push(this);
                    if(flipped.length === 2) {
                        lock = true;
                        if(flipped[0].dataset.icon === flipped[1].dataset.icon) { flipped = []; lock = false; }
                        else { flipped.forEach(c => c.classList.add('wrong')); setTimeout(() => {
                            flipped.forEach(c => { c.classList.remove('flipped'); c.classList.remove('wrong'); });
                            flipped = []; lock = false; }, 800);
                        }
                    }
                }; board.appendChild(card);
            });
        </script>
        """
        st.components.v1.html(MEMORY_HTML, height=500)
