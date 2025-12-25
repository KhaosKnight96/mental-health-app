import streamlit as st
import pandas as pd
import datetime
from groq import Groq

# --- SIMPLE LOGIN SYSTEM ---
def check_password():
    """Returns True if the user had the correct password."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("🔐 Secure Access")
        password = st.text_input("Enter Access Code:", type="password")
        if st.button("Unlock"):
            if password == "health2025": # You can change this password!
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect code.")
        return False
    return True

# If the password isn't correct, stop the script here
if not check_password():
    st.stop()

# --- 1. SET UP THE BRAIN (GROQ) ---
# Ensure you paste your key correctly here
GROQ_API_KEY = "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"
client = Groq(api_key=GROQ_API_KEY)

# --- 2. INITIALIZE MEMORY ---
if 'mood_history' not in st.session_state:
    st.session_state.mood_history = []

st.set_page_config(page_title="AI Health Bridge", page_icon="🧠")

# --- 3. SIDEBAR NAVIGATION ---
st.sidebar.title("Navigation")
role = st.sidebar.radio("Select your role:", ["Patient Portal", "Caregiver Coach"])
st.sidebar.markdown("---")
st.sidebar.warning("*Emergency:* Call 988 (USA) or 111 (UK)")

# --- 4. PATIENT PORTAL ---
if role == "Patient Portal":
    st.title("Patient Support Portal")
    
    # AI CHAT SECTION
    user_message = st.text_input("How are you feeling right now?")
    
    if user_message:
        # Safety Filter
        crisis_words = ["kill", "suicide", "hurt myself", "end it"]
        if any(word in user_message.lower() for word in crisis_words):
            st.error("🚨 Please reach out for professional help immediately. Call 988.")
        else:
            # DIAGNOSTIC CONTEXT: Prepare the mood history for the AI
            if st.session_state.mood_history:
                recent_scores = [str(entry['Energy']) for entry in st.session_state.mood_history[-3:]]
                history_context = f"The user's recent energy scores were: {', '.join(recent_scores)} out of 10."
            else:
                history_context = "No mood history available yet."

            try:
                with st.spinner("AI Therapist is listening..."):
                    chat_completion = client.chat.completions.create(
                        messages=[
                            {
                                "role": "system", 
                                "content": f"You are a compassionate AI therapist. {history_context}. Use this data to inform your response. If scores are low, be extra supportive."
                            },
                            {"role": "user", "content": user_message}
                        ],
                        model="llama-3.3-70b-versatile",
                    )
                    st.write("*AI Therapist:*", chat_completion.choices[0].message.content)
            except Exception as e:
                st.error(f"Connection Error: {e}")

    st.divider()

    # MOOD LOGGING SECTION
    st.write("### Daily Energy Tracker")
    mood_score = st.select_slider("Rate your mental energy (1=Low, 10=High)", options=range(1, 11), value=5)
    
    if st.button("Save Daily Log"):
        new_entry = {"Date": datetime.date.today().strftime("%Y-%m-%d"), "Energy": mood_score}
        st.session_state.mood_history.append(new_entry)
        st.success("Entry saved!")

    if st.session_state.mood_history:
        st.write("### Your Progress")
        df = pd.DataFrame(st.session_state.mood_history)
        st.line_chart(df.set_index("Date"))

# --- 5. CAREGIVER COACH ---
elif role == "Caregiver Coach":
    st.title("Caregiver Insights")
    
    # RED FLAG SYSTEM (The Bridge)
    if st.session_state.mood_history:
        last_score = st.session_state.mood_history[-1]['Energy']
        
        if last_score <= 3:
            st.error(f"⚠️ *Alert:* Their last energy log was a {last_score}/10. It might be a good time for a gentle check-in.")
        else:
            st.success(f"Trending: Their last energy log was a {last_score}/10. No immediate red flags.")

        st.write("### Shared Mood Trend")
        df_shared = pd.DataFrame(st.session_state.mood_history)
        st.line_chart(df_shared.set_index("Date"))
    else:
        st.info("Waiting for patient to share their first mood log.")

    st.divider()
    st.write("### Caregiver Tips")
    st.info("Tip: If they are withdrawing, don't force conversation. Just let them know you are there whenever they are ready.")
    st.divider()
    st.write("### AI Weekly Summary")
    
    if st.button("Generate Trend Analysis"):
        if st.session_state.mood_history:
            # Prepare the data for the AI
            history_summary = str(st.session_state.mood_history)
            
            try:
                with st.spinner("Analyzing weekly trends..."):
                    summary_response = client.chat.completions.create(
                        messages=[
                            {
                                "role": "system", 
                                "content": "You are a clinical supervisor helping a caregiver. Summarize the patient's mood trends from the data provided. Be objective, supportive, and point out if things are improving or declining. Keep it to one paragraph."
                            },
                            {
                                "role": "user", 
                                "content": f"Here is the recent mood data: {history_summary}"
                            }
                        ],
                        model="llama-3.3-70b-versatile",
                    )
                    st.success("Analysis Complete:")
                    st.write(summary_response.choices[0].message.content)
            except Exception as e:
                st.error(f"Could not generate summary: {e}")
        else:
            st.warning("No data available to analyze yet.")
