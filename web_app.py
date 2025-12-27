import streamlit as st
import pandas as pd
import datetime
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# --- 1. SETTINGS & STYLING ---
st.set_page_config(page_title="Health Bridge Portal", layout="wide")

# --- 2. CONNECTIONS ---
# Ensure your secrets.toml has the correct service_account info!
conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None, "name": None, "role": None}
if "chat_log" not in st.session_state: st.session_state.chat_log = []

def get_clean_users():
    """Fetches the latest data with zero caching (ttl=0)."""
    try:
        # Use ttl=0 to force Streamlit to ignore its memory and talk to Google
        df = conn.read(worksheet="Users", ttl=0)
        # Standardize columns to avoid 'HighScore' vs 'highscore' issues
        df.columns = [str(c).strip() for c in df.columns]
        if 'HighScore' in df.columns:
            df['HighScore'] = pd.to_numeric(df['HighScore'], errors='coerce').fillna(0).astype(int)
        return df
    except Exception as e:
        st.error(f"Data Fetch Error: {e}")
        return pd.DataFrame()

# --- 3. THE HIGH SCORE SYNC ENGINE ---
qp = st.query_params
if "last_score" in qp and st.session_state.auth.get("logged_in"):
    new_score = int(float(qp["last_score"]))
    current_user_id = str(st.session_state.auth['cid'])
    
    # 1. Get freshest data
    users_df = get_clean_users()
    
    if not users_df.empty:
        # 2. Find the user row
        user_idx = users_df.index[users_df['Username'].astype(str) == current_user_id]
        
        if not user_idx.empty:
            idx = user_idx[0]
            old_score = int(users_df.at[idx, 'HighScore'])
            
            if new_score > old_score:
                # 3. Update the local dataframe
                users_df.at[idx, 'HighScore'] = new_score
                
                # 4. Push to Google Sheets (CRITICAL STEP)
                try:
                    conn.update(worksheet="Users", data=users_df)
                    st.cache_data.clear() # Wipe Streamlit's cache
                    st.success(f"✅ Sheet Updated! New Best: {new_score}")
                except Exception as e:
                    st.error(f"Google Sheets Write Failed: {e}")
            else:
                st.info(f"Game Over. Score: {new_score}. (Best: {old_score})")

    # Clear URL to prevent infinite loops
    st.query_params.clear()
    st.rerun()

# --- 4. NAVIGATION & PAGES ---
# (Rest of the code logic remains similar, but ensure current_page is defined)
if not st.session_state.auth["logged_in"]:
    # Login Logic...
    st.markdown("### 🧠 Health Bridge Login")
    u_input = st.text_input("Couple ID")
    p_input = st.text_input("Password", type="password")
    if st.button("Login"):
        udf = get_clean_users()
        match = udf[(udf['Username'].astype(str) == u_input) & (udf['Password'].astype(str) == p_input)]
        if not match.empty:
            st.session_state.auth.update({"logged_in": True, "cid": u_input, "name": match.iloc[0]['Fullname']})
            st.rerun()
    st.stop()

# Basic Sidebar Navigation
with st.sidebar:
    page = st.radio("Go to", ["Dashboard", "Snake", "Memory Match"])

if page == "Dashboard":
    st.title(f"Welcome, {st.session_state.auth['name']}")
    # Display the current score from the sheet
    fresh_df = get_clean_users()
    user_row = fresh_df[fresh_df['Username'].astype(str) == str(st.session_state.auth['cid'])]
    score_display = user_row['HighScore'].values[0] if not user_row.empty else 0
    st.metric("Your High Score", f"{score_display} pts")

elif page == "Snake":
    # (Snake HTML Component from previous response goes here)
    st.title("🐍 Snake")
    # ... Snake HTML ...
    # Ensure the "saveAndExit" function in JS points to the right URL params
