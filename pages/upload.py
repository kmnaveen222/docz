import streamlit as st
import requests
import os
from streamlit_javascript import st_javascript  # make sure to install this package


BASE_URL = "http://127.0.0.1:5000"
st.set_page_config(page_title="DocZ", page_icon="🚀", layout="wide", menu_items={})
 

# Initialize session variables
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "token" not in st.session_state:
    st.session_state.token = None
if "messages" not in st.session_state:
    st.session_state.messages = []

st.markdown("""
    <style>
        [data-testid="stSidebarNav"] {
            display: none !important;
        }
    </style>
""", unsafe_allow_html=True)

def chathistory(headers):
    response = requests.get(f"{BASE_URL}/get_chat_history", headers=headers)
    if response.status_code == 200:
        st.session_state.messages = response.json().get("chat_history", [])

def username(headers):
    response = requests.get(f"{BASE_URL}/get_user_details", headers=headers)  
    if response.status_code == 200:
        user_data = response.json()
        st.session_state.username = user_data.get("username")
# Authentication Handling

if not st.session_state.logged_in:
    token = st_javascript("localStorage.getItem('token');")
    if token:

        st.session_state.token = token
        st.session_state.logged_in = True

        headers = {"Authorization": token}
        chathistory(headers)
        username(headers)
    

        


# if not st.session_state.logged_in:
    # st.switch_page("jwtstreamlit.py")
# st.sidebar.title("Navigation")
# page = st.sidebar.radio("Go to", ["Chatbot", "Upload Documents"])

# # Redirect to Upload Page
# if page == "Chatbot":


st.title("📂 Upload Documents")
st.markdown("Upload PDF, DOCX, or TXT files for processing.")

if "logged_in" not in st.session_state or not st.session_state.logged_in:  
    st.warning("Please log in to upload documents.")
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
    st.sidebar.header(f"Hi {st.session_state.username} 🙋🏼‍♂️")

    st.sidebar.title("Navigation")
    st.sidebar.page_link("jwtstreamlit.py", label=" ⬅️ Go Back to Main Page")
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

    hide_uploader_text = """
    <style>
    /* Hide the default small text initially */
    div[data-testid="stFileUploader"] small {
        display: none;
    }
    </style>
    """
    st.markdown(hide_uploader_text, unsafe_allow_html=True)
    


    uploaded_files = st.file_uploader("Upload files (Max: 5 MB)", type=["pdf", "docx", "txt"], accept_multiple_files=True)
    st.markdown(
    """
    <div style="font-size: 14px;font-style: italic;color: grey ;padding-bottom:20px">
        📑 Format allowed: PDF,docx,doc,txt
    </div>
    """,
    unsafe_allow_html=True
    )
    MAX_FILE_SIZE = 5 * 1024 * 1024  

    if uploaded_files:
        if st.button("Upload"):
            oversized_files = [file.name for file in uploaded_files if len(file.getvalue()) > MAX_FILE_SIZE]

            if oversized_files:
                st.error(f"The following files exceed 5MB: {', '.join(oversized_files)}")
            else:
                files_to_send = [("files", (file.name, file.getvalue(), file.type)) for file in uploaded_files]
                headers = {"Authorization": st.session_state.token}

                response = requests.post(f"{BASE_URL}/upload_documents", files=files_to_send, headers=headers)

                if response.status_code == 200:
                    st.success("File uploaded successfully.")
                else:
                    st.error(response.json().get("error", "File upload failed"))

    # if st.button("Go Back"):
    #     os.system("streamlit run jwtstreamlit.py")  # Restart the app (alternative)
    #     st.rerun()  # Rerun the script to refresh the app