import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime

# --- 1. CONFIG & MOBILE OPTIMIZATION ---
st.set_page_config(page_title="Health Bridge", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    [data-testid="stSidebar"] { background-color: #1E293B !important; border-right: 1px solid #334155; }
    .portal-card { background: #1E293B; padding: 25px; border-radius: 20px; border: 1px solid #334155; margin-bottom: 20px; }
    .stButton>button { border-radius: 12px; font-weight: 600; height: 3.5em; width: 100%; border: none; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- 2. CONNECTIONS & SESSION STATE ---
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

# --- 3. UNIVERSAL SIDEBAR ---
with st.sidebar:
    st.title("🌉 Bridge Menu")
    if st.session_state.auth["logged_in"]:
        st.write(f"👤 **{st.session_state.auth['name']}**")
        nav = st.selectbox("Go to:", ["Dashboard", "Caregiver Insights", "Games"])
        st.divider()
        if st.button("Logout"):
            st.session_state.auth = {"logged_in": False, "cid": None, "name": None}
            st.rerun()
    else:
        st.info("Please sign in to access the menu.")
        nav = "Login"

# --- 4. LOGIN / SIGNUP PAGE ---
if not st.session_state.auth["logged_in"]:
    st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge</h1>", unsafe_allow_html=True)
    tab_login, tab_signup = st.tabs(["🔐 Sign In", "📝 Create Account"])
    
    with tab_login:
        u = st.text_input("Couple ID", key="l_u")
        p = st.text_input("Password", type="password", key="l_p")
        if st.button("Sign In", type="primary"):
            df = get_data("Users")
            m = df[(df['Username'].astype(str) == u) & (df['Password'].astype(str) == p)]
            if not m.empty:
                st.session_state.auth.update({"logged_in": True, "cid": u, "name": m.iloc[0]['Fullname']})
                st.rerun()
            else: st.error("Invalid Credentials.")

    with tab_signup:
        new_name = st.text_input("Full Name")
        new_cid = st.text_input("Choose Couple ID")
        new_pwd = st.text_input("Choose Password", type="password")
        if st.button("Create Account"):
            df = get_data("Users")
            if not df.empty and new_cid in df['Username'].astype(str).values:
                st.error("ID already exists.")
            elif new_name and new_cid and new_pwd:
                new_user = pd.DataFrame([{"Fullname": new_name, "Username": new_cid, "Password": new_pwd}])
                conn.update(worksheet="Users", data=pd.concat([df, new_user], ignore_index=True))
                st.success("Account created! Now Sign In.")
    st.stop()

# --- 5. DASHBOARD ---
if nav == "Dashboard":
    st.title(f"Hi {st.session_state.auth['name']}! 👋")
    col_vibe, col_chat = st.columns([1, 1.5])
    with col_vibe:
        st.markdown('<div class="portal-card"><h3>⚡ Energy</h3>', unsafe_allow_html=True)
        energy_val = st.slider("Energy Scale", 1, 11, 6)
        st.markdown(f"<h1 style='text-align:center; font-size:60px;'>{ {1:'🚨', 2:'🪫', 3:'😫', 4:'🥱', 5:'🙁', 6:'😐', 7:'🙂', 8:'😊', 9:'⚡', 10:'🚀', 11:'☀️'}[energy_val] }</h1>", unsafe_allow_html=True)
        if st.button("💾 Sync"):
            try:
                new_row = pd.DataFrame([{"Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), "CoupleID": st.session_state.auth['cid'], "EnergyLog": energy_val}])
                conn.update(worksheet="Sheet1", data=pd.concat([conn.read(worksheet="Sheet1", ttl=0), new_row], ignore_index=True))
                st.success("Synced!")
            except Exception as e: st.error(f"Error: {e}")
        st.markdown('</div>', unsafe_allow_html=True)
    with col_chat:
        st.markdown('<div class="portal-card"><h3>💬 Cooper</h3>', unsafe_allow_html=True)
        for m in st.session_state.cooper_logs:
            with st.chat_message(m["role"]): st.write(m["content"])
        if p := st.chat_input("Hey Cooper..."):
            st.session_state.cooper_logs.append({"role": "user", "content": p})
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":"Warm friend Cooper."}]+st.session_state.cooper_logs[-5:]).choices[0].message.content
            st.session_state.cooper_logs.append({"role": "assistant", "content": res})
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- 6. CAREGIVER INSIGHTS ---
elif nav == "Caregiver Insights":
    st.title("📊 Energy Analytics")
    try:
        df_logs = conn.read(worksheet="Sheet1", ttl=0)
        df_plot = df_logs[df_logs['CoupleID'].astype(str) == str(st.session_state.auth['cid'])].copy()
        df_plot['Timestamp'] = pd.to_datetime(df_plot['Timestamp'])
        df_plot['Neutral Baseline'] = 6
        st.line_chart(df_plot.set_index('Timestamp')[['EnergyLog', 'Neutral Baseline']], color=["#38BDF8", "#F87171"])
    except: st.info("No data yet.")
    
    st.markdown('<div class="portal-card"><h3>🤖 Clara Analyst</h3>', unsafe_allow_html=True)
    for m in st.session_state.clara_logs:
        with st.chat_message(m["role"]): st.write(m["content"])
    if p := st.chat_input("Ask Clara..."):
        st.session_state.clara_logs.append({"role": "user", "content": p})
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":"Clinical analyst Clara."}]+st.session_state.clara_logs[-5:]).choices[0].message.content
        st.session_state.clara_logs.append({"role": "assistant", "content": res})
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# --- 7. GAMES ---
elif nav == "Games":
    game_type = st.radio("Game", ["Zen Snake", "Memory Match"], horizontal=True)
    if game_type == "Zen Snake":
        SNAKE_HTML = """
        <script src="https://cdnjs.cloudflare.com/ajax/libs/hammer.js/2.0.8/hammer.min.js"></script>
        <div class="game-container" style="display:flex; flex-direction:column; align-items:center; background:#1E293B; padding:20px; border-radius:15px;">
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
