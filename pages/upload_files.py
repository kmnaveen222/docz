from io import BytesIO
import io
import streamlit as st
import requests  
import os
from streamlit_javascript import st_javascript  
import pandas as pd

# BASE_URL = "http://127.0.0.1:5000"
BASE_URL = "https://docz-fzuo.onrender.com" # Backend URL

st.set_page_config(page_title="DocZ", page_icon="🚀", layout="wide", menu_items={})

# Initialize session variables
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "token" not in st.session_state:
    st.session_state.token = None
if "messages" not in st.session_state: 
    st.session_state.messages = []
if "username" not in st.session_state:
    st.session_state.username = None

# Hide Sidebar Navigation
st.markdown("""
    <style>
        [data-testid="stSidebarNav"] {
            display: none !important;}
    </style>
""",unsafe_allow_html=True)

# ----------------------------- #
#    AUTHENTICATION HANDLING 
# ----------------------------- #
def authenticate_user():
    token = st_javascript("localStorage.getItem('token');")
    if token:
        st.session_state.token = token
        st.session_state.logged_in = True
        headers = {"Authorization": token}

        try:
            headers = {"Authorization": st.session_state.token}
            response = requests.get(f"{BASE_URL}/get_chat_history", headers=headers)
            if response.status_code == 200:
                st.session_state.chats = response.json().get("chat_history", {})
            else:
                st.error("Failed to fetch chat history.")
                
            response = requests.get(f"{BASE_URL}/get_user_details", headers=headers, timeout=10)
            if response.status_code == 200:
                user_data = response.json()
                st.session_state.username = user_data.get("username", "User")
        except requests.exceptions.RequestException as e:
            st.error("❌ Error connecting to the server. Please try again later.")
            st.session_state.logged_in = False
            st.session_state.token = None
            print(f"Error: {e}")  # Debugging

if not st.session_state.logged_in:
        authenticate_user()
        

if not st.session_state.logged_in:
    st.warning("🔑 Please log in to see the uploaded files.")
    st.page_link("frontend.py", label=" ⬅️ Click here to Login")
    st.markdown("""
    <style>
        [data-testid="stSidebar"] {
            display: none !important;
        }
        [data-testid="stSidebarCollapsedControl"] {
            display: none !important;
        }
                
    </style>
""", unsafe_allow_html=True)
    st.stop()  # Stop execution to prevent the rest of the code from running
else:
    st.sidebar.title(f"Hi,{st.session_state.username} 🙋🏼‍♂️")
    st.sidebar.page_link("frontend.py", label=" 🏡 Go Back to Main Page")
    st.sidebar.page_link("pages/upload.py", label=" 📲 Go Back to Upload Page")
    # Custom styling for sidebar links
    st.markdown("""
    <style>
        [data-testid="stSidebar"] a {
            background-color: #1a1c24 !important; /* Change to any color */
            color: white !important;  /* Text color */
            padding: 10px 15px !important;
            margin: 10px 0px !important;
            display: block;
            text-align: center;
            font-weight: bold;
            text-decoration: none;
        }

        [data-testid="stSidebar"] a:hover {
            background-color: #474954 !important; /* Hover effect */
        }
    </style>
    """, unsafe_allow_html=True)
    headers = {"Authorization": st.session_state.token}
    response = requests.get(f"{BASE_URL}/user_files", headers=headers)


    if response.status_code == 200:
        files_data = response.json().get("files", [])
        if files_data:
            # Convert JSON to DataFrame
            df = pd.DataFrame(files_data)
            df.insert(0, "S.No", range(1, len(df) + 1))
            
            df["Download"] = df["file_path"].apply(lambda path: f'<a href="{path.replace(" ", "%20")}" download>⬇️</a>')
        #     df["Delete"] = df["file_path"].apply(
        #     lambda path: f'<button onclick="deleteFile(\'{path}\')">❌</button>'
        # )

            st.markdown(
        """
        <style>
        table {
            width: 100%;
        }
        th, td {
            text-align: center !important;
           
        }
        td:nth-child(2) {  /* File Name Column */
            text-align: left !important;
            # width:30% !important;
        }
        td:nth-child(5) {
        width:2% !important;
        }
        td a{
         text-decoration: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
            df = df.drop(columns=["file_path"])
            st.title("Uploaded Files")
            st.write(df.to_html(escape=False, index=False), unsafe_allow_html=True)
        else:
            st.warning("No files found!")
    else:
        st.error("Failed to fetch files. Check API response.")



