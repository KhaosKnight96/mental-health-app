import streamlit as st
from groq import Groq

# 1. SETUP & PAGE CONFIG
st.set_page_config(page_title="HealthConnect AI", layout="wide")

# 2. LOGIN SYSTEM
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("🔐 Secure Health Portal")
        user_input = st.text_input("Username")
        pass_input = st.text_input("Password", type="password")
        
        if st.button("Login"):
            # Your specific test credentials
            if user_input == "AppTest1" and pass_input == "TestPass1":
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Invalid credentials.")
        return False
    return True

# Stop app here if not logged in
if not check_password():
    st.stop()

# 3. ROLE SELECTION
if "role" not in st.session_state:
    st.title("Welcome! Please identify your role:")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🏥 I am a Patient", use_container_width=True):
            st.session_state.role = "Patient"
            st.rerun()
    with col2:
        if st.button("👩‍⚕️ I am a Caregiver", use_container_width=True):
            st.session_state.role = "Caregiver"
            st.rerun()
    st.stop()

# 4. SIDEBAR (Logout & Switch Role)
with st.sidebar:
    st.write(f"Logged in as: *{st.session_state.role}*")
    if st.button("Switch Role"):
        del st.session_state.role
        st.rerun()
    if st.button("Logout"):
        st.session_state.authenticated = False
        st.rerun()

# 5. DASHBOARDS
if st.session_state.role == "Patient":
    st.title("📝 Patient Dashboard")
    st.subheader("Welcome back! Let's check your vitals.")
    
    col1, col2 = st.columns(2)
    with col1:
        st.info("💡 Daily Tip: Remember to drink 8 glasses of water today!")
        weight = st.number_input("Enter Weight (kg)", value=70.0)
        steps = st.number_input("Steps Today", value=0)
        if st.button("Save Daily Log"):
            st.success("Stats updated for your caregiver to see!")

    with col2:
        st.subheader("🤖 Health AI Assistant")
        user_msg = st.text_input("Ask the AI anything about your health:")
        if user_msg:
            try:
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                chat_completion = client.chat.completions.create(
                    messages=[{"role": "user", "content": user_msg}],
                    model="llama3-8b-8192",
                )
                st.write(chat_completion.choices[0].message.content)
            except Exception as e:
                st.error("f"AI Error: {e}")

else: # CAREGIVER DASHBOARD
    st.title("👩‍⚕️ Caregiver Command Center")
    st.subheader("Monitoring: Patient A")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Avg Heart Rate", "72 bpm", "Stable")
    col2.metric("Sleep Quality", "8 hrs", "+10%")
    col3.metric("Medication", "Taken", "9:00 AM")

    st.divider()
    st.subheader("Recent Activity Log")
    st.write("- Patient logged 5,000 steps.")
    st.write("- Patient reported 'Feeling Good' at 10:00 AM.")
    
    if st.button("Send Encouragement Message"):
        st.balloons()
        st.success("Message sent to Patient!")


