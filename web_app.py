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
    /* ADMIN ALERT STYLE */
    .admin-bubble { 
        background: #7F1D1D; color: #FEE2E2; margin: 15px auto; 
        border: 2px solid #EF4444; width: 90%; text-align: center; 
        font-weight: bold; border-radius: 10px;
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

def save_log(agent, role, content, is_admin_alert=False):
    try:
        stored_role = "admin_alert" if is_admin_alert else role
        sent_score = get_ai_sentiment(content) if role == "user" else 0
        
        new_row = pd.DataFrame([{
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "memberid": st.session_state.auth['mid'],
            "agent": agent, 
            "role": stored_role,
            "content": content,
            "sentiment": sent_score
        }])
        
        all_logs = get_data("ChatLogs")
        updated_logs = pd.concat([all_logs, new_row], ignore_index=True)
        conn.update(worksheet="ChatLogs", data=updated_logs)
    except: pass

def get_ai_response(agent, prompt, history):
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"].strip())
        users_df = get_data("Users")
        user_profile = users_df[users_df['memberid'] == st.session_state.auth['mid']].iloc[0]
        
        u_name = user_profile.get('name', 'Friend')
        u_age = user_profile.get('age', 'Unknown')
        u_gender = user_profile.get('gender', 'Unknown')
        u_bio = user_profile.get('bio', 'No bio provided.')

        logs_df = get_data("ChatLogs")
        user_logs = logs_df[logs_df['memberid'] == st.session_state.auth['mid']]
        personal_context = user_logs[user_logs['agent'] == agent].tail(20)['content'].to_string()
        
        recent_sent = user_logs.tail(10)['sentiment'].mean() if not user_logs.empty else 0
        hidden_vibe = "thriving" if recent_sent > 1.5 else ("struggling" if recent_sent < -1 else "doing okay")

        if agent == "Cooper":
            sys = f"You are Cooper, a warm male friend. User: {u_name}, Age: {u_age}, Bio: {u_bio}. Mood: {hidden_vibe}. Use their name occasionally. Context: {personal_context}"
        else:
            sys = f"You are Clara, a wise female friend. User: {u_name}, Bio: {u_bio}. Mood: {hidden_vibe}. Be observant. Context: {personal_context}"
        
        full_history = [{"role": "system", "content": sys}] + history[-10:] + [{"role": "user", "content": prompt}]
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=full_history)
        return res.choices[0].message.content
    except Exception as e: return f"AI Error: {e}"

# --- 3. LOGIN & SIGNUP GATE ---
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
            new_u = st.text_input("Member ID (Username)").strip().lower()
            cp1, cp2 = st.columns(2)
            new_p = cp1.text_input("Password", type="password")
            conf_p = cp2.text_input("Confirm Password", type="password")
            age = st.number_input("Age", 13, 120, 25)
            gen = st.selectbox("Gender", ["Male", "Female", "Non-binary", "Other"])
            bio = st.text_area("Bio")
            if st.button("Register"):
                if new_p != conf_p: st.error("Passwords do not match!")
                elif not new_name or not new_u: st.error("Name and ID required.")
                else:
                    users = get_data("Users")
                    new_row = pd.DataFrame([{"memberid": new_u, "password": new_p, "name": new_name, "role": "user", "age": age, "gender": gen, "bio": bio, "joined": datetime.now().strftime("%Y-%m-%d")}])
                    conn.update(worksheet="Users", data=pd.concat([users, new_row], ignore_index=True))
                    st.success("Account Created! Please Sign In.")
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
                if m["role"] == "user": div = "user-bubble"
                elif m["role"] == "admin_alert": 
                    div = "admin-bubble"
                    st.components.v1.html("<script>const a=new AudioContext(); const o=a.createOscillator(); const g=a.createGain(); o.frequency.value=523; g.gain.exponentialRampToValueAtTime(0.01, a.currentTime+0.5); o.connect(g); g.connect(a.destination); o.start(); o.stop(a.currentTime+0.5);</script>", height=0)
                else: div = "ai-bubble"
                st.markdown(f'<div class="chat-bubble {div}">{m["content"]}</div>', unsafe_allow_html=True)

        if p := st.chat_input(f"Speak with {agent}...", key=f"chat_{agent}"):
            logs.append({"role": "user", "content": p})
            save_log(agent, "user", p)
            with st.spinner("Thinking..."):
                res = get_ai_response(agent, p, logs)
            logs.append({"role": "assistant", "content": res})
            save_log(agent, "assistant", res)
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
        # Create clear sub-navigation
        admin_sub_tabs = st.tabs(["🔍 Interaction Explorer", "🚨 Send Alert", "📈 Mood Analytics", "⚠️ System Tools"])
        
        # Load all data once for the admin session
        logs_df = get_data("ChatLogs")
        users_df = get_data("Users")
        
        if not logs_df.empty:
            # Data Cleaning for Admin View
            logs_df['timestamp'] = pd.to_datetime(logs_df['timestamp'])
            
            # --- TAB 1: SEARCH & MULTI-FILTER ---
            with admin_sub_tabs[0]:
                st.subheader("📋 Global Chat Explorer")
                
                # Filter Sidebar/Columns
                col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                
                with col1:
                    search_q = st.text_input("🔍 Search Message Content", placeholder="Type keywords...")
                with col2:
                    u_filter = st.selectbox("User", ["All Users"] + sorted(list(logs_df['memberid'].unique())))
                with col3:
                    a_filter = st.selectbox("Agent", ["All Agents", "Cooper", "Clara"])
                with col4:
                    # Date Filter
                    date_range = st.date_input("Date Range", [logs_df['timestamp'].min(), logs_df['timestamp'].max()])

                # Apply Filtering Logic
                filtered_df = logs_df.copy()
                if search_q:
                    filtered_df = filtered_df[filtered_df['content'].str.contains(search_q, case=False, na=False)]
                if u_filter != "All Users":
                    filtered_df = filtered_df[filtered_df['memberid'] == u_filter]
                if a_filter != "All Agents":
                    filtered_df = filtered_df[filtered_df['agent'] == a_filter]
                if len(date_range) == 2:
                    start_dt, end_dt = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1]) + pd.Timedelta(days=1)
                    filtered_df = filtered_df[(filtered_df['timestamp'] >= start_dt) & (filtered_df['timestamp'] < end_dt)]

                # Display Results
                st.write(f"Showing **{len(filtered_df)}** interactions")
                st.dataframe(
                    filtered_df.sort_values('timestamp', ascending=False), 
                    use_container_width=True, 
                    hide_index=True,
                    column_config={
                        "sentiment": st.column_config.NumberColumn("Score", format="%d 🎭"),
                        "timestamp": st.column_config.DatetimeColumn("Time", format="D MMM, h:mm A"),
                    }
                )

            # --- TAB 2: BROADCAST ALERT ---
            with admin_sub_tabs[1]:
                st.subheader("🚨 Send Direct Admin Notice")
                st.info("This message will appear in RED with a notification sound for the specific user.")
                
                c_a, c_b = st.columns(2)
                with c_a:
                    target_u = st.selectbox("Select User", sorted(list(users_df['memberid'].unique())), key="alert_u")
                with c_b:
                    target_a = st.radio("Target Chat Room", ["Cooper", "Clara"], horizontal=True)
                
                alert_text = st.text_area("Alert Message", placeholder="E.g., Please check your email or 'Let's discuss your recent mood score'.")
                
                if st.button("🚀 Broadcast Alert", use_container_width=True):
                    if alert_text:
                        save_log(target_a, "admin_alert", alert_text, is_admin_alert=True)
                        st.success(f"Alert successfully sent to {target_u} in {target_a}'s room.")
                    else:
                        st.error("Please enter a message.")

            # --- TAB 3: MOOD ANALYTICS ---
            with admin_sub_tabs[2]:
                st.subheader("📈 Emotional Sentiment Tracking")
                
                # Only analyze user messages
                mood_df = logs_df[logs_df['role'] == 'user'].copy()
                
                if not mood_df.empty:
                    # Group by User or Time
                    chart_view = st.segmented_control("View By", ["Timeline", "User Comparison"], default="Timeline")
                    
                    if chart_view == "Timeline":
                        daily_mood = mood_df.groupby(mood_df['timestamp'].dt.date)['sentiment'].mean().reset_index()
                        fig = go.Figure(go.Scatter(x=daily_mood['timestamp'], y=daily_mood['sentiment'], mode='lines+markers', line=dict(color='#38BDF8')))
                        fig.update_layout(title="Average Community Mood Over Time", template="plotly_dark", yaxis=dict(range=[-5, 5]))
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        user_mood = mood_df.groupby('memberid')['sentiment'].mean().sort_values().reset_index()
                        fig = go.Figure(go.Bar(x=user_mood['memberid'], y=user_mood['sentiment'], marker_color='#6366F1'))
                        fig.update_layout(title="Average Mood Score by User", template="plotly_dark")
                        st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Not enough sentiment data to generate charts.")

            # --- TAB 4: SYSTEM TOOLS ---
            with admin_sub_tabs[3]:
                st.subheader("🛠️ Database Management")
                
                with st.expander("🗑️ Delete User History"):
                    del_u = st.selectbox("User to Wipe", ["Select User..."] + sorted(list(users_df['memberid'].unique())))
                    confirm_del = st.checkbox("I understand this cannot be undone.")
                    if st.button("Wipe Chat History", type="primary"):
                        if del_u != "Select User..." and confirm_del:
                            clean_logs = logs_df[logs_df['memberid'] != del_u]
                            conn.update(worksheet="ChatLogs", data=clean_logs)
                            st.success(f"All logs for {del_u} have been deleted.")
                            st.rerun()
                        else:
                            st.error("Please select a user and check the confirmation box.")
                
                with st.expander("👥 User Directory"):
                    st.dataframe(users_df, use_container_width=True)
        else:
            st.info("The ChatLogs database is currently empty.")
    else:
        st.warning("⚠️ Restricted Area: Admin Privileges Required.")

with tabs[4]:
    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()


