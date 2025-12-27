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
    .stTabs [data-baseweb="tab"] { 
        background-color: #1E293B; border-radius: 10px; padding: 10px 20px; color: white; border: 1px solid #334155;
    }
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

def get_data(worksheet_name="Users"):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except: return pd.DataFrame()

# --- 3. LOGIN / SIGNUP ---
if not st.session_state.auth["logged_in"]:
    st.markdown("<h1 style='text-align:center; mt-50px;'>🧠 Health Bridge Portal</h1>", unsafe_allow_html=True)
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

# --- 5. DASHBOARD TAB ---
with main_nav[0]:
    col1, col2 = st.columns([1, 1.5])
    with col1:
        st.markdown('<div class="portal-card"><h3>⚡ Energy</h3>', unsafe_allow_html=True)
        ev = st.slider("Energy", 1, 11, 6)
        st.markdown(f"<h1 style='text-align:center; font-size:60px;'>{ {1:'🚨', 2:'🪫', 3:'😫', 4:'🥱', 5:'🙁', 6:'😐', 7:'🙂', 8:'😊', 9:'⚡', 10:'🚀', 11:'☀️'}[ev] }</h1>", unsafe_allow_html=True)
        if st.button("💾 Sync"):
            new_row = pd.DataFrame([{"Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), "CoupleID": st.session_state.auth['cid'], "EnergyLog": ev}])
            conn.update(worksheet="Sheet1", data=pd.concat([conn.read(worksheet="Sheet1", ttl=0), new_row], ignore_index=True))
            st.success("Logged!")
        st.markdown('</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="portal-card"><h3>💬 Cooper</h3>', unsafe_allow_html=True)
        for m in st.session_state.cooper_logs:
            with st.chat_message(m["role"]): st.write(m["content"])
        if p := st.chat_input("Chat with Cooper...", key="coop_in"):
            st.session_state.cooper_logs.append({"role": "user", "content": p})
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":"Cooper, a kind friend."}]+st.session_state.cooper_logs[-5:]).choices[0].message.content
            st.session_state.cooper_logs.append({"role": "assistant", "content": res})
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- 6. CAREGIVER TAB (REWORKED CHART) ---
with main_nav[1]:
    try:
        df_l = conn.read(worksheet="Sheet1", ttl=0)
        df_p = df_l[df_l['CoupleID'].astype(str) == str(st.session_state.auth['cid'])].copy()
        df_p['Timestamp'] = pd.to_datetime(df_p['Timestamp'])
        df_p = df_p.sort_values('Timestamp')

        if not df_p.empty:
            st.markdown('<div class="portal-card"><h3>📉 Energy Analytics</h3>', unsafe_allow_html=True)
            
            # Using Plotly for advanced color splitting
            fig = go.Figure()

            # Neutral Baseline Line
            fig.add_shape(type="line", x0=df_p['Timestamp'].min(), y0=6, x1=df_p['Timestamp'].max(), y1=6,
                          line=dict(color="White", width=2, dash="dash"))

            # The Energy Line
            fig.add_trace(go.Scatter(x=df_p['Timestamp'], y=df_p['EnergyLog'],
                                     mode='lines+markers',
                                     line=dict(color='#38BDF8', width=3),
                                     name='Energy Level',
                                     fill='tozeroy',
                                     fillcolor='rgba(248, 113, 113, 0.2)')) # Red for bottom

            # Green overlay for top half
            fig.add_trace(go.Scatter(x=df_p['Timestamp'], 
                                     y=[max(6, y) for y in df_p['EnergyLog']],
                                     mode='lines',
                                     line=dict(width=0),
                                     fill='tonexty',
                                     fillcolor='rgba(74, 222, 128, 0.3)', # Green for top
                                     showlegend=False))

            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                              font=dict(color="white"), margin=dict(l=0, r=0, t=30, b=0),
                              yaxis=dict(range=[1, 11], gridcolor="#334155"),
                              xaxis=dict(showgrid=False))
            
            st.plotly_chart(fig, use_container_width=True)
            st.markdown('<p style="text-align:center; color:#94A3B8;">Neutral Line at 6.0</p></div>', unsafe_allow_html=True)
    except Exception as e: 
        st.info("No data yet.")
    
    st.markdown('<div class="portal-card"><h3>🤖 Clara Analyst</h3>', unsafe_allow_html=True)
    for m in st.session_state.clara_logs:
        with st.chat_message(m["role"]): st.write(m["content"])
    if p := st.chat_input("Ask Clara...", key="clar_in"):
        st.session_state.clara_logs.append({"role": "user", "content": p})
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":"Analyst Clara."}]+st.session_state.clara_logs[-5:]).choices[0].message.content
        st.session_state.clara_logs.append({"role": "assistant", "content": res})
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# --- 7. GAMES TAB ---
with main_nav[2]:
    gt = st.radio("Choose Game", ["Snake", "Memory"], horizontal=True)
    if gt == "Snake":
        SNAKE_HTML = """
        <script src="https://cdnjs.cloudflare.com/ajax/libs/hammer.js/2.0.8/hammer.min.js"></script>
        <div style="display:flex; flex-direction:column; align-items:center; background:#1E293B; padding:20px; border-radius:15px; touch-action:none;">
            <canvas id="s" width="300" height="300" style="border:4px solid #38BDF8; background:black; border-radius:10px;"></canvas>
            <h2 id="st" style="color:#38BDF8; font-family:sans-serif;">Score: 0</h2>
            <button onclick="location.reload()" style="width:100%; padding:15px; background:#38BDF8; color:white; border:none; border-radius:10px; font-weight:bold;">🔄 Restart</button>
        </div>
        <script>
        const canvas=document.getElementById("s"), ctx=canvas.getContext("2d"), box=20;
        let score=0, d, snake=[{x:7*box, y:7*box}], food={x:Math.floor(Math.random()*14+1)*box, y:Math.floor(Math.random()*14+1)*box};
        window.addEventListener("keydown", e => { if(["ArrowUp","ArrowDown","ArrowLeft","ArrowRight"].includes(e.code)) e.preventDefault();
            if(e.code=="ArrowLeft" && d!="RIGHT") d="LEFT"; if(e.code=="ArrowUp" && d!="DOWN") d="UP";
            if(e.code=="ArrowRight" && d!="LEFT") d="RIGHT"; if(e.code=="ArrowDown" && d!="UP") d="DOWN"; });
        const mc = new Hammer(canvas); mc.get('swipe').set({ direction: Hammer.DIRECTION_ALL });
        mc.on("swipeleft swipeup swiperight swipedown", e => { e.preventDefault();
            if(e.type=="swipeleft" && d!="RIGHT") d="LEFT"; if(e.type=="swipeup" && d!="DOWN") d="UP";
            if(e.type=="swiperight" && d!="LEFT") d="RIGHT"; if(e.type=="swipedown" && d!="UP") d="DOWN"; });
        function draw() { ctx.fillStyle="black"; ctx.fillRect(0,0,300,300);
            ctx.font = "18px serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
            ctx.fillText("🍅", food.x + box/2, food.y + box/2);
            snake.forEach((p,i)=>{ ctx.fillStyle=i==0?"#38BDF8":"white"; ctx.fillRect(p.x,p.y,box-1,box-1); });
            let hX=snake[0].x, hY=snake[0].y;
            if(d=="LEFT") hX-=box; if(d=="UP") hY-=box; if(d=="RIGHT") hX+=box; if(d=="DOWN") hY+=box;
            if(hX==food.x && hY==food.y){ score++; document.getElementById("st").innerText="Score: "+score; 
                food={x:Math.floor(Math.random()*14+1)*box, y:Math.floor(Math.random()*14+1)*box};
            } else if(d) snake.pop();
            let h={x:hX, y:hY};
            if(hX<0||hX>=300||hY<0||hY>=300||(d && snake.some(z=>z.x==h.x&&z.y==h.y))){
                ctx.fillStyle="white"; ctx.font="bold 24px Arial"; ctx.fillText("GAME OVER", 150, 150); clearInterval(game); }
            if(d) snake.unshift(h); }
        let game = setInterval(draw, 140);
        </script>
        """
        st.components.v1.html(SNAKE_HTML, height=520)
    else:
        st.write("Memory Match game loading...")

# --- 8. LOGOUT TAB ---
with main_nav[3]:
    if st.button("Confirm Logout"):
        st.session_state.auth = {"logged_in": False, "cid": None, "name": None}
        st.rerun()
