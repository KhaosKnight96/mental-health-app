import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, date

# --- 1. SETTINGS & SESSION ---
st.set_page_config(page_title="Health Bridge Pro", layout="wide", initial_sidebar_state="collapsed")

if "auth" not in st.session_state: 
    st.session_state.auth = {"in": False, "mid": None, "role": "user"}

st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    .chat-bubble { padding: 12px 18px; border-radius: 18px; margin-bottom: 10px; max-width: 85%; line-height: 1.5; font-family: sans-serif; }
    .user-bubble { background: #1E40AF; color: white; margin-left: auto; border-bottom-right-radius: 2px; }
    .ai-bubble { background: #334155; color: white; margin-right: auto; border-bottom-left-radius: 2px; }
    .direct-bubble { background: #065F46; color: white; margin-right: auto; border-bottom-left-radius: 2px; border-left: 4px solid #10B981; }
    .avatar-pulse { width: 60px; height: 60px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 30px; margin: 0 auto 10px; background: linear-gradient(135deg, #38BDF8, #6366F1); box-shadow: 0 0 15px rgba(56, 189, 248, 0.4); }
    canvas { touch-action: none; border-radius: 15px; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATA CORE ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=5)
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
        all_logs = conn.read(worksheet="ChatLogs", ttl=0)
        conn.update(worksheet="ChatLogs", data=pd.concat([all_logs, new_row], ignore_index=True))
        st.cache_data.clear()
    except Exception as e: st.error(f"Save Error: {e}")

# --- 3. AI LOGIC ---
def get_ai_response(agent, prompt, history):
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"].strip())
        if agent == "Cooper":
            sys = "You are Cooper, a trusted male friend. Steady, loyal, supportive. Speak like a real person, not an assistant."
        else:
            sys = "You are Clara, a close female friend. Use casual, fluid, human speech (honestly, totally, I feel you). Be empathetic."
        
        full_history = [{"role": "system", "content": sys}] + history[-8:] + [{"role": "user", "content": prompt}]
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=full_history, temperature=0.8)
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
            st.rerun()
    st.stop()

# --- 5. INTERFACE ---
tabs = st.tabs(["🤝 Cooper", "✨ Clara", "📩 Messages", "🎮 Arcade", "🛠️ Admin", "🚪 Logout"])

# --- AI CHATS ---
for i, agent in enumerate(["Cooper", "Clara"]):
    with tabs[i]:
        st.markdown(f'<div class="avatar-pulse">{"🤝" if agent=="Cooper" else "✨"}</div>', unsafe_allow_html=True)
        all_logs = get_data("ChatLogs")
        ulogs = all_logs[(all_logs['memberid'].astype(str) == st.session_state.auth['mid']) & (all_logs['agent'] == agent)].tail(20)
        
        box = st.container(height=400, border=False)
        with box:
            for _, r in ulogs.iterrows():
                div = "user-bubble" if r['role'] == "user" else "ai-bubble"
                st.markdown(f'<div class="chat-bubble {div}">{r["content"]}</div>', unsafe_allow_html=True)
        
        if p := st.chat_input(f"Message {agent}...", key=f"ai_{agent}"):
            save_log(agent, "user", p)
            history = [{"role": r.role, "content": r.content} for _, r in ulogs.iterrows()]
            res = get_ai_response(agent, p, history)
            save_log(agent, "assistant", res)
            st.rerun()

# --- MESSAGING ---
with tabs[2]:
    st.subheader("📩 Direct Messages")
    u_df = get_data("Users")
    others = [str(uid) for uid in u_df['memberid'].unique() if str(uid) != st.session_state.auth['mid']]
    
    c1, c2 = st.columns([1, 3])
    with c1:
        recipient = st.radio("Friends List:", others)
    with c2:
        all_logs = get_data("ChatLogs")
        sent = all_logs[(all_logs['memberid'] == st.session_state.auth['mid']) & (all_logs['agent'] == f"Direct:{recipient}")]
        received = all_logs[(all_logs['memberid'] == recipient) & (all_logs['agent'] == f"Direct:{st.session_state.auth['mid']}")]
        chain = pd.concat([sent, received]).sort_values('timestamp')
        
        m_box = st.container(height=400, border=True)
        with m_box:
            for _, m in chain.iterrows():
                is_me = m['memberid'] == st.session_state.auth['mid']
                style = "user-bubble" if is_me else "direct-bubble"
                st.markdown(f'<div style="font-size:11px; opacity:0.7; text-align:{"right" if is_me else "left"}">{ "You" if is_me else recipient}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="chat-bubble {style}">{m["content"]}</div>', unsafe_allow_html=True)
        if p_msg := st.chat_input("Send private message..."):
            save_log(f"Direct:{recipient}", "user", p_msg); st.rerun()

# --- ARCADE RESTORED ---
with tabs[3]:
    game = st.selectbox("Choose a Game", ["Snake", "Memory Match", "Simon Says"])
    if game == "Snake":
        st.components.v1.html("""<div style="text-align:center; background:#1E293B; color:white; padding:15px; border-radius:20px;"><div id="scr">Score: 0</div><canvas id="snk" width="300" height="300" style="background:#0F172A; border:2px solid #38BDF8; margin:10px auto; display:block;"></canvas></div><script>const c=document.getElementById('snk'), x=c.getContext('2d'); let sn=[{x:150,y:150}], f={x:75,y:75}, d='R', sc=0, sx, sy; window.onkeydown=e=>{ if(e.key=='ArrowUp'&&d!='D')d='U'; if(e.key=='ArrowDown'&&d!='U')d='D'; if(e.key=='ArrowLeft'&&d!='R')d='L'; if(e.key=='ArrowRight'&&d!='L')d='R'; }; c.addEventListener('touchstart', e=>{sx=e.touches[0].clientX; sy=e.touches[0].clientY;}); c.addEventListener('touchend', e=>{ let dx=e.changedTouches[0].clientX-sx, dy=e.changedTouches[0].clientY-sy; if(Math.abs(dx)>Math.abs(dy)){ if(dx>30&&d!='L')d='R'; else if(dx<-30&&d!='R')d='L'; } else { if(dy>30&&d!='U')d='D'; else if(dy<-30&&d!='D')d='U'; } }); setInterval(()=>{ x.fillStyle='#0F172A'; x.fillRect(0,0,300,300); x.fillStyle='#F87171'; x.fillRect(f.x,f.y,15,15); x.fillStyle='#38BDF8'; sn.forEach(p=>x.fillRect(p.x,p.y,15,15)); let h={...sn[0]}; if(d=='L')h.x-=15; if(d=='U')h.y-=15; if(d=='R')h.x+=15; if(d=='D')h.y+=15; if(h.x==f.x&&h.y==f.y){sc++; f={x:Math.floor(Math.random()*19)*15,y:Math.floor(Math.random()*19)*15}} else sn.pop(); if(h.x<0||h.x>=300||h.y<0||h.y>=300){sn=[{x:150,y:150}]; sc=0; d='R';} sn.unshift(h); document.getElementById('scr').innerText="Score: "+sc; }, 130);</script>""", height=420)
    elif game == "Memory Match":
        st.components.v1.html("""<div style="text-align:center; background:#1E293B; padding:20px; border-radius:15px;"><div id="grid" style="display:grid; grid-template-columns:repeat(4, 1fr); gap:8px; max-width:300px; margin:auto;"></div></div><script>const icons=['❤️','❤️','⭐','⭐','🍀','🍀','💎','💎','🍎','🍎','🎈','🎈','🎨','🎨','⚡','⚡'].sort(()=>Math.random()-0.5); let act=[]; icons.forEach((ic)=>{ let c=document.createElement('div'); c.style="height:65px; background:#334155; border-radius:8px; display:flex; align-items:center; justify-content:center; font-size:24px; cursor:pointer;"; c.onclick=()=>{ if(act.length<2 && c.innerText==''){ c.innerText=ic; act.push({c,ic}); if(act.length==2){ if(act[0].ic==act[1].ic) act=[]; else setTimeout(()=>{ act[0].c.innerText=''; act[1].c.innerText=''; act=[]; }, 600); } } }; document.getElementById('grid').appendChild(c); });</script>""", height=380)
    elif game == "Simon Says":
        st.components.v1.html("""<div style="text-align:center; background:#1E293B; padding:20px; border-radius:15px;"><div id="stat" style="color:white; margin-bottom:15px;">Level 1</div><div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; max-width:240px; margin:auto;"><div id="0" onclick="tp(0)" style="height:80px; background:#EF4444; opacity:0.3; border-radius:10px;"></div><div id="1" onclick="tp(1)" style="height:80px; background:#3B82F6; opacity:0.3; border-radius:10px;"></div><div id="2" onclick="tp(2)" style="height:80px; background:#EAB308; opacity:0.3; border-radius:10px;"></div><div id="3" onclick="tp(3)" style="height:80px; background:#22C55E; opacity:0.3; border-radius:10px;"></div></div><button onclick="sq=[];nxt()" style="margin-top:15px; width:100%; padding:10px; background:#38BDF8; color:white; border:none; border-radius:8px;">START</button></div><script>let sq=[], u=[], lv=1; function nxt(){ u=[]; sq.push(Math.floor(Math.random()*4)); ply(); } function ply(){ let i=0; let t=setInterval(()=>{ fl(sq[i]); i++; if(i>=sq.length)clearInterval(t); }, 600); } function fl(id){ let e=document.getElementById(id); e.style.opacity='1'; setTimeout(()=>e.style.opacity='0.3', 300); } function tp(id){ fl(id); u.push(id); if(u[u.length-1]!==sq[u.length-1]){ alert('Over!'); sq=[]; lv=1; } else if(u.length==sq.length){ lv++; document.getElementById('stat').innerText='Level '+lv; setTimeout(nxt, 800); } }</script>""", height=400)

# --- ADMIN ---
with tabs[4]:
    if st.session_state.auth["role"] == "admin":
        st.subheader("🛡️ Log Explorer")
        l_df = get_data("ChatLogs")
        if not l_df.empty:
            l_df['ts_fix'] = pd.to_datetime(l_df['timestamp'], format='mixed', errors='coerce')
            with st.expander("🔍 Filters", expanded=True):
                c1, c2, c3 = st.columns(3)
                f_u = c1.selectbox("User", ["All"] + list(l_df['memberid'].unique()))
                f_a = c2.selectbox("Agent", ["All", "Cooper", "Clara", "Direct"])
                f_q = c3.text_input("Keyword")
            filt = l_df.copy()
            if f_u != "All": filt = filt[filt['memberid'].astype(str) == str(f_u)]
            if f_a != "All": filt = filt[filt['agent'].str.contains(f_a, case=False)]
            if f_q: filt = filt[filt['content'].str.contains(f_q, case=False)]
            st.dataframe(filt.drop(columns=['ts_fix']).sort_values('timestamp', ascending=False), use_container_width=True, hide_index=True)
            st.divider()
            target = st.selectbox("Purge User:", ["None"] + list(l_df['memberid'].unique()))
            if st.button("🔥 Delete History") and target != "None":
                new = l_df[l_df['memberid'].astype(str) != str(target)].drop(columns=['ts_fix'])
                conn.update(worksheet="ChatLogs", data=new); st.cache_data.clear(); st.rerun()
    else: st.error("Admin Required")

with tabs[5]:
    if st.button("Logout"): st.session_state.clear(); st.rerun()
