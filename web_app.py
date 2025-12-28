import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta
import plotly.graph_objects as go

# --- 1. MOBILE-FIRST CONFIGURATION ---
st.set_page_config(page_title="Health Bridge", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    
    /* Make columns stack vertically on mobile */
    [data-testid="column"] { width: 100% !important; min-width: 100% !important; }
    
    /* Mobile-friendly buttons */
    .stButton>button { 
        border-radius: 15px; font-weight: 600; height: 3.5em; 
        width: 100%; border: none; font-size: 16px !important;
    }
    
    .portal-card { 
        background: #1E293B; padding: 15px; border-radius: 20px; 
        border: 1px solid #334155; margin-bottom: 15px; 
    }

    /* D-Pad Styling */
    .dpad { display: grid; grid-template-columns: repeat(3, 65px); grid-gap: 8px; justify-content: center; margin-top: 15px; }
    .btn { width: 65px; height: 65px; background: #334155; border: none; border-radius: 12px; color: white; font-size: 20px; cursor: pointer; }
    .btn:active { background: #38BDF8; }
    .empty { visibility: hidden; }
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

def save_chat_to_sheets(agent, role, content):
    new_entry = pd.DataFrame([{
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "memberid": st.session_state.auth['mid'],
        "agent": agent, "role": role, "content": content
    }])
    conn.update(worksheet="ChatLogs", data=pd.concat([get_data("ChatLogs"), new_entry], ignore_index=True))

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
                else: st.error("Check ID/Password")
    with t2:
        mid_new = st.text_input("Create ID").strip().lower()
        p_new = st.text_input("Password", type="password")
        if st.button("Register"):
            df = get_data("Users")
            if not df.empty and mid_new in df['memberid'].astype(str).str.lower().values:
                st.error("ID taken.")
            else:
                new_user = pd.DataFrame([{"memberid": mid_new, "password": p_new, "role": "user"}])
                conn.update(worksheet="Users", data=pd.concat([df, new_user], ignore_index=True))
                st.success("Success! Login now.")
    st.stop()

# --- 4. NAVIGATION ---
tabs = ["🏠 Cooper", "🛋️ Clara", "🎮 Games"]
if st.session_state.auth['role'] == "admin": tabs.append("🛡️ Admin")
nav = st.tabs(tabs)

# --- 5. COOPER ---
with nav[0]:
    st.markdown('<div class="portal-card"><h3>⚡ Energy Status</h3>', unsafe_allow_html=True)
    ev = st.select_slider("How are you?", options=list(range(1,12)), value=6)
    if st.button("Save Sync"):
        new_row = pd.DataFrame([{"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), "memberid": st.session_state.auth['mid'], "energylog": ev}])
        conn.update(worksheet="Sheet1", data=pd.concat([get_data("Sheet1"), new_row], ignore_index=True))
        st.toast("Energy Logged!")
    st.markdown('</div>', unsafe_allow_html=True)
    
    for m in st.session_state.cooper_logs:
        st.chat_message(m["role"]).write(m["content"])
    if p := st.chat_input("Message Cooper..."):
        st.session_state.cooper_logs.append({"role": "user", "content": p})
        save_chat_to_sheets("Cooper", "user", p)
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":"You are Cooper."}]+st.session_state.cooper_logs[-3:]).choices[0].message.content
        st.session_state.cooper_logs.append({"role": "assistant", "content": res})
        save_chat_to_sheets("Cooper", "assistant", res)
        st.rerun()

# --- 6. GAMES (MOBILE D-PAD) ---
with nav[2]:
    game_choice = st.radio("Activity", ["Snake", "2048"], horizontal=True)
    
    if game_choice == "Snake":
        S_HTML = """
        <div style="display:flex; flex-direction:column; align-items:center; background:#1E293B; padding:15px; border-radius:15px;">
            <canvas id="sc" width="280" height="280" style="background:#0F172A; border:2px solid #38BDF8; border-radius:10px;"></canvas>
            <div class="dpad">
                <div class="empty"></div><button class="btn" onclick="d='UP'">▲</button><div class="empty"></div>
                <button class="btn" onclick="d='LEFT'">◀</button><button class="btn" onclick="d='DOWN'">▼</button><button class="btn" onclick="d='RIGHT'">▶</button>
            </div>
        </div>
        <script>
            const canvas=document.getElementById("sc"); const ctx=canvas.getContext("2d");
            let box=14, snake, food, d, game;
            function reset(){ snake=[{x:9*box,y:10*box}]; food={x:Math.floor(Math.random()*19)*box,y:Math.floor(Math.random()*19)*box}; d=null; if(game) clearInterval(game); game=setInterval(draw,130); }
            function draw(){
                ctx.fillStyle="#0F172A"; ctx.fillRect(0,0,280,280);
                ctx.fillStyle="#F87171"; ctx.fillRect(food.x, food.y, box, box);
                snake.forEach((p,i)=>{ ctx.fillStyle=i==0?"#38BDF8":"#334155"; ctx.fillRect(p.x,p.y,box,box); });
                let hX=snake[0].x, hY=snake[0].y;
                if(d=='LEFT') hX-=box; if(d=='UP') hY-=box; if(d=='RIGHT') hX+=box; if(d=='DOWN') hY+=box;
                if(hX==food.x && hY==food.y) food={x:Math.floor(Math.random()*19)*box,y:Math.floor(Math.random()*19)*box};
                else if(d) snake.pop();
                let head={x:hX,y:hY};
                if(hX<0||hX>=280||hY<0||hY>=280||(d && snake.some(s=>s.x==head.x&&s.y==head.y))) reset();
                if(d) snake.unshift(head);
            }
            reset();
        </script>
        <style>.dpad{display:grid;grid-template-columns:repeat(3,65px);gap:10px;margin-top:15px;}.btn{width:65px;height:65px;background:#334155;color:white;border:none;border-radius:12px;font-size:24px;}.empty{visibility:hidden;}</style>
        """
        st.components.v1.html(S_HTML, height=550)

# --- 7. ADMIN (KEYWORD SEARCH) ---
if st.session_state.auth['role'] == "admin":
    with nav[-1]:
        st.subheader("🛡️ Admin Explorer")
        search_query = st.text_input("🔍 Search Chat Keywords", placeholder="Type here...").strip().lower()
        
        logs_df = get_data("ChatLogs")
        if not logs_df.empty:
            if search_query:
                logs_df = logs_df[logs_df['content'].astype(str).str.lower().str.contains(search_query)]
            
            st.write(f"Showing {len(logs_df)} results")
            st.dataframe(logs_df, use_container_width=True, hide_index=True)
            st.download_button("Export CSV", logs_df.to_csv(index=False), "logs.csv")

st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())
