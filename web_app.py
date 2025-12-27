import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.graph_objects as go

# --- 1. CONFIG ---
st.set_page_config(page_title="Health Bridge", layout="wide")

# --- 2. CONNECTIONS ---
conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None, "name": None}

def get_data(worksheet_name):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except:
        return pd.DataFrame(columns=["CoupleID", "Game", "Score"])

# --- 3. AUTO-SYNC LOGIC (CATCHES SCORE FROM URL) ---
# When the game finishes, it reloads the page with ?score=XX in the URL
query_params = st.query_params
if "score" in query_params and st.session_state.auth["logged_in"]:
    new_score = int(query_params["score"])
    game_type = query_params.get("game", "Modern Snake")
    cid = st.session_state.auth['cid']
    
    hs_df = get_data("HighScores")
    idx = (hs_df['CoupleID'].astype(str) == str(cid)) & (hs_df['Game'] == game_type)
    current_pb = int(hs_df.loc[idx, 'Score'].values[0]) if not hs_df[idx].empty else 0
    
    if new_score > current_pb:
        if not hs_df[idx].empty:
            hs_df.loc[idx, 'Score'] = new_score
        else:
            hs_df = pd.concat([hs_df, pd.DataFrame([{"CoupleID": cid, "Game": game_type, "Score": new_score}])], ignore_index=True)
        conn.update(worksheet="HighScores", data=hs_df)
        st.toast(f"🏆 New High Score: {new_score} saved!", icon="🔥")
    
    # Clear the URL so it doesn't keep updating on every refresh
    st.query_params.clear()
    st.rerun()

# --- 4. LOGIN GATE ---
if not st.session_state.auth["logged_in"]:
    st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge Portal</h1>", unsafe_allow_html=True)
    u = st.text_input("Couple ID")
    p = st.text_input("Password", type="password")
    if st.button("Sign In"):
        df = get_data("Users")
        m = df[(df['Username'].astype(str) == u) & (df['Password'].astype(str) == p)]
        if not m.empty:
            st.session_state.auth.update({"logged_in": True, "cid": u, "name": m.iloc[0]['Fullname']})
            st.rerun()
    st.stop()

# --- 5. NAVIGATION ---
main_nav = st.tabs(["🏠 Dashboard", "📊 Caregiver Insights", "🎮 Games", "🚪 Logout"])

with main_nav[2]:
    gt = st.radio("Choose Game", ["Modern Snake", "Memory Match"], horizontal=True)
    
    # Show Personal Best
    hs_df = get_data("HighScores")
    cid = st.session_state.auth['cid']
    record = hs_df[(hs_df['CoupleID'].astype(str) == str(cid)) & (hs_df['Game'] == gt)]
    pb = int(record['Score'].values[0]) if not record.empty else 0
    
    st.markdown(f"""
        <div style="background: #1E293B; padding: 15px; border-radius: 15px; border: 2px solid #38BDF8; text-align: center; margin-bottom: 20px;">
            <h2 style="margin:0; color: #38BDF8;">🏆 Personal Best: {pb}</h2>
            <p style="margin:0; color: #94A3B8;">Scores update automatically after Game Over</p>
        </div>
    """, unsafe_allow_html=True)

    if gt == "Modern Snake":
        SNAKE_HTML = f"""
        <div style="display:flex; flex-direction:column; align-items:center; background:#1E293B; padding:20px; border-radius:15px;">
            <canvas id="s" width="300" height="300" style="border:4px solid #38BDF8; background:#0F172A; border-radius:10px;"></canvas>
            <h2 id="st" style="color:#38BDF8; font-family:sans-serif;">Score: 0</h2>
        </div>
        <script>
        const canvas=document.getElementById("s"), ctx=canvas.getContext("2d"), box=15;
        let score=0, d, snake=[{{x:10*box, y:10*box}}], food={{x:Math.floor(Math.random()*19)*box, y:Math.floor(Math.random()*19)*box}};
        
        window.addEventListener("keydown", e => {{ 
            if(["ArrowUp","ArrowDown","ArrowLeft","ArrowRight"].includes(e.code)) e.preventDefault();
            if(e.code=="ArrowLeft" && d!="RIGHT") d="LEFT"; if(e.code=="ArrowUp" && d!="DOWN") d="UP";
            if(e.code=="ArrowRight" && d!="LEFT") d="RIGHT"; if(e.code=="ArrowDown" && d!="UP") d="DOWN"; 
        }});

        function draw() {{
            ctx.fillStyle="#0F172A"; ctx.fillRect(0,0,300,300);
            ctx.fillStyle = "#F87171"; ctx.beginPath(); ctx.arc(food.x+box/2, food.y+box/2, box/3, 0, Math.PI*2); ctx.fill();
            snake.forEach((p,i)=>{{ ctx.fillStyle= i==0 ? "#38BDF8" : "rgba(56, 189, 248, "+(1-i/snake.length)+")"; ctx.fillRect(p.x, p.y, box-1, box-1); }});
            
            let hX=snake[0].x, hY=snake[0].y;
            if(d=="LEFT") hX-=box; if(d=="UP") hY-=box; if(d=="RIGHT") hX+=box; if(d=="DOWN") hY+=box;

            if(hX==food.x && hY==food.y){{
                score++; document.getElementById("st").innerText="Score: "+score;
                food={{x:Math.floor(Math.random()*19)*box, y:Math.floor(Math.random()*19)*box}};
            }} else if(d) snake.pop();

            let h={{x:hX, y:hY}};
            if(hX<0||hX>=300||hY<0||hY>=300||(d && snake.some(z=>z.x==h.x&&z.y==h.y))){{
                clearInterval(game);
                // THE AUTO-SYNC MAGIC:
                window.parent.location.href = window.parent.location.pathname + "?score=" + score + "&game=Modern Snake";
            }}
            if(d) snake.unshift(h);
        }
        let game = setInterval(draw, 100);
        </script>
        """
        st.components.v1.html(SNAKE_HTML, height=450)
    else:
        st.info("Memory Match: I can add the same auto-sync to this game next!")
