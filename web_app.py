import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.graph_objects as go
from streamlit_js_eval import streamlit_js_eval

# --- 1. CONFIG ---
st.set_page_config(page_title="Health Bridge", layout="wide")

# --- 2. CONNECTIONS ---
conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None, "name": None}
if "cooper_logs" not in st.session_state: st.session_state.cooper_logs = []

def get_data(worksheet_name):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except:
        return pd.DataFrame(columns=["CoupleID", "Game", "Score"])

# --- 3. LOGIN GATE ---
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

# --- 4. NAVIGATION ---
main_nav = st.tabs(["🏠 Dashboard", "📊 Caregiver Insights", "🎮 Games", "🚪 Logout"])

# --- 5. GAMES TAB (AUTOMATED SYNC) ---
with main_nav[2]:
    gt = st.radio("Choose Game", ["Modern Snake", "Memory Match"], horizontal=True)
    
    # 1. Load PB from Sheet
    hs_df = get_data("HighScores")
    cid = st.session_state.auth['cid']
    record = hs_df[(hs_df['CoupleID'].astype(str) == str(cid)) & (hs_df['Game'] == gt)]
    current_pb = int(record['Score'].values[0]) if not record.empty else 0

    st.markdown(f"""
        <div style="background: #1E293B; padding: 15px; border-radius: 15px; border: 2px solid #38BDF8; text-align: center; margin-bottom: 20px;">
            <h2 style="margin:0; color: #38BDF8;">🏆 Personal Best: {current_pb}</h2>
        </div>
    """, unsafe_allow_html=True)

    # 2. Automated Score Retrieval
    # We use a button to "fetch" the score from the JavaScript game state
    if st.button("🔄 Sync Final Score to Cloud"):
        # This JS snippet looks into the iframe of the game to find the score variable
        final_score = streamlit_js_eval(js_expressions="window.lastGameScore", want_output=True)
        
        if final_score is not None:
            final_score = int(final_score)
            if final_score > current_pb:
                if not record.empty:
                    hs_df.loc[(hs_df['CoupleID'].astype(str) == str(cid)) & (hs_df['Game'] == gt), 'Score'] = final_score
                else:
                    hs_df = pd.concat([hs_df, pd.DataFrame([{"CoupleID": cid, "Game": gt, "Score": final_score}])], ignore_index=True)
                
                conn.update(worksheet="HighScores", data=hs_df)
                st.success(f"New High Score: {final_score}! Saved to Cloud.")
                st.rerun()
            else:
                st.info(f"Last game score: {final_score}. Not higher than your PB.")
        else:
            st.warning("No game score detected yet. Play a round first!")

    # 3. Game Content with "Global Variable" for Score
    if gt == "Modern Snake":
        # The JS now saves the score to 'window.parent.lastGameScore' so Python can read it
        SNAKE_HTML = """
        <div style="display:flex; flex-direction:column; align-items:center; background:#1E293B; padding:20px; border-radius:15px;">
            <canvas id="s" width="300" height="300" style="border:4px solid #38BDF8; background:#0F172A; border-radius:10px;"></canvas>
            <h2 id="st" style="color:#38BDF8; font-family:sans-serif;">Score: 0</h2>
        </div>
        <script>
        const canvas=document.getElementById("s"), ctx=canvas.getContext("2d"), box=15;
        let score=0; let d; let snake=[{x:10*box, y:10*box}]; 
        let food={x:Math.floor(Math.random()*19)*box, y:Math.floor(Math.random()*19)*box};
        
        window.addEventListener("keydown", e => { if(e.code=="ArrowLeft" && d!="RIGHT") d="LEFT"; if(e.code=="ArrowUp" && d!="DOWN") d="UP"; if(e.code=="ArrowRight" && d!="LEFT") d="RIGHT"; if(e.code=="ArrowDown" && d!="UP") d="DOWN"; });
        
        function draw() {
            ctx.fillStyle="#0F172A"; ctx.fillRect(0,0,300,300);
            ctx.fillStyle = "#F87171"; ctx.beginPath(); ctx.arc(food.x+box/2, food.y+box/2, box/3, 0, Math.PI*2); ctx.fill();
            snake.forEach((p,i)=>{ ctx.fillStyle= i==0 ? "#38BDF8" : "rgba(56, 189, 248, "+(1-i/snake.length)+")"; ctx.fillRect(p.x, p.y, box-1, box-1); });
            let hX=snake[0].x, hY=snake[0].y;
            if(d=="LEFT") hX-=box; if(d=="UP") hY-=box; if(d=="RIGHT") hX+=box; if(d=="DOWN") hY+=box;
            if(hX==food.x && hY==food.y){ 
                score++; document.getElementById("st").innerText="Score: "+score; 
                window.parent.lastGameScore = score; // EXPORT SCORE TO PYTHON
                food={x:Math.floor(Math.random()*19)*box, y:Math.floor(Math.random()*19)*box}; 
            } else if(d) snake.pop();
            let h={x:hX, y:hY};
            if(hX<0||hX>=300||hY<0||hY>=300||(d && snake.some(z=>z.x==h.x&&z.y==h.y))){
                clearInterval(game); alert("Game Over! Click 'Sync' above to save.");
            }
            if(d) snake.unshift(h);
        }
        let game = setInterval(draw, 100);
        </script>
        """
        st.components.v1.html(SNAKE_HTML, height=450)
    else:
        st.write("Memory Match Auto-Sync loading...")
