import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, date

# --- 1. CONFIG ---
st.set_page_config(page_title="Health Bridge Pro", layout="wide", initial_sidebar_state="collapsed")

# Session State for Routing
if "auth" not in st.session_state:
    st.session_state.auth = {"in": False, "mid": None, "role": "user", "fname": "", "lname": "", "bio": "", "dob": "2000-01-01"}
if "view_target" not in st.session_state:
    st.session_state.view_target = None # This is the "Selected User" for the full-page view

# Styles
st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    .profile-header { background: linear-gradient(90deg, #1E293B, #0F172A); padding: 30px; border-radius: 15px; border: 1px solid #334155; margin-bottom: 20px; }
    .feed-card { background: #1E293B; padding: 20px; border-radius: 12px; border: 1px solid #334155; margin-bottom: 15px; }
    .msg-bubble { padding: 12px; border-radius: 15px; margin-bottom: 8px; width: fit-content; max-width: 80%; }
    .me { background: #2563EB; margin-left: auto; }
    .them { background: #334155; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATA CORE ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data(ws):
    df = conn.read(worksheet=ws, ttl=0)
    if df is None or df.empty: return pd.DataFrame()
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df

def sync_data(ws, df):
    conn.update(worksheet=ws, data=df)
    st.cache_data.clear()

def save_log(agent, role, content, custom_mid=None):
    mid = custom_mid if custom_mid else st.session_state.auth['mid']
    new_row = pd.DataFrame([{"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), "memberid": str(mid), "agent": agent, "role": role, "content": content}])
    sync_data("ChatLogs", pd.concat([get_data("ChatLogs"), new_row], ignore_index=True))

# --- 3. THE "FULL PROFILE" OVERLAY ---
# This function displays a full-screen profile when a user is selected
def render_full_profile(target_mid):
    u_df = get_data("Users")
    l_df = get_data("ChatLogs")
    user_row = u_df[u_df['memberid'].astype(str) == str(target_mid)]
    
    if not user_row.empty:
        u = user_row.iloc[0]
        if st.button("← Close and Return", key="close_profile"):
            st.session_state.view_target = None
            st.rerun()
            
        st.markdown(f"""<div class="profile-header">
            <h1>{u['firstname']} {u['lastname']}</h1>
            <p style="color: #94A3B8;">@{u['memberid']} | Bio: {u['bio']}</p>
        </div>""", unsafe_allow_html=True)
        
        c1, c2 = st.columns([2, 1])
        with c1:
            st.subheader("User Timeline")
            posts = l_df[(l_df['agent']=="Feed") & (l_df['memberid']==str(target_mid))].sort_values('timestamp', ascending=False)
            for _, p in posts.iterrows():
                st.markdown(f'<div class="feed-card"><small>{p["timestamp"]}</small><br>{p["content"]}</div>', unsafe_allow_html=True)
        with c2:
            st.subheader("Actions")
            if st.button(f"Message {u['firstname']}", use_container_width=True):
                st.session_state.active_chat_mid = target_mid
                st.session_state.view_target = None # Close profile to go to chat
                st.rerun()
    else:
        st.error("User not found.")
        if st.button("Go Back"): st.session_state.view_target = None; st.rerun()

# --- 4. MAIN NAVIGATION LOGIC ---
if not st.session_state.auth["in"]:
    # (Login Logic stays the same as previous versions)
    st.title("Health Bridge Pro")
    st.info("Please Login to continue.")
    # ... Login code ...
    st.stop()

# CHECK IF WE ARE VIEWING A PROFILE
if st.session_state.view_target:
    render_full_profile(st.session_state.view_target)
    st.stop() # Stops the rest of the app from rendering while viewing a profile

# --- 5. THE MAIN APP TABS ---
u_df = get_data("Users")
l_df = get_data("ChatLogs")
f_df = get_data("Friends")
mid = st.session_state.auth['mid']

tabs = st.tabs(["👤 My Profile", "🤝 Cooper", "👥 Friends & Search", "📩 Messages", "🚪 Logout"])

with tabs[0]: # MY PROFILE (Logged in User Only)
    st.header(f"Welcome, {st.session_state.auth['fname']}")
    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown(f"**ID:** @{mid}")
        st.markdown(f"**Bio:** {st.session_state.auth['bio']}")
    with c2:
        st.subheader("My Timeline")
        p_in = st.text_area("What's on your mind?")
        if st.button("Post"):
            save_log("Feed", "user", p_in); st.rerun()
        my_posts = l_df[(l_df['agent']=="Feed") & (l_df['memberid']==mid)].sort_values('timestamp', ascending=False)
        for _, r in my_posts.iterrows():
            st.markdown(f'<div class="feed-card"><small>{r["timestamp"]}</small><br>{r["content"]}</div>', unsafe_allow_html=True)

with tabs[2]: # FRIENDS & SEARCH
    st.subheader("Social Search")
    query = st.text_input("Search Users by ID").lower().strip()
    if query:
        results = u_df[u_df['memberid'].astype(str).str.contains(query)]
        for _, row in results.iterrows():
            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                col1.write(f"**{row['firstname']}** (@{row['memberid']})")
                # THE FIX: This button triggers the full-page view
                if col2.button("View Full Profile", key=f"v_{row['memberid']}"):
                    st.session_state.view_target = row['memberid']
                    st.rerun()

    st.divider()
    st.subheader("My Friends")
    # (Friends list logic showing names that link to view_target)
    # ...
