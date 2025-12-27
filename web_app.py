import streamlit as st
import pandas as pd
import datetime
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# --- 1. SETTINGS ---
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

def get_clean_users():
    try:
        df = conn.read(worksheet="Users", ttl=0)
        df.columns = [str(c).strip() for c in df.columns]
        target = [c for c in df.columns if c.lower().replace(" ", "") == "highscore"]
        if target:
            df = df.rename(columns={target[0]: "HighScore"})
            df['HighScore'] = pd.to_numeric(df['HighScore'], errors='coerce').fillna(0).astype(int)
        return df
    except: return pd.DataFrame()

# --- 3. THE ACTUAL SYNC LOGIC (FIXED) ---
qp = st.query_params
if "save_score" in qp and st.session_state.auth.get("logged_in"):
    try:
        new_score = int(float(qp["save_score"]))
        udf = get_clean_users()
        cid = str(st.session_state.auth['cid'])
        user_mask = udf['Username'].astype(str) == cid
        
        if any(user_mask):
            idx = udf.index[user_mask][0]
            current_best = int(udf.at[idx, 'HighScore'])
            if new_score > current_best:
                udf.at[idx, 'HighScore'] = new_score
                conn.update(worksheet="Users", data=udf)
                st.cache_data.clear()
                st.toast(f"🏆 Record Saved: {new_score}!", icon="🔥")
            else:
                st.toast(f"Final Score: {new_score}", icon="🎮")
    except Exception as e:
        st.error(f"Sync Error: {e}")
    
    # Clear params and go to dashboard
    st.query_params.clear()
    st.rerun()

# --- 4. LOGIN ---
if not st.session_state.auth["logged_in"]:
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.title("🧠 Health Bridge")
        u = st.text_input("Couple ID")
        p = st.text_input("Password", type="password")
        if st.button("Sign In"):
            udf = get_clean_users()
            m = udf[(udf['Username'].astype(str) == u) & (udf['Password'].astype(str) == p)]
            if not m.empty:
                st.session_state.auth.update({"logged_in": True, "cid": u, "name": m.iloc[0]['Fullname']})
                st.rerun()
    st.stop()

# --- 5. NAVIGATION ---
with st.sidebar:
    st.title("🌉 Health Bridge")
    page = st.radio("Navigation", ["Dashboard", "Snake"])
    if st.button("Logout"):
        st.session_state.auth = {"logged_in": False, "cid": None, "name": None}
        st.rerun()

# --- 6. PAGES ---
if page == "Dashboard":
    st.header(f"Welcome, {st.session_state.auth['name']}")
    udf = get_clean_users()
    row = udf[udf['Username'].astype(str) == str(st.session_state.auth['cid'])]
    pb = int(row['HighScore'].values[0]) if not row.empty else 0
    st.metric("Personal Best", f"{pb} pts")

elif page == "Snake":
    st.title("🐍 Zen Snake")
    
    # Game Logic
    SNAKE_HTML = """
    <div style="display:flex; flex-direction:column; align-items:center; background:#1E293B; padding:20px; border-radius:20px;">
        <canvas id="s" width="400" height="400" style="border:4px solid #38BDF8; background:#0F172A;"></canvas>
        <div id="o" style="display:none; position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); background:rgba(0,0,0,0.9); padding:30px; border-radius:20px; text-align:center;">
            <h1 style="color:white; font-family:sans-serif;">GAME OVER</h1>
            <p id="fs" style="color:cyan; font-size:24px;"></p>
            <button id="sb" style="padding:10px 20px; background:#38BDF8; color:white; border:none; border-radius:5px; cursor:pointer;">💾 SAVE & EXIT</button>
        </div>
    </div>
    <script>
    const c=document.getElementById("s"), x=c.getContext("2d"), b=20;
    let s=0, d, n=[{x:9*b,y:10*b}], f={x:Math.floor(Math.random()*19)*b, y:Math.floor(Math.random()*19)*b};
    
    document.getElementById("sb").onclick = () => {
        // This is the specific fix for Streamlit Cloud/Iframe environments
        const url = new URL(window.parent.location.href);
        url.searchParams.set('save_score', s);
        window.parent.location.href = url.href;
    };

    document.onkeydown = e => {
        if(e.keyCode==37 && d!="RIGHT") d="LEFT";
        if(e.keyCode==38 && d!="DOWN") d="UP";
        if(e.keyCode==39 && d!="LEFT") d="RIGHT";
        if(e.keyCode==40 && d!="UP") d="DOWN";
    };

    function draw() {
        x.fillStyle="#0F172A"; x.fillRect(0,0,400,400);
        x.fillStyle="red"; x.fillRect(f.x,f.y,b,b);
        n.forEach((p,i)=>{ x.fillStyle=i==0?"cyan":"blue"; x.fillRect(p.x,p.y,b,b); });
        let hX=n[0].x, hY=n[0].y;
        if(d=="LEFT") hX-=b; if(d=="UP") hY-=b; if(d=="RIGHT") hX+=b; if(d=="DOWN") hY+=b;
        if(hX==f.x && hY==f.y){ s++; f={x:Math.floor(Math.random()*19)*b, y:Math.floor(Math.random()*19)*b}; }
        else if(d) n.pop();
        let h={x:hX,y:hY};
        if(hX<0||hX>=400||hY<0||hY>=400||(d && n.some(z=>z.x==h.x&&z.y==h.y))){
            clearInterval(g); document.getElementById("fs").innerText="Score: "+s;
            document.getElementById("o").style.display="block";
        }
        if(d) n.unshift(h);
    }
    let g = setInterval(draw,100);
    </script>
    """
    st.components.v1.html(SNAKE_HTML, height=500)
