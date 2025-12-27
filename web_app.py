import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta
import plotly.graph_objects as # --- 8. ADMIN PORTAL ---
if st.session_state.auth["role"] == "admin":
    with main_nav[-2]:
        st.header("🛡️ Admin Chat Explorer")
        
        # 1. Fetch Fresh Data
        logs_df = get_data("ChatLogs")
        
        if not logs_df.empty:
            # 2. Top Level Filters
            c1, c2, c3 = st.columns([1, 1, 2])
            with c1: 
                u_f = st.multiselect("Member ID", options=logs_df['memberid'].unique())
            with c2: 
                a_f = st.multiselect("Agent", options=logs_df['agent'].unique())
            with c3:
                # NEW: Keyword Search Box
                search_query = st.text_input("🔍 Search Keywords", placeholder="Type a word (e.g. 'anxious', 'happy', 'help')...").strip().lower()

            # 3. Filtering Logic
            f_df = logs_df.copy()
            
            if u_f: 
                f_df = f_df[f_df['memberid'].isin(u_f)]
            if a_f: 
                f_df = f_df[f_df['agent'].isin(a_f)]
            
            # Apply Keyword Search
            if search_query:
                # We search the 'content' column and make it case-insensitive
                f_df = f_df[f_df['content'].astype(str).str.lower().str.contains(search_query)]
            
            # 4. Display Results
            st.markdown(f"**Found {len(f_df)} messages matching your criteria.**")
            
            st.dataframe(
                f_df[['timestamp', 'memberid', 'agent', 'role', 'content']], 
                use_container_width=True, 
                hide_index=True
            )
            
            # 5. Export
            csv = f_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Export Current View to CSV", data=csv, file_name="filtered_logs.csv", mime="text/csv")
        else: 
            st.info("No logs found in the database.")

# --- 1. MOBILE-FIRST CONFIGURATION ---
st.set_page_config(page_title="Health Bridge", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    [data-testid="column"] { width: 100% !important; min-width: 100% !important; }
    
    /* Optimized buttons for mobile tapping */
    .stButton>button { 
        border-radius: 15px; font-weight: 600; height: 3.5em; 
        width: 100%; border: none; font-size: 16px !important;
    }
    
    .portal-card { 
        background: #1E293B; padding: 15px; border-radius: 20px; 
        border: 1px solid #334155; margin-bottom: 15px; 
    }
    
    /* Game Layout Styling */
    .game-container {
        display: flex; flex-direction: column; align-items: center;
        background: #1E293B; border-radius: 20px; padding: 15px;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. DATA HELPERS ---
conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "mid": None, "role": "user"}
if "cooper_logs" not in st.session_state: st.session_state.cooper_logs = []

def get_data(worksheet_name):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        df.columns = [str(c).strip().lower() for c in df.columns]
        return df
    except: return pd.DataFrame()

# --- 3. LOGIN & DUPLICATE PROTECTION ---
if not st.session_state.auth["logged_in"]:
    st.markdown("<h2 style='text-align:center;'>🧠 Health Bridge</h2>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["🔐 Login", "📝 Sign Up"])
    with t1:
        u = st.text_input("Member ID").strip().lower()
        p = st.text_input("Password", type="password")
        if st.button("Sign In"):
            df = get_data("Users")
            if not df.empty and 'memberid' in df.columns:
                m = df[(df['memberid'].astype(str).str.lower() == u) & (df['password'].astype(str) == p)]
                if not m.empty:
                    st.session_state.auth.update({"logged_in": True, "mid": u, "role": str(m.iloc[0]['role']).lower()})
                    st.rerun()
                else: st.error("Check credentials")
    with t2:
        mid_new = st.text_input("New Member ID").strip().lower()
        p_new = st.text_input("Create Password", type="password")
        if st.button("Register"):
            df = get_data("Users")
            if not df.empty and mid_new in df['memberid'].astype(str).str.lower().values:
                st.error("ID already exists.")
            else:
                new_user = pd.DataFrame([{"memberid": mid_new, "password": p_new, "role": "user"}])
                conn.update(worksheet="Users", data=pd.concat([df, new_user], ignore_index=True))
                st.success("Account created!")
    st.stop()

# --- 4. NAVIGATION ---
tabs = ["🏠 Cooper", "🎮 Games", "🛡️ Admin"] if st.session_state.auth['role'] == "admin" else ["🏠 Cooper", "🎮 Games"]
nav = st.tabs(tabs)

# --- 5. COOPER ---
with nav[0]:
    st.markdown('<div class="portal-card"><h3>⚡ Energy Status</h3>', unsafe_allow_html=True)
    ev = st.select_slider("Level", options=list(range(1,12)), value=6)
    if st.button("Log Energy"):
        new_row = pd.DataFrame([{"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), "memberid": st.session_state.auth['mid'], "energylog": ev}])
        conn.update(worksheet="Sheet1", data=pd.concat([get_data("Sheet1"), new_row], ignore_index=True))
        st.toast("Synced!")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Simple Chat
    if p := st.chat_input("Speak with Cooper..."):
        st.session_state.cooper_logs.append({"role": "user", "content": p})
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":"You are Cooper."}]+st.session_state.cooper_logs[-3:]).choices[0].message.content
        st.session_state.cooper_logs.append({"role": "assistant", "content": res})
        st.rerun()

# --- 6. GAMES (D-PAD CONTROLS) ---
with nav[1]:
    game_mode = st.radio("Select Game", ["Snake D-Pad", "2048 D-Pad"], horizontal=True)

    # REUSABLE D-PAD CSS
    DPAD_STYLE = """
    <style>
        .dpad { display: grid; grid-template-columns: repeat(3, 70px); grid-gap: 10px; margin-top: 20px; }
        .btn { width: 70px; height: 70px; background: #334155; border: none; border-radius: 15px; color: white; font-size: 24px; font-weight: bold; cursor: pointer; }
        .btn:active { background: #38BDF8; }
        .empty { visibility: hidden; }
    </style>
    """

    if game_mode == "Snake D-Pad":
        SNAKE_HTML = f"""
        {DPAD_STYLE}
        <div class="game-container">
            <canvas id="sc" width="280" height="280" style="background:#0F172A; border:2px solid #38BDF8; border-radius:10px;"></canvas>
            <div class="dpad">
                <div class="empty"></div><button class="btn" onclick="d='UP'">▲</button><div class="empty"></div>
                <button class="btn" onclick="d='LEFT'">◀</button><button class="btn" onclick="d='DOWN'">▼</button><button class="btn" onclick="d='RIGHT'">▶</button>
            </div>
            <button onclick="reset()" style="margin-top:15px; width:230px; padding:10px; background:#38BDF8; border:none; border-radius:10px; color:white;">RESTART</button>
        </div>
        <script>
            const canvas = document.getElementById("sc"); const ctx = canvas.getContext("2d");
            let box = 14; let snake, food, d, game;
            function reset() {{ snake=[{{x:9*box,y:10*box}}]; food={{x:Math.floor(Math.random()*19)*box,y:Math.floor(Math.random()*19)*box}}; d=null; if(game) clearInterval(game); game=setInterval(draw,130); }}
            function draw() {{
                ctx.fillStyle="#0F172A"; ctx.fillRect(0,0,280,280);
                ctx.fillStyle="#F87171"; ctx.fillRect(food.x, food.y, box, box);
                snake.forEach((p,i)=>{{ ctx.fillStyle=i==0?"#38BDF8":"#334155"; ctx.fillRect(p.x,p.y,box,box); }});
                let head = {{x:snake[0].x, y:snake[0].y}};
                if(d=='LEFT') head.x-=box; if(d=='UP') head.y-=box; if(d=='RIGHT') head.x+=box; if(d=='DOWN') head.y+=box;
                if(head.x==food.x && head.y==food.y) food={{x:Math.floor(Math.random()*19)*box,y:Math.floor(Math.random()*19)*box}};
                else if(d) snake.pop();
                if(head.x<0||head.x>=280||head.y<0||head.y>=280||(d && snake.some(s=>s.x==head.x&&s.y==head.y))) reset();
                if(d) snake.unshift(head);
            }}
            reset();
        </script>
        """
        st.components.v1.html(SNAKE_HTML, height=650)

    else:
        T2048_HTML = f"""
        {DPAD_STYLE}
        <div class="game-container">
            <div id="grid" style="display:grid; grid-template-columns:repeat(4,60px); gap:8px; background:#0F172A; padding:10px; border-radius:10px;"></div>
            <div class="dpad">
                <div class="empty"></div><button class="btn" onclick="mv(0,4,1);add();ren();">▲</button><div class="empty"></div>
                <button class="btn" onclick="mv(0,1,4);add();ren();">◀</button><button class="btn" onclick="mv(12,-4,1);add();ren();">▼</button><button class="btn" onclick="mv(3,-1,4);add();ren();">▶</button>
            </div>
        </div>
        <script>
            let board=Array(16).fill(0); let score=0;
            function add(){{ let e=board.map((v,i)=>v==0?i:null).filter(v=>v!=null); if(e.length) board[e[Math.floor(Math.random()*e.length)]]=2; }}
            function ren(){{ 
                const g=document.getElementById('grid'); g.innerHTML='';
                board.forEach(v=>{{ const t=document.createElement('div'); t.style=`width:60px;height:60px;background:${{v?'#38BDF8':'#334155'}};color:white;display:flex;align-items:center;justify-content:center;border-radius:8px;font-weight:bold;`; t.innerText=v||''; g.appendChild(t); }});
            }}
            function mv(s,st,sd){{ for(let i=0;i<4;i++){{ let l=[]; for(let j=0;j<4;j++) l.push(board[s+i*sd+j*st]); let f=l.filter(v=>v); for(let j=0;j<f.length-1;j++) if(f[j]==f[j+1]){{ f[j]*=2; f.splice(j+1,1); }} while(f.length<4) f.push(0); for(let j=0;j<4;j++) board[s+i*sd+j*st]=f[j]; }} }}
            add(); add(); ren();
        </script>
        """
        st.components.v1.html(T2048_HTML, height=650)

# --- 7. ADMIN ---
if st.session_state.auth['role'] == "admin":
    with nav[-1]:
        st.subheader("🛡️ Admin Log Search")
        q = st.text_input("🔍 Search Keyword")
        df_logs = get_data("ChatLogs")
        if q and not df_logs.empty:
            df_logs = df_logs[df_logs['content'].astype(str).str.contains(q, case=False)]
        st.dataframe(df_logs, use_container_width=True)

st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())

