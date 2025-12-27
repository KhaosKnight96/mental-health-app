import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# --- 1. SETUP ---
st.set_page_config(page_title="Health Bridge", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None}

def get_fresh_data():
    return conn.read(worksheet="Users", ttl=0)

# --- 2. LOGIN (Fast) ---
if not st.session_state.auth["logged_in"]:
    st.title("🧠 Health Bridge")
    u = st.text_input("Couple ID")
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        df = get_fresh_data()
        m = df[(df['Username'].astype(str) == u) & (df['Password'].astype(str) == p)]
        if not m.empty:
            st.session_state.auth.update({"logged_in": True, "cid": u})
            st.rerun()
    st.stop()

# --- 3. DASHBOARD METRICS ---
df = get_fresh_data()
df.columns = [str(c).strip() for c in df.columns]
user_row = df[df['Username'].astype(str) == str(st.session_state.auth['cid'])]
current_pb = int(pd.to_numeric(user_row['HighScore'].values[0], errors='coerce') or 0)

st.title(f"🎮 Zen Snake")
st.subheader(f"Current Personal Best: {current_pb}")

# --- 4. THE GAME WITH AUTOMATIC DATA RETURN ---
# We use a trick: the game sends a message to the parent, 
# and we catch it using a query parameter update that actually works.

SNAKE_HTML = f"""
<div style="display:flex; flex-direction:column; align-items:center; background:#1E293B; padding:20px; border-radius:15px;">
    <canvas id="s" width="400" height="400" style="border:4px solid #38BDF8; background:black;"></canvas>
    <div id="m" style="display:none; margin-top:20px;">
        <h2 style="color:white; font-family:sans-serif;">Game Over!</h2>
        <button id="save" style="padding:12px 25px; background:#38BDF8; color:white; border:none; border-radius:8px; cursor:pointer; font-weight:bold;">SYNC SCORE TO SHEETS</button>
    </div>
</div>

<script>
const c=document.getElementById("s"), ctx=c.getContext("2d"), box=20;
let score=0, d, snake=[{{x:9*box, y:10*box}}], food={{x:5*box, y:5*box}};

document.getElementById("save").onclick = () => {{
    // The most compatible way to send data back to Streamlit
    const link = window.parent.location.origin + window.parent.location.pathname + "?new_score=" + score;
    window.parent.location.href = link;
}};

document.onkeydown = e => {{
    if([37,38,39,40].includes(e.keyCode)) e.preventDefault();
    if(e.keyCode==37 && d!="RIGHT") d="LEFT";
    if(e.keyCode==38 && d!="DOWN") d="UP";
    if(e.keyCode==39 && d!="LEFT") d="RIGHT";
    if(e.keyCode==40 && d!="UP") d="DOWN";
}};

function draw() {{
    ctx.fillStyle="black"; ctx.fillRect(0,0,400,400);
    ctx.fillStyle="#F87171"; ctx.fillRect(food.x, food.y, box, box);
    snake.forEach((p,i)=>{{ ctx.fillStyle=i==0?"#38BDF8":"white"; ctx.fillRect(p.x,p.y,box,box); }});
    let hX=snake[0].x, hY=snake[0].y;
    if(d=="LEFT") hX-=box; if(d=="UP") hY-=box; if(d=="RIGHT") hX+=box; if(d=="DOWN") hY+=box;
    if(hX==food.x && hY==food.y){{ score++; food={{x:Math.floor(Math.random()*19)*box, y:Math.floor(Math.random()*19)*box}}; }}
    else if(d) snake.pop();
    let h={{x:hX, y:hY}};
    if(hX<0||hX>=400||hY<0||hY>=400||(d && snake.some(z=>z.x==h.x&&z.y==h.y))){{
        clearInterval(g);
        document.getElementById("m").style.display="block";
    }}
    if(d) snake.unshift(h);
}}
let g = setInterval(draw, 100);
</script>
"""

# --- 5. THE CATCHER ---
# This looks for the score in the URL after the game "Save" is clicked
params = st.query_params
if "new_score" in params:
    incoming = int(params["new_score"])
    if incoming > current_pb:
        df.at[user_row.index[0], 'HighScore'] = incoming
        conn.update(worksheet="Users", data=df)
        st.cache_data.clear()
        st.success(f"🔥 AMAZING! New High Score: {incoming}")
        st.balloons()
    else:
        st.info(f"Good game! Score: {incoming}")
    
    # Reset URL
    st.query_params.clear()
    # No rerun needed here, the URL change already handled it

st.components.v1.html(SNAKE_HTML, height=600)

if st.button("Logout"):
    st.session_state.auth = {"logged_in": False, "cid": None}
    st.rerun()
