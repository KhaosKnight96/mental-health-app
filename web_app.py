import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.graph_objects as go

# --- 1. SETTINGS & SESSION INITIALIZATION ---
st.set_page_config(page_title="Health Bridge Pro", layout="wide", initial_sidebar_state="collapsed")

# Standardize Session State
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

# --- 2. CACHED DATA LOGIC (SOLVES QUOTA 429) ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=15) # Saves API calls by remembering data for 15 seconds
def get_data(ws):
    try:
        df = conn.read(worksheet=ws, ttl=0)
        # Clean headers to prevent KeyError
        df.columns = [str(c).strip().lower() for c in df.columns]
        return df
    except Exception as e:
        if "429" in str(e):
            st.error("Google Sheets Quota Exceeded. Please wait 30 seconds.")
        return pd.DataFrame()

def save_log(agent, role, content, target_mid=None, is_admin_alert=False):
    try:
        mid = target_mid if is_admin_alert else st.session_state.auth['mid']
        # Sentiment analysis only for user messages
        sent_score = 0
        if role == "user":
            try:
                client = Groq(api_key=st.secrets["GROQ_API_KEY"].strip())
                res = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "system", "content": "Score sentiment -5 to 5. Integer only."},
                              {"role": "user", "content": content}]
                )
                sent_score = int(res.choices[0].message.content.strip())
            except: sent_score = 0

        new_row = pd.DataFrame([{
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "memberid": mid,
            "agent": agent, 
            "role": "admin_alert" if is_admin_alert else role,
            "content": content,
            "sentiment": sent_score
        }])
        
        # Bypass cache for saving
        all_logs = conn.read(worksheet="ChatLogs", ttl=0)
        updated_logs = pd.concat([all_logs, new_row], ignore_index=True)
        conn.update(worksheet="ChatLogs", data=updated_logs)
        st.cache_data.clear() # Force fresh data on next read
    except Exception as e:
        st.error(f"Save Error: {e}")

# --- 3. UI FRAGMENTS ---
@st.fragment(run_every="30s") # Reduced frequency to save quota
def alert_listener():
    if st.session_state.auth["in"]:
        all_logs = get_data("ChatLogs")
        if not all_logs.empty and 'role' in all_logs.columns:
            my_alerts = all_logs[(all_logs['memberid'].astype(str) == str(st.session_state.auth['mid'])) & (all_logs['role'] == 'admin_alert')]
            if not my_alerts.empty:
                st.toast(f"🚨 ADMIN NOTICE: {my_alerts.iloc[-1]['content']}", icon="📢")

def get_ai_response(agent, prompt, history):
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"].strip())
        users_df = get_data("Users")
        user_profile = users_df[users_df['memberid'].astype(str) == str(st.session_state.auth['mid'])].iloc[0]
        
        logs_df = get_data("ChatLogs")
        user_logs = logs_df[logs_df['memberid'].astype(str) == str(st.session_state.auth['mid'])]
        
        recent_sent = user_logs.tail(5)['sentiment'].mean() if not user_logs.empty else 0
        vibe = "thriving" if recent_sent > 1 else ("struggling" if recent_sent < -1 else "stable")

        sys = f"You are {agent}. Help {user_profile.get('name', 'Friend')}. Vibe: {vibe}."
        full_history = [{"role": "system", "content": sys}] + history[-10:] + [{"role": "user", "content": prompt}]
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=full_history)
        return res.choices[0].message.content
    except Exception as e: return f"AI Error: {e}"

# --- 4. AUTHENTICATION ---
if not st.session_state.auth["in"]:
    st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge</h1>", unsafe_allow_html=True)
    auth_mode = st.radio("Access", ["Sign In", "Sign Up"], horizontal=True)
    
    with st.container(border=True):
        if auth_mode == "Sign In":
            u = st.text_input("Member ID").strip().lower()
            p = st.text_input("Password", type="password")
            if st.button("Sign In", use_container_width=True):
                users = get_data("Users")
                if not users.empty:
                    m = users[(users['memberid'].astype(str).str.lower() == u) & (users['password'].astype(str) == p)]
                    if not m.empty:
                        st.session_state.auth.update({"in": True, "mid": u, "role": str(m.iloc[0]['role']).lower()})
                        all_logs = get_data("ChatLogs")
                        if not all_logs.empty:
                            ulogs = all_logs[all_logs['memberid'].astype(str) == u].sort_values('timestamp').tail(50)
                            st.session_state.cooper_logs = [{"role": r.role, "content": r.content} for _,r in ulogs[ulogs.agent == "Cooper"].iterrows()]
                            st.session_state.clara_logs = [{"role": r.role, "content": r.content} for _,r in ulogs[ulogs.agent == "Clara"].iterrows()]
                        st.rerun()
                    else: st.error("Invalid Credentials")
        else:
            new_name = st.text_input("Name")
            new_u = st.text_input("New Member ID").strip().lower()
            new_p = st.text_input("New Password", type="password")
            if st.button("Register"):
                users = get_data("Users")
                new_row = pd.DataFrame([{"memberid": new_u, "password": new_p, "name": new_name, "role": "user", "joined": datetime.now().strftime("%Y-%m-%d")}])
                conn.update(worksheet="Users", data=pd.concat([users, new_row], ignore_index=True))
                st.success("Success! Please Sign In.")
    st.stop()

alert_listener()

# --- 5. MAIN NAVIGATION ---
tabs = st.tabs(["🏠 Cooper", "🛋️ Clara", "🎮 Games", "🛡️ Admin", "🚪 Logout"])

# Agent Rooms
for i, agent in enumerate(["Cooper", "Clara"]):
    with tabs[i]:
        st.markdown(f'<div class="avatar-pulse">{"🤝" if agent=="Cooper" else "📊"}</div>', unsafe_allow_html=True)
        logs = st.session_state.cooper_logs if agent == "Cooper" else st.session_state.clara_logs
        
        chat_box = st.container(height=450, border=False)
        with chat_box:
            for m in logs:
                div = "user-bubble" if m["role"] == "user" else ("admin-bubble" if m["role"] == "admin_alert" else "ai-bubble")
                st.markdown(f'<div class="chat-bubble {div}">{m["content"]}</div>', unsafe_allow_html=True)

        if p := st.chat_input(f"Chat with {agent}...", key=f"chat_{agent}"):
            logs.append({"role": "user", "content": p})
            save_log(agent, "user", p)
            with st.spinner("..."):
                res = get_ai_response(agent, p, logs)
            logs.append({"role": "assistant", "content": res})
            save_log(agent, "assistant", res)
            st.rerun()

# Arcade
with tabs[2]:
    game = st.radio("Activity", ["Snake", "Memory Pattern"], horizontal=True)
    if game == "Snake":
        st.components.v1.html("""<div style='text-align:center; background:#1E293B; padding:10px; border-radius:15px;'><canvas id='s' width='300' height='300' style='border:2px solid #38BDF8;'></canvas></div><script>let sn=[{x:150,y:150}],f={x:75,y:75},d='R',c=document.getElementById('s'),x=c.getContext('2d'); setInterval(()=>{x.fillStyle='#0F172A';x.fillRect(0,0,300,300);x.fillStyle='#F87171';x.fillRect(f.x,f.y,15,15);sn.forEach(p=>{x.fillStyle='#38BDF8';x.fillRect(p.x,p.y,15,15)});let h={...sn[0]};if(d=='L')h.x-=15;if(d=='U')h.y-=15;if(d=='R')h.x+=15;if(d=='D')h.y+=15;if(h.x==f.x&&h.y==f.y){f={x:Math.floor(Math.random()*20)*15,y:Math.floor(Math.random()*20)*15}}else sn.pop();sn.unshift(h);},100);window.onkeydown=e=>{if(e.key.includes('Left')&&d!='R')d='L';if(e.key.includes('Up')&&d!='D')d='U';if(e.key.includes('Right')&&d!='L')d='R';if(e.key.includes('Down')&&d!='U')d='D'};</script>""", height=400)

# Robust Admin Panel
with tabs[3]:
    if st.session_state.auth["role"] == "admin":
        sub = st.tabs(["🔍 Explorer", "🚨 Broadcast", "📈 Analytics", "🛠️ Tools"])
        l_df = get_data("ChatLogs")
        u_df = get_data("Users")
        
        if not l_df.empty:
            l_df['timestamp'] = pd.to_datetime(l_df['timestamp'], format='mixed', errors='coerce')
            
            with sub[0]:
                st.metric("Total Logs", len(l_df))
                u_sel = st.selectbox("User", ["All"] + list(l_df['memberid'].unique()))
                filt = l_df if u_sel == "All" else l_df[l_df['memberid'].astype(str) == u_sel]
                st.dataframe(filt.sort_values('timestamp', ascending=False), use_container_width=True)

            with sub[1]:
                t_u = st.selectbox("Target ID", u_df['memberid'].unique())
                msg = st.text_area("Admin Message")
                if st.button("Send Alert"):
                    save_log("Cooper", "admin_alert", msg, target_mid=t_u, is_admin_alert=True)
                    st.success("Pushed.")

            with sub[2]:
                m_df = l_df[l_df['role'] == 'user'].sort_values('timestamp')
                st.plotly_chart(go.Figure(go.Scatter(x=m_df['timestamp'], y=m_df['sentiment'])), use_container_width=True)

            with sub[3]:
                if st.button("🔥 Wipe Logs for " + str(u_sel)):
                    conn.update(worksheet="ChatLogs", data=l_df[l_df['memberid'].astype(str) != str(u_sel)])
                    st.cache_data.clear()
                    st.rerun()
    else: st.error("Admin Only")

with tabs[4]:
    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()
