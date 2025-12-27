import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# --- 1. SETUP ---
st.set_page_config(page_title="Health Bridge", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None, "name": None}
if "chat_log" not in st.session_state: st.session_state.chat_log = []

def get_data():
    df = conn.read(worksheet="Users", ttl=0)
    df.columns = [str(c).strip() for c in df.columns]
    return df

# --- 2. LOGIN GATE ---
if not st.session_state.auth["logged_in"]:
    st.title("🧠 Health Bridge")
    u = st.text_input("Couple ID")
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        df = get_data()
        m = df[(df['Username'].astype(str) == u) & (df['Password'].astype(str) == p)]
        if not m.empty:
            st.session_state.auth.update({"logged_in": True, "cid": u, "name": m.iloc[0]['Fullname']})
            st.rerun()
    st.stop()

# --- 3. HIGH SCORE SYNC LOGIC (The Fix) ---
# This catches the score from the URL to avoid the DeltaGenerator error
params = st.query_params
if "score_to_sync" in params:
    try:
        incoming_score = int(params["score_to_sync"])
        df = get_data()
        user_idx = df.index[df['Username'].astype(str) == str(st.session_state.auth['cid'])][0]
        current_pb = int(pd.to_numeric(df.at[user_idx, 'HighScore'], errors='coerce') or 0)

        if incoming_score > current_pb:
            df.at[user_idx, 'HighScore'] = incoming_score
            conn.update(worksheet="Users", data=df)
            st.cache_data.clear()
            st.success(f"🔥 NEW RECORD: {incoming_score}!")
            st.balloons()
        else:
            st.info(f"Score synced: {incoming_score}. (Not a new record)")
    except Exception as e:
        st.error(f"Sync failed: {e}")
    
    st.query_params.clear() # Clean the URL
    st.rerun()

# --- 4. NAVIGATION ---
page = st.sidebar.radio("Navigation", ["Dashboard", "Zen Snake", "Zen AI Meditation"])

# --- 5. DASHBOARD (COOPER AI) ---
if page == "Dashboard":
    df = get_data()
    user_row = df[df['Username'].astype(str) == str(st.session_state.auth['cid'])]
    current_pb = int(pd.to_numeric(user_row['HighScore'].values[0], errors='coerce') or 0)
    
    st.title(f"Welcome, {st.session_state.auth['name']}")
    st.metric("Global High Score", f"{current_pb} pts")

    st.subheader("🤖 Chat with Cooper")
    container = st.container(height=300)
    for m in st.session_state.chat_log:
        with container.chat_message(m["role"]): st.markdown(m["content"])
    
    if prompt := st.chat_input("Message Cooper..."):
        st.session_state.chat_log.append({"role": "user", "content": prompt})
        res = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": "You are Cooper, a wellness assistant."}] + st.session_state.chat_log[-5:]
        ).choices[0].message.content
        st.session_state.chat_log.append({"role": "assistant", "content": res})
        st.rerun()

# --- 6. ZEN SNAKE (FIXED AUTO-SYNC) ---
elif page == "Zen Snake":
    st.title("🐍 Zen Snake")
    st.info("Play the game. When you finish, click the 'Sync Score' button that appears.")

    SNAKE_HTML = """
    <div style="display:flex; flex-direction:column; align-items:center; background:#1E293B; padding:20px; border-radius:15px;">
        <canvas id="s" width="400" height="400" style="border:4px solid #38BDF8; background:black; border-radius:10px;"></canvas>
        <div id="ui" style="display:none; margin-top:15px; text-align:center;">
            <h2 id="fs" style="color:white; font-family:sans-serif;"></h2>
            <button id="syncBtn" style="padding:12px 24px; background:#38BDF8; color:white; border:none; border-radius:8px; cursor:pointer; font-weight:bold; font-size:16px;">🚀 SYNC SCORE TO SHEETS</button>
        </div>
    </div>
    <script>
    const c=document.getElementById("s"), ctx=c.getContext("2d"), box=20;
    let score=0, d, snake=[{x:9*box, y:10*box}], food={x:5*box, y:5*box};

    document.getElementById("syncBtn").onclick = () => {
        const url = new URL(window.parent.location.href);
        url.searchParams.set('score_to_sync', score);
        window.parent.location.href = url.href;
    };

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
            food={x:Math.floor(Math.random()*19)*box, y:Math.floor(Math.random()*19)*box}; 
        } else if(d) snake.pop();
        let h={x:hX, y:hY};
        if(hX<0||hX>=400||hY<0||hY>=400||(d && snake.some(z=>z.x==h.x&&z.y==h.y))){
            clearInterval(g);
            document.getElementById("fs").innerText = "Final Score: " + score;
            document.getElementById("ui").style.display = "block";
        }
        if(d) snake.unshift(h);
    }
    let g = setInterval(draw, 100);
    </script>
    """
    st.components.v1.html(SNAKE_HTML, height=600)

# --- 7. ZEN AI (MEDITATION) ---
elif page == "Zen AI Meditation":
    st.title("🧘 Zen AI")
    if "zen_log" not in st.session_state: st.session_state.zen_log = []
    
    z_container = st.container(height=300)
    for m in st.session_state.zen_log:
        with z_container.chat_message(m["role"]): st.markdown(m["content"])
    
    if z_p := st.chat_input("Seek tranquility..."):
        st.session_state.zen_log.append({"role": "user", "content": z_p})
        z_res = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": "You are Zen AI, a peaceful guide."}] + st.session_state.zen_log[-3:]
        ).choices[0].message.content
        st.session_state.zen_log.append({"role": "assistant", "content": z_res})
        st.rerun()

# --- 8. LOGOUT ---
if st.sidebar.button("Logout"):
    st.session_state.auth = {"logged_in": False, "cid": None}
    st.rerun()
