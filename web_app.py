import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# --- SETTINGS ---
st.set_page_config(page_title="Health Bridge", layout="wide")

# --- CONNECTIONS ---
conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None}

def fetch_latest_data():
    """Forces a fresh read from Google Sheets bypasses all caching."""
    df = conn.read(worksheet="Users", ttl=0)
    df.columns = [str(c).strip() for c in df.columns]
    # Ensure HighScore exists and is a number
    if 'HighScore' not in df.columns:
        df['HighScore'] = 0
    df['HighScore'] = pd.to_numeric(df['HighScore'], errors='coerce').fillna(0).astype(int)
    return df

# --- THE SYNC ENGINE (TRIGGERED BY URL) ---
params = st.query_params
if "update_score" in params and st.session_state.auth["logged_in"]:
    new_score = int(float(params["update_score"]))
    cid = str(st.session_state.auth['cid'])
    
    # Fetch fresh data
    df = fetch_latest_data()
    user_idx = df.index[df['Username'].astype(str) == cid]
    
    if not user_idx.empty:
        idx = user_idx[0]
        current_best = int(df.at[idx, 'HighScore'])
        
        if new_score > current_best:
            df.at[idx, 'HighScore'] = new_score
            try:
                # PUSH TO GOOGLE
                conn.update(worksheet="Users", data=df)
                st.cache_data.clear() # Wipe Streamlit's local memory
                st.success(f"Successfully saved {new_score} to Google Sheets!")
            except Exception as e:
                st.error(f"WRITE FAILED: Ensure your service account email is an 'Editor' on the Google Sheet. Error: {e}")
    
    # Clear URL and refresh UI
    st.query_params.clear()
    st.rerun()

# --- APP UI ---
if not st.session_state.auth["logged_in"]:
    # Login Logic
    st.title("🧠 Health Bridge Login")
    u = st.text_input("Couple ID")
    p = st.text_input("Password", type="password")
    if st.button("Enter"):
        df = fetch_latest_data()
        match = df[(df['Username'].astype(str) == u) & (df['Password'].astype(str) == p)]
        if not match.empty:
            st.session_state.auth.update({"logged_in": True, "cid": u})
            st.rerun()
    st.stop()

# --- NAVIGATION ---
page = st.sidebar.radio("Navigation", ["Dashboard", "Play Snake"])

if page == "Dashboard":
    df = fetch_latest_data()
    row = df[df['Username'].astype(str) == str(st.session_state.auth['cid'])]
    score = row['HighScore'].values[0] if not row.empty else 0
    st.title("🏠 Dashboard")
    st.metric("Your Current High Score", f"{score} pts")
    if st.button("Force Refresh Data"):
        st.cache_data.clear()
        st.rerun()

elif page == "Play Snake":
    st.title("🐍 Zen Snake")
    st.info("Beat your score and click 'Save & Exit' to update the Google Sheet.")
    
    SNAKE_HTML = """
    <div style="display:flex; flex-direction:column; align-items:center;">
        <canvas id="game" width="400" height="400" style="border:5px solid #38BDF8; background:#000;"></canvas>
        <div id="menu" style="display:none; text-align:center; margin-top:20px;">
            <h1 style="color:white;">GAME OVER</h1>
            <button id="save" style="padding:15px 30px; font-size:20px; background:#38BDF8; color:white; border:none; border-radius:10px; cursor:pointer;">💾 SAVE & EXIT</button>
        </div>
    </div>
    <script>
    const c=document.getElementById("game"), ctx=c.getContext("2d"), box=20;
    let score=0, d, snake=[{x:9*box, y:10*box}], food={x:Math.floor(Math.random()*19)*box, y:Math.floor(Math.random()*19)*box};

    document.getElementById("save").onclick = () => {
        const url = new URL(window.parent.location.href);
        url.searchParams.set('update_score', score);
        window.parent.location.href = url.href;
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
            clearInterval(g); document.getElementById("menu").style.display="block";
        }
        if(d) snake.unshift(h);
    }
    let g = setInterval(draw, 100);
    </script>
    """
    st.components.v1.html(SNAKE_HTML, height=600)
