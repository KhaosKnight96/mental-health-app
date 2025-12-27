import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# --- 1. SETUP ---
st.set_page_config(page_title="Health Bridge", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None}

def get_data():
    df = conn.read(worksheet="Users", ttl=0)
    df.columns = [str(c).strip() for c in df.columns]
    return df

# --- 2. LOGIN ---
if not st.session_state.auth["logged_in"]:
    st.title("🧠 Health Bridge Login")
    u = st.text_input("Couple ID")
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        df = get_data()
        m = df[(df['Username'].astype(str) == u) & (df['Password'].astype(str) == p)]
        if not m.empty:
            st.session_state.auth.update({"logged_in": True, "cid": u})
            st.rerun()
    st.stop()

# --- 3. SIDEBAR SYNC (THE FIX) ---
with st.sidebar:
    st.title("🌉 Control Panel")
    df = get_data()
    row = df[df['Username'].astype(str) == str(st.session_state.auth['cid'])]
    current_pb = int(pd.to_numeric(row['HighScore'].values[0], errors='coerce') or 0)
    
    st.metric("Your Record", f"{current_pb} pts")
    st.divider()
    
    st.subheader("🏁 Finish Game")
    final_score = st.number_input("Enter Game Score:", min_value=0, step=1)
    
    if st.button("💾 Sync to Google Sheets", type="primary", use_container_width=True):
        if final_score > current_pb:
            df.at[row.index[0], 'HighScore'] = final_score
            conn.update(worksheet="Users", data=df)
            st.cache_data.clear()
            st.success(f"New Record: {final_score}!")
            st.balloons()
        else:
            st.warning(f"Score {final_score} isn't higher than {current_pb}.")

    if st.button("🚪 Logout"):
        st.session_state.auth = {"logged_in": False, "cid": None}
        st.rerun()

# --- 4. THE GAME ---
st.title("🐍 Zen Snake")
st.write("Controls: Arrow Keys. After 'Game Over', enter your score in the sidebar to save.")

SNAKE_HTML = """
<div style="display:flex; justify-content:center; background:#1E293B; padding:20px; border-radius:15px;">
    <canvas id="s" width="400" height="400" style="border:4px solid #38BDF8; background:black;"></canvas>
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
    if(hX==food.x && hY==food.y){ score++; food={x:Math.floor(Math.random()*19)*box, y:Math.floor(Math.random()*19)*box}; }
    else if(d) snake.pop();
    let h={x:hX, y:hY};
    if(hX<0||hX>=400||hY<0||hY>=400||(d && snake.some(z=>z.x==h.x&&z.y==h.y))){
        ctx.fillStyle="white"; ctx.font="30px Arial"; ctx.fillText("GAME OVER: " + score, 80, 200);
        clearInterval(g);
    }
    if(d) snake.unshift(h);
}
let g = setInterval(draw, 100);
</script>
"""
st.components.v1.html(SNAKE_HTML, height=500)
