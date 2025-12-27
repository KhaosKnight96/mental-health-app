import streamlit as st
import pandas as pd
import random
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIG & MOBILE OPTIMIZATION ---
st.set_page_config(page_title="Health Bridge", layout="wide", initial_sidebar_state="collapsed")

# This CSS makes the app feel more like a mobile interface
st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    [data-testid="stSidebar"] { background-color: #1E293B; border-right: 1px solid #334155; }
    .portal-card { background: #1E293B; padding: 20px; border-radius: 15px; border: 1px solid #334155; margin-bottom: 15px; }
    .stButton>button { border-radius: 10px; font-weight: 600; height: 3em; width: 100%; }
    /* Hide Streamlit branding for a cleaner app look */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
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

def get_data():
    df = conn.read(worksheet="Users", ttl=0)
    df.columns = [str(c).strip() for c in df.columns]
    return df

# --- 3. LOGIN ---
if not st.session_state.auth["logged_in"]:
    st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge</h1>", unsafe_allow_html=True)
    with st.container():
        u = st.text_input("Couple ID")
        p = st.text_input("Password", type="password")
        if st.button("Sign In"):
            df = get_data()
            m = df[(df['Username'].astype(str) == u) & (df['Password'].astype(str) == p)]
            if not m.empty:
                st.session_state.auth.update({"logged_in": True, "cid": u, "name": m.iloc[0]['Fullname']})
                st.rerun()
            else: st.error("Access Denied.")
    st.stop()

# --- 4. NAVIGATION ---
with st.sidebar:
    st.title("🌉 Menu")
    nav = st.selectbox("Go to:", ["Dashboard", "Caregiver Insights", "Games"])
    st.divider()
    if st.button("Logout"):
        st.session_state.auth = {"logged_in": False, "cid": None}
        st.rerun()

# --- 5. DASHBOARD (COOPER - FRIEND) ---
if nav == "Dashboard":
    st.title(f"Hi {st.session_state.auth['name']}! 👋")
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown('<div class="portal-card"><h3>🤝 Cooper AI</h3><p>Your friendly companion. Talk to me about anything on your mind.</p></div>', unsafe_allow_html=True)
    
    with col2:
        container = st.container(height=400)
        for m in st.session_state.cooper_logs:
            with container.chat_message(m["role"]): st.write(m["content"])
        
        if p := st.chat_input("Chat with Cooper..."):
            st.session_state.cooper_logs.append({"role": "user", "content": p})
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":"You are Cooper, a warm, casual friend to a patient."}]+st.session_state.cooper_logs[-5:]).choices[0].message.content
            st.session_state.cooper_logs.append({"role": "assistant", "content": res})
            st.rerun()

# --- 6. CAREGIVER (CLARA - ANALYST) ---
elif nav == "Caregiver Insights":
    st.title("📊 Clara Analysis")
    df = get_data()
    user_row = df[df['Username'].astype(str) == str(st.session_state.auth['cid'])]
    
    col_a, col_b = st.columns([1, 2])
    with col_a:
        st.markdown('<div class="portal-card"><h3>📋 Data Summary</h3>', unsafe_allow_html=True)
        if not user_row.empty:
            # Clean data for display
            clean_display = user_row.drop(columns=['Password', 'Username']).T
            clean_display.columns = ["Value"]
            st.table(clean_display)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_b:
        st.markdown('<div class="portal-card"><h3>🤖 Clara Analyst</h3>', unsafe_allow_html=True)
        container = st.container(height=400)
        for m in st.session_state.clara_logs:
            with container.chat_message(m["role"]): st.write(m["content"])
        
        if p := st.chat_input("Request analysis..."):
            st.session_state.clara_logs.append({"role": "user", "content": p})
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":"You are Clara, a precise medical data analyst for caregivers."}]+st.session_state.clara_logs[-5:]).choices[0].message.content
            st.session_state.clara_logs.append({"role": "assistant", "content": res})
            st.rerun()

# --- 7. GAMES (SNAKE & MEMORY) ---
elif nav == "Games":
    game_type = st.radio("Choose Game", ["Zen Snake", "Memory Match"], horizontal=True)
    
    if st.button("⬅️ Back to Dashboard", type="secondary"):
        st.session_state.nav = "Dashboard" # Needs nav in state to work perfectly, but rerun works
        st.rerun()

    if game_type == "Zen Snake":
        # Swipe and Keyboard Compatible Snake
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
        mc.on("swipeleft", () => { if(d!="RIGHT") d="LEFT" });
        mc.on("swiperight", () => { if(d!="LEFT") d="RIGHT" });
        mc.on("swipeup", () => { if(d!="DOWN") d="UP" });
        mc.on("swipedown", () => { if(d!="UP") d="DOWN" });

        document.onkeydown = e => {
            if([37,38,39,40].includes(e.keyCode)) e.preventDefault();
            if(e.keyCode==37 && d!="RIGHT") d="LEFT";
            if(e.keyCode==38 && d!="DOWN") d="UP";
            if(e.keyCode==39 && d!="LEFT") d="RIGHT";
            if(e.keyCode==40 && d!="UP") d="DOWN";
        };

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
                ctx.fillStyle="white"; ctx.font="20px Arial"; ctx.fillText("GAME OVER", 110, 160);
                clearInterval(g);
            }
            if(d) snake.unshift(h);
        }
        let g = setInterval(draw, 120);
        </script>
        """
        st.components.v1.html(SNAKE_HTML, height=600)

    elif game_type == "Memory Match":
        MEMORY_HTML = """
        <div id="g" style="display:grid; grid-template-columns:repeat(4, 1fr); gap:8px; max-width:320px; margin:auto;"></div>
        <button onclick="location.reload()" style="width:100%; max-width:320px; display:block; margin:20px auto; padding:15px; background:#38BDF8; color:white; border:none; border-radius:10px; font-weight:bold;">🔄 New Game</button>
        <script>
        const cards = ['🍎','🍎','💎','💎','🌟','🌟','🚀','🚀','🌈','🌈','🔥','🔥','🍀','🍀','🎁','🎁'];
        let shuffled = cards.sort(() => 0.5 - Math.random());
        let sel = [];
        const board = document.getElementById('g');

        shuffled.forEach((s, i) => {
            const el = document.createElement('div');
            el.style = "height:70px; background:#1E293B; border:2px solid #38BDF8; border-radius:8px; display:flex; align-items:center; justify-content:center; font-size:25px; cursor:pointer; color:transparent; transition: 0.3s;";
            el.dataset.s = s;
            el.onclick = function() {
                if (sel.length < 2 && this.style.color === 'transparent') {
                    this.style.color = 'white';
                    this.style.background = '#334155';
                    sel.push(this);
                    if (sel.length === 2) {
                        if (sel[0].dataset.s === sel[1].dataset.s) { sel = []; }
                        else { setTimeout(() => { sel.forEach(c => { c.style.color='transparent'; c.style.background='#1E293B'; }); sel = []; }, 600); }
                    }
                }
            };
            board.appendChild(el);
        });
        </script>
        """
        st.components.v1.html(MEMORY_HTML, height=500)
