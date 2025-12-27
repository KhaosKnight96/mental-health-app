import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# --- 1. SETUP ---
st.set_page_config(page_title="Health Bridge", layout="wide")

conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None}

# --- 2. THE SYNC ENGINE ---
def force_save_score(score_to_save):
    """Explicitly writes the score to Google Sheets."""
    try:
        # 1. Fetch freshest possible data
        df = conn.read(worksheet="Users", ttl=0)
        df.columns = [str(c).strip() for c in df.columns]
        
        cid = str(st.session_state.auth['cid'])
        user_mask = df['Username'].astype(str) == cid
        
        if any(user_mask):
            idx = df.index[user_mask][0]
            old_score = int(pd.to_numeric(df.at[idx, 'HighScore'], errors='coerce') or 0)
            
            if score_to_save > old_score:
                df.at[idx, 'HighScore'] = score_to_save
                # 2. Push the update
                conn.update(worksheet="Users", data=df)
                st.cache_data.clear()
                return True, old_score
        return False, 0
    except Exception as e:
        st.error(f"Sync Error: {e}")
        return False, 0

# --- 3. URL PARAMETER CATCHER ---
params = st.query_params
if "score" in params and st.session_state.auth["logged_in"]:
    incoming_score = int(float(params["score"]))
    success, old = force_save_score(incoming_score)
    
    if success:
        st.success(f"🏆 NEW RECORD! Updated from {old} to {incoming_score}")
    else:
        st.info(f"Game finished. Score: {incoming_score}")
    
    # Clear URL to prevent loops
    st.query_params.clear()
    st.rerun()

# --- 4. LOGIN ---
if not st.session_state.auth["logged_in"]:
    st.title("🧠 Health Bridge")
    u = st.text_input("Couple ID")
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        df = conn.read(worksheet="Users", ttl=0)
        df.columns = [str(c).strip() for c in df.columns]
        match = df[(df['Username'].astype(str) == u) & (df['Password'].astype(str) == p)]
        if not match.empty:
            st.session_state.auth.update({"logged_in": True, "cid": u})
            st.rerun()
    st.stop()

# --- 5. DASHBOARD ---
page = st.sidebar.radio("Nav", ["Dashboard", "Snake"])

if page == "Dashboard":
    df = conn.read(worksheet="Users", ttl=0)
    df.columns = [str(c).strip() for c in df.columns]
    row = df[df['Username'].astype(str) == str(st.session_state.auth['cid'])]
    current_pb = row['HighScore'].values[0] if not row.empty else 0
    
    st.title(f"Welcome Back")
    st.metric("Your Sheet Record", f"{int(current_pb)} pts")
    
    if st.button("Test Sync (+5)"):
        st.query_params.update(score=int(current_pb) + 5)
        st.rerun()

# --- 6. SNAKE GAME ---
elif page == "Snake":
    st.title("🐍 Zen Snake")
    
    # We use a completely different approach for the URL redirect here
    SNAKE_HTML = """
    <div style="display:flex; flex-direction:column; align-items:center; background:#1E293B; padding:20px; border-radius:15px;">
        <canvas id="s" width="400" height="400" style="border:4px solid #38BDF8; background:black;"></canvas>
        <div id="m" style="display:none; margin-top:20px;">
            <button id="v" style="padding:15px 30px; background:#38BDF8; color:white; border:none; border-radius:10px; font-weight:bold; cursor:pointer;">💾 SAVE SCORE & EXIT</button>
        </div>
    </div>
    <script>
    const c=document.getElementById("s"), ctx=c.getContext("2d"), box=20;
    let score=0, d, snake=[{x:9*box, y:10*box}], food={x:5*box, y:5*box};

    document.getElementById("v").onclick = () => {
        // FORCE the parent window to reload with the score
        const currentUrl = window.parent.location.href.split('?')[0];
        window.parent.location.href = currentUrl + "?score=" + score;
    };

    document.onkeydown = e => {
        if(e.keyCode==37 && d!="RIGHT") d="LEFT";
        if(e.keyCode==38 && d!="DOWN") d="UP";
        if(e.keyCode==39 && d!="LEFT") d="RIGHT";
        if(e.keyCode==40 && d!="UP") d="DOWN";
    };

    function draw() {
        ctx.fillStyle="black"; ctx.fillRect(0,0,400,400);
        ctx.fillStyle="red"; ctx.fillRect(food.x, food.y, box, box);
        snake.forEach((p,i)=>{ ctx.fillStyle=i==0?"cyan":"white"; ctx.fillRect(p.x,p.y,box,box); });
        let hX=snake[0].x, hY=snake[0].y;
        if(d=="LEFT") hX-=box; if(d=="UP") hY-=box; if(d=="RIGHT") hX+=box; if(d=="DOWN") hY+=box;
        if(hX==food.x && hY==food.y){ score++; food={x:Math.floor(Math.random()*19)*box, y:Math.floor(Math.random()*19)*box}; }
        else if(d) snake.pop();
        let h={x:hX, y:hY};
        if(hX<0||hX>=400||hY<0||hY>=400||(d && snake.some(z=>z.x==h.x&&z.y==h.y))){
            clearInterval(g); document.getElementById("m").style.display="block";
        }
        if(d) snake.unshift(h);
    }
    let g = setInterval(draw, 100);
    </script>
    """
    st.components.v1.html(SNAKE_HTML, height=550)
