import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.graph_objects as go

# --- 1. CONFIGURATION & THEME ---
st.set_page_config(page_title="Health Bridge", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    .glass-panel {
        background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(15px);
        border-radius: 25px; border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 25px; margin-bottom: 20px;
    }
    .stChatMessage { border-radius: 15px; margin-bottom: 10px; }
    [data-testid="stChatMessageUser"] { background-color: #1E3A8A !important; border-bottom-right-radius: 2px !important; }
    [data-testid="stChatMessageAssistant"] { background-color: #334155 !important; border-bottom-left-radius: 2px !important; }
    .avatar-pulse {
        width: 70px; height: 70px; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: 35px; margin: 0 auto 15px;
        background: linear-gradient(135deg, #38BDF8, #6366F1);
        box-shadow: 0 0 20px rgba(56, 189, 248, 0.4);
    }
</style>
""", unsafe_allow_html=True)

# --- 2. THE HARD-CODED KEY & CLIENT ---
# We use a helper to ensure the key is stripped of any hidden whitespace
MY_KEY = "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"

def get_ai_client():
    return Groq(api_key=MY_KEY.strip())

# --- 3. CONNECTIONS & SESSION STATE ---
conn = st.connection("gsheets", type=GSheetsConnection)

if "auth" not in st.session_state: st.session_state.auth = {"in": False, "mid": None, "role": "user"}
if "chats" not in st.session_state: st.session_state.chats = {"Cooper": [], "Clara": []}

def get_data(ws):
    try:
        df = conn.read(worksheet=ws, ttl=0)
        df.columns = [str(c).strip().lower() for c in df.columns]
        return df
    except: return pd.DataFrame()

def save_log(agent, role, content):
    try:
        new_row = pd.DataFrame([{
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "memberid": st.session_state.auth['mid'],
            "agent": agent, "role": role, "content": content
        }])
        conn.update(worksheet="ChatLogs", data=pd.concat([get_data("ChatLogs"), new_row], ignore_index=True))
    except: pass

# --- 4. LOGIN GATE ---
if not st.session_state.auth["in"]:
    st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge Portal</h1>", unsafe_allow_html=True)
    u = st.text_input("Member ID").strip().lower()
    p = st.text_input("Password", type="password")
    if st.button("Sign In"):
        users = get_data("Users")
        if not users.empty:
            m = users[(users['memberid'].astype(str).str.lower() == u) & (users['password'].astype(str) == p)]
            if not m.empty:
                st.session_state.auth.update({"in": True, "mid": u, "role": str(m.iloc[0]['role']).lower()})
                st.rerun()
        st.error("Invalid Credentials")
    st.stop()

# --- 5. APP LAYOUT ---
tabs = st.tabs(["🏠 Cooper", "🧘‍♀️ Clara", "🎮 Games", "🛡️ Admin"])

# --- 6. AGENT LOGIC (COOPER & CLARA) ---
for i, agent in enumerate(["Cooper", "Clara"]):
    with tabs[i]:
        color = "#38BDF8" if agent == "Cooper" else "#F472B6"
        st.markdown(f'<div class="glass-panel"><div class="avatar-pulse">{"🤖" if agent=="Cooper" else "🧘‍♀️"}</div><h3 style="text-align:center; color:{color};">{agent}</h3></div>', unsafe_allow_html=True)
        
        # Display Chat History
        for msg in st.session_state.chats[agent]:
            with st.chat_message(msg["role"]): st.write(msg["content"])
        
        if prompt := st.chat_input(f"Speak with {agent}...", key=f"in_{agent}"):
            st.session_state.chats[agent].append({"role": "user", "content": prompt})
            save_log(agent, "user", prompt)
            
            try:
                client = get_ai_client()
                sys_msg = "You are Cooper, a health coach." if agent == "Cooper" else "You are Clara, a health analyst."
                res = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "system", "content": sys_msg}] + st.session_state.chats[agent][-4:]
                ).choices[0].message.content
                
                st.session_state.chats[agent].append({"role": "assistant", "content": res})
                save_log(agent, "assistant", res)
            except Exception as e:
                st.error(f"AI Error: {e}")
            st.rerun()

# --- 7. GAMES ---
with tabs[2]:
    gt = st.radio("Activity", ["Snake", "Memory", "2048"], horizontal=True)
    
    # Common Sound Effects Utility
    JS_SOUND = "const actx=new(window.AudioContext||window.webkitAudioContext)(); function play(f,d){const o=actx.createOscillator(),g=actx.createGain(); o.frequency.value=f; g.gain.exponentialRampToValueAtTime(0.01,actx.currentTime+d); o.connect(g); g.connect(actx.destination); o.start(); o.stop(actx.currentTime+d);}"

    if gt == "Snake":
        st.components.v1.html(f"<script>{JS_SOUND}</script>" + """
        <div style="text-align:center; background:#1E293B; padding:20px; border-radius:20px;">
            <canvas id="snk" width="300" height="300" style="background:#0F172A; border:2px solid #38BDF8;"></canvas>
            <h2 id="sc" style="color:#38BDF8; font-family:sans-serif;">Score: 0</h2>
        </div>
        <script>
            const c=document.getElementById("snk"), x=c.getContext("2d");
            let b=15, s, f, d, g;
            function rst(){ s=[{x:150,y:150}]; f={x:Math.floor(Math.random()*20)*b,y:Math.floor(Math.random()*20)*b}; d=null; clearInterval(g); g=setInterval(upd,100); }
            window.onkeydown=e=>{ if(e.key=="ArrowLeft"&&d!="R")d="L"; if(e.key=="ArrowUp"&&d!="D")d="U"; if(e.key=="ArrowRight"&&d!="L")d="R"; if(e.key=="ArrowDown"&&d!="U")d="D"; };
            function upd(){
                x.fillStyle="#0F172A"; x.fillRect(0,0,300,300); x.fillStyle="#F87171"; x.fillRect(f.x,f.y,b,b);
                s.forEach((p,i)=>{ x.fillStyle=i==0?"#38BDF8":"#334155"; x.fillRect(p.x,p.y,b,b); });
                let h={...s[0]}; if(d=="L")h.x-=b; if(d=="U")h.y-=b; if(d=="R")h.x+=b; if(d=="D")h.y+=b;
                if(h.x==f.x&&h.y==f.y){ f={x:Math.floor(Math.random()*20)*b,y:Math.floor(Math.random()*20)*b}; play(600,0.1); } else if(d) s.pop();
                if(h.x<0||h.x>=300||h.y<0||h.y>=300||(d&&s.some(z=>z.x==h.x&&z.y==h.y))){ rst(); play(150,0.5); }
                if(d) s.unshift(h); document.getElementById("sc").innerText="Score: "+(s.length-1);
            }
            rst();
        </script>""", height=450)

    elif gt == "Memory":
        st.components.v1.html(f"<script>{JS_SOUND}</script>" + """
        <div style="background:#1E293B; padding:20px; border-radius:20px; text-align:center;">
            <div id="grid" style="display:grid; grid-template-columns:repeat(4,1fr); gap:10px; max-width:300px; margin:auto;"></div>
        </div>
        <script>
            const icons=['🍎','💎','🚀','🌟','🔥','🌈','🍕','⚽'];
            let deck=[...icons,...icons].sort(()=>Math.random()-0.5), flipped=[], matches=0;
            const g=document.getElementById("grid");
            deck.forEach((icon,i)=>{
                const card=document.createElement("div");
                card.style="height:60px; background:#334155; border-radius:8px; display:flex; align-items:center; justify-content:center; font-size:24px; cursor:pointer";
                card.onclick=()=>{
                    if(flipped.length<2 && !card.innerText){
                        card.innerText=icon; card.style.background="#38BDF8"; play(400+i*20,0.1); flipped.push({card,icon});
                        if(flipped.length==2){
                            if(flipped[0].icon==flipped[1].icon){ matches++; flipped=[]; if(matches==8) alert("Win!"); }
                            else { setTimeout(()=>{ flipped.forEach(f=>{f.card.innerText=""; f.card.style.background="#334155"}); flipped=[]; },500); }
                        }
                    }
                };
                g.appendChild(card);
            });
        </script>""", height=400)

# --- 8. ADMIN ---
with tabs[3]:
    if st.session_state.auth['role'] == "admin":
        st.dataframe(get_data("ChatLogs"), use_container_width=True)
    else: st.warning("Admin Only")

if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.rerun()
