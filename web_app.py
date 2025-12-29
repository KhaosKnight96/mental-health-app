import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.graph_objects as go

# --- 1. SETTINGS & SESSION INITIALIZATION ---
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
    .chat-bubble { padding: 12px 18px; border-radius: 18px; margin-bottom: 10px; max-width: 80%; line-height: 1.5; font-family: sans-serif; }
    .user-bubble { background: #1E40AF; color: white; margin-left: auto; border-bottom-right-radius: 2px; }
    .ai-bubble { background: #334155; color: white; margin-right: auto; border-bottom-left-radius: 2px; }
    .admin-bubble { 
        background: #7F1D1D; color: #FEE2E2; margin: 15px auto; 
        border: 2px solid #EF4444; width: 90%; text-align: center; 
        font-weight: bold; border-radius: 10px; padding: 15px;
    }
    .avatar-pulse {
        width: 60px; height: 60px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
        font-size: 30px; margin: 0 auto 10px; background: linear-gradient(135deg, #38BDF8, #6366F1);
        box-shadow: 0 0 15px rgba(56, 189, 248, 0.4);
    }
</style>
""", unsafe_allow_html=True)

# --- 2. CORE LOGIC ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data(ws):
    try:
        # Read the sheet
        df = conn.read(worksheet=ws, ttl=0)
        
        # CLEANING HEADERS: This fixes the KeyError 'memberid'
        # 1. Convert to string
        # 2. Remove leading/trailing spaces
        # 3. Force lowercase
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        # If the dataframe is empty but has columns, return it
        # If it's totally missing, return an empty DF with the expected columns
        if df.empty and ws == "ChatLogs":
            return pd.DataFrame(columns=["timestamp", "memberid", "agent", "role", "content", "sentiment"])
            
        return df
    except Exception as e:
        st.error(f"Error reading worksheet '{ws}': {e}")
        return pd.DataFrame()

# --- 3. LIVE ALERT LISTENER ---
@st.fragment(run_every="8s")
def alert_listener():
    if st.session_state.auth["in"]:
        all_logs = get_data("ChatLogs")
        if not all_logs.empty:
            my_alerts = all_logs[(all_logs['memberid'] == st.session_state.auth['mid']) & (all_logs['role'] == 'admin_alert')]
            if not my_alerts.empty:
                latest_msg = my_alerts.iloc[-1]['content']
                st.toast(f"🚨 ADMIN NOTICE: {latest_msg}", icon="📢")

def get_ai_response(agent, prompt, history):
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"].strip())
        users_df = get_data("Users")
        user_profile = users_df[users_df['memberid'] == st.session_state.auth['mid']].iloc[0]
        u_name = user_profile.get('name', 'Friend')
        
        logs_df = get_data("ChatLogs")
        user_logs = logs_df[logs_df['memberid'] == st.session_state.auth['mid']]
        personal_context = user_logs[user_logs['agent'] == agent].tail(15)['content'].to_string()
        
        recent_sent = user_logs.tail(10)['sentiment'].mean() if not user_logs.empty else 0
        hidden_vibe = "thriving" if recent_sent > 1.5 else ("struggling" if recent_sent < -1 else "doing okay")

        sys = f"You are {agent}. User: {u_name}. Mood: {hidden_vibe}. Context: {personal_context}"
        full_history = [{"role": "system", "content": sys}] + history[-10:] + [{"role": "user", "content": prompt}]
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=full_history)
        return res.choices[0].message.content
    except Exception as e: return f"AI Error: {e}"

# --- 4. AUTHENTICATION ---
if not st.session_state.auth["in"]:
    st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge</h1>", unsafe_allow_html=True)
    auth_mode = st.radio("Choose Action", ["Sign In", "Sign Up"], horizontal=True)
    
    with st.container(border=True):
        if auth_mode == "Sign In":
            u = st.text_input("Member ID").strip().lower()
            p = st.text_input("Password", type="password")
            if st.button("Sign In", use_container_width=True):
                users = get_data("Users")
                m = users[(users['memberid'].astype(str).str.lower() == u) & (users['password'].astype(str) == p)]
                if not m.empty:
                    st.session_state.auth.update({"in": True, "mid": u, "role": str(m.iloc[0]['role']).lower()})
                    all_logs = get_data("ChatLogs")
                    if not all_logs.empty:
                        ulogs = all_logs[all_logs['memberid'] == u].sort_values('timestamp').tail(50)
                        st.session_state.cooper_logs = [{"role": r.role, "content": r.content} for _,r in ulogs[ulogs.agent == "Cooper"].iterrows()]
                        st.session_state.clara_logs = [{"role": r.role, "content": r.content} for _,r in ulogs[ulogs.agent == "Clara"].iterrows()]
                    st.rerun()
                else: st.error("Invalid Credentials")
        else:
            new_name = st.text_input("Full Name")
            new_u = st.text_input("Member ID").strip().lower()
            new_p = st.text_input("Password", type="password")
            if st.button("Register"):
                users = get_data("Users")
                new_row = pd.DataFrame([{"memberid": new_u, "password": new_p, "name": new_name, "role": "user", "joined": datetime.now().strftime("%Y-%m-%d")}])
                conn.update(worksheet="Users", data=pd.concat([users, new_row], ignore_index=True))
                st.success("Account Created! Please Sign In.")
    st.stop()

alert_listener()

# --- 5. TABS ---
tabs = st.tabs(["🏠 Cooper", "🛋️ Clara", "🎮 Games", "🛡️ Admin", "🚪 Logout"])

for i, agent in enumerate(["Cooper", "Clara"]):
    with tabs[i]:
        st.markdown(f'<div class="avatar-pulse">{"🤝" if agent=="Cooper" else "📊"}</div>', unsafe_allow_html=True)
        logs = st.session_state.cooper_logs if agent == "Cooper" else st.session_state.clara_logs
        chat_box = st.container(height=500, border=False)
        with chat_box:
            for m in logs:
                div = "user-bubble" if m["role"] == "user" else ("admin-bubble" if m["role"] == "admin_alert" else "ai-bubble")
                st.markdown(f'<div class="chat-bubble {div}">{m["content"]}</div>', unsafe_allow_html=True)

        if p := st.chat_input(f"Speak with {agent}...", key=f"chat_{agent}"):
            logs.append({"role": "user", "content": p})
            save_log(agent, "user", p)
            with st.spinner("Thinking..."):
                res = get_ai_response(agent, p, logs)
            logs.append({"role": "assistant", "content": res})
            save_log(agent, "assistant", res)
            st.rerun()

# --- 6. ARCADE TAB ---
with tabs[2]:
    game_mode = st.radio("Select Activity", ["Snake", "Memory Pattern", "Flash Match"], horizontal=True)
    JS_CORE = """
    <script>
    const actx = new(window.AudioContext || window.webkitAudioContext)();
    function snd(f, t, d) {
        const o = actx.createOscillator(), g = actx.createGain();
        o.type = t; o.frequency.value = f;
        g.gain.exponentialRampToValueAtTime(0.01, actx.currentTime + d);
        o.connect(g); g.connect(actx.destination);
        o.start(); o.stop(actx.currentTime + d);
    }
    window.addEventListener("keydown", e => {
        if(["ArrowUp","ArrowDown","ArrowLeft","ArrowRight"].includes(e.key)) e.preventDefault();
    }, {passive: false});
    </script>
    """
    if game_mode == "Snake":
        st.components.v1.html(JS_CORE + """<div style="text-align:center; background:#1E293B; padding:20px; border-radius:20px;"><div style="color:#38BDF8; font-family:sans-serif; margin-bottom:10px;">Score: <span id="s">0</span></div><canvas id="sn" width="300" height="300" style="border:2px solid #38BDF8; border-radius:10px;"></canvas></div><script>let sn=[{x:150,y:150}], f={x:75,y:75}, d="R", s=0, c=document.getElementById("sn"), x=c.getContext("2d"); setInterval(()=>{ x.fillStyle="#0F172A"; x.fillRect(0,0,300,300); x.fillStyle="#F87171"; x.fillRect(f.x,f.y,15,15); sn.forEach(p=>{x.fillStyle="#38BDF8"; x.fillRect(p.x,p.y,15,15)}); let h={...sn[0]}; if(d=="L")h.x-=15; if(d=="U")h.y-=15; if(d=="R")h.x+=15; if(d=="D")h.y+=15; if(h.x==f.x&&h.y==f.y){s++; snd(600,"sine",0.1); f={x:Math.floor(Math.random()*20)*15,y:Math.floor(Math.random()*20)*15}}else sn.pop(); sn.unshift(h); document.getElementById("s").innerText=s; }, 100); window.onkeydown=e=>{if(e.key=="ArrowLeft"&&d!="R")d="L";if(e.key=="ArrowUp"&&d!="D")d="U";if(e.key=="ArrowRight"&&d!="L")d="R";if(e.key=="ArrowDown"&&d!="U")d="D"};</script>""", height=450)

# --- 7. ROBUST ADMIN PANEL ---
with tabs[3]:
    if st.session_state.auth["role"] == "admin":
        admin_sub = st.tabs(["🔍 Explorer", "🚨 Broadcast", "📈 Analytics", "🛠️ System Tools"])
        
        raw_logs = get_data("ChatLogs")
        users_df = get_data("Users")
        
        if not raw_logs.empty:
            # FIX: Robust Date Parsing & Cleaning
            logs_df = raw_logs.dropna(subset=['content']).copy()
            logs_df['timestamp'] = pd.to_datetime(logs_df['timestamp'], format='mixed', errors='coerce')
            logs_df = logs_df.dropna(subset=['timestamp']) 
            
            with admin_sub[0]:
                st.subheader("📋 Global Log Explorer")
                
                # Metric Summary
                m1, m2, m3 = st.columns(3)
                m1.metric("Total Messages", len(logs_df))
                m2.metric("Active Users", logs_df['memberid'].nunique())
                m3.metric("Avg Sentiment", round(logs_df[logs_df['role']=='user']['sentiment'].mean(), 2) if not logs_df.empty else 0)

                c1, c2, c3 = st.columns([2,1,1])
                s_q = c1.text_input("🔍 Search message content...", placeholder="Keyword search...")
                u_list = ["All Users"] + sorted([str(x) for x in logs_df['memberid'].unique()])
                u_f = c2.selectbox("Filter User", u_list)
                a_f = c3.selectbox("Filter Agent", ["All Agents", "Cooper", "Clara"])
                
                f_df = logs_df.copy()
                if u_f != "All Users": f_df = f_df[f_df['memberid'].astype(str) == u_f]
                if a_f != "All Agents": f_df = f_df[f_df['agent'] == a_f]
                if s_q: f_df = f_df[f_df['content'].str.contains(s_q, case=False, na=False)]
                
                st.dataframe(f_df.sort_values('timestamp', ascending=False), use_container_width=True, hide_index=True)

            with admin_sub[1]:
                st.subheader("🚨 Targeted Broadcast")
                st.info("Broadcasted messages will only appear for the specific user selected.")
                ca, cb = st.columns(2)
                with ca:
                    t_u = st.selectbox("Recipient (Member ID)", sorted(list(users_df['memberid'].unique())), key="admin_target_broadcast")
                with cb:
                    t_r = st.radio("Display Room", ["Cooper", "Clara"], horizontal=True, key="admin_room_broadcast")
                
                msg = st.text_area("Alert Content", placeholder="Type your notice here...")
                if st.button("🚀 Push Alert", use_container_width=True):
                    if msg:
                        save_log(t_r, "admin_alert", msg, target_mid=t_u, is_admin_alert=True)
                        st.success(f"✅ Alert pushed to {t_u}")
                        st.cache_data.clear()
                    else:
                        st.error("Message cannot be empty.")

            with admin_sub[2]:
                st.subheader("📈 Emotional Sentiment Trends")
                mood_df = logs_df[logs_df['role'] == 'user'].sort_values('timestamp')
                if not mood_df.empty:
                    fig = go.Figure(go.Scatter(x=mood_df['timestamp'], y=mood_df['sentiment'], mode='lines+markers', line=dict(color='#38BDF8')))
                    fig.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', yaxis_title="Score (-5 to 5)")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Not enough data for analytics.")

            with admin_sub[3]:
                st.subheader("🛠️ Database Tools")
                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown("#### User History Purge")
                    target_wipe = st.selectbox("Select User to Wipe", ["None"] + sorted(list(users_df['memberid'].unique())))
                    confirm = st.checkbox("I confirm permanent deletion")
                    if st.button("🔥 Wipe User History", type="primary"):
                        if target_wipe != "None" and confirm:
                            new_logs = logs_df[logs_df['memberid'].astype(str) != str(target_wipe)]
                            conn.update(worksheet="ChatLogs", data=new_logs)
                            st.success(f"History for {target_wipe} deleted.")
                            st.rerun()
                with col_b:
                    st.markdown("#### Database View")
                    st.write("Registered Users:", len(users_df))
                    st.dataframe(users_df[['memberid', 'name', 'role']], hide_index=True)
    else:
        st.error("⛔ Admin Access Required")

with tabs[4]:
    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()

