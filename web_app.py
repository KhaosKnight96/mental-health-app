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

# --- 3. AUTO-SYNC LOGIC ---
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
    
    hs_df = get_data("HighScores")
    cid = st.session_state.auth['cid']
    record = hs_df[(hs_df['CoupleID'].astype(str) == str(cid)) & (hs_df['Game'] == gt)]
    pb = int(record['Score'].values[0]) if not record.empty else 0
    
    st.markdown(f"""
        <div style="background: #1E293B; padding: 15px; border-radius: 15px; border: 2px solid #38BDF8; text-align: center; margin-bottom: 20px;">
            <h2 style="margin:0; color: #38BDF8;">🏆 Personal Best: {pb}</h2>
            <p style="margin:0; color: #94A3B8;">Scores sync to Cloud automatically on Game Over</p>
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
                window.parent.location.href = window.parent.location.pathname + "?score=" + score + "&game=Modern Snake";
            }}
            if(d) snake.unshift(h);
        }}
        let game = setInterval(draw, 100);
        </script>
        """
        st.components.v1.html(SNAKE_HTML, height=450)
    
    elif gt == "Memory Match":
        MEMORY_HTML = f"""
        <style>
            .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; max-width: 320px; margin: auto; }}
            .card {{ height: 75px; position: relative; transform-style: preserve-3d; transition: transform 0.5s; cursor: pointer; }}
            .card.flipped {{ transform: rotateY(180deg); }}
            .face {{ position: absolute; width: 100%; height: 100%; backface-visibility: hidden; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 25px; border: 2px solid #334155; }}
            .front {{ background: #1E293B; border-color: #38BDF8; }}
            .back {{ background: #334155; transform: rotateY(180deg); color: white; }}
        </style>
        <div class="grid" id="g"></div>
        <script>
            const icons = ['🍎','🍎','💎','💎','🌟','🌟','🚀','🚀','🌈','🌈','🔥','🔥','🍀','🍀','🎁','🎁'];
            let shuffled = icons.sort(() => 0.5 - Math.random());
            let flipped = [], lock = false, matches = 0;
            const board = document.getElementById('g');
            shuffled.forEach(icon => {{
                const card = document.createElement('div'); card.className = 'card';
                card.innerHTML = `<div class="face front"></div><div class="face back">${{icon}}</div>`;
                card.dataset.icon = icon;
                card.onclick = function() {{
                    if(lock || this.classList.contains('flipped')) return;
                    this.classList.add('flipped'); flipped.push(this);
                    if(flipped.length === 2) {{
                        lock = true;
                        if(flipped[0].dataset.icon === flipped[1].dataset.icon) {{
                            matches++; flipped = []; lock = false;
                            if(matches === 8) {{
                                setTimeout(() => {{
                                    window.parent.location.href = window.parent.location.pathname + "?score=100&game=Memory Match";
                                }}, 500);
                            }}
                        }} else {{
                            setTimeout(() => {{ 
                                flipped.forEach(c => c.classList.remove('flipped')); 
                                flipped = []; lock = false; 
                            }}, 800);
                        }}
                    }}
                }}; board.appendChild(card);
            }});
        </script>
        """
        st.components.v1.html(MEMORY_HTML, height=400)
