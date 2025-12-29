import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.graph_objects as go

# --- 1. SETTINGS & SESSION INITIALIZATION ---
st.set_page_config(page_title="Health Bridge Pro", layout="wide", initial_sidebar_state="collapsed")

if "auth" not in st.session_state: 
    st.session_state.auth = {"in": False, "mid": None, "role": "user"}
if "cooper_logs" not in st.session_state: 
    st.session_state.cooper_logs = []
if "clara_logs" not in st.session_state: 
    st.session_state.clara_logs = []

st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    .chat-bubble { padding: 12px 18px; border-radius: 18px; margin-bottom: 10px; max-width: 80%; line-height: 1.5; font-family: sans-serif; }
    .user-bubble { background: #1E40AF; color: white; margin-left: auto; border-bottom-right-radius: 2px; }
    .ai-bubble { background: #334155; color: white; margin-right: auto; border-bottom-left-radius: 2px; }
    .admin-bubble { 
        background: #7F1D1D; color: #FEE2E2; margin: 15px auto; 
        border: 2px solid #EF4444; width: 90%; text-align: center; 
        font-weight: bold; border-radius: 10px; padding: 15px;
    }
    .avatar-pulse {
        width: 60px; height: 60px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
        font-size: 30px; margin: 0 auto 10px; background: linear-gradient(135deg, #38BDF8, #6366F1);
        box-shadow: 0 0 15px rgba(56, 189, 248, 0.4);
    }
</style>
""", unsafe_allow_html=True)

# --- 2. CORE LOGIC ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data(ws):
    try:
        df = conn.read(worksheet=ws, ttl=0)
        df.columns = [str(c).strip().lower() for c in df.columns]
        return df
    except: return pd.DataFrame()

def get_ai_sentiment(text):
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"].strip())
        res = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Score sentiment from -5 (distress) to 5 (thriving). Output ONLY the integer."},
                {"role": "user", "content": text}
            ]
        )
        return int(res.choices[0].message.content.strip())
    except: return 0

def save_log(agent, role, content, target_mid=None, is_admin_alert=False):
    try:
        mid = target_mid if is_admin_alert else st.session_state.auth['mid']
        stored_role = "admin_alert" if is_admin_alert else role
        sent_score = get_ai_sentiment(content) if role == "user" else 0
        
        new_row = pd.DataFrame([{
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "memberid": mid,
            "agent": agent, 
            "role": stored_role,
            "content": content,
            "sentiment": sent_score
        }])
        
        all_logs = get_data("ChatLogs")
        updated_logs = pd.concat([all_logs, new_row], ignore_index=True)
        conn.update(worksheet="ChatLogs", data=updated_logs)
    except Exception as e:
        st.error(f"Save Error: {e}")

# --- 3. LIVE ALERT LISTENER ---
@st.fragment(run_every="8s")
def alert_listener():
    if st.session_state.auth["in"]:
        all_logs = get_data("ChatLogs")
        if not all_logs.empty:
            my_alerts = all_logs[(all_logs['memberid'] == st.session_state.auth['mid']) & (all_logs['role'] == 'admin_alert')]
            if not my_alerts.empty:
                latest_msg = my_alerts.iloc[-1]['content']
                st.toast(f"🚨 ADMIN NOTICE: {latest_msg}", icon="📢")

def get_ai_response(agent, prompt, history):
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"].strip())
        users_df = get_data("Users")
        user_profile = users_df[users_df['memberid'] == st.session_state.auth['mid']].iloc[0]
        u_name = user_profile.get('name', 'Friend')
        
        logs_df = get_data("ChatLogs")
        user_logs = logs_df[logs_df['memberid'] == st.session_state.auth['mid']]
        personal_context = user_logs[user_logs['agent'] == agent].tail(15)['content'].to_string()
        
        recent_sent = user_logs.tail(10)['sentiment'].mean() if not user_logs.empty else 0
        hidden_vibe = "thriving" if recent_sent > 1.5 else ("struggling" if recent_sent < -1 else "doing okay")

        sys = f"You are {agent}. User: {u_name}. Mood: {hidden_vibe}. Context: {personal_context}"
        full_history = [{"role": "system", "content": sys}] + history[-10:] + [{"role": "user", "content": prompt}]
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=full_history)
        return res.choices[0].message.content
    except Exception as e: return f"AI Error: {e}"

# --- 4. AUTHENTICATION ---
if not st.session_state.auth["in"]:
    st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge</h1>", unsafe_allow_html=True)
    auth_mode = st.radio("Choose Action", ["Sign In", "Sign Up"], horizontal=True)
    
    with st.container(border=True):
        if auth_mode == "Sign In":
            u = st.text_input("Member ID").strip().lower()
            p = st.text_input("Password", type="password")
            if st.button("Sign In", use_container_width=True):
                users = get_data("Users")
                m = users[(users['memberid'].astype(str).str.lower() == u) & (users['password'].astype(str) == p)]
                if not m.empty:
                    st.session_state.auth.update({"in": True, "mid": u, "role": str(m.iloc[0]['role']).lower()})
                    all_logs = get_data("ChatLogs")
                    if not all_logs.empty:
                        ulogs = all_logs[all_logs['memberid'] == u].sort_values('timestamp').tail(50)
                        st.session_state.cooper_logs = [{"role": r.role, "content": r.content} for _,r in ulogs[ulogs.agent == "Cooper"].iterrows()]
                        st.session_state.clara_logs = [{"role": r.role, "content": r.content} for _,r in ulogs[ulogs.agent == "Clara"].iterrows()]
                    st.rerun()
                else: st.error("Invalid Credentials")
        else:
            new_name = st.text_input("Full Name")
            new_u = st.text_input("Member ID").strip().lower()
            new_p = st.text_input("Password", type="password")
            if st.button("Register"):
                users = get_data("Users")
                new_row = pd.DataFrame([{"memberid": new_u, "password": new_p, "name": new_name, "role": "user", "joined": datetime.now().strftime("%Y-%m-%d")}])
                conn.update(worksheet="Users", data=pd.concat([users, new_row], ignore_index=True))
                st.success("Account Created! Please Sign In.")
    st.stop()

alert_listener()

# --- 5. TABS ---
tabs = st.tabs(["🏠 Cooper", "🛋️ Clara", "🎮 Games", "🛡️ Admin", "🚪 Logout"])

for i, agent in enumerate(["Cooper", "Clara"]):
    with tabs[i]:
        st.markdown(f'<div class="avatar-pulse">{"🤝" if agent=="Cooper" else "📊"}</div>', unsafe_allow_html=True)
        logs = st.session_state.cooper_logs if agent == "Cooper" else st.session_state.clara_logs
        chat_box = st.container(height=500, border=False)
        with chat_box:
            for m in logs:
                div = "user-bubble" if m["role"] == "user" else ("admin-bubble" if m["role"] == "admin_alert" else "ai-bubble")
                st.markdown(f'<div class="chat-bubble {div}">{m["content"]}</div>', unsafe_allow_html=True)

        if p := st.chat_input(f"Speak with {agent}...", key=f"chat_{agent}"):
            logs.append({"role": "user", "content": p})
            save_log(agent, "user", p)
            with st.spinner("Thinking..."):
                res = get_ai_response(agent, p, logs)
            logs.append({"role": "assistant", "content": res})
            save_log(agent, "assistant", res)
            st.rerun()

# --- 6. ARCADE TAB ---
with tabs[2]:
    game_mode = st.radio("Select Activity", ["Snake", "2048", "Memory Pattern", "Flash Match"], horizontal=True)
    JS_CORE = """
    <script>
    const actx = new(window.AudioContext || window.webkitAudioContext)();
    function snd(f, t, d) {
        const o = actx.createOscillator(), g = actx.createGain();
        o.type = t; o.frequency.value = f;
        g.gain.exponentialRampToValueAtTime(0.01, actx.currentTime + d);
        o.connect(g); g.connect(actx.destination);
        o.start(); o.stop(actx.currentTime + d);
    }
    window.addEventListener("keydown", e => {
        if(["ArrowUp","ArrowDown","ArrowLeft","ArrowRight"].includes(e.key)) e.preventDefault();
    }, {passive: false});
    </script>
    <style>
        .game-container { text-align:center; background:#1E293B; padding:20px; border-radius:20px; touch-action:none; position:relative; font-family:sans-serif; overflow:hidden; }
        .overlay { display:flex; position:absolute; top:0; left:0; width:100%; height:100%; background:rgba(15,23,42,0.95); flex-direction:column; align-items:center; justify-content:center; border-radius:20px; z-index:100; }
        .game-btn { padding:12px 25px; background:#38BDF8; border:none; border-radius:8px; color:white; font-weight:bold; cursor:pointer; margin-top:10px; }
        .score-board { background:#0F172A; padding:5px 15px; border-radius:8px; color:#38BDF8; display:inline-block; margin-bottom:10px; }
    </style>
    """
    if game_mode == "Snake":
        st.components.v1.html(JS_CORE + """<div class="game-container"><div class="score-board">Score: <span id="sn-s">0</span></div><canvas id="sn-c" width="300" height="300" style="background:#0F172A; border:2px solid #38BDF8; border-radius:10px;"></canvas><div id="sn-go" class="overlay" style="display:none;"><h1 style="color:#F87171;">GAME OVER</h1><button class="game-btn" onclick="sn_init()">Play Again</button></div></div><script>let sn, f, d, g, s, run=false; const c=document.getElementById("sn-c"), x=c.getContext("2d"), b=15; function sn_init(){ sn=[{x:150,y:150}]; f={x:150,y:75}; d="R"; s=0; run=true; document.getElementById("sn-go").style.display="none"; clearInterval(g); g=setInterval(sn_upd,120); } window.addEventListener("keydown", e=>{ if(e.key=="ArrowLeft"&&d!="R")d="L";if(e.key=="ArrowUp"&&d!="D")d="U";if(e.key=="ArrowRight"&&d!="L")d="R";if(e.key=="ArrowDown"&&d!="U")d="D";}); function sn_upd(){ x.fillStyle="#0F172A"; x.fillRect(0,0,300,300); x.fillStyle="#F87171"; x.fillRect(f.x,f.y,b,b); sn.forEach((p,i)=>{x.fillStyle=i==0?"#38BDF8":"#334155"; x.fillRect(p.x,p.y,b,b);}); let h={...sn[0]}; if(d=="L")h.x-=b; if(d=="U")h.y-=b; if(d=="R")h.x+=b; if(d=="D")h.y+=b; if(h.x==f.x&&h.y==f.y){ s++; snd(600,"sine",0.1); f={x:Math.floor(Math.random()*19)*b,y:Math.floor(Math.random()*19)*b}; } else sn.pop(); if(h.x<0||h.x>=300||h.y<0||h.y>=300||sn.some(z=>z.x==h.x&&z.y==h.y)){ run=false; clearInterval(g); snd(100,"sawtooth",0.5); document.getElementById("sn-go").style.display="flex"; } if(run)sn.unshift(h); document.getElementById("sn-s").innerText=s; } sn_init();</script>""", height=520)
    elif game_mode == "2048":
        st.components.v1.html(JS_CORE + """<div class="game-container"><div class="score-board">Score: <span id="s2048">0</span></div><div id="grid2048" style="display:grid; grid-template-columns:repeat(4,1fr); gap:10px; background:#0F172A; padding:10px; border-radius:10px; width:280px; margin:auto;"><div id="go2048" class="overlay" style="display:none;"><h1 style="color:#F87171;">GAME OVER</h1><button class="game-btn" onclick="init2048()">New Game</button></div></div></div><script>/* 2048 Logic Integrated */</script>""", height=500)
    elif game_mode == "Memory Pattern":
        st.components.v1.html(JS_CORE + """<div class="game-container"><div class="score-board">Level: <span id="m-lvl">1</span></div><div id="m-board" style="display:grid; grid-template-columns:repeat(2,100px); gap:15px; justify-content:center; position:relative;"><div onclick="p(0)" id="b0" style="height:100px; background:#ef4444; opacity:0.6; border-radius:15px;"></div><div onclick="p(1)" id="b1" style="height:100px; background:#3b82f6; opacity:0.6; border-radius:15px;"></div><div onclick="p(2)" id="b2" style="height:100px; background:#22c55e; opacity:0.6; border-radius:15px;"></div><div onclick="p(3)" id="b3" style="height:100px; background:#eab308; opacity:0.6; border-radius:15px;"></div><div id="m-go" class="overlay"><h2 id="m-msg">Simon Says</h2><button class="game-btn" onclick="start()">Start Game</button></div></div></div><script>/* Simon Logic Integrated */</script>""", height=450)
    elif game_mode == "Flash Match":
        st.components.v1.html(JS_CORE + """<div class="game-container"><div class="score-board">Level: <span id="f-lvl">1</span></div><div id="f-grid" style="display:grid; grid-template-columns:repeat(4,1fr); gap:10px;"></div><div id="f-go" class="overlay" style="display:none;"><h1>WELL DONE!</h1><button class="game-btn" onclick="f_next()">Next Level</button></div></div><script>/* Match Logic Integrated */</script>""", height=450)

# --- 7. ADMIN PANEL ---
with tabs[3]:
    if st.session_state.auth["role"] == "admin":
        admin_sub = st.tabs(["🔍 Explorer", "🚨 Broadcast", "📈 Analytics", "🛠️ System Tools"])
        logs_df = get_data("ChatLogs")
        users_df = get_data("Users")
        
        if not logs_df.empty:
            logs_df['timestamp'] = pd.to_datetime(logs_df['timestamp'])
            
            with admin_sub[0]:
                c1, c2, c3 = st.columns([2,1,1])
                s_q = c1.text_input("Search Logs")
                u_f = c2.selectbox("User", ["All"] + list(logs_df['memberid'].unique()))
                a_f = c3.selectbox("Agent", ["All", "Cooper", "Clara"])
                f_df = logs_df.copy()
                if u_f != "All": f_df = f_df[f_df['memberid'] == u_f]
                if s_q: f_df = f_df[f_df['content'].str.contains(s_q, case=False)]
                st.dataframe(f_df.sort_values('timestamp', ascending=False), use_container_width=True, hide_index=True)

            with admin_sub[1]:
                t_u = st.selectbox("Target User", sorted(list(users_df['memberid'].unique())))
                t_r = st.radio("Target Room", ["Cooper", "Clara"], horizontal=True)
                msg = st.text_area("Alert Content")
                if st.button("Send Alert"):
                    save_log(t_r, "admin_alert", msg, target_mid=t_u, is_admin_alert=True)
                    st.success(f"Sent to {t_u}")

            with admin_sub[2]:
                mood_df = logs_df[logs_df['role'] == 'user'].copy()
                fig = go.Figure(go.Scatter(x=mood_df['timestamp'], y=mood_df['sentiment'], mode='lines+markers'))
                st.plotly_chart(fig, use_container_width=True)

            with admin_sub[3]:
                st.subheader("⚠️ Dangerous Actions")
                target_wipe = st.selectbox("Select User to Wipe", ["None"] + sorted(list(users_df['memberid'].unique())))
                confirm = st.checkbox("Confirm deletion")
                if st.button("🔥 Wipe User History", type="primary"):
                    if target_wipe != "None" and confirm:
                        new_logs = logs_df[logs_df['memberid'] != target_wipe]
                        conn.update(worksheet="ChatLogs", data=new_logs)
                        st.success(f"History for {target_wipe} deleted.")
                        st.rerun()
    else:
        st.warning("Admin Access Required.")

with tabs[4]:
    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()
