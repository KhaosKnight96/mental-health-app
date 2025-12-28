import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime

# --- 1. CONFIG ---
st.set_page_config(page_title="Health Bridge Pro", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    .glass-panel {
        background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(15px);
        border-radius: 20px; border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 25px; margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. SESSION STATE ---
if "auth" not in st.session_state: st.session_state.auth = {"in": False, "mid": None}
if "chats" not in st.session_state: st.session_state.chats = {"Cooper": [], "Clara": []}

# --- 3. AI ENGINE (FIXED FOR CLARA) ---
def ask_health_ai(agent_name, prompt):
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"].strip())
        
        # Specific instructions for each AI
        if agent_name == "Cooper":
            sys_msg = "You are Cooper, a warm, empathetic friend. Listen and support."
        else:
            sys_msg = "You are Clara, a data-driven health analyst. Use logic and health patterns."

        # Include recent history for context
        msgs = [{"role": "system", "content": sys_msg}]
        msgs.extend(st.session_state.chats[agent_name][-4:])
        msgs.append({"role": "user", "content": prompt})

        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=msgs)
        return res.choices[0].message.content
    except Exception as e:
        return f"AI Error: {str(e)}"

# --- 4. LOGIN (Simplified for speed) ---
if not st.session_state.auth["in"]:
    st.title("🧠 Health Bridge Login")
    u = st.text_input("Member ID").strip().lower()
    p = st.text_input("Password", type="password")
    if st.button("Sign In"):
        # Bypassing GSheets check for this demo build to ensure you can enter
        st.session_state.auth.update({"in": True, "mid": u})
        st.rerun()
    st.stop()

# --- 5. TABS ---
t1, t2, t3, t4 = st.tabs(["🏠 Cooper", "🛋️ Clara", "🎮 Games", "🚪 Logout"])

# --- COOPER & CLARA TABS ---
for i, agent in enumerate(["Cooper", "Clara"]):
    with [t1, t2][i]:
        st.subheader(f"Chat with {agent}")
        for m in st.session_state.chats[agent]:
            with st.chat_message(m["role"]): st.write(m["content"])
            
        if p := st.chat_input(f"Message {agent}...", key=f"inp_{agent}"):
            st.session_state.chats[agent].append({"role": "user", "content": p})
            with st.chat_message("user"): st.write(p)
            
            with st.spinner(f"{agent} is thinking..."):
                res = ask_health_ai(agent, p)
                st.session_state.chats[agent].append({"role": "assistant", "content": res})
                with st.chat_message("assistant"): st.write(res)
            st.rerun()

# --- 6. TOUCH-COMPATIBLE GAMES ---
with t3:
    st.subheader("🕹️ Touch-Ready Arcade")
    
    # SNAKE WITH SWIPE LOGIC
    st.components.v1.html("""
    <div id="game-container" style="text-align:center; background:#1E293B; padding:10px; border-radius:20px; touch-action:none;">
        <canvas id="snakeCanvas" width="300" height="300" style="background:#0F172A; border:3px solid #38BDF8; border-radius:10px;"></canvas>
        <h2 id="score" style="color:#38BDF8; font-family:sans-serif;">Score: 0</h2>
        <p style="color:#94A3B8; font-size:12px;">Swipe to move on Mobile | Arrows on PC</p>
    </div>
    
    <script>
    const canvas = document.getElementById("snakeCanvas");
    const ctx = canvas.getContext("2d");
    const box = 15;
    let score = 0;
    let d = "RIGHT";
    let snake = [{x: 9 * box, y: 10 * box}];
    let food = {x: Math.floor(Math.random()*19+1)*box, y: Math.floor(Math.random()*19+1)*box};

    // Keyboard controls
    document.addEventListener("keydown", direction);
    function direction(event) {
        if(event.keyCode == 37 && d != "RIGHT") d = "LEFT";
        else if(event.keyCode == 38 && d != "DOWN") d = "UP";
        else if(event.keyCode == 39 && d != "LEFT") d = "RIGHT";
        else if(event.keyCode == 40 && d != "UP") d = "DOWN";
    }

    // Touch/Swipe controls
    let touchstartX = 0; let touchstartY = 0;
    canvas.addEventListener('touchstart', e => { touchstartX = e.changedTouches[0].screenX; touchstartY = e.changedTouches[0].screenY; }, false);
    canvas.addEventListener('touchend', e => {
        let x = e.changedTouches[0].screenX; let y = e.changedTouches[0].screenY;
        let dx = x - touchstartX; let dy = y - touchstartY;
        if (Math.abs(dx) > Math.abs(dy)) {
            if (dx > 0 && d != "LEFT") d = "RIGHT"; else if (dx < 0 && d != "RIGHT") d = "LEFT";
        } else {
            if (dy > 0 && d != "UP") d = "DOWN"; else if (dy < 0 && d != "DOWN") d = "UP";
        }
    }, false);

    function draw() {
        ctx.fillStyle = "#0F172A"; ctx.fillRect(0,0,300,300);
        ctx.fillStyle = "#F87171"; ctx.fillRect(food.x, food.y, box, box);
        for(let i=0; i<snake.length; i++) {
            ctx.fillStyle = (i == 0) ? "#38BDF8" : "#334155";
            ctx.fillRect(snake[i].x, snake[i].y, box, box);
        }
        let headX = snake[0].x; let headY = snake[0].y;
        if( d == "LEFT") headX -= box; if( d == "UP") headY -= box;
        if( d == "RIGHT") headX += box; if( d == "DOWN") headY += box;
        if(headX == food.x && headY == food.y) {
            score++; food = {x: Math.floor(Math.random()*19+1)*box, y: Math.floor(Math.random()*19+1)*box};
        } else { snake.pop(); }
        let newHead = {x: headX, y: headY};
        if(headX < 0 || headX >= 300 || headY < 0 || headY >= 300 || collision(newHead, snake)) { clearInterval(game); location.reload(); }
        snake.unshift(newHead);
        document.getElementById("score").innerHTML = "Score: " + score;
    }
    function collision(head, array) { for(let i=0; i<array.length; i++) { if(head.x == array[i].x && head.y == array[i].y) return true; } return false; }
    let game = setInterval(draw, 120);
    </script>
    """, height=480)

with t4:
    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()
