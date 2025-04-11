# from socketIO_client_nexus import SocketIO
import streamlit as st
import requests
from dotenv import load_dotenv
from streamlit_javascript import st_javascript


# Load environment variables
load_dotenv()

# Backend URL
BASE_URL = "http://127.0.0.1:5000"


# Page Configuration
st.set_page_config(page_title="DocZ", page_icon="🚀", layout="wide", menu_items={})
st.title("💬 AI Chatbot")
st.markdown("🚀 Chat with your AI assistant!")

# Apply Custom Styles
def apply_custom_styles():
    st.markdown("""
        <style>
            body {
                background-color: #ffffff;
                color: white;
            }
            .stChatMessage {
                animation: fadeIn 0.5s ease-in-out;
            }
            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(10px); }
                to { opacity: 1; transform: translateY(0); }
            }
            .chat-container {
                background: linear-gradient(135deg, #1f1c2c, #928DAB);
                padding: 20px;
                border-radius: 10px;
            }
            [data-testid="stSidebarNav"] {
                display: none !important;
            }
        </style>
    """, unsafe_allow_html=True)
    

# Initialize Session State
def initialize_session():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "token" not in st.session_state:
        st.session_state.token = None
    if "chats" not in st.session_state:
        st.session_state.chats = {}  
    if "active_chat" not in st.session_state:
        st.session_state.active_chat = None 
    if "username" not in st.session_state:
        st.session_state.username = None 
     
        st.session_state.active_chat = None
    if "username" not in st.session_state:
        st.session_state.username = None  

# Fetch User Details
def fetch_user_details():
    headers = {"Authorization": st.session_state.token}
    response = requests.get(f"{BASE_URL}/get_user_details", headers=headers)
    if response.status_code == 200:
        user_data = response.json()
        st.session_state.username = user_data.get("username")
    elif response.status_code == 500:
        st.error("Server error. Please try again later.")
    else:
        # st.error("Failed to fetch user details.")
        logout_user()

# Fetch Chat History
def fetch_chat_history():
    headers = {"Authorization": st.session_state.token}
    response = requests.get(f"{BASE_URL}/get_chat_history", headers=headers)
    if response.status_code == 200:
        st.session_state.chats = response.json().get("chat_history", {})
    else:
        st.error("Failed to fetch chat history.")

# Handle Authentication
def authenticate_user():
    if not st.session_state.logged_in:
        token = st_javascript("localStorage.getItem('token');")
        if token:
            st.session_state.token = token
            st.session_state.logged_in = True
            fetch_user_details()
            fetch_chat_history()
  
# Logout User
def logout_user():
    st.session_state.logged_in = False
    st.session_state.token = None
    st.session_state.username = None
    st.session_state.chats = {}
    st.session_state.active_chat = None
    st.components.v1.html("""
        <script>
            localStorage.removeItem("token");
            sessionStorage.removeItem('drive_token');
            window.parent.location.reload(); 
        </script>
    """, height=0, width=0)

# Sidebar Navigation
def sidebar_navigation():
    if not st.session_state.logged_in:
        st.sidebar.header("🔑 Authentication")
        username = st.sidebar.text_input("Username : ")
        password=st.sidebar.text_input("Password :")
        
        
        if st.sidebar.button("Login") :
            if username :
                if password:
                    response = requests.post(f"{BASE_URL}/login", json={"username": username,"password": password})
                    if response.status_code == 200:
                        data = response.json()
                        st.session_state.logged_in = True
                        st.session_state.token = data.get("token")
                        fetch_user_details()
                        fetch_chat_history()
                        st.components.v1.html(f"""
                            <script>
                                localStorage.setItem("token", "{st.session_state.token}");
                                window.parent.location.reload();
                            </script>
                        """, height=0, width=0)
                    else:
                        st.sidebar.error(response.json().get("error", "Login failed."))
                else:
                    st.sidebar.error("Password is empty!")
            else:
                st.sidebar.error("Username is empty!")

        if st.sidebar.button("Register"):
            if username:
                if password:
                    response = requests.post(f"{BASE_URL}/register", json={"username": username,"password": password})
                    if response.status_code == 201:
                        st.sidebar.success("Registered successfully. You can now login.")
                    else:
                        st.sidebar.error(response.json().get("error", "Registration failed"))
                else:
                    st.sidebar.error("Password is empty!")
            else:
                st.sidebar.error("Username is empty!")
                # st.sidebar.markdown("🔒 First time here?\n\n🛩️Set up your username, password to get started!")
        st.sidebar.markdown(
        """<div style="font-size: 15px;font-style: italic;color: grey ;padding-bottom:20px">
            🔒 First time here?\n\nSet up your username, password to get started!
        </div>
        """,
        unsafe_allow_html=True
        )
    
    else:
        if st.session_state.username:
            st.sidebar.title(f"Hi {st.session_state.username} 🙋🏼‍♂️")
            if st.sidebar.button("🆕 New Chat"):
                chat_id = f"chat_{len(st.session_state.chats) + 1}"
                st.session_state.chats[chat_id] = []
                st.session_state.active_chat = chat_id

            if st.session_state.chats:
                for chat_id in reversed(list(st.session_state.chats.keys())):
                    is_active = st.session_state.active_chat == chat_id
                    if is_active:
                        if st.sidebar.button(chat_id.upper().replace("_", " "), key=f"btn_{chat_id}", on_click=lambda id=chat_id: setattr(st.session_state, 'active_chat', id)):
                            st.session_state.active_chat = chat_id
                    else:
                        st.sidebar.button(chat_id.upper().replace("_", " "), key=f"btn_{chat_id}", on_click=lambda id=chat_id: setattr(st.session_state, 'active_chat', id))
            st.markdown(f"""
            <style>
            .st-key-btn_{st.session_state.active_chat} button{{
                # background-color: purple !important;
                color: #FF4B4B !important;
                border-color:#FF4B4B !important;
        
            }}
            </style>
            """, unsafe_allow_html=True)

            st.sidebar.page_link("pages/upload.py", label="📲 Go to Upload Page")
            st.sidebar.page_link("pages/upload_files.py", label=" 🔖 View uploaded docs")
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
            </style>""", unsafe_allow_html=True)

            if st.sidebar.button("Logout"):
               logout_user()
        else:
            logout_user()    

# Chat Interface
def chat_interface():
    if st.session_state.logged_in:
        
        st.subheader("Chat with AI")
        if st.session_state.active_chat is None:
            st.warning("Start a new chat or select an existing one.")
        else:
            active_chat_id = st.session_state.active_chat
            messages = st.session_state.chats[active_chat_id]

            for message in messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            user_input = st.chat_input("Type a message...")

            if user_input:
                messages.append({"role": "user", "content": user_input})
                with st.chat_message("user"):
                    st.markdown(user_input)

                with st.spinner("Thinking..."):
                    try:
                        headers = {"Authorization": st.session_state.token}
                        response = requests.post(
                            f"{BASE_URL}/ask",
                            json={"question": user_input, "chatid": active_chat_id},
                            headers=headers,
                            timeout=100
                        )
                        if response.status_code == 200:
                            bot_reply = response.json()["answer"]
                        else:
                            bot_reply = "Something went wrong."
                            st.sidebar.error(response.json().get("error", "Something went wrong"))

                    except requests.exceptions.Timeout:
                        bot_reply = "The server took too long to respond. Please try again."

                    except requests.exceptions.ConnectionError:
                        bot_reply = "Could not connect to the server. Make sure it's running."

                    with st.chat_message("assistant"):
                        st.markdown(bot_reply)

                    messages.append({"role": "assistant", "content": bot_reply})

    else:
        st.warning("Please log in to start chatting.")

# Run App
def main():
    apply_custom_styles()
    initialize_session()
    authenticate_user()
    sidebar_navigation()
    chat_interface()

if __name__ == "__main__":
    main()
