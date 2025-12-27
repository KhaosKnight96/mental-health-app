import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# --- 1. SETUP ---
st.set_page_config(page_title="Health Bridge", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None}
if "game_over_score" not in st.session_state:
    st.session_state.game_over_score = 0

def get_data():
    df = conn.read(worksheet="Users", ttl=0)
    df.columns = [str(c).strip() for c in df.columns]
    return df

# --- 2. LOGIN ---
if not st.session_state.auth["logged_in"]:
    st.title("🧠 Health Bridge")
    u = st.text_input("Couple ID")
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        df = get_data()
        m = df[(df['Username'].astype(str) == u) & (df['Password'].astype(str) == p)]
        if not m.empty:
            st.session_state.auth.update({"logged_in": True, "cid": u})
            st.rerun()
    st.stop()

# --- 3. DATA REFRESH ---
df = get_data()
user_idx = df.index[df['Username'].astype(str) == str(st.session_state.auth['cid'])]
current_pb = int(pd.to_numeric(df.at[user_idx[0], 'HighScore'], errors='coerce') or 0)

# --- 4. THE UI LAYOUT ---
st.title("🐍 Zen Snake")
col1, col2 = st.columns([2, 1])

with col2:
    st.markdown(f"### 🏆 Record: **{current_pb}**")
    st.divider()
    st.write("1. Play the game on the left.")
    st.write("2. When 'Game Over' appears, enter your score below.")
    
    score_input = st.number_input("Final Game Score:", min_value=0, step=1, key="manual_score")
    
    if st.button("🚀 Sync Score to Google Sheets", type="primary", use_container_width=True):
        if score_input > current_best:
            df.at[user_idx[0], 'HighScore'] = score_input
            conn.update(worksheet="Users", data=df)
            st.cache_data.clear()
            st.success(f"Sheet Updated! New Record: {score_input}")
            st.balloons()
            st.rerun()
        else:
            st.warning(f"Your score ({score_input}) didn't beat your record ({current_best}).")

with col1:
    # Game component - simplified to prevent any browser errors
    SNAKE_HTML = """
    <div style="display:flex; flex-direction:column; align-items:center; background:#1E293B; padding:20px; border-radius:15px;">
        <canvas id="s" width="400" height="400" style="border:4px solid #38BDF8; background:black;"></canvas>
        <h2 id="status" style="color:#38BDF8; font-family:sans-serif; margin-top:10px;">Score: 0</h2>
    </div>
    <script>
    const c=document.getElementById("s"), ctx=c.getContext("2d"), box=20;
    let score=0, d, snake=[{x:9*box, y:10*box}], food={x:5*box, y:5*box};

    document.onkeydown = e => {
        if([37,38,39,40].includes(e.keyCode)) e.preventDefault();
        if(e.keyCode==37 && d!="RIGHT") d="LEFT";
        if(e.keyCode==38 && d!="DOWN") d="UP";
        if(e.keyCode==39 && d!="LEFT") d="RIGHT";
        if(e.keyCode==40 && d!="UP") d="DOWN";
    };

    function draw() {
        ctx.fillStyle="black"; ctx.fillRect(0,0,400,400);
        ctx.fillStyle="#F87171"; ctx.fillRect(food.x, food.y, box, box);
        snake.forEach((p,i)=>{ ctx.fillStyle=i==0?"#38BDF8":"white"; ctx.fillRect(p.x,p.y,box,box); });
        
        let hX=snake[0].x, hY=snake[0].y;
        if(d=="LEFT") hX-=box; if(d=="UP") hY-=box; if(d=="RIGHT") hX+=box; if(d=="DOWN") hY+=box;
        
        if(hX==food.x && hY==food.y){ 
            score++; 
            document.getElementById("status").innerText = "Score: " + score;
            food={x:Math.floor(Math.random()*19)*box, y:Math.floor(Math.random()*19)*box}; 
        } else if(d) snake.pop();
        
        let h={x:hX, y:hY};
        if(hX<0||hX>=400||hY<0||hY>=400||(d && snake.some(z=>z.x==h.x&&z.y==h.y))){
            document.getElementById("status").innerText = "GAME OVER! Final Score: " + score;
            document.getElementById("status").style.color = "#F87171";
            clearInterval(g);
        }
        if(d) snake.unshift(h);
    }
    let g = setInterval(draw, 100);
    </script>
    """
    st.components.v1.html(SNAKE_HTML, height=550)

if st.sidebar.button("Logout"):
    st.session_state.auth = {"logged_in": False, "cid": None}
    st.rerun()
