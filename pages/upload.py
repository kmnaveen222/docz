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
import google.auth
from io import BytesIO
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.credentials import Credentials
from streamlit.runtime.uploaded_file_manager import UploadedFile
import io
 
 
# Google OAuth Client ID & Secret file
CLIENT_SECRETS_FILE = r".streamlit/client_secret_741902476574-peibmj559cm9fqkf71vr6rgcc9eb8vkp.apps.googleusercontent.com.json"
 
# Define the OAuth scope (Google Drive)
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
 
 
 
BASE_URL = "http://127.0.0.1:5000" # Backend URL
 

 
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
 
 
# 1. Define a proper MockUploadedFile class (compatible with Streamlit)
class DriveUploadedFile:
    def __init__(self, file_content: bytes, name: str, type: str):
        self._file = BytesIO(file_content)
        self.name = name
        self.type = type
        self.size = len(file_content)
 
    def read(self, n=-1):
        return self._file.read(n)
   
    def seek(self, offset, whence=0):
        return self._file.seek(offset, whence)
   
    def tell(self):
        return self._file.tell()
   
    def getvalue(self):
        return self._file.getvalue()
 
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
    def authenticate_google():
        flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri="https://localhost:8501/upload")
       
        auth_url, state = flow.authorization_url(prompt='select_account',access_type="online")
        # print("Auth_url",auth_url)
        # print("AUTH State",state)
        # print("Google auth")
       
        # st.session_state["auth_state"] = state
        # st.session_state["auth_url"] = auth_url
 
        # st.markdown(f'[Click here to authorize with Google Drive]({auth_url})', unsafe_allow_html=True)

        st.markdown(f"""
        <meta http-equiv="refresh" content="0; url={auth_url}" />
        <script>
            window.location.href = "{auth_url}";
        </script>
    """, unsafe_allow_html=True)


    def get_drive_service():
        query_params = st.query_params
        auth_code = query_params.get("code", None)
        # print("Auth code",auth_code)
        # print("GET DRIVE SERVICE")
 
        if not auth_code:
            st.error("Authorization code missing. Please authenticate again.")
            st.stop()
        # print("Auth state in session ",st.session_state.get("auth_state"))
 
        # if query_params.get("state", None) != st.session_state.get("auth_state"):
        #     st.error("Invalid OAuth state. Please try again.")
        #     st.stop()
 
        authorization_response = f"https://localhost:8501/?code={auth_code}"
       
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri="https://localhost:8501/upload"
        )
        flow.fetch_token(authorization_response=authorization_response)
 
        credentials = flow.credentials
        return build("drive", "v3", credentials=credentials)
   
   
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
    # print("local uploaded files",uploaded_files)
    # st.title("Google Drive File Uploader")
#     st.markdown(
#     """
#     <h1 style='display: flex; align-items: center; gap: 10px;'>
#         <img src='https://ssl.gstatic.com/images/branding/product/2x/drive_2020q4_48dp.png' width='40'/>
#         Google Drive File Uploader
#     </h1>
#     """,
#     unsafe_allow_html=True
# )

    upload_button_placeholder = st.empty()
    if upload_button_placeholder.button("Upload files from Google Drive"):
        authenticate_google()
 
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
 
 
    g_auth_token=st_javascript("sessionStorage.getItem('drive_token');")
 
    if not g_auth_token and "code" in st.query_params and upload_button_placeholder.button("View Files to upload") :
        drive_service = get_drive_service()
        creds = drive_service._http.credentials
        g_auth_token = creds.token
        # st_javascript(f"localStorage.setItem('drive_token', '{g_auth_token}');")
        st.components.v1.html(f"""
                                <script>
                                    sessionStorage.setItem("drive_token","{g_auth_token}");
                                    window.parent.location.reload();
                                </script>
                           """, height=0, width=0)
    elif g_auth_token:    
        creds = Credentials(token=g_auth_token)
        drive_service = build("drive", "v3", credentials=creds)
        # print("Drive",drive_service)
 
        try:
            results = drive_service.files().list(
            pageSize=1000,
            fields="files(id, name, mimeType)",
            q="mimeType='application/pdf' or mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document'"
            ).execute()
            files = results.get("files", [])
 
            selected_files = []
            for file in files:
                if st.checkbox(f"📄 {file['name']}", key=file['id']):
                    selected_files.append(file)
 
            # Process selected files (without downloading)
            if selected_files :
                uploaded_files = []
               
                for file in selected_files:
                    try:
                        # Download to buffer (no disk write)
                        request = drive_service.files().get_media(fileId=file['id'])
                        buffer = BytesIO()
                        downloader = MediaIoBaseDownload(buffer, request)
                       
                        with st.spinner(f"Loading {file['name']}..."):
                            done = False
                            while not done:
                                _, done = downloader.next_chunk()
 
                    # Convert Google Drive file to mimic Streamlit's UploadedFile
                        uploaded_file = io.BytesIO(buffer.getvalue())  # Create a file-like object
                        uploaded_file.name = file["name"]  # Add file name attribute
                        uploaded_file.type = file["mimeType"]  # Add MIME type attribute
                        uploaded_files.append(uploaded_file)
 
                   
                    except Exception as e:
                        st.error(f"Error processing {file['name']}: {str(e)}")
                   
        except Exception as e:
            st.error(f"Error accessing Google Drive: {e}")
 
    if uploaded_files:

        sio = socketio.Client()
        sio.connect("http://127.0.0.1:5000",wait_timeout=20)

        def handle_upload_status(data):
            # print("Data from backend:", data)
            status_queue.put(data)
 
        # Ensure the WebSocket event listener is registered
        if "upload_status" not in sio.handlers:
            sio.on("upload_status", handle_upload_status) 
        #     print("🟢 Event Listener Registered for 'upload_status'")
        #     print("Current handlers 1:", sio.handlers)
        # else:
        #     print("🔴 Event Listener already registered!")
 
        upload_button_placeholder = st.empty()
 
 
        if upload_button_placeholder.button("📥 Upload") or st.session_state.disable_uploader == True:
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
                                sio.disconnect()
                                if data['code']=='200':
                                    st.success(f"{data['status']}")
                                      
                                    if 'files_updated' in data:
                                        st.success("✅ Files Updated:\n" + "\n".join(f"- {file}" for file in data['files_updated']))
                       
                                else:
                                    st.error(f"{data['status']}")
                    # st.session_state.disable_uploader = False
                                if st.button("Upload again ↗️"):
                                    st.components.v1.html("""
                                        <script>
                                            localStorage.removeItem("drive_token");
                                            window.parent.location.reload();
                                        </script>
                                        """, height=0, width=0)
                                    st.rerun()
                            else:
                                st.error(response.json().get("error", "❌ File upload failed"))
                                st.session_state.disable_uploader = False
                    # time.sleep(10)
                    # st.components.v1.html("""
                    #         <script>
                    #             localStorage.removeItem("drive_token");
                    #             window.parent.location.reload();
                    #         </script>
                    #         """, height=0, width=0)
                except requests.exceptions.RequestException as e:
                    st.error("❌ Server error! Please try again later.")
                    print(f"Upload Error: {e}")  # Debugging
                    if st.button("Try again 💪🏼🔄️"):
                        st.session_state.disable_uploader = False
                        st.rerun()
#     # if st.button("Go Back"):
#     #     os.system("streamlit run jwtstreamlit.py")  # Restart the app (alternative)
#     #     st.rerun()  # Rerun the script to refresh the app
 