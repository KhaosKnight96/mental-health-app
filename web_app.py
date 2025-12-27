import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# --- 1. SETTINGS & STYLING ---
st.set_page_config(page_title="Health Bridge Portal", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0F172A !important; color: #F8FAFC !important; }
    [data-testid="stSidebar"] { background-color: #1E293B !important; border-right: 1px solid #334155; }
    .portal-card { background: #1E293B; padding: 25px; border-radius: 20px; border: 1px solid #334155; margin-bottom: 20px; }
    h1, h2, h3, p, label { color: #F8FAFC !important; }
    .stButton>button { border-radius: 12px !important; font-weight: 600 !important; }
</style>
""", unsafe_allow_html=True)

# --- 2. CONNECTIONS ---
conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None, "name": None}
if "cooper_logs" not in st.session_state: st.session_state.cooper_logs = []
if "clara_logs" not in st.session_state: st.session_state.clara_logs = []

def get_data():
    df = conn.read(worksheet="Users", ttl=0)
    df.columns = [str(c).strip() for c in df.columns]
    return df

# --- 3. LOGIN GATE ---
if not st.session_state.auth["logged_in"]:
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge</h1>", unsafe_allow_html=True)
        u_l = st.text_input("Couple ID")
        p_l = st.text_input("Password", type="password")
        if st.button("Sign In", use_container_width=True, type="primary"):
            df = get_data()
            m = df[(df['Username'].astype(str) == u_l) & (df['Password'].astype(str) == p_l)]
            if not m.empty:
                st.session_state.auth.update({"logged_in": True, "cid": u_l, "name": m.iloc[0]['Fullname']})
                st.rerun()
            else: 
                st.error("Invalid credentials.")
    st.stop()

# --- 4. SIDEBAR NAVIGATION ---
with st.sidebar:
    st.title("🌉 Health Bridge")
    page = st.radio("Navigation", ["Dashboard (Patient)", "Caregiver Section", "Zen Snake"])
    st.divider()
    if st.button("🚪 Logout"):
        st.session_state.auth = {"logged_in": False, "cid": None, "name": None}
        st.rerun()

# --- 5. PAGE: DASHBOARD (COOPER - THE FRIEND) ---
if page == "Dashboard (Patient)":
    st.markdown(f"<h1>Welcome, {st.session_state.auth['name']}! ☀️</h1>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown("""
        <div class="portal-card">
            <h3>🤝 Meet Cooper</h3>
            <p>Cooper is your companion. He's here to listen, chat, and keep you company throughout your journey. No medical jargon here—just a friendly ear.</p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("✨ High Five Cooper", use_container_width=True):
            st.balloons()

    with col2:
        st.markdown('<div class="portal-card"><h3>💬 Chat with Cooper</h3>', unsafe_allow_html=True)
        chat_container = st.container(height=400)
        for m in st.session_state.cooper_logs:
            with chat_container.chat_message(m["role"]):
                st.write(m["content"])
        
        if prompt := st.chat_input("Hey Cooper..."):
            st.session_state.cooper_logs.append({"role": "user", "content": prompt})
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": "You are Cooper, a warm, casual, and incredibly supportive friend to the patient. You avoid being overly clinical. You focus on empathy, storytelling, and companionship."}] + st.session_state.cooper_logs[-5:]
            ).choices[0].message.content
            st.session_state.cooper_logs.append({"role": "assistant", "content": response})
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- 6. PAGE: CAREGIVER SECTION (CLARA - THE ANALYST) ---
elif page == "Caregiver Section":
    st.markdown("<h1>Caregiver Insights 📊</h1>", unsafe_allow_html=True)
    
    col_info, col_chat = st.columns([1, 2])
    with col_info:
        st.markdown("""
        <div class="portal-card">
            <h3>📉 Clara Data Analyst</h3>
            <p>Clara provides professional data analysis and clinical insights. She helps you track trends, manage logistics, and understand medical details.</p>
        </div>
        """, unsafe_allow_html=True)

    with col_chat:
        st.markdown('<div class="portal-card"><h3>🤖 Clara Analyst AI</h3>', unsafe_allow_html=True)
        clara_container = st.container(height=400)
        for m in st.session_state.clara_logs:
            with clara_container.chat_message(m["role"]):
                st.write(m["content"])
                
        if clara_prompt := st.chat_input("Inquire for analysis..."):
            st.session_state.clara_logs.append({"role": "user", "content": clara_prompt})
            c_response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": "You are Clara, a highly intelligent, professional, and efficient medical data analyst. You provide clear, logical insights and help caregivers manage the technical aspects of health care."}] + st.session_state.clara_logs[-5:]
            ).choices[0].message.content
            st.session_state.clara_logs.append({"role": "assistant", "content": c_response})
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- 7. PAGE: ZEN SNAKE ---
elif page == "Zen Snake":
    st.title("🐍 Zen Snake")
    st.write("Arrow keys to navigate.")
    
    SNAKE_HTML = """
    <div style="display:flex; flex-direction:column; align-items:center; background:#1E293B; padding:20px; border-radius:15px;">
        <canvas id="s" width="400" height="400" style="border:4px solid #38BDF8; background:black; border-radius:10px;"></canvas>
        <h2 id="status" style="color:#38BDF8; font-family:sans-serif; margin-top:15px;">Score: 0</h2>
    </div>
    <script>
    const c=document.getElementById("s"), ctx=c.getContext("2d"), box=20;
    let score=0, d, snake=[{x:9*box, y:10*box}], food={x:5*box, y:5*box};
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
        if(hX==food.x && hY==food.y){ score++; document.getElementById("status").innerText = "Score: " + score; food={x:Math.floor(Math.random()*19)*box, y:Math.floor(Math.random()*19)*box}; }
        else if(d) snake.pop();
        let h={x:hX, y:hY};
        if(hX<0||hX>=400||hY<0||hY>=400||(d && snake.some(z=>z.x==h.x&&z.y==h.y))){
            document.getElementById("status").innerText = "Game Over! Final Score: " + score;
            document.getElementById("status").style.color = "#F87171";
            clearInterval(g);
        }
        if(d) snake.unshift(h);
    }
    let g = setInterval(draw, 100);
    </script>
    """
    st.components.v1.html(SNAKE_HTML, height=550)
