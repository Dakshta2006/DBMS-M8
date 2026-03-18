import streamlit as st

def signup_page():
    st.title("Create Account")

    role = st.selectbox("Signup as", ["Patient", "Doctor"])
    st.text_input("Full Name")
    st.text_input("Email")
    st.text_input("Password", type="password")

    if st.button("Create Account"):
        st.session_state.page = "login"
        st.rerun()
