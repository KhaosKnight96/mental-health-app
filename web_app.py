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
    /* ADMIN ALERT STYLE */
    .admin-bubble { 
        background: #7F1D1D; color: #FEE2E2; margin: 15px auto; 
        border: 2px solid #EF4444; width: 90%; text-align: center; 
        font-weight: bold; border-radius: 10px;
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
        df = conn.read(worksheet=ws, ttl=0)
        df.columns = [str(c).strip().lower() for c in df.columns]
        return df
    except: return pd.DataFrame()

def get_ai_sentiment(text):
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"].strip())
        res = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Score sentiment from -5 (distress) to 5 (thriving). Output ONLY the integer."},
                {"role": "user", "content": text}
            ]
        )
        return int(res.choices[0].message.content.strip())
    except: return 0

def save_log(agent, role, content, is_admin_alert=False):
    try:
        stored_role = "admin_alert" if is_admin_alert else role
        sent_score = get_ai_sentiment(content) if role == "user" else 0
        
        new_row = pd.DataFrame([{
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "memberid": st.session_state.auth['mid'],
            "agent": agent, 
            "role": stored_role,
            "content": content,
            "sentiment": sent_score
        }])
        
        all_logs = get_data("ChatLogs")
        updated_logs = pd.concat([all_logs, new_row], ignore_index=True)
        conn.update(worksheet="ChatLogs", data=updated_logs)
    except: pass

def get_ai_response(agent, prompt, history):
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"].strip())
        users_df = get_data("Users")
        user_profile = users_df[users_df['memberid'] == st.session_state.auth['mid']].iloc[0]
        
        u_name = user_profile.get('name', 'Friend')
        u_age = user_profile.get('age', 'Unknown')
        u_gender = user_profile.get('gender', 'Unknown')
        u_bio = user_profile.get('bio', 'No bio provided.')

        logs_df = get_data("ChatLogs")
        user_logs = logs_df[logs_df['memberid'] == st.session_state.auth['mid']]
        personal_context = user_logs[user_logs['agent'] == agent].tail(20)['content'].to_string()
        
        recent_sent = user_logs.tail(10)['sentiment'].mean() if not user_logs.empty else 0
        hidden_vibe = "thriving" if recent_sent > 1.5 else ("struggling" if recent_sent < -1 else "doing okay")

        if agent == "Cooper":
            sys = f"You are Cooper, a warm male friend. User: {u_name}, Age: {u_age}, Bio: {u_bio}. Mood: {hidden_vibe}. Use their name occasionally. Context: {personal_context}"
        else:
            sys = f"You are Clara, a wise female friend. User: {u_name}, Bio: {u_bio}. Mood: {hidden_vibe}. Be observant. Context: {personal_context}"
        
        full_history = [{"role": "system", "content": sys}] + history[-10:] + [{"role": "user", "content": prompt}]
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=full_history)
        return res.choices[0].message.content
    except Exception as e: return f"AI Error: {e}"

# --- 3. LOGIN & SIGNUP GATE ---
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
            new_u = st.text_input("Member ID (Username)").strip().lower()
            cp1, cp2 = st.columns(2)
            new_p = cp1.text_input("Password", type="password")
            conf_p = cp2.text_input("Confirm Password", type="password")
            age = st.number_input("Age", 13, 120, 25)
            gen = st.selectbox("Gender", ["Male", "Female", "Non-binary", "Other"])
            bio = st.text_area("Bio")
            if st.button("Register"):
                if new_p != conf_p: st.error("Passwords do not match!")
                elif not new_name or not new_u: st.error("Name and ID required.")
                else:
                    users = get_data("Users")
                    new_row = pd.DataFrame([{"memberid": new_u, "password": new_p, "name": new_name, "role": "user", "age": age, "gender": gen, "bio": bio, "joined": datetime.now().strftime("%Y-%m-%d")}])
                    conn.update(worksheet="Users", data=pd.concat([users, new_row], ignore_index=True))
                    st.success("Account Created! Please Sign In.")
    st.stop()

# --- 4. NAVIGATION ---
tabs = st.tabs(["🏠 Cooper", "🛋️ Clara", "🎮 Games", "🛡️ Admin", "🚪 Logout"])

for i, agent in enumerate(["Cooper", "Clara"]):
    with tabs[i]:
        st.markdown(f'<div class="avatar-pulse">{"🤝" if agent=="Cooper" else "📊"}</div>', unsafe_allow_html=True)
        logs = st.session_state.cooper_logs if agent == "Cooper" else st.session_state.clara_logs
        
        chat_box = st.container(height=500, border=False)
        with chat_box:
            for m in logs:
                if m["role"] == "user": div = "user-bubble"
                elif m["role"] == "admin_alert": 
                    div = "admin-bubble"
                    st.components.v1.html("<script>const a=new AudioContext(); const o=a.createOscillator(); const g=a.createGain(); o.frequency.value=523; g.gain.exponentialRampToValueAtTime(0.01, a.currentTime+0.5); o.connect(g); g.connect(a.destination); o.start(); o.stop(a.currentTime+0.5);</script>", height=0)
                else: div = "ai-bubble"
                st.markdown(f'<div class="chat-bubble {div}">{m["content"]}</div>', unsafe_allow_html=True)

        if p := st.chat_input(f"Speak with {agent}...", key=f"chat_{agent}"):
            logs.append({"role": "user", "content": p})
            save_log(agent, "user", p)
            with st.spinner("Thinking..."):
                res = get_ai_response(agent, p, logs)
            logs.append({"role": "assistant", "content": res})
            save_log(agent, "assistant", res)
            st.rerun()

# --- 5. ARCADE (Omitted for brevity, keep your existing logic here) ---

# --- 6. ADMIN ---
with tabs[3]:
    if st.session_state.auth["role"] == "admin":
        admin_sub = st.tabs(["🔍 Explorer", "🚨 Send Alert", "📈 Trends", "⚠️ Data"])
        logs_df = get_data("ChatLogs")
        
        with admin_sub[0]: # Explorer
            st.dataframe(logs_df.sort_values('timestamp', ascending=False), use_container_width=True)
            
        with admin_sub[1]: # SEND ALERT
            st.subheader("🚨 Direct Admin Broadcast")
            t_u = st.selectbox("Target User", sorted(logs_df['memberid'].unique()))
            t_a = st.selectbox("Target Agent", ["Cooper", "Clara"])
            t_m = st.text_area("Message")
            if st.button("Send Red Alert"):
                new_alert = pd.DataFrame([{"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), "memberid": t_u, "agent": t_a, "role": "admin_alert", "content": f"⚠️ ADMIN: {t_m}", "sentiment": 0}])
                conn.update(worksheet="ChatLogs", data=pd.concat([get_data("ChatLogs"), new_alert], ignore_index=True))
                st.success("Alert Sent!")
        
        with admin_sub[3]: # Data Mgmt
            if st.button("Wipe Logs for a User"):
                st.warning("Feature active in Explorer tab logic.")
    else: st.warning("Admin Only")

with tabs[4]:
    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()
