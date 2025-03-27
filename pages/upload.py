import socketio
import streamlit as st
import requests
import os
from streamlit_javascript import st_javascript  
import time
from queue import Queue
status_queue = Queue()
import logging
logging.getLogger("engineio").setLevel(logging.ERROR)  # Hide PING/PONG logs
logging.getLogger("socketio").setLevel(logging.ERROR)  # Hide Socket.IO logs


BASE_URL = "http://127.0.0.1:5000" # Backend URL

sio = socketio.Client()
sio.connect("http://127.0.0.1:5000")

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


# ----------------------------- #
#        UPLOAD PAGE UI
# ----------------------------- #
st.title("📂 Upload Documents")
st.markdown("Upload PDF, DOCX, or TXT files for processing.")

if not st.session_state.logged_in:
    st.warning("🔑 Please log in to upload documents.")
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
    st.sidebar.page_link("pages/upload_files.py", label=" 🔖 View uploaded docs")
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

    hide_uploader_text = """
    <style>
    /* Hide the default small text initially */
    div[data-testid="stFileUploader"] small {
        display: none;
    }
    </style>
    """
    st.markdown(hide_uploader_text, unsafe_allow_html=True)
    

    # ----------------------------- #
    #        FILE UPLOADER
    # ----------------------------- #
 
    if "disable_uploader" not in st.session_state:
        st.session_state.disable_uploader = False

    uploaded_files = st.file_uploader("Upload files (Max: 5 MB each)", type=["pdf", "docx", "txt","doc"], accept_multiple_files=True,disabled=st.session_state.disable_uploader)
    st.markdown(
    """<div style="font-size: 15px;font-style: italic;color: grey ;padding-bottom:20px">
        ⚠️ Warning: If you upload the same file again, it will be updated automatically.
    </div>
    """,
    unsafe_allow_html=True
    )
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

    if uploaded_files: 
        def handle_upload_status(data):
            # print("Data from backend:", data)
            status_queue.put(data)

        # Ensure the WebSocket event listener is registered
        if "upload_status" not in sio.handlers:
            sio.on("upload_status", handle_upload_status)  # ✅ Fix: Pass function reference
        #     print("🟢 Event Listener Registered for 'upload_status'")
        #     print("Current handlers 1:", sio.handlers)
        # else:
        #     print("🔴 Event Listener already registered!")

        upload_button_placeholder = st.empty()


        if upload_button_placeholder.button("📥 Upload") or st.session_state.disable_uploader == True:
            if st.session_state.disable_uploader == False:
                st.session_state.disable_uploader = True
                st.rerun()
            oversized_files = [file.name for file in uploaded_files if len(file.getvalue()) > MAX_FILE_SIZE]

            if oversized_files:
                st.error(f"❌ The following files exceed 5MB: {', '.join(oversized_files)}")
            else:
                files_to_send = [("files", (file.name, file.getvalue(), file.type)) for file in uploaded_files]
                headers = {"Authorization": st.session_state.token}

                upload_button_placeholder.empty()  # Remove button after click
 
                try:
                    response = requests.post(f"{BASE_URL}/upload_documents", files=files_to_send, headers=headers)
                    if response.status_code == 200:
                        message_placeholder = st.empty()
                        response=response.json()
                        message_placeholder.success(response.get("message"))
                        with st.spinner("Uploading... Please wait ⏳"):
                            data = status_queue.get()  # Retrieve data from the queue
                            if data:
                                message_placeholder.empty()
                                if data['code']=='200':
                                    st.success(f"{data['status']}")  
                                    if 'files_updated' in data:
                                        st.success("✅ Files Updated:\n" + "\n".join(f"- {file}" for file in data['files_updated']))
                                    st.session_state.disable_uploader = False
                                else:
                                    st.error(f"{data['status']}")
                                    st.session_state.disable_uploader = False
                            if st.button("Upload again ↗️"):
                                st.rerun()
                    else:
                        st.error(response.json().get("error", "❌ File upload failed"))
                        st.session_state.disable_uploader = False
                except requests.exceptions.RequestException as e:
                    st.error("❌ Server error! Please try again later.")
                    print(f"Upload Error: {e}")  # Debugging
                    if st.button("Try again 💪🏼🔄️"):
                        st.session_state.disable_uploader = False
                        st.rerun()
#     # if st.button("Go Back"):
#     #     os.system("streamlit run jwtstreamlit.py")  # Restart the app (alternative)
#     #     st.rerun()  # Rerun the script to refresh the app
