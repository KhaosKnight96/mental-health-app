import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, date

# --- 1. SETTINGS & SESSION ---
st.set_page_config(page_title="Health Bridge Pro", layout="wide", initial_sidebar_state="collapsed")

if "auth" not in st.session_state: 
    st.session_state.auth = {"in": False, "mid": None, "role": "user", "name": "", "bio": "", "age": ""}

st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    .chat-bubble { padding: 12px 18px; border-radius: 18px; margin-bottom: 10px; max-width: 85%; line-height: 1.5; font-family: sans-serif; }
    .user-bubble { background: #1E40AF; color: white; margin-left: auto; border-bottom-right-radius: 2px; }
    .ai-bubble { background: #334155; color: white; margin-right: auto; border-bottom-left-radius: 2px; }
    .direct-bubble { background: #065F46; color: white; margin-right: auto; border-bottom-left-radius: 2px; border-left: 4px solid #10B981; }
    .feed-card { background: #1E293B; padding: 20px; border-radius: 15px; border: 1px solid #334155; margin-bottom: 15px; }
    .avatar-pulse { width: 60px; height: 60px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 30px; margin: 0 auto 10px; background: linear-gradient(135deg, #38BDF8, #6366F1); box-shadow: 0 0 15px rgba(56, 189, 248, 0.4); }
</style>
""", unsafe_allow_html=True)

# --- 2. DATA CORE ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=2)
def get_data(ws):
    try:
        df = conn.read(worksheet=ws, ttl=0)
        df.columns = [str(c).strip().lower() for c in df.columns]
        return df
    except: return pd.DataFrame()

def save_to_sheet(ws_name, df_to_add):
    try:
        existing = conn.read(worksheet=ws_name, ttl=0)
        updated = pd.concat([existing, df_to_add], ignore_index=True)
        conn.update(worksheet=ws_name, data=updated)
        st.cache_data.clear()
    except Exception as e: st.error(f"Save Error: {e}")

def save_log(agent, role, content):
    new_row = pd.DataFrame([{
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "memberid": st.session_state.auth['mid'], 
        "agent": agent, "role": role, "content": content
    }])
    save_to_sheet("ChatLogs", new_row)

# --- 3. AI LOGIC ---
def get_ai_response(agent, prompt, history):
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"].strip())
        sys = f"You are {agent}. Speak like a real human friend."
        full_history = [{"role": "system", "content": sys}] + history[-5:] + [{"role": "user", "content": prompt}]
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=full_history, temperature=0.8)
        return res.choices[0].message.content
    except Exception as e: return f"AI Error: {e}"

# --- 4. AUTH ---
if not st.session_state.auth["in"]:
    st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge</h1>", unsafe_allow_html=True)
    u = st.text_input("Member ID").strip().lower()
    p = st.text_input("Password", type="password")
    if st.button("Sign In", use_container_width=True):
        users = get_data("Users")
        m = users[(users['memberid'].astype(str).str.lower() == u) & (users['password'].astype(str) == p)]
        if not m.empty:
            st.session_state.auth.update({
                "in": True, "mid": u, "role": str(m.iloc[0]['role']).lower(),
                "name": str(m.iloc[0].get('name', 'User')), 
                "bio": str(m.iloc[0].get('bio', 'No bio yet.')),
                "age": str(m.iloc[0].get('age', 'N/A'))
            })
            st.rerun()
    st.stop()

# --- 5. INTERFACE ---
tabs = st.tabs(["👤 Profile", "🤝 Cooper", "✨ Clara", "👥 Friends", "📩 Messages", "🎮 Arcade", "🛠️ Admin", "🚪 Logout"])

# --- PROFILE & FEED ---
with tabs[0]:
    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown('<div class="avatar-pulse">👤</div>', unsafe_allow_html=True)
        st.subheader(st.session_state.auth['name'])
        st.write(f"**Age:** {st.session_state.auth['age']} | **ID:** {st.session_state.auth['mid']}")
        st.write(f"**Bio:** {st.session_state.auth['bio']}")
        with st.expander("📝 Edit Profile"):
            n_name = st.text_input("Name", value=st.session_state.auth['name'])
            n_age = st.text_input("Age", value=st.session_state.auth['age'])
            n_bio = st.text_area("Bio", value=st.session_state.auth['bio'])
            if st.button("Save Profile"):
                users = get_data("Users")
                users.loc[users['memberid'].astype(str).str.lower() == st.session_state.auth['mid'], ['name', 'age', 'bio']] = [n_name, n_age, n_bio]
                conn.update(worksheet="Users", data=users)
                st.session_state.auth.update({"name": n_name, "age": n_age, "bio": n_bio})
                st.cache_data.clear(); st.rerun()
    with c2:
        st.subheader("📢 Community Feed")
        post_txt = st.text_area("Post to feed...", label_visibility="collapsed")
        if st.button("Post"):
            if post_txt: save_log("Feed", "user", post_txt); st.rerun()
        l_df = get_data("ChatLogs")
        if not l_df.empty:
            feed = l_df[l_df['agent'] == "Feed"].sort_values('timestamp', ascending=False).head(10)
            for _, p in feed.iterrows():
                st.markdown(f'<div class="feed-card"><b>@{p["memberid"]}</b><br><small>{p["timestamp"]}</small><p>{p["content"]}</p></div>', unsafe_allow_html=True)

# --- FRIENDS TAB (ENHANCED) ---
with tabs[3]:
    st.subheader("👥 Find & Manage Friends")
    f_df = get_data("Friends")
    u_df = get_data("Users")
    l_df = get_data("ChatLogs")
    
    col_a, col_b = st.columns(2)
    with col_a:
        st.write("### Add Friends")
        target_id = st.text_input("Enter Member ID:").strip().lower()
        if st.button("Send Request"):
            if target_id == st.session_state.auth['mid']: st.error("You cannot add yourself.")
            elif target_id not in u_df['memberid'].astype(str).values: st.error("User not found.")
            else:
                exists = not f_df[((f_df['sender'] == st.session_state.auth['mid']) & (f_df['receiver'] == target_id)) | 
                                 ((f_df['sender'] == target_id) & (f_df['receiver'] == st.session_state.auth['mid']))].empty
                if exists: st.warning("Relationship already exists.")
                else:
                    new_req = pd.DataFrame([{"sender": st.session_state.auth['mid'], "receiver": target_id, "status": "pending"}])
                    save_to_sheet("Friends", new_req); st.success("Request Sent!"); st.rerun()

        st.write("### Pending Requests")
        in_reqs = f_df[(f_df['receiver'] == st.session_state.auth['mid']) & (f_df['status'] == "pending")]
        for _, r in in_reqs.iterrows():
            if st.button(f"✅ Accept {r['sender']}"):
                f_df.loc[(f_df['sender'] == r['sender']) & (f_df['receiver'] == st.session_state.auth['mid']), 'status'] = "accepted"
                conn.update(worksheet="Friends", data=f_df); st.cache_data.clear(); st.rerun()

    with col_b:
        st.write("### My Friends")
        f1 = f_df[(f_df['sender'] == st.session_state.auth['mid']) & (f_df['status'] == "accepted")]['receiver'].tolist()
        f2 = f_df[(f_df['receiver'] == st.session_state.auth['mid']) & (f_df['status'] == "accepted")]['sender'].tolist()
        friends = list(set(f1 + f2))
        
        if not friends: st.info("No friends yet.")
        else:
            sel_friend = st.selectbox("View Friend Profile:", ["Select a Friend"] + friends)
            if sel_friend != "Select a Friend":
                f_info = u_df[u_df['memberid'].astype(str).str.lower() == sel_friend].iloc[0]
                st.markdown(f"""
                <div style="background:#1E293B; padding:15px; border-radius:10px; border-left: 5px solid #38BDF8;">
                    <h4>{f_info.get('name', sel_friend)}</h4>
                    <p><b>Age:</b> {f_info.get('age', 'N/A')}</p>
                    <p><b>Bio:</b> {f_info.get('bio', 'No bio.')}</p>
                </div>
                """, unsafe_allow_html=True)
                
                st.write(f"--- {sel_friend}'s Recent Posts ---")
                f_posts = l_df[(l_df['memberid'] == sel_friend) & (l_df['agent'] == "Feed")].sort_values('timestamp', ascending=False).head(5)
                if f_posts.empty: st.caption("No posts yet.")
                for _, p in f_posts.iterrows():
                    st.markdown(f'<div class="feed-card" style="padding:10px;">{p["content"]}<br><small>{p["timestamp"]}</small></div>', unsafe_allow_html=True)

# --- MESSAGES (FRIENDS ONLY) ---
with tabs[4]:
    f_df = get_data("Friends")
    f1 = f_df[(f_df['sender'] == st.session_state.auth['mid']) & (f_df['status'] == "accepted")]['receiver'].tolist()
    f2 = f_df[(f_df['receiver'] == st.session_state.auth['mid']) & (f_df['status'] == "accepted")]['sender'].tolist()
    my_friends = list(set(f1 + f2))
    if not my_friends: st.info("Add friends to start messaging.")
    else:
        sel_f = st.selectbox("Select Friend:", my_friends, key="msg_select")
        all_logs = get_data("ChatLogs")
        chain = all_logs[((all_logs['memberid'] == st.session_state.auth['mid']) & (all_logs['agent'] == f"Direct:{sel_f}")) | 
                         ((all_logs['memberid'] == sel_f) & (all_logs['agent'] == f"Direct:{st.session_state.auth['mid']}"))].sort_values('timestamp')
        with st.container(height=350, border=True):
            for _, m in chain.iterrows():
                sty = "user-bubble" if m['memberid'] == st.session_state.auth['mid'] else "direct-bubble"
                st.markdown(f'<div class="chat-bubble {sty}">{m["content"]}</div>', unsafe_allow_html=True)
        if p_msg := st.chat_input("Send message..."):
            save_log(f"Direct:{sel_f}", "user", p_msg); st.rerun()

# --- AI CHATS ---
for i, agent in enumerate(["Cooper", "Clara"]):
    with tabs[i+1]:
        st.markdown(f'<div class="avatar-pulse">{"🤝" if agent=="Cooper" else "✨"}</div>', unsafe_allow_html=True)
        all_logs = get_data("ChatLogs")
        ulogs = all_logs[(all_logs['memberid'] == st.session_state.auth['mid']) & (all_logs['agent'] == agent)].tail(20)
        with st.container(height=400):
            for _, r in ulogs.iterrows():
                sty = "user-bubble" if r['role'] == "user" else "ai-bubble"
                st.markdown(f'<div class="chat-bubble {sty}">{r["content"]}</div>', unsafe_allow_html=True)
        if p := st.chat_input(f"Chat with {agent}...", key=f"ai_{agent}"):
            save_log(agent, "user", p)
            res = get_ai_response(agent, p, [{"role": r.role, "content": r.content} for _, r in ulogs.iterrows()])
            save_log(agent, "assistant", res); st.rerun()

# --- ARCADE (WITH SIMON SAYS) ---
with tabs[5]:
    game = st.selectbox("Games", ["Snake", "Memory Match", "Simon Says"])
    if game == "Snake":
        st.components.v1.html("""<div style="text-align:center; background:#1E293B; padding:15px; border-radius:20px;"><div id="scr" style="color:white">Score: 0</div><canvas id="snk" width="300" height="300" style="background:#0F172A; border:2px solid #38BDF8; display:block; margin:auto;"></canvas></div><script>const c=document.getElementById('snk'), x=c.getContext('2d'); let sn=[{x:150,y:150}], f={x:75,y:75}, d='R', sc=0; window.onkeydown=e=>{ if(e.key=='ArrowUp'&&d!='D')d='U'; if(e.key=='ArrowDown'&&d!='U')d='D'; if(e.key=='ArrowLeft'&&d!='R')d='L'; if(e.key=='ArrowRight'&&d!='L')d='R'; }; setInterval(()=>{ x.fillStyle='#0F172A'; x.fillRect(0,0,300,300); x.fillStyle='#F87171'; x.fillRect(f.x,f.y,15,15); x.fillStyle='#38BDF8'; sn.forEach(p=>x.fillRect(p.x,p.y,15,15)); let h={...sn[0]}; if(d=='L')h.x-=15; if(d=='U')h.y-=15; if(d=='R')h.x+=15; if(d=='D')h.y+=15; if(h.x==f.x&&h.y==f.y){sc++; f={x:Math.floor(Math.random()*19)*15,y:Math.floor(Math.random()*19)*15}} else sn.pop(); if(h.x<0||h.x>=300||h.y<0||h.y>=300){sn=[{x:150,y:150}]; sc=0; d='R';} sn.unshift(h); document.getElementById('scr').innerText="Score: "+sc; }, 130);</script>""", height=420)
    elif game == "Memory Match":
        st.components.v1.html("""<div style="text-align:center; background:#1E293B; padding:20px; border-radius:15px;"><div id="grid" style="display:grid; grid-template-columns:repeat(4, 1fr); gap:8px; max-width:300px; margin:auto;"></div></div><script>const icons=['❤️','❤️','⭐','⭐','🍀','🍀','💎','💎','🍎','🍎','🎈','🎈','🎨','🎨','⚡','⚡'].sort(()=>Math.random()-0.5); let act=[]; icons.forEach((ic)=>{ let c=document.createElement('div'); c.style="height:65px; background:#334155; border-radius:8px; display:flex; align-items:center; justify-content:center; font-size:24px; cursor:pointer;"; c.onclick=()=>{ if(act.length<2 && c.innerText==''){ c.innerText=ic; act.push({c,ic}); if(act.length==2){ if(act[0].ic==act[1].ic) act=[]; else setTimeout(()=>{ act[0].c.innerText=''; act[1].c.innerText=''; act=[]; }, 600); } } }; document.getElementById('grid').appendChild(c); });</script>""", height=380)
    elif game == "Simon Says":
        st.components.v1.html("""<div style="text-align:center; background:#1E293B; padding:20px; border-radius:15px;"><div id="stat" style="color:white; margin-bottom:15px;">Level 1</div><div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; max-width:240px; margin:auto;"><div id="0" onclick="tp(0)" style="height:80px; background:#EF4444; opacity:0.3; border-radius:10px;"></div><div id="1" onclick="tp(1)" style="height:80px; background:#3B82F6; opacity:0.3; border-radius:10px;"></div><div id="2" onclick="tp(2)" style="height:80px; background:#EAB308; opacity:0.3; border-radius:10px;"></div><div id="3" onclick="tp(3)" style="height:80px; background:#22C55E; opacity:0.3; border-radius:10px;"></div></div><button onclick="sq=[];nxt()" style="margin-top:15px; width:100%; padding:10px; background:#38BDF8; color:white; border:none; border-radius:8px; cursor:pointer;">START</button></div><script>let sq=[], u=[], lv=1; function nxt(){ u=[]; sq.push(Math.floor(Math.random()*4)); ply(); } function ply(){ let i=0; let t=setInterval(()=>{ fl(sq[i]); i++; if(i>=sq.length)clearInterval(t); }, 600); } function fl(id){ let e=document.getElementById(id); e.style.opacity='1'; setTimeout(()=>e.style.opacity='0.3', 300); } function tp(id){ fl(id); u.push(id); if(u[u.length-1]!==sq[u.length-1]){ alert('Game Over!'); sq=[]; lv=1; document.getElementById('stat').innerText='Level 1'; } else if(u.length==sq.length){ lv++; document.getElementById('stat').innerText='Level '+lv; setTimeout(nxt, 800); } }</script>""", height=400)

# --- 6. ADMIN ---
with tabs[6]:
    if st.session_state.auth["role"] == "admin":
        st.subheader("🛡️ Admin Log Explorer")
        l_df = get_data("ChatLogs")
        if not l_df.empty:
            l_df['dt_obj'] = pd.to_datetime(l_df['timestamp'], errors='coerce')
            with st.expander("🔍 Filter Tools", expanded=True):
                f_u = st.selectbox("User", ["All"] + sorted(list(l_df['memberid'].unique())))
                dr = st.date_input("Date Range", value=(l_df['dt_obj'].min().date(), date.today()))
            filt = l_df.copy()
            if f_u != "All": filt = filt[filt['memberid'].astype(str) == str(f_u)]
            if isinstance(dr, (list, tuple)) and len(dr) == 2:
                filt = filt[(filt['dt_obj'].dt.date >= dr[0]) & (filt['dt_obj'].dt.date <= dr[1])]
            st.dataframe(filt.drop(columns=['dt_obj']).sort_values('timestamp', ascending=False), use_container_width=True)
    else: st.error("Admin Only")

with tabs[7]:
    if st.button("Logout"): st.session_state.clear(); st.rerun()
