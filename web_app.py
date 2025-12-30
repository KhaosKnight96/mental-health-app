import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, date

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
    .avatar-pulse { width: 60px; height: 60px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 30px; margin: 0 auto 10px; background: linear-gradient(135deg, #38BDF8, #6366F1); box-shadow: 0 0 15px rgba(56, 189, 248, 0.4); }
    canvas { touch-action: none; border-radius: 15px; }
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

def save_log(agent, role, content):
    try:
        new_row = pd.DataFrame([{
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "memberid": st.session_state.auth['mid'], "agent": agent, "role": role,
            "content": content
        }])
        all_logs = conn.read(worksheet="ChatLogs", ttl=0)
        conn.update(worksheet="ChatLogs", data=pd.concat([all_logs, new_row], ignore_index=True))
        st.cache_data.clear()
    except Exception as e: st.error(f"Save Error: {e}")

# --- 3. AI LOGIC ---
# --- 3. REFINED AI LOGIC (FRIEND DYNAMIC) ---
def get_ai_response(agent, prompt, history):
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"].strip())
        
        # --- PERSONALITY DEFINITIONS ---
        if agent == "Cooper":
            # Cooper: The Trusted Male Friend
            sys_prompt = (
                "You are Cooper, a trusted and reliable male friend. "
                "Your vibe is steady, loyal, and supportive. You speak like a real person, "
                "not an assistant. You give solid advice when asked, but mostly you're "
                "just there to listen and have your friend's back. Avoid being overly "
                "formal or 'bot-like'. Speak with warmth and maturity."
            )
        else: 
            # Clara: The Fluid Female Friend
            sys_prompt = (
                "You are Clara, a close female friend. Your speech is fluid, natural, "
                "and very human-like. You use modern, casual language (e.g., 'totally', "
                "'I feel you', 'honestly') but remain deeply empathetic. "
                "You aren't a 'zen master'; you're a girl just chatting with a friend. "
                "Be expressive, use a bit of humor if appropriate, and keep the "
                "conversation flowing naturally without being repetitive."
            )

        # We keep the history short to maintain responsiveness
        full_history = [
            {"role": "system", "content": sys_prompt}
        ] + history[-8:] + [{"role": "user", "content": prompt}]
        
        res = client.chat.completions.create(
            model="llama-3.3-70b-versatile", 
            messages=full_history,
            temperature=0.8, # Slightly higher temperature for more fluid, "human" speech
        )
        return res.choices[0].message.content
    except Exception as e: 
        return f"AI Error: {e}"

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
                # Filter logs specifically for the logged-in user to populate initial chat history
                ulogs = all_logs[all_logs['memberid'].astype(str) == u].tail(50)
                st.session_state.cooper_logs = [{"role": r.role, "content": r.content} for _,r in ulogs[ulogs.agent == "Cooper"].iterrows()]
                st.session_state.clara_logs = [{"role": r.role, "content": r.content} for _,r in ulogs[ulogs.agent == "Clara"].iterrows()]
            st.rerun()
    st.stop()

# --- 5. INTERFACE ---
tabs = st.tabs(["🤝 Cooper", "🧘 Clara", "🎮 Arcade", "🛠️ Admin", "🚪 Logout"])

for i, agent in enumerate(["Cooper", "Clara"]):
    with tabs[i]:
        st.markdown(f'<div class="avatar-pulse">{"🤝" if agent=="Cooper" else "🧘"}</div>', unsafe_allow_html=True)
        logs = st.session_state.cooper_logs if agent == "Cooper" else st.session_state.clara_logs
        chat_box = st.container(height=450, border=False)
        with chat_box:
            for m in logs:
                div = "user-bubble" if m["role"] == "user" else "ai-bubble"
                st.markdown(f'<div class="chat-bubble {div}">{m["content"]}</div>', unsafe_allow_html=True)
        if p := st.chat_input(f"Message {agent}...", key=f"chat_{agent}"):
            logs.append({"role": "user", "content": p}); save_log(agent, "user", p)
            res = get_ai_response(agent, p, logs)
            logs.append({"role": "assistant", "content": res}); save_log(agent, "assistant", res)
            st.rerun()

# --- 6. ARCADE (KEYBOARD + SWIPE) ---
with tabs[2]:
    game = st.selectbox("Choose a Game", ["Snake", "Memory Match", "Simon Says"])
    
    if game == "Snake":
        st.components.v1.html("""
        <div style="text-align:center; background:#1E293B; color:white; padding:15px; border-radius:20px; font-family:sans-serif;">
            <div id="scr">Score: 0</div>
            <canvas id="snk" width="300" height="300" style="background:#0F172A; border:2px solid #38BDF8; margin:10px auto; display:block;"></canvas>
        </div>
        <script>
            const c=document.getElementById('snk'), x=c.getContext('2d');
            let sn=[{x:150,y:150}], f={x:75,y:75}, d='R', sc=0, sx, sy;
            window.onkeydown=e=>{
                if(e.key=='ArrowUp'&&d!='D')d='U'; if(e.key=='ArrowDown'&&d!='U')d='D';
                if(e.key=='ArrowLeft'&&d!='R')d='L'; if(e.key=='ArrowRight'&&d!='L')d='R';
            };
            c.addEventListener('touchstart', e=>{sx=e.touches[0].clientX; sy=e.touches[0].clientY;}, false);
            c.addEventListener('touchend', e=>{
                let dx=e.changedTouches[0].clientX-sx, dy=e.changedTouches[0].clientY-sy;
                if(Math.abs(dx)>Math.abs(dy)){ if(dx>30&&d!='L')d='R'; else if(dx<-30&&d!='R')d='L'; }
                else { if(dy>30&&d!='U')d='D'; else if(dy<-30&&d!='D')d='U'; }
            }, false);
            setInterval(()=>{
                x.fillStyle='#0F172A'; x.fillRect(0,0,300,300); x.fillStyle='#F87171'; x.fillRect(f.x,f.y,15,15);
                x.fillStyle='#38BDF8'; sn.forEach(p=>x.fillRect(p.x,p.y,15,15));
                let h={...sn[0]}; if(d=='L')h.x-=15; if(d=='U')h.y-=15; if(d=='R')h.x+=15; if(d=='D')h.y+=15;
                if(h.x==f.x&&h.y==f.y){sc++; f={x:Math.floor(Math.random()*19)*15,y:Math.floor(Math.random()*19)*15}} else sn.pop();
                if(h.x<0||h.x>=300||h.y<0||h.y>=300){sn=[{x:150,y:150}]; sc=0; d='R';}
                sn.unshift(h); document.getElementById('scr').innerText="Score: "+sc;
            }, 130);
        </script>""", height=420)

    elif game == "Memory Match":
        st.components.v1.html("""
        <div style="text-align:center; background:#1E293B; padding:20px; border-radius:15px;"><div id="grid" style="display:grid; grid-template-columns:repeat(4, 1fr); gap:8px; max-width:300px; margin:auto;"></div></div>
        <script>
            const icons=['❤️','❤️','⭐','⭐','🍀','🍀','💎','💎','🍎','🍎','🎈','🎈','🎨','🎨','⚡','⚡'].sort(()=>Math.random()-0.5);
            let act=[];
            icons.forEach((ic)=>{
                let c=document.createElement('div');
                c.style="height:65px; background:#334155; border-radius:8px; display:flex; align-items:center; justify-content:center; font-size:24px; cursor:pointer;";
                c.onclick=()=>{
                    if(act.length<2 && c.innerText==''){
                        c.innerText=ic; act.push({c,ic});
                        if(act.length==2){
                            if(act[0].ic==act[1].ic) act=[];
                            else setTimeout(()=>{ act[0].c.innerText=''; act[1].c.innerText=''; act=[]; }, 600);
                        }
                    }
                };
                document.getElementById('grid').appendChild(c);
            });
        </script>""", height=380)

    elif game == "Simon Says":
        st.components.v1.html("""
        <div style="text-align:center; background:#1E293B; padding:20px; border-radius:15px;">
            <div id="stat" style="color:white; margin-bottom:15px;">Level 1</div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; max-width:240px; margin:auto;">
                <div id="0" onclick="tp(0)" style="height:80px; background:#EF4444; opacity:0.3; border-radius:10px;"></div>
                <div id="1" onclick="tp(1)" style="height:80px; background:#3B82F6; opacity:0.3; border-radius:10px;"></div>
                <div id="2" onclick="tp(2)" style="height:80px; background:#EAB308; opacity:0.3; border-radius:10px;"></div>
                <div id="3" onclick="tp(3)" style="height:80px; background:#22C55E; opacity:0.3; border-radius:10px;"></div>
            </div>
            <button onclick="sq=[];nxt()" style="margin-top:15px; width:100%; padding:10px; background:#38BDF8; color:white; border:none; border-radius:8px;">START</button>
        </div>
        <script>
            let sq=[], u=[], lv=1;
            function nxt(){ u=[]; sq.push(Math.floor(Math.random()*4)); ply(); }
            function ply(){ let i=0; let t=setInterval(()=>{ fl(sq[i]); i++; if(i>=sq.length)clearInterval(t); }, 600); }
            function fl(id){ let e=document.getElementById(id); e.style.opacity='1'; setTimeout(()=>e.style.opacity='0.3', 300); }
            function tp(id){ fl(id); u.push(id); if(u[u.length-1]!==sq[u.length-1]){ alert('Over!'); sq=[]; lv=1; } else if(u.length==sq.length){ lv++; document.getElementById('stat').innerText='Level '+lv; setTimeout(nxt, 800); } }
        </script>""", height=400)

# --- 7. FIXED ADMIN ---
with tabs[3]:
    if st.session_state.auth["role"] == "admin":
        st.subheader("🛡️ Advanced Log Explorer")
        l_df = get_data("ChatLogs")
        
        if not l_df.empty:
            # FIX: Convert timestamps safely using mixed format
            l_df['timestamp_fixed'] = pd.to_datetime(l_df['timestamp'], format='mixed', errors='coerce')
            
            with st.expander("🔍 Filter Controls", expanded=True):
                c1, c2, c3, c4 = st.columns(4)
                f_user = c1.selectbox("Member ID", ["All Users"] + list(l_df['memberid'].unique()))
                f_agent = c2.selectbox("Agent", ["All Agents", "Cooper", "Clara"])
                f_date = c3.date_input("Date Range", [date(2025, 1, 1), date.today()])
                f_text = c4.text_input("Keyword Search")

            filt = l_df.copy()
            filt['timestamp_dt'] = filt['timestamp_fixed'].dt.date
            
            # Apply Filters
            if f_user != "All Users": filt = filt[filt['memberid'].astype(str) == str(f_user)]
            if f_agent != "All Agents": filt = filt[filt['agent'] == f_agent]
            if len(f_date) == 2:
                filt = filt[(filt['timestamp_dt'] >= f_date[0]) & (filt['timestamp_dt'] <= f_date[1])]
            if f_text: filt = filt[filt['content'].str.contains(f_text, case=False, na=False)]

            st.write(f"Showing {len(filt)} results")
            # Drop the helper columns before displaying
            display_df = filt.drop(columns=['timestamp_dt', 'timestamp_fixed']).sort_values('timestamp', ascending=False)
            st.dataframe(display_df, use_container_width=True, hide_index=True)

            st.divider()
            st.warning("Data Management")
            wipe_target = st.selectbox("Purge all logs for:", ["None"] + list(l_df['memberid'].unique()))
            if st.button("🔥 Permanently Purge User Data") and wipe_target != "None":
                new_logs = l_df[l_df['memberid'].astype(str) != str(wipe_target)]
                # Drop helper columns before updating the sheet
                if 'timestamp_fixed' in new_logs.columns: new_logs = new_logs.drop(columns=['timestamp_fixed'])
                conn.update(worksheet="ChatLogs", data=new_logs)
                st.cache_data.clear()
                st.success(f"Logs for {wipe_target} deleted."); st.rerun()
        else: st.info("No logs found in database.")
    else: st.error("Admin Access Required")

with tabs[4]:
    if st.button("Logout"): st.session_state.clear(); st.rerun()

