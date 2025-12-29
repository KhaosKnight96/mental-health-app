import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime

# --- 1. SETTINGS & SESSION ---
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
    .chat-bubble { padding: 12px 18px; border-radius: 18px; margin-bottom: 10px; max-width: 85%; line-height: 1.5; }
    .user-bubble { background: #1E40AF; color: white; margin-left: auto; border-bottom-right-radius: 2px; }
    .ai-bubble { background: #334155; color: white; margin-right: auto; border-bottom-left-radius: 2px; }
    .admin-bubble { background: #7F1D1D; color: #FEE2E2; margin: 15px auto; border: 2px solid #EF4444; text-align: center; font-weight: bold; border-radius: 10px; padding: 15px; }
    .avatar-pulse { width: 60px; height: 60px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 30px; margin: 0 auto 10px; background: linear-gradient(135deg, #38BDF8, #6366F1); box-shadow: 0 0 15px rgba(56, 189, 248, 0.4); }
    /* Mobile optimization for games */
    iframe { border-radius: 15px; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATA CORE ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=10)
def get_data(ws):
    try:
        df = conn.read(worksheet=ws, ttl=0)
        df.columns = [str(c).strip().lower() for c in df.columns]
        return df
    except: return pd.DataFrame()

def save_log(agent, role, content, target_mid=None, is_admin_alert=False):
    try:
        mid = target_mid if is_admin_alert else st.session_state.auth['mid']
        new_row = pd.DataFrame([{
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "memberid": mid, "agent": agent, "role": "admin_alert" if is_admin_alert else role,
            "content": content, "sentiment": 0
        }])
        all_logs = conn.read(worksheet="ChatLogs", ttl=0)
        conn.update(worksheet="ChatLogs", data=pd.concat([all_logs, new_row], ignore_index=True))
        st.cache_data.clear()
    except Exception as e: st.error(f"Save Error: {e}")

# --- 3. AI LOGIC ---
def get_ai_response(agent, prompt, history):
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"].strip())
        sys = f"You are {agent}, a supportive health companion. Be concise and empathetic."
        full_history = [{"role": "system", "content": sys}] + history[-10:] + [{"role": "user", "content": prompt}]
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=full_history)
        return res.choices[0].message.content
    except Exception as e: return f"AI Error: {e}"

# --- 4. AUTH ---
if not st.session_state.auth["in"]:
    st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge</h1>", unsafe_allow_html=True)
    u = st.text_input("Member ID").strip().lower()
    p = st.text_input("Password", type="password")
    if st.button("Sign In", use_container_width=True):
        users = get_data("Users")
        m = users[(users['memberid'].astype(str).str.lower() == u) & (users['password'].astype(str) == p)]
        if not m.empty:
            st.session_state.auth.update({"in": True, "mid": u, "role": str(m.iloc[0]['role']).lower()})
            all_logs = get_data("ChatLogs")
            if not all_logs.empty:
                ulogs = all_logs[all_logs['memberid'].astype(str) == u].tail(50)
                st.session_state.cooper_logs = [{"role": r.role, "content": r.content} for _,r in ulogs[ulogs.agent == "Cooper"].iterrows()]
                st.session_state.clara_logs = [{"role": r.role, "content": r.content} for _,r in ulogs[ulogs.agent == "Clara"].iterrows()]
            st.rerun()
    st.stop()

# --- 5. INTERFACE ---
tabs = st.tabs(["🏠 Cooper", "🛋️ Clara", "🎮 Arcade", "🛡️ Admin", "🚪 Logout"])

# --- CHAT ROOMS ---
for i, agent in enumerate(["Cooper", "Clara"]):
    with tabs[i]:
        st.markdown(f'<div class="avatar-pulse">{"🤝" if agent=="Cooper" else "📊"}</div>', unsafe_allow_html=True)
        logs = st.session_state.cooper_logs if agent == "Cooper" else st.session_state.clara_logs
        chat_box = st.container(height=450, border=False)
        with chat_box:
            for m in logs:
                div = "user-bubble" if m["role"] == "user" else ("admin-bubble" if m["role"] == "admin_alert" else "ai-bubble")
                st.markdown(f'<div class="chat-bubble {div}">{m["content"]}</div>', unsafe_allow_html=True)
        if p := st.chat_input(f"Message {agent}...", key=f"chat_{agent}"):
            logs.append({"role": "user", "content": p})
            save_log(agent, "user", p)
            res = get_ai_response(agent, p, logs)
            logs.append({"role": "assistant", "content": res})
            save_log(agent, "assistant", res)
            st.rerun()

# --- ARCADE (MOBILE + PC COMPATIBLE) ---
with tabs[2]:
    game = st.selectbox("Choose a Game", ["Snake (with D-Pad)", "Memory Match", "Flash Pattern (Simon Says)"])
    
    if game == "Snake (with D-Pad)":
        st.components.v1.html("""
        <div style="text-align:center; background:#1E293B; color:white; padding:15px; border-radius:20px; font-family:sans-serif;">
            <div id="score">Score: 0</div>
            <canvas id="game" width="300" height="300" style="border:3px solid #38BDF8; background:#0F172A; margin:10px auto; display:block; touch-action:none;"></canvas>
            <div style="display:grid; grid-template-columns: repeat(3, 60px); gap:10px; justify-content:center; margin-top:10px;">
                <button onclick="changeDir('U')" style="grid-column:2; height:50px; border-radius:10px; border:none; background:#38BDF8; color:white;">▲</button>
                <button onclick="changeDir('L')" style="grid-column:1; height:50px; border-radius:10px; border:none; background:#38BDF8; color:white;">◀</button>
                <button onclick="changeDir('D')" style="grid-column:2; height:50px; border-radius:10px; border:none; background:#38BDF8; color:white;">▼</button>
                <button onclick="changeDir('R')" style="grid-column:3; height:50px; border-radius:10px; border:none; background:#38BDF8; color:white;">▶</button>
            </div>
        </div>
        <script>
            const canvas=document.getElementById('game'), ctx=canvas.getContext('2d');
            let snake=[{x:150,y:150}], food={x:75,y:75}, d='R', score=0;
            function changeDir(newD){ if(newD=='U'&&d!='D')d='U'; if(newD=='D'&&d!='U')d='D'; if(newD=='L'&&d!='R')d='L'; if(newD=='R'&&d!='L')d='R'; }
            window.onkeydown=e=>{ if(e.key=='ArrowUp')changeDir('U'); if(e.key=='ArrowDown')changeDir('D'); if(e.key=='ArrowLeft')changeDir('L'); if(e.key=='ArrowRight')changeDir('R'); };
            setInterval(()=>{
                ctx.fillStyle='#0F172A'; ctx.fillRect(0,0,300,300);
                ctx.fillStyle='#F87171'; ctx.fillRect(food.x,food.y,15,15);
                ctx.fillStyle='#38BDF8'; snake.forEach(p=>ctx.fillRect(p.x,p.y,15,15));
                let h={...snake[0]}; if(d=='L')h.x-=15; if(d=='U')h.y-=15; if(d=='R')h.x+=15; if(d=='D')h.y+=15;
                if(h.x==food.x&&h.y==food.y){score++; food={x:Math.floor(Math.random()*20)*15,y:Math.floor(Math.random()*20)*15}} else snake.pop();
                if(h.x<0||h.x>=300||h.y<0||h.y>=300) { snake=[{x:150,y:150}]; score=0; d='R'; } // Wall death reset
                snake.unshift(h); document.getElementById('score').innerText="Score: "+score;
            }, 120);
        </script>
        """, height=550)

    elif game == "Memory Match":
        st.components.v1.html("""
        <div style="text-align:center; background:#1E293B; padding:15px; border-radius:20px; color:white; font-family:sans-serif;">
            <div id="msg">Find the pairs!</div>
            <div id="grid" style="display:grid; grid-template-columns: repeat(4, 60px); gap:10px; justify-content:center; margin-top:15px;"></div>
        </div>
        <script>
            const icons=['🍎','🍎','🍌','🍌','🍇','🍇','🍓','🍓','🍒','🍒','🍍','🍍','🥭','🥭','🥝','🥝'].sort(()=>Math.random()-0.5);
            const grid=document.getElementById('grid'); let flipped=[];
            icons.forEach((icon, i)=>{
                const card=document.createElement('div');
                card.style="width:60px; height:60px; background:#334155; border-radius:10px; display:flex; align-items:center; justify-content:center; font-size:24px; cursor:pointer;";
                card.onclick=()=>{
                    if(flipped.length<2 && card.innerText==''){
                        card.innerText=icon; flipped.push({card, icon});
                        if(flipped.length==2){
                            if(flipped[0].icon==flipped[1].icon) flipped=[];
                            else setTimeout(()=>{ flipped[0].card.innerText=''; flipped[1].card.innerText=''; flipped=[]; }, 700);
                        }
                    }
                };
                grid.appendChild(card);
            });
        </script>
        """, height=400)

    elif game == "Flash Pattern (Simon Says)":
        st.components.v1.html("""
        <div style="text-align:center; background:#1E293B; padding:15px; border-radius:20px; color:white; font-family:sans-serif;">
            <div id="lvl">Level: 1</div>
            <div style="display:grid; grid-template-columns:100px 100px; gap:15px; justify-content:center; margin-top:20px;">
                <div id="0" onclick="tap(0)" style="width:100px; height:100px; background:red; opacity:0.6; border-radius:15px;"></div>
                <div id="1" onclick="tap(1)" style="width:100px; height:100px; background:blue; opacity:0.6; border-radius:15px;"></div>
                <div id="2" onclick="tap(2)" style="width:100px; height:100px; background:yellow; opacity:0.6; border-radius:15px;"></div>
                <div id="3" onclick="tap(3)" style="width:100px; height:100px; background:green; opacity:0.6; border-radius:15px;"></div>
            </div>
            <button onclick="start()" style="margin-top:20px; padding:10px 30px; border-radius:10px; background:#38BDF8; color:white; border:none;">Start Game</button>
        </div>
        <script>
            let seq=[], user=[], level=1;
            function start(){ seq=[]; nextLvl(); }
            function nextLvl(){ user=[]; seq.push(Math.floor(Math.random()*4)); showSeq(); }
            function showSeq(){
                let i=0; const t = setInterval(()=>{
                    flash(seq[i]); i++; if(i>=seq.length) clearInterval(t);
                }, 600);
            }
            function flash(id){ 
                const el=document.getElementById(id); el.style.opacity='1'; 
                setTimeout(()=>el.style.opacity='0.6', 300);
            }
            function tap(id){
                flash(id); user.push(id);
                if(user[user.length-1] !== seq[user.length-1]){ alert('Game Over!'); start(); }
                else if(user.length === seq.length){ level++; document.getElementById('lvl').innerText='Level: '+level; setTimeout(nextLvl, 800); }
            }
        </script>
        """, height=500)

# --- 7. ADMIN TOOLS (RE-POLISHED) ---
with tabs[3]:
    if st.session_state.auth["role"] == "admin":
        sub = st.tabs(["🔍 Search Logs", "🚨 Broadcast", "🛠️ System"])
        l_df = get_data("ChatLogs")
        
        with sub[0]:
            c1, c2 = st.columns([2,1])
            s_q = c1.text_input("🔍 Keyword Search")
            u_f = c2.selectbox("User ID", ["All"] + list(l_df['memberid'].unique()) if not l_df.empty else ["All"])
            filt = l_df.copy()
            if u_f != "All": filt = filt[filt['memberid'].astype(str) == u_f]
            if s_q: filt = filt[filt['content'].str.contains(s_q, case=False, na=False)]
            st.dataframe(filt.sort_values('timestamp', ascending=False), use_container_width=True, hide_index=True)

        with sub[1]:
            users_list = get_data("Users")
            t_u = st.selectbox("Recipient", users_list['memberid'].unique())
            msg = st.text_area("Admin Alert Content")
            if st.button("🚀 Push Alert"):
                save_log("Cooper", "admin_alert", msg, target_mid=t_u, is_admin_alert=True)
                st.success("Alert sent to user.")

        with sub[2]:
            st.warning("Critical Operations")
            wipe_target = st.selectbox("Purge History for:", ["None"] + list(l_df['memberid'].unique()) if not l_df.empty else ["None"])
            if st.button("🔥 Permanently Delete Logs"):
                if wipe_target != "None":
                    new_logs = l_df[l_df['memberid'].astype(str) != str(wipe_target)]
                    conn.update(worksheet="ChatLogs", data=new_logs)
                    st.cache_data.clear()
                    st.success(f"History for {wipe_target} cleared.")
                    st.rerun()
    else: st.error("Admin Only")

with tabs[4]:
    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()
