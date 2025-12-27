import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# --- 1. SETUP & CONNECTIONS ---
st.set_page_config(page_title="Health Bridge", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None, "name": None}
if "chat_log" not in st.session_state: st.session_state.chat_log = []
if "snake_score" not in st.session_state: st.session_state.snake_score = 0

def get_data():
    df = conn.read(worksheet="Users", ttl=0)
    df.columns = [str(c).strip() for c in df.columns]
    return df

# --- 2. LOGIN GATE ---
if not st.session_state.auth["logged_in"]:
    st.title("🧠 Health Bridge Portal")
    u = st.text_input("Couple ID")
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        df = get_data()
        m = df[(df['Username'].astype(str) == u) & (df['Password'].astype(str) == p)]
        if not m.empty:
            st.session_state.auth.update({"logged_in": True, "cid": u, "name": m.iloc[0]['Fullname']})
            st.rerun()
    st.stop()

# --- 3. DATA LOAD ---
df = get_data()
user_idx = df.index[df['Username'].astype(str) == str(st.session_state.auth['cid'])][0]
current_pb = int(pd.to_numeric(df.at[user_idx, 'HighScore'], errors='coerce') or 0)

# --- 4. NAVIGATION ---
page = st.sidebar.radio("Navigation", ["Dashboard", "Zen Snake", "Zen AI Meditation"])

# --- 5. PAGE: DASHBOARD (COOPER AI) ---
if page == "Dashboard":
    st.title(f"Welcome, {st.session_state.auth['name']} ☀️")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.metric("Your High Score", f"{current_pb} pts")
        st.info("Cooper is your daily health companion. Ask him anything about your wellness or just chat!")

    with col2:
        st.subheader("🤖 Chat with Cooper")
        container = st.container(height=400)
        for m in st.session_state.chat_log:
            with container.chat_message("user" if m["role"]=="user" else "assistant"):
                st.markdown(m["content"])
        
        if prompt := st.chat_input("Message Cooper..."):
            st.session_state.chat_log.append({"role": "user", "content": prompt})
            with container.chat_message("user"): st.markdown(prompt)
            
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": "You are Cooper, a friendly health bridge assistant."}] + st.session_state.chat_log[-5:]
            ).choices[0].message.content
            
            st.session_state.chat_log.append({"role": "assistant", "content": response})
            with container.chat_message("assistant"): st.markdown(response)

# --- 6. PAGE: ZEN SNAKE (AUTO-CAPTURE SYNC) ---
elif page == "Zen Snake":
    st.title("🐍 Zen Snake")
    
    col_game, col_sync = st.columns([2, 1])
    
    with col_sync:
        st.markdown(f"### 🏆 Record: {current_pb}")
        st.divider()
        # The game "pokes" this value via the component return
        st.write("Current Session Score:")
        st.header(f"✨ {st.session_state.snake_score}")
        
        if st.button("🚀 Sync Score to Sheets", type="primary", use_container_width=True):
            if st.session_state.snake_score > current_pb:
                df.at[user_idx, 'HighScore'] = st.session_state.snake_score
                conn.update(worksheet="Users", data=df)
                st.cache_data.clear()
                st.success("Record Updated!")
                st.balloons()
            else:
                st.warning("Score must beat your record to sync!")

    with col_game:
        # We use st.components.v1.html with the "on_change" trick
        # When game ends, it sends the score back to the 'value' of the component
        SNAKE_HTML = """
        <div style="display:flex; flex-direction:column; align-items:center; background:#1E293B; padding:20px; border-radius:15px;">
            <canvas id="s" width="400" height="400" style="border:4px solid #38BDF8; background:black;"></canvas>
        </div>
        <script>
        const c=document.getElementById("s"), ctx=c.getContext("2d"), box=20;
        let score=0, d, snake=[{x:9*box, y:10*box}], food={x:5*box, y:5*box};

        function sendToStreamlit(val) {
            window.parent.postMessage({type: 'streamlit:setComponentValue', value: val}, '*');
        }

        document.onkeydown = e => {
            if([37,38,39,40].includes(e.keyCode)) e.preventDefault();
            if(e.keyCode==37 && d!="RIGHT") d="LEFT";
            if(e.keyCode==38 && d!="DOWN") d="UP";
            if(e.keyCode==39 && d!="LEFT") d="RIGHT";
            if(e.keyCode==40 && d!="UP") d="DOWN";
        };

        function draw() {
            ctx.fillStyle="black"; ctx.fillRect(0,0,400,400);
            ctx.fillStyle="#F87171"; ctx.fillRect(food.x, food.y, box, box);
            snake.forEach((p,i)=>{ ctx.fillStyle=i==0?"#38BDF8":"white"; ctx.fillRect(p.x,p.y,box,box); });
            let hX=snake[0].x, hY=snake[0].y;
            if(d=="LEFT") hX-=box; if(d=="UP") hY-=box; if(d=="RIGHT") hX+=box; if(d=="DOWN") hY+=box;
            if(hX==food.x && hY==food.y){ 
                score++; 
                sendToStreamlit(score); // Automatically update the Python session state
                food={x:Math.floor(Math.random()*19)*box, y:Math.floor(Math.random()*19)*box}; 
            } else if(d) snake.pop();
            let h={x:hX, y:hY};
            if(hX<0||hX>=400||hY<0||hY>=400||(d && snake.some(z=>z.x==h.x&&z.y==h.y))){
                clearInterval(g);
            }
            if(d) snake.unshift(h);
        }
        let g = setInterval(draw, 100);
        </script>
        """
        # Capture the value returned by the HTML component
        game_result = st.components.v1.html(SNAKE_HTML, height=450)
        if game_result:
            st.session_state.snake_score = game_result

# --- 7. PAGE: ZEN AI (MEDITATION) ---
elif page == "Zen AI Meditation":
    st.title("🧘 Zen AI Meditation")
    st.write("Take a deep breath. Zen AI is here to guide your mindfulness journey.")
    
    if "zen_log" not in st.session_state: st.session_state.zen_log = []
    
    z_container = st.container(height=400)
    for m in st.session_state.zen_log:
        with z_container.chat_message(m["role"]): st.markdown(m["content"])
        
    if z_prompt := st.chat_input("Ask Zen AI for a meditation..."):
        st.session_state.zen_log.append({"role": "user", "content": z_prompt})
        with z_container.chat_message("user"): st.markdown(z_prompt)
        
        z_res = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": "You are Zen AI, a calm, poetic meditation guide. Speak with tranquility."}] + st.session_state.zen_log[-3:]
        ).choices[0].message.content
        
        st.session_state.zen_log.append({"role": "assistant", "content": z_res})
        with z_container.chat_message("assistant"): st.markdown(z_res)

# --- 8. LOGOUT ---
if st.sidebar.button("Logout"):
    st.session_state.auth = {"logged_in": False, "cid": None}
    st.rerun()
