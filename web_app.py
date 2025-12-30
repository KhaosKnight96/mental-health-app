import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, date, timedelta

# --- 1. SETTINGS & SESSION ---
st.set_page_config(page_title="Health Bridge Pro", layout="wide", initial_sidebar_state="collapsed")

if "auth" not in st.session_state: 
    st.session_state.auth = {"in": False, "mid": None, "role": "user", "name": "", "bio": "", "age": ""}
if "selected_search_id" not in st.session_state:
    st.session_state.selected_search_id = None

st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    .chat-bubble { padding: 12px 18px; border-radius: 18px; margin-bottom: 10px; max-width: 85%; line-height: 1.5; }
    .user-bubble { background: #1E40AF; color: white; margin-left: auto; border-bottom-right-radius: 2px; }
    .ai-bubble { background: #334155; color: white; margin-right: auto; border-bottom-left-radius: 2px; }
    .feed-card { background: #1E293B; padding: 20px; border-radius: 15px; border: 1px solid #334155; margin-bottom: 15px; }
    
    /* Touch optimization */
    .game-container { touch-action: none; user-select: none; -webkit-tap-highlight-color: transparent; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATA CORE ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=1)
def get_data(ws):
    try:
        df = conn.read(worksheet=ws, ttl=0)
        df.columns = [str(c).strip().lower() for c in df.columns]
        return df
    except: return pd.DataFrame()

def save_to_sheet(ws_name, df_to_add):
    try:
        existing = conn.read(worksheet=ws_name, ttl=0)
        updated = pd.concat([existing, df_to_add], ignore_index=True)
        conn.update(worksheet=ws_name, data=updated)
        st.cache_data.clear()
    except Exception as e: st.error(f"Save Error: {e}")

# --- 3. ARCADE (SWIPE & TOUCH ENGINE) ---
def render_arcade(game_type):
    if game_type == "Snake (Swipe/Keys)":
        return st.components.v1.html("""
        <div class="game-container" style="text-align:center; background:#1E293B; padding:15px; border-radius:20px;">
            <div id="scr" style="color:#38BDF8; font-size:20px; font-weight:bold;">Score: 0</div>
            <canvas id="snk" width="300" height="300" style="background:#0F172A; border:3px solid #334155; border-radius:10px; margin-top:10px;"></canvas>
            <p style="color:#64748B; margin-top:10px;">Swipe or use Arrow Keys to Move</p>
        </div>
        <script>
            const c=document.getElementById('snk'), x=c.getContext('2d');
            let sn=[{x:150,y:150}], f={x:75,y:75}, d='R', sc=0, tsX=null, tsY=null;
            
            // KEYBOARD
            window.onkeydown=e=>{
                if(e.key=='ArrowUp'&&d!='D')d='U'; if(e.key=='ArrowDown'&&d!='U')d='D';
                if(e.key=='ArrowLeft'&&d!='R')d='L'; if(e.key=='ArrowRight'&&d!='L')d='R';
            };
            // SWIPE
            c.addEventListener('touchstart', e=>{ tsX=e.touches[0].clientX; tsY=e.touches[0].clientY; }, false);
            c.addEventListener('touchmove', e=>{
                if(!tsX||!tsY) return;
                let tdX=tsX-e.touches[0].clientX, tdY=tsY-e.touches[0].clientY;
                if(Math.abs(tdX)>Math.abs(tdY)){ if(tdX>0 && d!='R')d='L'; else if(d!='L') d='R'; }
                else { if(tdY>0 && d!='D')d='U'; else if(d!='U') d='D'; }
                tsX=null; tsY=null; e.preventDefault();
            }, {passive: false});

            setInterval(()=>{
                x.fillStyle='#0F172A'; x.fillRect(0,0,300,300);
                x.fillStyle='#F87171'; x.fillRect(f.x,f.y,15,15);
                x.fillStyle='#38BDF8'; sn.forEach(p=>x.fillRect(p.x,p.y,15,15));
                let h={...sn[0]};
                if(d=='L')h.x-=15; if(d=='U')h.y-=15; if(d=='R')h.x+=15; if(d=='D')h.y+=15;
                if(h.x==f.x&&h.y==f.y){sc++; f={x:Math.floor(Math.random()*19)*15,y:Math.floor(Math.random()*19)*15}} else sn.pop();
                if(h.x<0||h.x>=300||h.y<0||h.y>=300||sn.some(s=>s.x==h.x&&s.y==h.y)){sn=[{x:150,y:150}]; sc=0; d='R';}
                sn.unshift(h); document.getElementById('scr').innerText="Score: "+sc;
            }, 120);
        </script>
        """, height=450)

    elif game_type == "Memory (Touch Level-Up)":
        return st.components.v1.html("""
        <div class="game-container" style="text-align:center; background:#1E293B; padding:15px; border-radius:15px;">
            <div id="msg" style="color:#38BDF8; font-size:18px; margin-bottom:10px;">Stage 1 (2x2)</div>
            <div id="grid" style="display:grid; gap:8px; margin:auto; max-width:320px;"></div>
        </div>
        <script>
            let cards=[], flipped=[], matched=0, sz=2;
            const icons=['🍎','⭐','🍀','💎','🎈','🎨','⚡','🔥','🍄','🌈','🌊','🍕'];
            function start(n){
                sz=n; matched=0; flipped=[];
                const g=document.getElementById('grid');
                g.innerHTML=''; g.style.gridTemplateColumns=`repeat(${n}, 1fr)`;
                document.getElementById('msg').innerText=`Stage ${n-1} (${n}x${n})`;
                let count=(n*n)/2;
                let items=[...icons.slice(0,count), ...icons.slice(0,count)].sort(()=>Math.random()-0.5);
                items.forEach(icon=>{
                    let c=document.createElement('div');
                    c.style="height:70px; background:#334155; border-radius:10px; display:flex; align-items:center; justify-content:center; font-size:28px; cursor:pointer;";
                    c.onclick=()=>{ if(flipped.length<2 && c.innerText==''){
                        c.innerText=icon; c.style.background='#1E40AF'; flipped.push({c,icon});
                        if(flipped.length==2){
                            if(flipped[0].icon==flipped[1].icon){ matched++; flipped=[]; if(matched==(n*n)/2) setTimeout(()=>start(n+2),600); }
                            else { setTimeout(()=>{ flipped.forEach(f=>{f.c.innerText=''; f.c.style.background='#334155';}); flipped=[]; }, 500); }
                        }
                    }};
                    g.appendChild(c);
                });
            }
            start(2);
        </script>
        """, height=500)

# --- 4. ADMIN TAB (THE DEFINITIVE DATE FIX) ---
def admin_tab():
    st.subheader("🛡️ Administrative Activity Logs")
    l_df = get_data("ChatLogs")
    if not l_df.empty:
        # Convert timestamp strings to actual datetime objects
        l_df['dt'] = pd.to_datetime(l_df['timestamp'])
        
        c1, c2 = st.columns(2)
        u_filter = c1.selectbox("Filter by User ID", ["All Users"] + list(l_df['memberid'].unique()))
        
        # Streamlit date_input returns datetime.date objects
        d_range = c2.date_input("Filter Date Range", value=(l_df['dt'].min().date(), date.today()))
        
        # CRITICAL FIX: Convert dates to pd.Timestamp for valid comparison with datetime64[ns]
        if isinstance(d_range, tuple) and len(d_range) == 2:
            start_bound = pd.Timestamp(d_range[0])
            end_bound = pd.Timestamp(d_range[1]) + pd.Timedelta(days=1)
            
            mask = (l_df['dt'] >= start_bound) & (l_df['dt'] < end_bound)
            if u_filter != "All Users":
                mask &= (l_df['memberid'] == u_filter)
            
            st.dataframe(l_df[mask].drop(columns=['dt']).sort_values('timestamp', ascending=False), use_container_width=True)
        else:
            st.info("Please select a complete start and end date.")

# --- 5. MAIN APP ---
if not st.session_state.auth["in"]:
    # (Standard login code here)
    st.title("Health Bridge Pro")
    u = st.text_input("ID")
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        users = get_data("Users")
        match = users[(users['memberid'].astype(str) == u) & (users['password'].astype(str) == p)]
        if not match.empty:
            st.session_state.auth.update({"in":True, "mid":u, "role":match.iloc[0]['role']})
            st.rerun()
    st.stop()

tabs = st.tabs(["👤 Profile", "🎮 Arcade", "🛠️ Admin", "🚪 Logout"])

with tabs[1]:
    g_choice = st.segmented_control("Select Experience", ["Snake (Swipe/Keys)", "Memory (Touch Level-Up)"], default="Snake (Swipe/Keys)")
    render_arcade(g_choice)

with tabs[2]:
    if st.session_state.auth['role'] == 'admin': admin_tab()
    else: st.error("Access Denied.")

with tabs[3]:
    if st.button("Logout"): st.session_state.clear(); st.rerun()
