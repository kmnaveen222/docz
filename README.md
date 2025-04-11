# Docze - AI Chatbot with Document Integration

## 📌 Overview

Docze is an AI-powered chatbot application that allows users to:
- Chat with an AI assistant (powered by GPT-4o-mini)
- Upload and analyze documents (PDF, DOCX, TXT)
- Get context-aware responses based on uploaded documents
- Manage chat history across multiple sessions

The application features a Flask backend with JWT authentication and a Streamlit frontend.

## 🛠️ Technologies Used

### Backend
- **Python 3.10+**
- **Flask** (Web framework)
- **Flask-SocketIO** (Real-time communication)
- **JWT** (Authentication)
- **Postgres** (Database)
- **LangChain** (Document processing and embeddings)
- **OpenAI API** (GPT-4o-mini and embeddings)
- **PyMuPDF** (PDF processing)
- **Python-Docx** (Document text extraction)

### Frontend
- **Streamlit** (Web interface)
- **JavaScript** (Client-side operations)
- **CSS** (Styling)

## 🔧 Installation

### Prerequisites
- Python 3.10 or higher
- Docker
- OpenAI API key
- Node.js (for optional frontend development)

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/LeeonTek/Docze.git
   cd Docze
   ```

2. Install dependencies:

   ```bash
   pip install flask flask-socketio python-dotenv openai langchain langchain-openai langchain-community pymupdf scikit-learn numpy requests pyjwt python-docx streamlit streamlit-javascript google-auth google-auth-oauthlib google-api-python-client pandas psycopg2 websocket-client
   ```
 
   ### Note:
   - If you encounter any dependency errors, you can try uninstalling and reinstalling the conflicting packages. 
   - For example:
   ```bash
   pip uninstall python-dateutil six -y
   pip install python-dateutil six
   ```

3. Create a `.env` file in the root directory with your OpenAI API key & Python path:
   ```
   OPENAI_API_KEY=your_api_key_here
   PYTHON_PATH=your Interpreter path (python.exe)
   ```

4. Create a `docker-compose.yaml` file in the root directory with your Postgres database setup:
   ```
   services:
      database:
         image: postgres
         ports:
            - '5432:5432'
         restart: always
         
         environment:
            POSTGRES_DB: # db name
            POSTGRES_USER: # username
            POSTGRES_PASSWORD: # password

   adminer:
      image: adminer
      restart: always
      ports:
         - '8081:8081'
      depends_on:
         - database
      
   ```

## 🚀 Running the Application

```bash
python Start_Docze.py
```

The application will be available at:
- Frontend: `https://localhost:8501`

## 📂 Project Structure

```
Docze/
├── backend1.py           # Backend Flask application
├── frontend.py           # Streamlit frontend
├── Postgres.py           # Database operations
├── context_manager.py    # Context template generation
├── pages/                # Multi-page Streamlit app
│   ├── upload.py         # Document upload page
│   └── upload_files.py   # View uploaded docs page
├── .env                  # Environment variables
├── .gitignore            # Ignore mentioned files
├── docker-compose.yaml   # Posgres setup in Docker
└── README.md             # This file
```

## 🔒 Authentication

Docze uses JWT (JSON Web Tokens) for authentication. Users can:
- Register with a username and password
- Login to access their chat history and documents

## 📄 Document Processing

- Supported formats: PDF, DOCX, TXT
- Documents are:
  - Stored locally in user-specific directories
  - Processed to extract text
  - Converted to embeddings for semantic search

## 💬 Chat Features

- Context-aware responses using document embeddings
- Pronoun resolution for more natural conversations
- Multiple chat sessions management
- Chat history persistence

## ✅ Conclusion

Docze brings together the power of GPT-4o-mini and document intelligence to create an interactive, context-aware chatbot experience. With real-time chat capabilities, document integration, and session persistence, Docze is a robust starting point for building intelligent assistants tailored to user-uploaded content. 

