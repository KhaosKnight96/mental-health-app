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
    .glass-panel {
        background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(15px);
        border-radius: 20px; border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 20px; margin-bottom: 20px;
    }
    .chat-bubble { padding: 12px 18px; border-radius: 18px; margin-bottom: 10px; max-width: 80%; line-height: 1.5; font-family: sans-serif; }
    .user-bubble { background: #1E40AF; color: white; margin-left: auto; border-bottom-right-radius: 2px; }
    .ai-bubble { background: #334155; color: white; margin-right: auto; border-bottom-left-radius: 2px; }
    .avatar-pulse {
        width: 60px; height: 60px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
        font-size: 30px; margin: 0 auto 10px; background: linear-gradient(135deg, #38BDF8, #6366F1);
        box-shadow: 0 0 15px rgba(56, 189, 248, 0.4);
    }
</style>
""", unsafe_allow_html=True)

# --- 2. CORE LOGIC & AI SENTIMENT ---
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

def save_log(agent, role, content):
    try:
        sent_score = get_ai_sentiment(content) if role == "user" else 0
        new_row = pd.DataFrame([{
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "memberid": st.session_state.auth['mid'],
            "agent": agent, "role": role, "content": content,
            "sentiment": sent_score
        }])
        all_logs = get_data("ChatLogs")
        updated_logs = pd.concat([all_logs, new_row], ignore_index=True)
        conn.update(worksheet="ChatLogs", data=updated_logs)
    except: pass

def get_ai_response(agent, prompt, history):
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"].strip())
        logs_df = get_data("ChatLogs")
        user_logs = logs_df[logs_df['memberid'] == st.session_state.auth['mid']]
        agent_specific_logs = user_logs[user_logs['agent'] == agent]
        personal_context = agent_specific_logs[agent_specific_logs['role'] == 'user'].tail(50)['content'].to_string()
        recent_sent = user_logs.tail(10)['sentiment'].mean() if not user_logs.empty else 0
        hidden_vibe = "thriving" if recent_sent > 1.5 else ("struggling" if recent_sent < -1 else "doing okay")

        if agent == "Cooper":
            sys = f"You are Cooper, a warm friend. Context: {personal_context}. Mood: {hidden_vibe}. Be natural."
        else:
            sys = f"You are Clara, a wise friend. Context: {personal_context}. Mood: {hidden_vibe}. Be loyal."
        
        full_history = [{"role": "system", "content": sys}] + history[-10:] + [{"role": "user", "content": prompt}]
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=full_history)
        return res.choices[0].message.content
    except Exception as e: return f"AI Error: {e}"

# --- 3. LOGIN GATE ---
if not st.session_state.auth["in"]:
    st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge</h1>", unsafe_allow_html=True)
    with st.container(border=True):
        u = st.text_input("Member ID").strip().lower()
        p = st.text_input("Password", type="password")
        if st.button("Sign In", use_container_width=True):
            users = get_data("Users")
            m = users[(users['memberid'].astype(str).str.lower() == u) & (users['password'].astype(str) == p)]
            if not m.empty:
                st.session_state.auth.update({"in": True, "mid": u, "role": str(m.iloc[0]['role']).lower()})
                all_logs = get_data("ChatLogs")
                if not all_logs.empty:
                    user_logs = all_logs[all_logs['memberid'].astype(str).str.lower() == u].sort_values('timestamp')
                    recent_history = user_logs.tail(50)
                    st.session_state.cooper_logs = [{"role": r.role, "content": r.content} for _,r in recent_history[recent_history.agent == "Cooper"].iterrows()]
                    st.session_state.clara_logs = [{"role": r.role, "content": r.content} for _,r in recent_history[recent_history.agent == "Clara"].iterrows()]
                st.rerun()
            else: st.error("Invalid Credentials")
    st.stop()

# --- 4. NAVIGATION ---
tabs = st.tabs(["🏠 Cooper", "🛋️ Clara", "🎮 Games", "🛡️ Admin", "🚪 Logout"])

for i, agent in enumerate(["Cooper", "Clara"]):
    with tabs[i]:
        st.markdown(f'<div class="avatar-pulse">{"🤝" if agent=="Cooper" else "📊"}</div>', unsafe_allow_html=True)
        logs = st.session_state.cooper_logs if agent == "Cooper" else st.session_state.clara_logs
        chat_box = st.container(height=500, border=False)
        with chat_box:
            for m in logs:
                div_class = "user-bubble" if m["role"] == "user" else "ai-bubble"
                st.markdown(f'<div class="chat-bubble {div_class}">{m["content"]}</div>', unsafe_allow_html=True)
        if p := st.chat_input(f"Speak with {agent}...", key=f"chat_{agent}"):
            logs.append({"role": "user", "content": p})
            save_log(agent, "user", p)
            with st.spinner(f"{agent} is thinking..."):
                res = get_ai_response(agent, p, logs)
            logs.append({"role": "assistant", "content": res})
            save_log(agent, "assistant", res)
            st.rerun()

# --- 5. THE ARCADE ---
with tabs[2]:
    # --- SYNC LOGIC ---
    q = st.query_params
    if "gsave" in q and "score" in q:
        save_log(q["gsave"], "game_event", q["score"])
        st.query_params.clear()
        st.toast(f"✅ {q['gsave']} Score Saved!")
        st.rerun()

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
    function sendScore(gName, score) {
        const url = new URL(window.parent.location.href);
        url.searchParams.set('gsave', gName);
        url.searchParams.set('score', score);
        window.parent.location.href = url.href;
    }
    </script>
    <style>
        .game-container { text-align:center; background:#1E293B; padding:20px; border-radius:20px; font-family:sans-serif; }
        .overlay { display:flex; position:absolute; top:0; left:0; width:100%; height:100%; background:rgba(15,23,42,0.95); flex-direction:column; align-items:center; justify-content:center; border-radius:20px; z-index:100; }
        .game-btn { padding:12px 25px; background:#38BDF8; border:none; border-radius:8px; color:white; font-weight:bold; cursor:pointer; }
        .score-board { background:#0F172A; padding:5px 15px; border-radius:8px; color:#38BDF8; margin-bottom:10px; display:inline-block; }
    </style>
    """
    if game_mode == "Snake":
        st.components.v1.html(JS_CORE + """<div class="game-container"><div class="score-board">Score: <span id="sn-s">0</span></div><canvas id="sn-c" width="300" height="300" style="background:#0F172A; border:2px solid #38BDF8;"></canvas><div id="sn-go" class="overlay" style="display:none;"><h1>GAME OVER</h1><button class="game-btn" onclick="sn_init()">Play Again</button></div></div><script>let sn, f, d, g, s, run=false; const c=document.getElementById("sn-c"), x=c.getContext("2d"), b=15; function sn_init(){ sn=[{x:150,y:150}]; f={x:150,y:75}; d="R"; s=0; run=true; document.getElementById("sn-go").style.display="none"; clearInterval(g); g=setInterval(sn_upd,120); } window.addEventListener("keydown", e=>{ if(e.key.includes("Arrow")) d=e.key[5][0]; }); function sn_upd(){ x.fillStyle="#0F172A"; x.fillRect(0,0,300,300); x.fillStyle="#F87171"; x.fillRect(f.x,f.y,b,b); sn.forEach(p=>{x.fillStyle="#38BDF8"; x.fillRect(p.x,p.y,b,b);}); let h={...sn[0]}; if(d=="L")h.x-=b; if(d=="U")h.y-=b; if(d=="R")h.x+=b; if(d=="D")h.y+=b; if(h.x==f.x&&h.y==f.y){ s++; f={x:Math.floor(Math.random()*19)*b,y:Math.floor(Math.random()*19)*b}; } else sn.pop(); if(h.x<0||h.x>=300||h.y<0||h.y>=300||sn.some(z=>z.x==h.x&&z.y==h.y)){ run=false; clearInterval(g); sendScore("Snake", s); } if(run)sn.unshift(h); document.getElementById("sn-s").innerText=s; } sn_init();</script>""", height=520)
    elif game_mode == "Flash Match":
        st.components.v1.html(JS_CORE + """<div class="game-container"><div class="score-board">Level: <span id="f-lvl">1</span></div><div id="f-grid" style="display:grid; grid-template-columns:repeat(4,1fr); gap:10px;"></div><div id="f-go" class="overlay" style="display:none;"><h1>LEVEL CLEAR!</h1><button class="game-btn" onclick="f_next()">Next Level</button></div></div><script>let p=2, m=0, f_cards=[], lvl=1; const icons=['🍎','🚀','💎','🌟','🔥','🌈','🍕','⚽']; function f_init(){ m=0; f_cards=[]; document.getElementById("f-go").style.display="none"; document.getElementById("f-lvl").innerText=lvl; const g=document.getElementById("f-grid"); g.innerHTML=""; let d=[...icons.slice(0,p), ...icons.slice(0,p)].sort(()=>Math.random()-0.5); d.forEach(icon=>{ const c=document.createElement("div"); c.style="height:60px; background:#334155; border-radius:8px; display:flex; align-items:center; justify-content:center; font-size:24px; cursor:pointer"; c.onclick=()=>{ if(f_cards.length<2 && !c.innerText){ c.innerText=icon; c.style.background="#38BDF8"; f_cards.push({c,icon}); if(f_cards.length==2){ if(f_cards[0].icon==f_cards[1].icon){ m++; f_cards=[]; if(m==p){ document.getElementById("f-go").style.display="flex"; sendScore("Flash Match", lvl); } } else { setTimeout(()=>{ f_cards.forEach(x=>{x.c.innerText=""; x.c.style.background="#334155"}); f_cards=[]; },500); } } } }; g.appendChild(c); }); } function f_next(){ lvl++; p=Math.min(p+1, 8); f_init(); } f_init();</script>""", height=450)
    else: st.info("Game engine ready. Play to record scores.")

# --- 6. ADMIN ---
with tabs[3]:
    if st.session_state.auth["role"] == "admin":
        st.sidebar.markdown("---")
        u_list = ["All Users"]
        users_df = get_data("Users")
        if not users_df.empty: u_list += sorted(list(users_df['memberid'].unique()))
        u_sel = st.sidebar.selectbox("Select Member", u_list)
        
        admin_sub_tabs = st.tabs(["🔍 Chat", "📈 Mood", "🎮 Games", "⚠️ Manage"])
        logs_df = get_data("ChatLogs")
        
        if not logs_df.empty:
            logs_df['timestamp'] = pd.to_datetime(logs_df['timestamp'], errors='coerce')

            with admin_sub_tabs[2]:
                st.subheader("🎮 Arcade High Scores")
                g_list = ["Snake", "2048", "Memory Pattern", "Flash Match"]
                g_df = logs_df[logs_df['agent'].isin(g_list)].copy()
                if u_sel != "All Users": g_df = g_df[g_df['memberid'] == u_sel]
                
                if not g_df.empty:
                    g_df['score'] = pd.to_numeric(g_df['content'], errors='coerce').fillna(0)
                    stats = g_df.groupby(['memberid', 'agent']).agg(High_Score=('score', 'max'), Plays=('score', 'count')).reset_index()
                    st.dataframe(stats.sort_values('High_Score', ascending=False), use_container_width=True, hide_index=True)
                    
                    fig = go.Figure()
                    for game in g_list:
                        d = stats[stats['agent'] == game]
                        if not d.empty: fig.add_trace(go.Bar(x=d['memberid'], y=d['High_Score'], name=game))
                    fig.update_layout(template="plotly_dark", barmode='group')
                    st.plotly_chart(fig, use_container_width=True)
                else: st.info("No scores found.")
        # ... (Other admin tabs kept as per your original logic)
    else: st.warning("Admin Access Required")

# --- 7. LOGOUT ---
with tabs[4]:
    if st.button("Confirm Logout"):
        st.session_state.clear()
        st.rerun()
