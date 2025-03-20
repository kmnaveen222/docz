import streamlit as st
import requests
import os
import streamlit.components.v1 as components
from dotenv import load_dotenv
from streamlit_javascript import st_javascript  # make sure to install this package
# Load environment variables
load_dotenv()

# Backend URL
BASE_URL = "http://127.0.0.1:5000"
st.set_page_config(page_title="DocZ", page_icon="🚀", layout="wide", menu_items={})
 
# Custom CSS for stylish UI
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
    </style>
""", unsafe_allow_html=True)

st.title("💬 AI Chatbot")
st.markdown("🚀 Chat with your AI assistant!")

st.markdown("""
    <style>
        [data-testid="stSidebarNav"] {
            display: none !important;
        }
    </style>
""", unsafe_allow_html=True)


# Initialize session variables
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "token" not in st.session_state:
    st.session_state.token = None
if "chats" not in st.session_state:
    st.session_state.chats = {}  # Store multiple chats
if "active_chat" not in st.session_state:
    st.session_state.active_chat = None  # Track the current chat

# Authentication Handling


if not st.session_state.logged_in:
    token = st_javascript("localStorage.getItem('token');")
    if token:
        st.session_state.token = token
        st.session_state.logged_in = True
        # print("genral",st.session_state.messages)
        # Fetch chat history
        
        headers = {"Authorization": token}
        response = requests.get(f"{BASE_URL}/get_chat_history", headers=headers)
        if response.status_code == 200:
            st.session_state.chats = response.json().get("chat_history", {})
            
        

        response = requests.get(f"{BASE_URL}/get_user_details", headers=headers)  
        if response.status_code == 200:
            user_data = response.json()
            st.session_state.username = user_data.get("username")
        else:
            st.error("Failed to fetch chat history.")
        

if not st.session_state.logged_in:
    st.sidebar.header("🔑 Authentication")
    username = st.sidebar.text_input("Enter Username")

    if st.sidebar.button("Login"):
        response = requests.post(f"{BASE_URL}/login", json={"username": username})
        if response.status_code == 200:
            data = response.json()
            st.session_state.logged_in = True
            st.session_state.token = data.get("token")
            
            headers = {"Authorization": st.session_state.token}
            response = requests.get(f"{BASE_URL}/get_user_details", headers=headers)  
            if response.status_code == 200:
                user_data = response.json()
                st.session_state.username = user_data.get("username")
                

            st.session_state.chats = data.get("chat_history", {})
            # print(st.session_state.messages)
            st.components.v1.html(
                f"""
                <script>
                    localStorage.setItem("token", "{st.session_state.token}");
                    window.parent.location.reload();
                </script>
                """,
                height=0,
                width=0
            )
        else:
            st.sidebar.error("Login failed. User not found.")
        

    if st.sidebar.button("Register"):
        response = requests.post(f"{BASE_URL}/register", json={"username": username})
        if response.status_code == 201:
            st.sidebar.success("Registered successfully. You can now login.")
        else:
            st.sidebar.error(response.json().get("error", "Registration failed"))
else:
    if "username" in st.session_state and st.session_state.username:
        st.sidebar.title(f"Hi {st.session_state.username} 🙋🏼‍♂️")
   
  
    # Ensure session state variable exists and is a dictionary
    if "chats" not in st.session_state or not isinstance(st.session_state.chats, dict):
        st.session_state.chats = {}  # Initialize as a dictionary

    if "active_chat" not in st.session_state:
        st.session_state.active_chat = None
        
    if st.sidebar.button("🆕 New Chat"):
        chat_id = f"chat {len(st.session_state.chats) + 1}"
        st.session_state.chats[chat_id] = []
        st.session_state.active_chat = chat_id

    # **Existing Chats List**
        # In the section where you display existing chats in the sidebar
    if st.session_state.chats:
        for chat_id in st.session_state.chats.keys():
            # Check if this is the active chat
            is_active = st.session_state.active_chat == chat_id
            
            # Use different button types based on active status
            if is_active:

                if st.sidebar.button(chat_id, key=f"btn_{chat_id}", on_click=lambda id=chat_id: setattr(st.session_state, 'active_chat', id)):
                    st.session_state.active_chat = chat_id
            else:
                st.sidebar.button(chat_id, key=f"btn_{chat_id}", on_click=lambda id=chat_id: setattr(st.session_state, 'active_chat', id))
    
    st.markdown(f"""
        <style>
        .st-key-btn_{st.session_state.active_chat} button{{
            # background-color: purple !important;
            color: #FF4B4B !important;
            border-color:#FF4B4B;
        }}
        
        .st-key-btn_{st.session_state.active_chat}:hover {{
            background-color: darkpurple !important;
        }}
        </style>
    """, unsafe_allow_html=True)
   
    st.sidebar.page_link("pages/upload.py", label="Go to Upload Page ➡️")
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

    
    


    if st.sidebar.button("Logout"):
        # st.session_state.clear()
        st.components.v1.html(
            """
            <script>
                localStorage.removeItem("token");
                window.parent.location.reload(); 
            </script>
            """,
            height=0,
            width=0
        )
        st.session_state.logged_in = False
        st.session_state.token = None
        st.session_state.username = None
        st.session_state.chats = {}
        st.session_state.active_chat = None

if st.session_state.logged_in:
    st.subheader("Chat with AI")

    # Check if a chat is selected
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
                headers = {"Authorization": st.session_state.token}
                response = requests.post(f"{BASE_URL}/ask", json={"question": user_input, "chatid": active_chat_id}, headers=headers)
        
                if response.status_code == 200:
                    bot_reply = response.json()["answer"]
                else:
                    bot_reply = "Something went wrong."
                    st.sidebar.error(response.json().get("error", "Something went wrong"))

                with st.chat_message("assistant"):
                    st.markdown(bot_reply)

                messages.append({"role": "assistant", "content": bot_reply})

else:
    st.warning("Please log in to start chatting.")
