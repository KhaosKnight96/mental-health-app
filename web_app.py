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

# --- 2. CORE LOGIC & QUOTA PROTECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=15)
def get_data(ws):
    try:
        df = conn.read(worksheet=ws, ttl=0)
        df.columns = [str(c).strip().lower() for c in df.columns]
        return df
    except Exception as e:
        if "429" in str(e): st.error("Quota reached. Waiting for Google...")
        return pd.DataFrame()

def save_log(agent, role, content, target_mid=None, is_admin_alert=False):
    try:
        mid = target_mid if is_admin_alert else st.session_state.auth['mid']
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
        
        # Fresh read for update
        all_logs = conn.read(worksheet="ChatLogs", ttl=0)
        updated_logs = pd.concat([all_logs, new_row], ignore_index=True)
        conn.update(worksheet="ChatLogs", data=updated_logs)
        st.cache_data.clear() # Reset cache so update is visible
    except Exception as e:
        st.error(f"Save Error: {e}")

# --- 3. UI COMPONENTS ---
@st.fragment(run_every="30s")
def alert_listener():
    if st.session_state.auth["in"]:
        all_logs = get_data("ChatLogs")
        if not all_logs.empty and 'role' in all_logs.columns:
            my_alerts = all_logs[(all_logs['memberid'].astype(str) == str(st.session_state.auth['mid'])) & (all_logs['role'] == 'admin_alert')]
            if not my_alerts.empty:
                st.toast(f"🚨 ADMIN: {my_alerts.iloc[-1]['content']}", icon="📢")

def get_ai_response(agent, prompt, history):
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"].strip())
        users_df = get_data("Users")
        user_profile = users_df[users_df['memberid'].astype(str) == str(st.session_state.auth['mid'])].iloc[0]
        
        logs_df = get_data("ChatLogs")
        user_logs = logs_df[logs_df['memberid'].astype(str) == str(st.session_state.auth['mid'])]
        
        recent_sent = user_logs.tail(5)['sentiment'].mean() if not user_logs.empty else 0
        vibe = "thriving" if recent_sent > 1 else ("struggling" if recent_sent < -1 else "stable")

        sys = f"You are {agent}. Help {user_profile.get('name', 'User')}. Context: {vibe}."
        full_history = [{"role": "system", "content": sys}] + history[-10:] + [{"role": "user", "content": prompt}]
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=full_history)
        return res.choices[0].message.content
    except Exception as e: return f"AI Error: {e}"

# --- 4. AUTH ---
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
                st.success("Account Created!")
    st.stop()

alert_listener()

# --- 5. MAIN UI ---
tabs = st.tabs(["🏠 Cooper", "🛋️ Clara", "🎮 Games", "🛡️ Admin", "🚪 Logout"])

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

# --- 6. ARCADE RESTORED ---
with tabs[2]:
    game_mode = st.radio("Select Activity", ["Snake", "Memory Pattern"], horizontal=True)
    JS_CORE = """<script>window.addEventListener("keydown", e => {if(["ArrowUp","ArrowDown","ArrowLeft","ArrowRight"].includes(e.key)) e.preventDefault();}, {passive: false});</script>"""
    if game_mode == "Snake":
        st.components.v1.html(JS_CORE + """<div style='text-align:center; background:#1E293B; padding:20px; border-radius:20px; font-family:sans-serif;'><div style='color:#38BDF8; margin-bottom:10px;'>Score: <span id='s'>0</span></div><canvas id='sn' width='300' height='300' style='border:2px solid #38BDF8; border-radius:10px;'></canvas></div><script>let sn=[{x:150,y:150}], f={x:75,y:75}, d='R', s=0, c=document.getElementById('sn'), x=c.getContext('2d'); setInterval(()=>{ x.fillStyle='#0F172A'; x.fillRect(0,0,300,300); x.fillStyle='#F87171'; x.fillRect(f.x,f.y,15,15); sn.forEach(p=>{x.fillStyle='#38BDF8'; x.fillRect(p.x,p.y,15,15)}); let h={...sn[0]}; if(d=='L')h.x-=15; if(d=='U')h.y-=15; if(d=='R')h.x+=15; if(d=='D')h.y+=15; if(h.x==f.x&&h.y==f.y){s++; f={x:Math.floor(Math.random()*20)*15,y:Math.floor(Math.random()*20)*15}}else sn.pop(); sn.unshift(h); document.getElementById('s').innerText=s; }, 100); window.addEventListener("keydown", e=>{if(e.key=="ArrowLeft"&&d!="R")d="L";if(e.key=="ArrowUp"&&d!="D")d="U";if(e.key=="ArrowRight"&&d!="L")d="R";if(e.key=="ArrowDown"&&d!="U")d="D"});</script>""", height=450)
    else:
        st.write("Pattern game loading...")

# --- 7. FULL ADMIN RESTORED ---
with tabs[3]:
    if st.session_state.auth["role"] == "admin":
        admin_sub = st.tabs(["🔍 Explorer", "🚨 Broadcast", "📈 Analytics", "🛠️ System Tools"])
        l_df = get_data("ChatLogs")
        u_df = get_data("Users")
        
        if not l_df.empty:
            l_df['timestamp'] = pd.to_datetime(l_df['timestamp'], format='mixed', errors='coerce')
            
            with admin_sub[0]:
                st.subheader("📋 Global Log Explorer")
                m1, m2, m3 = st.columns(3)
                m1.metric("Total Logs", len(l_df))
                m2.metric("Users", l_df['memberid'].nunique())
                m3.metric("Avg Sentiment", round(l_df[l_df['role']=='user']['sentiment'].mean(), 2) if not l_df.empty else 0)

                c1, c2, c3 = st.columns([2,1,1])
                s_q = c1.text_input("🔍 Search Logs...")
                u_f = c2.selectbox("Filter User", ["All"] + sorted([str(x) for x in l_df['memberid'].unique()]))
                a_f = c3.selectbox("Filter Agent", ["All", "Cooper", "Clara"])
                
                filt = l_df.copy()
                if u_f != "All": filt = filt[filt['memberid'].astype(str) == u_f]
                if a_f != "All": filt = filt[filt['agent'] == a_f]
                if s_q: filt = filt[filt['content'].str.contains(s_q, case=False, na=False)]
                
                st.dataframe(filt.sort_values('timestamp', ascending=False), use_container_width=True, hide_index=True)

            with admin_sub[1]:
                st.subheader("🚨 Targeted Alert")
                t_u = st.selectbox("Recipient ID", u_df['memberid'].unique())
                t_r = st.radio("Room", ["Cooper", "Clara"], horizontal=True)
                msg = st.text_area("Alert Content")
                if st.button("🚀 Push to User"):
                    save_log(t_r, "admin_alert", msg, target_mid=t_u, is_admin_alert=True)
                    st.success("Alert Sent.")

            with admin_sub[2]:
                st.subheader("📈 Emotional Trends")
                mood_df = l_df[l_df['role'] == 'user'].sort_values('timestamp')
                fig = go.Figure(go.Scatter(x=mood_df['timestamp'], y=mood_df['sentiment'], mode='lines+markers', line=dict(color='#38BDF8')))
                fig.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig, use_container_width=True)

            with admin_sub[3]:
                st.subheader("🛠️ Data Purge")
                target_wipe = st.selectbox("User ID to Wipe", ["None"] + sorted(list(u_df['memberid'].unique())))
                confirm = st.checkbox("Confirm permanent deletion")
                if st.button("🔥 Wipe User History", type="primary"):
                    if target_wipe != "None" and confirm:
                        new_logs = l_df[l_df['memberid'].astype(str) != str(target_wipe)]
                        conn.update(worksheet="ChatLogs", data=new_logs)
                        st.cache_data.clear()
                        st.success(f"History for {target_wipe} deleted.")
                        st.rerun()
    else: st.error("Access Denied")

with tabs[4]:
    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()
