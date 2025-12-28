import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.graph_objects as go

# --- 1. SETTINGS & SESSION INITIALIZATION ---
st.set_page_config(page_title="Health Bridge Pro", layout="wide", initial_sidebar_state="collapsed")

# MUST BE AT TOP: Initialize session state to prevent AttributeErrors
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
    """Hidden AI call to score user sentiment (-5 to 5)"""
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
        # Append to existing logs
        all_logs = get_data("ChatLogs")
        updated_logs = pd.concat([all_logs, new_row], ignore_index=True)
        conn.update(worksheet="ChatLogs", data=updated_logs)
    except: pass

def get_ai_response(agent, prompt, history):
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"].strip())
        
        # 1. LOAD ALL USER LOGS
        logs_df = get_data("ChatLogs")
        user_logs = logs_df[logs_df['memberid'] == st.session_state.auth['mid']]
        
        # 2. ISOLATE MEMORY BY AGENT
        # We filter the logs to only include messages from this specific agent
        agent_specific_logs = user_logs[user_logs['agent'] == agent]
        
        # 🟢 DEEP MEMORY: Scan the last 50 user messages for this specific agent
        # This allows for long-term callbacks to previous conversations
        personal_context = agent_specific_logs[agent_specific_logs['role'] == 'user'].tail(50)['content'].to_string()
        
        # 3. HIDDEN DATA (Global Vibe)
        recent_sent = user_logs.tail(10)['sentiment'].mean() if not user_logs.empty else 0
        hidden_vibe = "thriving" if recent_sent > 1.5 else ("struggling" if recent_sent < -1 else "doing okay")

        # --- AGENT 1: COOPER (The Natural Friend) ---
        if agent == "Cooper":
            sys = f"""
            You are Cooper, a warm and deeply empathetic male friend. 
            
            DEEP MEMORY (Last 50 interactions with you): {personal_context}
            USER MOOD: {hidden_vibe}
            
            YOUR ROLE:
            - You have a long-term memory, but NEVER reference that you are 'remembering' something.
            - DO NOT use phrases like 'You mentioned earlier', 'I remember when you said', or 'Last time we talked'.
            - Instead, weave the details into your current thoughts naturally. 
              (e.g., instead of 'You said your sister is visiting', say 'I hope things with your sister are going smoothly today.')
            - Focus on the 'here and now' while subtly showing you understand their world.
            - If the user mood is {hidden_vibe}, match that energy without explaining why.
            """
        
        # --- AGENT 2: CLARA (Insight + Deep Memory) ---
        else:
            energy_df = get_data("Sheet1")
            user_energy = energy_df[energy_df['memberid'] == st.session_state.auth['mid']].tail(5).to_string()
            
            sys = f"""
            You are Clara, a wise and loyal female friend. 
            DEEP MEMORY (Last 50 interactions with you): {personal_context}
            ENERGY TRENDS: {user_energy}
            USER MOOD: {hidden_vibe}
            
            YOUR ROLE:
            - You are deeply observant and remember patterns over the last 50 messages.
            - Use this deep context to call out improvements or recurring struggles.
            - Be witty and loyal. Act as the friend who 'never forgets' what the user tells her.
            """
        
        # We send the recent chat history (the current conversation window) plus the system instructions
        full_history = [{"role": "system", "content": sys}] + history[-10:] + [{"role": "user", "content": prompt}]
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=full_history)
        return res.choices[0].message.content
    except Exception as e: return f"AI Error: {e}"
# --- 3. LOGIN GATE (OPTIMIZED LOAD) ---
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
                
                # Load persistent history (Limited to last 50 for performance)
                all_logs = get_data("ChatLogs")
                if not all_logs.empty:
                    # Filter for current user and sort by time
                    user_logs = all_logs[all_logs['memberid'].astype(str).str.lower() == u]
                    user_logs = user_logs.sort_values('timestamp')
                    
                    # 🟢 PERFORMANCE CAP: Only load the last 50 into the session
                    # This ensures the chat is fast and scrolls to bottom correctly
                    recent_history = user_logs.tail(50)
                    
                    st.session_state.cooper_logs = [{"role": r.role, "content": r.content} for _,r in recent_history[recent_history.agent == "Cooper"].iterrows()]
                    st.session_state.clara_logs = [{"role": r.role, "content": r.content} for _,r in recent_history[recent_history.agent == "Clara"].iterrows()]
                st.rerun()
            else: st.error("Invalid Credentials")
    st.stop()
# --- 4. NAVIGATION (WITH AUTO-SCROLL) ---
tabs = st.tabs(["🏠 Cooper", "🛋️ Clara", "🎮 Games", "🛡️ Admin", "🚪 Logout"])

# --- COOPER & CLARA (WHATSAPP STYLE WITH AUTO-SCROLL) ---
for i, agent in enumerate(["Cooper", "Clara"]):
    with tabs[i]:
        st.markdown(f'<div class="avatar-pulse">{"🤝" if agent=="Cooper" else "📊"}</div>', unsafe_allow_html=True)
        
        # Get the logs for the current agent
        logs = st.session_state.cooper_logs if agent == "Cooper" else st.session_state.clara_logs
        
        # 🟢 THE FIX: Setting a height creates a scrollable area. 
        # Streamlit automatically scrolls this to the bottom when the script reruns.
        chat_box = st.container(height=500, border=False)
        
        with chat_box:
            for m in logs:
                div_class = "user-bubble" if m["role"] == "user" else "ai-bubble"
                st.markdown(f'<div class="chat-bubble {div_class}">{m["content"]}</div>', unsafe_allow_html=True)
        
        # Input field at the bottom
        if p := st.chat_input(f"Speak with {agent}...", key=f"chat_{agent}"):
            # 1. Add user message to state and save
            logs.append({"role": "user", "content": p})
            save_log(agent, "user", p)
            
            # 2. Trigger the "Thinking" state
            with st.spinner(f"{agent} is thinking..."):
                res = get_ai_response(agent, p, logs)
            
            # 3. Add AI response to state and save
            logs.append({"role": "assistant", "content": res})
            save_log(agent, "assistant", res)
            
            # 4. Rerun to push the new bubbles into the container and snap to bottom
            st.rerun()

# --- 5. THE ARCADE (REPACKAGED) ---
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
    window.addEventListener("touchmove", e => { e.preventDefault(); }, {passive: false});
    </script>
    <style>
        .game-container { text-align:center; background:#1E293B; padding:20px; border-radius:20px; touch-action:none; position:relative; font-family:sans-serif; overflow:hidden; }
        .overlay { display:flex; position:absolute; top:0; left:0; width:100%; height:100%; background:rgba(15,23,42,0.95); flex-direction:column; align-items:center; justify-content:center; border-radius:20px; z-index:100; }
        .game-btn { padding:12px 25px; background:#38BDF8; border:none; border-radius:8px; color:white; font-weight:bold; cursor:pointer; margin-top:10px; }
        .score-board { background:#0F172A; padding:5px 15px; border-radius:8px; color:#38BDF8; display:inline-block; margin-bottom:10px; }
    </style>
    """
    if game_mode == "Snake":
        st.components.v1.html(JS_CORE + """<div class="game-container"><div class="score-board">Score: <span id="sn-s">0</span></div><canvas id="sn-c" width="300" height="300" style="background:#0F172A; border:2px solid #38BDF8; border-radius:10px;"></canvas><div id="sn-go" class="overlay" style="display:none;"><h1 style="color:#F87171;">GAME OVER</h1><button class="game-btn" onclick="sn_init()">Play Again</button></div></div><script>let sn, f, d, g, s, run=false; const c=document.getElementById("sn-c"), x=c.getContext("2d"), b=15; function sn_init(){ sn=[{x:150,y:150}]; f={x:150,y:75}; d="R"; s=0; run=true; document.getElementById("sn-go").style.display="none"; clearInterval(g); g=setInterval(sn_upd,120); } window.addEventListener("keydown", e=>{ if(e.key=="ArrowLeft"&&d!="R")d="L";if(e.key=="ArrowUp"&&d!="D")d="U";if(e.key=="ArrowRight"&&d!="L")d="R";if(e.key=="ArrowDown"&&d!="U")d="D";}); let tx, ty; c.ontouchstart=e=>{tx=e.touches[0].clientX; ty=e.touches[0].clientY;}; c.ontouchend=e=>{let dx=e.changedTouches[0].clientX-tx, dy=e.changedTouches[0].clientY-ty; if(Math.abs(dx)>Math.abs(dy)){if(dx>0&&d!="L")d="R";else if(dx<0&&d!="R")d="L";}else{if(dy>0&&d!="U")d="D";else if(dy<0&&d!="D")d="U";}}; function sn_upd(){ x.fillStyle="#0F172A"; x.fillRect(0,0,300,300); x.fillStyle="#F87171"; x.fillRect(f.x,f.y,b,b); sn.forEach((p,i)=>{x.fillStyle=i==0?"#38BDF8":"#334155"; x.fillRect(p.x,p.y,b,b);}); let h={...sn[0]}; if(d=="L")h.x-=b; if(d=="U")h.y-=b; if(d=="R")h.x+=b; if(d=="D")h.y+=b; if(h.x==f.x&&h.y==f.y){ s++; snd(600,"sine",0.1); f={x:Math.floor(Math.random()*19)*b,y:Math.floor(Math.random()*19)*b}; } else sn.pop(); if(h.x<0||h.x>=300||h.y<0||h.y>=300||sn.some(z=>z.x==h.x&&z.y==h.y)){ run=false; clearInterval(g); snd(100,"sawtooth",0.5); document.getElementById("sn-go").style.display="flex"; } if(run)sn.unshift(h); document.getElementById("sn-s").innerText=s; } sn_init();</script>""", height=520)
    elif game_mode == "2048":
        st.components.v1.html(JS_CORE + """<div class="game-container"><div class="score-board">Score: <span id="s2048">0</span></div><div id="grid2048" style="display:grid; grid-template-columns:repeat(4,1fr); gap:10px; background:#0F172A; padding:10px; border-radius:10px; position:relative; width:280px; margin:auto;"><div id="go2048" class="overlay" style="display:none;"><h1 style="color:#F87171;">GAME OVER</h1><button class="game-btn" onclick="init2048()">New Game</button></div></div></div><script>let board, score, run=false; const g=document.getElementById("grid2048"); function init2048(){ board=Array(16).fill(0); score=0; run=true; document.getElementById("go2048").style.display="none"; addT(); addT(); draw(); } function addT(){ let e=board.map((v,i)=>v===0?i:null).filter(v=>v!==null); if(e.length) board[e[Math.floor(Math.random()*e.length)]]=Math.random()<0.9?2:4; } function draw(){ [...g.querySelectorAll(".t")].forEach(t=>t.remove()); board.forEach(v=>{ const t=document.createElement("div"); t.className="t"; t.style=`height:60px; display:flex; align-items:center; justify-content:center; border-radius:5px; font-weight:bold; background:${getCol(v)}; color:${v>4?"#fff":"#0F172A"}`; t.innerText=v||""; g.appendChild(t); }); document.getElementById("s2048").innerText=score; } function getCol(v){ const c={0:"#334155", 2:"#eee4da", 4:"#ede0c8", 8:"#f2b179", 16:"#f59563", 32:"#f67c5f", 64:"#f65e3b", 128:"#edcf72", 256:"#edcc61"}; return c[v]||"#edc22e"; } function move(d){ if(!run) return; let p=JSON.stringify(board); for(let i=0;i<4;i++){ let r=[]; for(let j=0;j<4;j++) r.push(d=="L"||d=="R"?board[i*4+j]:board[j*4+i]); if(d=="R"||d=="D") r.reverse(); let a=r.filter(v=>v); for(let k=0;k<a.length-1;k++) if(a[k]==a[k+1]){a[k]*=2; score+=a[k]; a[k+1]=0; snd(440,"sine",0.05);} a=a.filter(v=>v); while(a.length<4) a.push(0); if(d=="R"||d=="D") a.reverse(); for(let j=0;j<4;j++) if(d=="L"||d=="R") board[i*4+j]=a[j]; else board[j*4+i]=a[j]; } if(p!=JSON.stringify(board)){ addT(); draw(); if(!board.includes(0)){ run=false; document.getElementById("go2048").style.display="flex"; } } } window.addEventListener("keydown", e=>{ if(e.key.includes("Arrow")) move(e.key[5][0]); }); init2048();</script>""", height=500)
    elif game_mode == "Memory Pattern":
        st.components.v1.html(JS_CORE + """<div class="game-container"><div class="score-board">Level: <span id="m-lvl">1</span></div><div id="m-board" style="display:grid; grid-template-columns:repeat(2,100px); gap:15px; justify-content:center; position:relative;"><div onclick="p(0)" id="b0" style="height:100px; background:#ef4444; opacity:0.6; border-radius:15px;"></div><div onclick="p(1)" id="b1" style="height:100px; background:#3b82f6; opacity:0.6; border-radius:15px;"></div><div onclick="p(2)" id="b2" style="height:100px; background:#22c55e; opacity:0.6; border-radius:15px;"></div><div onclick="p(3)" id="b3" style="height:100px; background:#eab308; opacity:0.6; border-radius:15px;"></div><div id="m-go" class="overlay"><h2 id="m-msg">Simon Says</h2><button class="game-btn" onclick="start()">Start Game</button></div></div></div><script>let seq=[], usr=[], lv=1, wait=true; const f=[261,329,392,523]; function start(){ seq=[]; lv=1; document.getElementById("m-lvl").innerText=lv; document.getElementById("m-go").style.display="none"; next(); } function next(){ usr=[]; wait=true; seq.push(Math.floor(Math.random()*4)); show(); } async function show(){ for(let i of seq){ await new Promise(r=>setTimeout(r,600)); flash(i); } wait=false; } function flash(i){ snd(f[i],"triangle",0.3); document.getElementById("b"+i).style.opacity="1"; setTimeout(()=>document.getElementById("b"+i).style.opacity="0.6",300); } function p(i){ if(wait)return; flash(i); usr.push(i); if(usr[usr.length-1]!=seq[usr.length-1]){ snd(100,"sawtooth",0.5); document.getElementById("m-msg").innerText="TRY AGAIN"; document.getElementById("m-go").style.display="flex"; } else if(usr.length==seq.length){ lv++; document.getElementById("m-lvl").innerText=lv; setTimeout(next,800); } } </script>""", height=450)
    elif game_mode == "Flash Match":
        st.components.v1.html(JS_CORE + """
        <div class="game-container">
            <div class="score-board">Level: <span id="f-lvl">1</span></div>
            <div id="f-grid" style="display:grid; grid-template-columns:repeat(4,1fr); gap:10px;"></div>
            <div id="f-go" class="overlay" style="display:none;">
                <h1>WELL DONE!</h1>
                <button class="game-btn" onclick="f_next()">Next Level</button>
            </div>
        </div>
        <script>
        let p=2, m=0, f=[], lvl=1; 
        const icons=['🍎','🚀','💎','🌟','🔥','🌈','🍕','⚽','🍀','👾','🦄','🐯'];
        
        function f_init(){
            m=0; f=[];
            document.getElementById("f-go").style.display="none";
            document.getElementById("f-lvl").innerText = lvl; // This updates the UI
            const g=document.getElementById("f-grid");
            g.innerHTML="";
            
            let d=[...icons.slice(0,p), ...icons.slice(0,p)].sort(()=>Math.random()-0.5);
            d.forEach(icon=>{
                const c=document.createElement("div");
                c.style="height:60px; background:#334155; border-radius:8px; display:flex; align-items:center; justify-content:center; font-size:24px; cursor:pointer";
                c.onclick=()=>{
                    if(f.length<2 && !c.innerText){
                        c.innerText=icon;
                        c.style.background="#38BDF8";
                        snd(400,"sine",0.1);
                        f.push({c,icon});
                        if(f.length==2){
                            if(f[0].icon==f[1].icon){
                                m++; f=[];
                                if(m==p){
                                    document.getElementById("f-go").style.display="flex";
                                }
                            } else {
                                setTimeout(()=>{
                                    f.forEach(x=>{x.c.innerText=""; x.c.style.background="#334155"});
                                    f=[];
                                },500);
                            }
                        }
                    }
                };
                g.appendChild(c);
            });
        }

        function f_next(){
            lvl++; // Increment the Level number
            p = Math.min(p + 1, 12); // Increase pairs for difficulty
            f_init();
        }

        f_init();
        </script>""", height=450)
# --- 6. ADMIN (THE BRIDGE & DATA MANAGEMENT) ---
with tabs[3]:
    if st.session_state.auth["role"] == "admin":
        st.sidebar.markdown("---")
        st.sidebar.subheader("🎯 Admin Focus")
        
        # Pull user list for the filter
        u_list = ["All Users"]
        users_df = get_data("Users")
        if not users_df.empty:
            u_list += sorted(list(users_df['memberid'].unique()))
            
        u_sel = st.sidebar.selectbox("Select Member to Inspect", u_list)
        admin_sub_tabs = st.tabs(["🔍 Chat Explorer", "📈 Mood Trends", "🎮 Game Overview", "⚠️ Management"])
        
        logs_df = get_data("ChatLogs")
        
        if not logs_df.empty:
            logs_df['timestamp'] = pd.to_datetime(logs_df['timestamp'], errors='coerce')

            with admin_sub_tabs[0]:
                st.subheader("📋 Interaction Logs")
                search_q = st.text_input("🔍 Search message content...", key="admin_search")
                f_df = logs_df.copy()
                if u_sel != "All Users": f_df = f_df[f_df['memberid'] == u_sel]
                if search_q: f_df = f_df[f_df['content'].str.contains(search_q, case=False, na=False)]
                st.dataframe(f_df.sort_values('timestamp', ascending=False), use_container_width=True, hide_index=True)

            with admin_sub_tabs[1]:
                st.subheader(f"📈 Sentiment Analysis: {u_sel}")
                sent_df = logs_df[logs_df['role'] == 'user'].copy()
                if u_sel != "All Users": sent_df = sent_df[sent_df['memberid'] == u_sel]
                if not sent_df.empty:
                    sent_df['sentiment'] = pd.to_numeric(sent_df['sentiment'], errors='coerce').fillna(0)
                    daily_mood = sent_df.groupby(sent_df['timestamp'].dt.date)['sentiment'].mean().reset_index()
                    fig = go.Figure(go.Scatter(x=daily_mood['timestamp'], y=daily_mood['sentiment'], mode='lines+markers', line=dict(color='#38BDF8')))
                    fig.update_layout(template="plotly_dark", yaxis=dict(range=[-5.5, 5.5], title="Score"))
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No sentiment data found.")

            with admin_sub_tabs[2]:
                st.subheader(f"🎮 Arcade Performance: {u_sel}")
                games = ["Snake", "2048", "Memory Pattern", "Flash Match"]
                g_df = logs_df[logs_df['agent'].isin(games)].copy()
                if u_sel != "All Users": g_df = g_df[g_df['memberid'] == u_sel]
                if not g_df.empty:
                    g_df['score'] = pd.to_numeric(g_df['content'], errors='coerce').fillna(0)
                    stats = g_df.groupby(['memberid', 'agent']).agg(High_Score=('score', 'max'), Total_Plays=('score', 'count')).reset_index()
                    st.dataframe(stats.sort_values('High_Score', ascending=False), use_container_width=True, hide_index=True)
                    fig_g = go.Figure()
                    for game in games:
                        g_data = stats[stats['agent'] == game]
                        if not g_data.empty:
                            fig_g.add_trace(go.Bar(x=g_data['memberid'], y=g_data['High_Score'], name=game))
                    fig_g.update_layout(template="plotly_dark", barmode='group')
                    st.plotly_chart(fig_g, use_container_width=True)
                else:
                    st.info("No game scores recorded yet.")

            with admin_sub_tabs[3]:
                st.subheader("⚠️ Data Management")
                if u_sel != "All Users":
                    if st.button(f"🗑️ Permanent Wipe: {u_sel}"):
                        new_logs = logs_df[logs_df['memberid'] != u_sel]
                        conn.update(worksheet="ChatLogs", data=new_logs)
                        st.success(f"Records for {u_sel} destroyed.")
                        st.rerun()
                else:
                    st.write("Select a specific user in the sidebar to enable deletion.")
        else:
            st.info("The ChatLogs sheet is currently empty.")
    else:
        st.warning("Admin Access Required")
# --- 7. LOGOUT ---
with tabs[4]:
    if st.button("Confirm Logout"):
        st.session_state.clear()
        st.rerun()
