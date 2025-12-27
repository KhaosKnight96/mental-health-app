import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# --- 1. SETTINGS & STYLING ---
st.set_page_config(page_title="Health Bridge Portal", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0F172A !important; color: #F8FAFC !important; }
    [data-testid="stSidebar"] { background-color: #1E293B !important; border-right: 1px solid #334155; }
    .portal-card { background: #1E293B; padding: 25px; border-radius: 20px; border: 1px solid #334155; margin-bottom: 20px; }
    h1, h2, h3, p, label { color: #F8FAFC !important; }
    .stButton>button { border-radius: 12px !important; font-weight: 600 !important; }
</style>
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

# --- 3. LOGIN GATE ---
if not st.session_state.auth["logged_in"]:
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge</h1>", unsafe_allow_html=True)
        u_l = st.text_input("Couple ID")
        p_l = st.text_input("Password", type="password")
        if st.button("Sign In", use_container_width=True, type="primary"):
            df = get_data()
            m = df[(df['Username'].astype(str) == u_l) & (df['Password'].astype(str) == p_l)]
            if not m.empty:
                st.session_state.auth.update({"logged_in": True, "cid": u_l, "name": m.iloc[0]['Fullname']})
                st.rerun()
            else: st.error("Invalid credentials.")
    st.stop()

# --- 4. SIDEBAR NAVIGATION ---
with st.sidebar:
    st.title("🌉 Health Bridge")
    # Unified Game Navigation
    main_page = st.selectbox("Navigation", ["Dashboard", "Caregiver Section", "Games"])
    
    game_choice = None
    if main_page == "Games":
        game_choice = st.radio("Select Game", ["Zen Snake", "Memory Match"])
        
    st.divider()
    if st.button("🚪 Logout"):
        st.session_state.auth = {"logged_in": False, "cid": None, "name": None}
        st.rerun()

# --- 5. DASHBOARD (COOPER - THE FRIEND) ---
if main_page == "Dashboard":
    st.markdown(f"<h1>Welcome, {st.session_state.auth['name']}! ☀️</h1>", unsafe_allow_html=True)
    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown('<div class="portal-card"><h3>🤝 Meet Cooper</h3><p>Your companion for the journey.</p></div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="portal-card"><h3>💬 Chat with Cooper</h3>', unsafe_allow_html=True)
        chat_container = st.container(height=350)
        for m in st.session_state.cooper_logs:
            with chat_container.chat_message(m["role"]): st.write(m["content"])
        if prompt := st.chat_input("Hey Cooper..."):
            st.session_state.cooper_logs.append({"role": "user", "content": prompt})
            response = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "system", "content": "You are Cooper, a warm friend."}] + st.session_state.cooper_logs[-5:]).choices[0].message.content
            st.session_state.cooper_logs.append({"role": "assistant", "content": response})
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- 6. CAREGIVER SECTION (CLARA - THE ANALYST) ---
elif main_page == "Caregiver Section":
    st.markdown("<h1>Caregiver Insights 📊</h1>", unsafe_allow_html=True)
    df = get_data()
    user_data = df[df['Username'].astype(str) == str(st.session_state.auth['cid'])]
    
    col_data, col_chat = st.columns([1, 2])
    with col_data:
        st.markdown('<div class="portal-card"><h3>📋 Data Summary</h3>', unsafe_allow_html=True)
        if not user_data.empty:
            st.write(user_data.T) # Display user row as a vertical table
        else:
            st.warning("No data found for this ID.")
        st.markdown('</div>', unsafe_allow_html=True)

    with col_chat:
        st.markdown('<div class="portal-card"><h3>🤖 Clara Analyst AI</h3>', unsafe_allow_html=True)
        clara_container = st.container(height=400)
        for m in st.session_state.clara_logs:
            with clara_container.chat_message(m["role"]): st.write(m["content"])
        if clara_prompt := st.chat_input("Analyze data..."):
            st.session_state.clara_logs.append({"role": "user", "content": clara_prompt})
            c_response = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "system", "content": "You are Clara, a medical data analyst."}] + st.session_state.clara_logs[-5:]).choices[0].message.content
            st.session_state.clara_logs.append({"role": "assistant", "content": c_response})
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- 7. GAMES SECTION ---
elif main_page == "Games":
    if st.button("⬅️ Back to Dashboard"):
        st.rerun() # Restarts script, defaulting back to Dashboard

    if game_choice == "Zen Snake":
        st.title("🐍 Swipe Snake")
        SNAKE_HTML = """
        <script src="https://cdnjs.cloudflare.com/ajax/libs/hammer.js/2.0.8/hammer.min.js"></script>
        <div style="display:flex; flex-direction:column; align-items:center; background:#1E293B; padding:20px; border-radius:15px; touch-action:none;">
            <canvas id="s" width="350" height="350" style="border:4px solid #38BDF8; background:black;"></canvas>
            <h2 id="status" style="color:#38BDF8; font-family:sans-serif; margin:10px 0;">Score: 0</h2>
            <button onclick="location.reload()" style="padding:10px 20px; background:#38BDF8; color:white; border:none; border-radius:8px; cursor:pointer; font-weight:bold;">🔄 Restart Game</button>
        </div>
        <script>
        const c=document.getElementById("s"), ctx=c.getContext("2d"), box=17.5;
        let score=0, d, snake=[{x:9*box, y:10*box}], food={x:5*box, y:5*box};
        
        // Touch/Swipe Logic
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
            ctx.fillStyle="black"; ctx.fillRect(0,0,350,350);
            ctx.fillStyle="#F87171"; ctx.fillRect(food.x, food.y, box, box);
            snake.forEach((p,i)=>{ ctx.fillStyle=i==0?"#38BDF8":"white"; ctx.fillRect(p.x,p.y,box,box); });
            let hX=snake[0].x, hY=snake[0].y;
            if(d=="LEFT") hX-=box; if(d=="UP") hY-=box; if(d=="RIGHT") hX+=box; if(d=="DOWN") hY+=box;
            if(hX==food.x && hY==food.y){ score++; document.getElementById("status").innerText="Score: "+score; food={x:Math.floor(Math.random()*19)*box, y:Math.floor(Math.random()*19)*box};}
            else if(d) snake.pop();
            let h={x:hX, y:hY};
            if(hX<0||hX>=350||hY<0||hY>=350||(d && snake.some(z=>z.x==h.x&&z.y==h.y))){
                ctx.fillStyle="white"; ctx.fillText("GAME OVER", 130, 175);
                clearInterval(g);
            }
            if(d) snake.unshift(h);
        }
        let g = setInterval(draw, 120);
        </script>
        """
        st.components.v1.html(SNAKE_HTML, height=550)

    elif game_choice == "Memory Match":
        st.title("🧩 Memory Match")
        MEMORY_HTML = """
        <div id="game-board" style="display:grid; grid-template-columns:repeat(4, 1fr); gap:10px; max-width:400px; margin:auto;"></div>
        <div style="text-align:center; margin-top:20px;">
            <button onclick="location.reload()" style="padding:10px 20px; background:#38BDF8; color:white; border:none; border-radius:8px; cursor:pointer; font-weight:bold;">🔄 New Game</button>
        </div>
        <script>
        const cards = ['🍎','🍎','💎','💎','🌟','🌟','🚀','🚀','🌈','🌈','🔥','🔥','🍀','🍀','🎁','🎁'];
        let shuffled = cards.sort(() => 0.5 - Math.random());
        let selected = [];
        const board = document.getElementById('game-board');

        shuffled.forEach((symbol, index) => {
            const card = document.createElement('div');
            card.style = "height:80px; background:#1E293B; border:2px solid #38BDF8; border-radius:10px; display:flex; align-items:center; justify-content:center; font-size:30px; cursor:pointer; color:transparent;";
            card.dataset.symbol = symbol;
            card.onclick = function() {
                if (selected.length < 2 && this.style.color === 'transparent') {
                    this.style.color = 'white';
                    this.style.background = '#334155';
                    selected.push(this);
                    if (selected.length === 2) {
                        if (selected[0].dataset.symbol === selected[1].dataset.symbol) {
                            selected = [];
                        } else {
                            setTimeout(() => {
                                selected.forEach(c => { c.style.color = 'transparent'; c.style.background = '#1E293B'; });
                                selected = [];
                            }, 700);
                        }
                    }
                }
            };
            board.appendChild(card);
        });
        </script>
        """
        st.components.v1.html(MEMORY_HTML, height=500)
