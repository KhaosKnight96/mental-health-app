import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.graph_objects as go

# --- UI CONFIGURATION ---
st.set_page_config(page_title="Health Bridge Pro", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    .glass-panel {
        background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(12px);
        border-radius: 18px; padding: 25px; border: 1px solid rgba(255, 255, 255, 0.1);
        margin-bottom: 20px;
    }
    /* Animated Game Over Overlay */
    @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
    .game-over-screen {
        position: absolute; top: 0; left: 0; width: 100%; height: 100%;
        background: rgba(15, 23, 42, 0.95); display: flex; flex-direction: column;
        align-items: center; justify-content: center; z-index: 100;
        animation: fadeIn 0.5s ease-in; border-radius: 15px;
    }
    .restart-btn {
        background: linear-gradient(135deg, #6366F1, #A855F7);
        color: white; border: none; padding: 12px 24px; border-radius: 30px;
        font-weight: bold; cursor: pointer; transition: 0.3s;
    }
    .restart-btn:hover { transform: scale(1.1); box-shadow: 0 0 15px #6366F1; }
</style>
""", unsafe_allow_html=True)

# --- SESSION STATE ---
if "auth" not in st.session_state: st.session_state.auth = {"in": False, "mid": None, "role": "user"}
if "chats" not in st.session_state: st.session_state.chats = {"Cooper": [], "Clara": []}
if "active_game" not in st.session_state: st.session_state.active_game = None

# --- DATABASE & AI HANDLERS ---
def get_ai_response(agent_name, system_prompt, history):
    api_key = st.secrets.get("GROQ_API_KEY")
    if not api_key: return "⚠️ API Key not found in Secrets."
    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system_prompt}] + history[-5:]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Offline: {str(e)}"

def load_data(sheet):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet=sheet, ttl=0)
        df.columns = [str(c).strip().lower() for c in df.columns]
        return df
    except: return pd.DataFrame()

# --- LOGIN GATE ---
if not st.session_state.auth["in"]:
    st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge</h1>", unsafe_allow_html=True)
    with st.container():
        u = st.text_input("Member ID").strip().lower()
        p = st.text_input("Password", type="password")
        if st.button("Access Dashboard", use_container_width=True):
            users = load_data("Users")
            if not users.empty:
                match = users[users['memberid'].astype(str).str.lower() == u]
                if not match.empty and str(match.iloc[0]['password']) == p:
                    st.session_state.auth.update({"in": True, "mid": u, "role": str(match.iloc[0]['role']).lower()})
                    st.rerun()
            st.error("Invalid Credentials")
    st.stop()

# --- MAIN NAVIGATION ---
tabs = st.tabs(["🏠 Cooper", "🛋️ Clara", "🎮 Activity"])

with tabs[0]:
    st.markdown('<div class="glass-panel"><h3>🤖 Cooper</h3></div>', unsafe_allow_html=True)
    for m in st.session_state.chats["Cooper"]:
        with st.chat_message(m["role"]): st.write(m["content"])
    
    if p := st.chat_input("Chat with Cooper...", key="coop_msg"):
        st.session_state.chats["Cooper"].append({"role": "user", "content": p})
        ans = get_ai_response("Cooper", "You are Cooper, a helpful health coach.", st.session_state.chats["Cooper"])
        st.session_state.chats["Cooper"].append({"role": "assistant", "content": ans})
        st.rerun()

with tabs[1]:
    st.markdown('<div class="glass-panel"><h3>🧘‍♀️ Clara</h3></div>', unsafe_allow_html=True)
    for m in st.session_state.chats["Clara"]:
        with st.chat_message(m["role"]): st.write(m["content"])
    
    if p := st.chat_input("Chat with Clara...", key="clara_msg"):
        st.session_state.chats["Clara"].append({"role": "user", "content": p})
        ans = get_ai_response("Clara", "You are Clara, a data-driven health analyst.", st.session_state.chats["Clara"])
        st.session_state.chats["Clara"].append({"role": "assistant", "content": ans})
        st.rerun()

with tabs[2]:
    if st.session_state.active_game is None:
        c1, c2, c3 = st.columns(3)
        if c1.button("🐍 Snake"): st.session_state.active_game = "Snake"; st.rerun()
        if c2.button("🧠 Memory"): st.session_state.active_game = "Memory"; st.rerun()
        if c3.button("🧩 2048"): st.session_state.active_game = "2048"; st.rerun()
    else:
        st.button("⬅️ Back to Menu", on_click=lambda: st.session_state.update({"active_game": None}))
        
        # --- ENHANCED GAME CODE ---
        OVERLAY_JS = """
        function showGameOver(score) {
            document.getElementById('over').style.display = 'flex';
            if(score !== undefined) document.getElementById('fsc').innerText = 'Final Score: ' + score;
        }
        """

        if st.session_state.active_game == "Snake":
            st.components.v1.html(f"<script>{OVERLAY_JS}</script>" + """
            <div style="position:relative; width:300px; margin:auto; background:#1E293B; padding:15px; border-radius:20px; text-align:center; font-family:sans-serif;">
                <div id="over" class="game-over-screen" style="display:none; position:absolute; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.9); z-index:10; flex-direction:column; align-items:center; justify-content:center; border-radius:20px;">
                    <h1 style="color:#F87171; margin:0;">GAME OVER</h1>
                    <p id="fsc" style="color:white;"></p>
                    <button class="restart-btn" onclick="init()">TRY AGAIN</button>
                </div>
                <canvas id="s" width="270" height="270" style="background:#0F172A; border-radius:10px;"></canvas>
                <h3 style="color:#38BDF8;">Score: <span id="sc">0</span></h3>
            </div>
            <script>
                const c=document.getElementById("s"), x=c.getContext("2d");
                let b=15, snk, fd, d, gm;
                document.onkeydown=e=>{ let k=e.key; if(k.includes("Arrow")) e.preventDefault(); if(k=="ArrowLeft"&&d!='R')d='L'; if(k=="ArrowUp"&&d!='D')d='U'; if(k=="ArrowRight"&&d!='L')d='R'; if(k=="ArrowDown"&&d!='U')d='D';};
                function init(){ document.getElementById('over').style.display='none'; snk=[{x:135,y:135}]; fd={x:45,y:45}; d=null; clearInterval(gm); gm=setInterval(upd,130); }
                function upd(){
                    x.fillStyle="#0F172A"; x.fillRect(0,0,270,270); x.fillStyle="#F87171"; x.fillRect(fd.x,fd.y,b,b);
                    snk.forEach((p,i)=>{ x.fillStyle=i==0?"#38BDF8":"#334155"; x.fillRect(p.x,p.y,b,b); });
                    if(!d) return; let h={...snk[0]}; if(d=='L')h.x-=b; if(d=='U')h.y-=b; if(d=='R')h.x+=b; if(d=='D')h.y+=b;
                    if(h.x==fd.x&&h.y==fd.y){ fd={x:Math.floor(Math.random()*18)*b,y:Math.floor(Math.random()*18)*b}; } else snk.pop();
                    if(h.x<0||h.x>=270||h.y<0||h.y>=270||snk.some(s=>s.x==h.x&&s.y==h.y)){ clearInterval(gm); showGameOver(snk.length-1); }
                    snk.unshift(h); document.getElementById("sc").innerText=snk.length-1;
                }
                init();
            </script>
            <style>
                .restart-btn { background:#6366F1; color:white; border:none; padding:10px 20px; border-radius:20px; cursor:pointer; font-weight:bold; margin-top:10px; }
            </style>
            """, height=450)

        elif st.session_state.active_game == "Memory":
            st.components.v1.html("""
            <div style="position:relative; width:300px; margin:auto; background:#1E293B; padding:20px; border-radius:20px; text-align:center; font-family:sans-serif;">
                <div id="over" style="display:none; position:absolute; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.9); z-index:10; flex-direction:column; align-items:center; justify-content:center; border-radius:20px;">
                    <h1 style="color:#F472B6; margin:0;">WRONG TILE</h1>
                    <button id="rb" style="background:#F472B6; color:white; border:none; padding:10px 20px; border-radius:20px; cursor:pointer; font-weight:bold; margin-top:10px;">RESTART</button>
                </div>
                <h2 id="lv" style="color:#F472B6;">Level 1</h2>
                <div id="g" style="display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin:20px 0;"></div>
                <button id="st" style="width:100%; background:#38BDF8; color:white; border:none; padding:12px; border-radius:10px; cursor:pointer; font-weight:bold;">WATCH SEQUENCE</button>
            </div>
            <script>
                const g=document.getElementById("g"), lvD=document.getElementById("lv"), stB=document.getElementById("st"), ov=document.getElementById("over");
                let seq=[], user=[], lv=1, wait=false;
                function build(){ g.innerHTML=""; for(let i=0;i<9;i++){ let d=document.createElement("div"); d.style="height:65px;background:#334155;border-radius:10px;cursor:pointer"; d.onclick=()=>tap(i); g.appendChild(d); } }
                async function flash(i){ g.children[i].style.background="#F472B6"; await new Promise(r=>setTimeout(r,400)); g.children[i].style.background="#334155"; }
                stB.onclick=async()=>{
                    seq.push(Math.floor(Math.random()*9)); user=[]; wait=true; stB.disabled=true;
                    for(let i of seq){ await new Promise(r=>setTimeout(r,300)); await flash(i); }
                    wait=false; stB.innerText="YOUR TURN";
                };
                document.getElementById("rb").onclick=()=>{ ov.style.display='none'; seq=[]; lv=1; lvD.innerText="Level 1"; stB.disabled=false; stB.innerText="WATCH SEQUENCE"; build(); };
                async function tap(i){
                    if(wait) return; g.children[i].style.background="#38BDF8"; setTimeout(()=>g.children[i].style.background="#334155",200);
                    user.push(i);
                    if(user[user.length-1]!==seq[user.length-1]){ ov.style.display='flex'; }
                    else if(user.length===seq.length){ lv++; lvD.innerText="Level "+lv; wait=true; stB.disabled=false; stB.innerText="NEXT LEVEL"; }
                }
                build();
            </script>
            """, height=450)
