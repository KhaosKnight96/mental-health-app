import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.graph_objects as go

# --- 1. CONFIG ---
st.set_page_config(page_title="Health Bridge", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    .portal-card { background: #1E293B; padding: 25px; border-radius: 20px; border: 1px solid #334155; margin-bottom: 20px; }
    .stButton>button { border-radius: 12px; font-weight: 600; height: 3.5em; width: 100%; border: none; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    .stTabs [data-baseweb="tab-list"] { gap: 20px; }
    .stTabs [data-baseweb="tab"] { background-color: #1E293B; border-radius: 10px; padding: 10px 20px; color: white; border: 1px solid #334155; }
    .stTabs [aria-selected="true"] { background-color: #38BDF8 !important; border: 1px solid #38BDF8 !important; }
</style>
""", unsafe_allow_html=True)

# --- 2. CONNECTIONS ---
conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None, "name": None}
if "cooper_logs" not in st.session_state: st.session_state.cooper_logs = []
if "clara_logs" not in st.session_state: st.session_state.clara_logs = []

def get_data(worksheet_name):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except:
        return pd.DataFrame(columns=["CoupleID", "Game", "Score"])

# --- 3. LOGIN GATE ---
if not st.session_state.auth["logged_in"]:
    st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge Portal</h1>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["🔐 Login", "📝 Sign Up"])
    with t1:
        u = st.text_input("Couple ID", key="l_u")
        p = st.text_input("Password", type="password", key="l_p")
        if st.button("Sign In"):
            df = get_data("Users")
            m = df[(df['Username'].astype(str) == u) & (df['Password'].astype(str) == p)]
            if not m.empty:
                st.session_state.auth.update({"logged_in": True, "cid": u, "name": m.iloc[0]['Fullname']})
                st.rerun()
            else: st.error("Invalid Credentials")
    with t2:
        n = st.text_input("Full Name")
        c = st.text_input("Couple ID")
        pw = st.text_input("Password", type="password")
        if st.button("Register"):
            df = get_data("Users")
            new_user = pd.DataFrame([{"Fullname": n, "Username": c, "Password": pw}])
            conn.update(worksheet="Users", data=pd.concat([df, new_user], ignore_index=True))
            st.success("Account created!")
    st.stop()

# --- 4. NAVIGATION ---
st.markdown(f"### Welcome, {st.session_state.auth['name']} ✨")
main_nav = st.tabs(["🏠 Dashboard", "📊 Caregiver Insights", "🎮 Games", "🚪 Logout"])

# (Dashboard and Caregiver sections remain identical to previous version)
with main_nav[0]:
    col1, col2 = st.columns([1, 1.5])
    with col1:
        st.markdown('<div class="portal-card"><h3>⚡ Energy</h3>', unsafe_allow_html=True)
        ev = st.slider("Energy", 1, 11, 6)
        if st.button("💾 Sync Energy"):
            new_row = pd.DataFrame([{"Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), "CoupleID": st.session_state.auth['cid'], "EnergyLog": ev}])
            conn.update(worksheet="Sheet1", data=pd.concat([conn.read(worksheet="Sheet1", ttl=0), new_row], ignore_index=True))
            st.success("Logged!")
        st.markdown('</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="portal-card"><h3>💬 Cooper</h3>', unsafe_allow_html=True)
        for m in st.session_state.cooper_logs:
            with st.chat_message(m["role"]): st.write(m["content"])
        if p := st.chat_input("Chat..."):
            st.session_state.cooper_logs.append({"role": "user", "content": p})
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":"Kind friend."}]+st.session_state.cooper_logs[-5:]).choices[0].message.content
            st.session_state.cooper_logs.append({"role": "assistant", "content": res})
            st.rerun()

with main_nav[1]:
    try:
        df_l = conn.read(worksheet="Sheet1", ttl=0)
        df_p = df_l[df_l['CoupleID'].astype(str) == str(st.session_state.auth['cid'])].copy()
        df_p['Timestamp'] = pd.to_datetime(df_p['Timestamp'])
        df_p = df_p.sort_values('Timestamp')
        fig = go.Figure()
        fig.add_shape(type="line", x0=df_p['Timestamp'].min(), y0=6, x1=df_p['Timestamp'].max(), y1=6, line=dict(color="White", width=2, dash="dash"))
        fig.add_trace(go.Scatter(x=df_p['Timestamp'], y=df_p['EnergyLog'], fill='tozeroy', fillcolor='rgba(248, 113, 113, 0.2)', line=dict(color='#38BDF8')))
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="white"))
        st.plotly_chart(fig, use_container_width=True)
    except: st.info("No data yet.")

# --- 7. GAMES TAB (FIXED HIGH SCORE) ---
with main_nav[2]:
    gt = st.radio("Choose Game", ["Modern Snake", "Memory Match"], horizontal=True)
    
    # Display Current Personal Best
    hs_df = get_data("HighScores")
    best_record = hs_df[(hs_df['CoupleID'].astype(str) == str(st.session_state.auth['cid'])) & (hs_df['Game'] == gt)]
    current_pb = int(best_record['Score'].values[0]) if not best_record.empty else 0
    st.subheader(f"🏆 Personal Best: {current_pb}")

    # Manual Sync for High Scores (Bridge between JS and Python)
    with st.expander("📝 Save New High Score"):
        new_score = st.number_input("Enter your score to save:", min_value=0, step=1)
        if st.button("Update Cloud Leaderboard"):
            if new_score > current_pb:
                if not best_record.empty:
                    hs_df.loc[(hs_df['CoupleID'].astype(str) == str(st.session_state.auth['cid'])) & (hs_df['Game'] == gt), 'Score'] = new_score
                else:
                    hs_df = pd.concat([hs_df, pd.DataFrame([{"CoupleID": st.session_state.auth['cid'], "Game": gt, "Score": new_score}])], ignore_index=True)
                conn.update(worksheet="HighScores", data=hs_df)
                st.success(f"New High Score of {new_score} saved!")
                st.rerun()
            else:
                st.warning("Only scores higher than your Personal Best can be saved.")

    if gt == "Modern Snake":
        SNAKE_HTML = """
        <div style="display:flex; flex-direction:column; align-items:center; background:#1E293B; padding:20px; border-radius:15px;">
            <canvas id="s" width="300" height="300" style="border:4px solid #38BDF8; background:#0F172A; border-radius:10px;"></canvas>
            <h2 id="st" style="color:#38BDF8; font-family:sans-serif;">Score: 0</h2>
            <button onclick="location.reload()" style="padding:10px 20px; background:#38BDF8; color:white; border:none; border-radius:5px; cursor:pointer;">Play Again</button>
        </div>
        <script>
        const canvas=document.getElementById("s"), ctx=canvas.getContext("2d"), box=15;
        let score=0, d, snake=[{x:10*box, y:10*box}], food={x:Math.floor(Math.random()*19)*box, y:Math.floor(Math.random()*19)*box};
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        function playS(f, t, d) { const o=audioCtx.createOscillator(); const g=audioCtx.createGain(); o.type=t; o.frequency.setValueAtTime(f, audioCtx.currentTime); g.gain.setValueAtTime(0.1, audioCtx.currentTime); o.connect(g); g.connect(audioCtx.destination); o.start(); o.stop(audioCtx.currentTime+d); }
        window.addEventListener("keydown", e => { if(e.code=="ArrowLeft" && d!="RIGHT") d="LEFT"; if(e.code=="ArrowUp" && d!="DOWN") d="UP"; if(e.code=="ArrowRight" && d!="LEFT") d="RIGHT"; if(e.code=="ArrowDown" && d!="UP") d="DOWN"; });
        function draw() {
            ctx.fillStyle="#0F172A"; ctx.fillRect(0,0,300,300);
            ctx.fillStyle = "#F87171"; ctx.beginPath(); ctx.arc(food.x+box/2, food.y+box/2, box/3, 0, Math.PI*2); ctx.fill();
            snake.forEach((p,i)=>{ ctx.fillStyle= i==0 ? "#38BDF8" : "rgba(56, 189, 248, "+(1-i/snake.length)+")"; ctx.fillRect(p.x, p.y, box-1, box-1); });
            let hX=snake[0].x, hY=snake[0].y;
            if(d=="LEFT") hX-=box; if(d=="UP") hY-=box; if(d=="RIGHT") hX+=box; if(d=="DOWN") hY+=box;
            if(hX==food.x && hY==food.y){ score++; document.getElementById("st").innerText="Score: "+score; playS(600, 'sine', 0.1); food={x:Math.floor(Math.random()*19)*box, y:Math.floor(Math.random()*19)*box}; } else if(d) snake.pop();
            let h={x:hX, y:hY};
            if(hX<0||hX>=300||hY<0||hY>=300||(d && snake.some(z=>z.x==h.x&&z.y==h.y))){ playS(150, 'sawtooth', 0.5); clearInterval(game); alert("Game Over! Score: " + score); }
            if(d) snake.unshift(h);
        }
        let game = setInterval(draw, 100);
        </script>
        """
        st.components.v1.html(SNAKE_HTML, height=500)
    else:
        # (Memory Match HTML remains same as previous version)
        st.info("Memory Match: Finish all pairs to see your score!")
