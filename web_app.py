import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime

# --- 1. CONFIG & THEME ---
st.set_page_config(page_title="Health Bridge Pro", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    .glass-panel {
        background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(15px);
        border-radius: 20px; border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 25px; margin-bottom: 20px;
    }
    .stButton>button { border-radius: 12px; height: 3em; width: 100%; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATA & AI HELPERS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data(ws):
    try:
        df = conn.read(worksheet=ws, ttl=0)
        df.columns = [str(c).strip().lower() for c in df.columns]
        return df
    except: return pd.DataFrame()

def talk_to_ai(agent_name, prompt, system_msg):
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"].strip())
        history = [{"role": "system", "content": system_msg}] + st.session_state.chats[agent_name][-3:]
        history.append({"role": "user", "content": prompt})
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=history)
        return res.choices[0].message.content
    except Exception as e: return f"AI Error: {e}"

# --- 3. SESSION STATE ---
if "auth" not in st.session_state: st.session_state.auth = {"in": False, "mid": None}
if "chats" not in st.session_state: st.session_state.chats = {"Cooper": [], "Clara": []}

# --- 4. LOGIN GATE ---
if not st.session_state.auth["in"]:
    st.title("🧠 Health Bridge Login")
    u = st.text_input("Member ID").strip().lower()
    p = st.text_input("Password", type="password")
    if st.button("Sign In"):
        df = get_data("Users")
        if not df.empty:
            m = df[(df['memberid'].astype(str).str.lower() == u) & (df['password'].astype(str) == p)]
            if not m.empty:
                st.session_state.auth.update({"in": True, "mid": u})
                st.rerun()
        st.error("Login Failed")
    st.stop()

# --- 5. MAIN TABS ---
t1, t2, t3, t4 = st.tabs(["🏠 Cooper", "🛋️ Clara", "🎮 Games", "🚪 Logout"])

with t1:
    st.markdown('<div class="glass-panel"><h3 style="text-align:center;">🤝 Cooper: Your Friend</h3></div>', unsafe_allow_html=True)
    for m in st.session_state.chats["Cooper"]:
        with st.chat_message(m["role"]): st.write(m["content"])
    if p := st.chat_input("Talk to Cooper..."):
        st.session_state.chats["Cooper"].append({"role": "user", "content": p})
        with st.chat_message("user"): st.write(p)
        res = talk_to_ai("Cooper", p, "You are a warm, empathetic friend.")
        st.session_state.chats["Cooper"].append({"role": "assistant", "content": res})
        st.rerun()

with t2:
    st.markdown('<div class="glass-panel"><h3 style="text-align:center;">📊 Clara: Insights</h3></div>', unsafe_allow_html=True)
    # Simple Logic: Clara looks at your Cooper chats too!
    if cp := st.chat_input("Ask Clara for a data review..."):
        st.session_state.chats["Clara"].append({"role": "user", "content": cp})
        res = talk_to_ai("Clara", cp, "You are a data analyst who reviews health logs.")
        st.session_state.chats["Clara"].append({"role": "assistant", "content": res})
        st.rerun()

with t3:
    st.subheader("🕹️ Health Bridge Arcade")
    game = st.radio("Select Game", ["Modern Snake", "Memory Match"], horizontal=True)
    
    if game == "Modern Snake":
        st.components.v1.html("""
        <div style="text-align:center; background:#1E293B; padding:20px; border-radius:20px;">
            <canvas id="s" width="300" height="300" style="border:2px solid #38BDF8; background:#0F172A;"></canvas>
            <h2 id="sc" style="color:#38BDF8; font-family:sans-serif;">Score: 0</h2>
        </div>
        <script>
            const c=document.getElementById("s"), x=c.getContext("2d");
            let b=15, s=[{x:150,y:150}], f={x:150,y:75}, d="R", sc=0;
            window.onkeydown=e=>{ if(e.key=="ArrowLeft"&&d!="R")d="L"; if(e.key=="ArrowUp"&&d!="D")d="U"; if(e.key=="ArrowRight"&&d!="L")d="R"; if(e.key=="ArrowDown"&&d!="U")d="D"; };
            function loop(){
                x.fillStyle="#0F172A"; x.fillRect(0,0,300,300); x.fillStyle="#F87171"; x.fillRect(f.x,f.y,b,b);
                s.forEach((p,i)=>{ x.fillStyle=i==0?"#38BDF8":"#334155"; x.fillRect(p.x,p.y,b,b); });
                let h={...s[0]}; if(d=="L")h.x-=b; if(d=="U")h.y-=b; if(d=="R")h.x+=b; if(d=="D")h.y+=b;
                if(h.x==f.x&&h.y==f.y){ f={x:Math.floor(Math.random()*20)*b,y:Math.floor(Math.random()*20)*b}; sc++; } else s.pop();
                if(h.x<0||h.x>=300||h.y<0||h.y>=300||s.some(z=>z.x==h.x&&z.y==h.y)){ s=[{x:150,y:150}]; d="R"; sc=0; }
                s.unshift(h); document.getElementById("sc").innerText="Score: "+sc;
            }
            setInterval(loop, 100);
        </script>
        """, height=450)
    
    elif game == "Memory Match":
        st.components.v1.html("""
        <div id="g" style="display:grid; grid-template-columns:repeat(4,1fr); gap:10px; max-width:320px; margin:auto; background:#1E293B; padding:20px; border-radius:20px;"></div>
        <script>
            const icons=['🍎','🍎','💎','💎','🚀','🚀','🌟','🌟','🔥','🔥','🍕','🍕','🌈','🌈','⚽','⚽'];
            let deck=icons.sort(()=>Math.random()-0.5), sel=[];
            const g=document.getElementById("g");
            deck.forEach((icon,i)=>{
                const card=document.createElement("div");
                card.style="height:60px; background:#334155; border-radius:8px; display:flex; align-items:center; justify-content:center; font-size:24px; cursor:pointer";
                card.onclick=()=>{
                    if(sel.length<2 && !card.innerText){
                        card.innerText=icon; card.style.background="#38BDF8"; sel.push({card,icon});
                        if(sel.length==2){
                            if(sel[0].icon==sel[1].icon) sel=[];
                            else setTimeout(()=>{ sel.forEach(s=>{s.card.innerText=""; s.card.style.background="#334155"}); sel=[]; },500);
                        }
                    }
                };
                g.appendChild(card);
            });
        </script>
        """, height=400)

with t4:
    if st.button("Confirm Logout"):
        st.session_state.clear()
        st.rerun()
