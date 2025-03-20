import os
import jwt as pyjwt
import datetime
import openai
import re
import sqlite3
import numpy as np
import requests
from flask import Flask, request, jsonify,send_from_directory
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyMuPDFLoader
from sklearn.metrics.pairwise import cosine_similarity
from context_manager import generate_reply_template
from werkzeug.utils import secure_filename
import textract
from langchain.schema import Document
import hashlib
# Load OpenAI API Key
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
 
# Initialize Flask App
app = Flask(__name__)
SECRET_KEY = "your_secret_key"
 
# Database Setup
DB_PATH = "ats.db"
 
# Initialize Embedding Model
embeddings_model = OpenAIEmbeddings(model="text-embedding-ada-002")
#Initialize AI Model
chat_model = ChatOpenAI(model="gpt-4o-mini")
 
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_embeddings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            filename TEXT,
            embedding BLOB,
            text_snippet TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            newchat_id INTEGER,
            embedding BLOB,
            message TEXT,
            role TEXT CHECK(role IN ('user', 'assistant')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_storage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            file_name TEXT,
            file_type TEXT,
            file_size INTEGER,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            used_space INTEGER DEFAULT 0,
            file_path TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()
 
init_db()
 
def store_chat_embedding(user_id, newchat_id, message, role):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    embedding = embeddings_model.embed_query(message)
    embedding_blob = np.array(embedding, dtype=np.float32).tobytes()
    cursor.execute("INSERT INTO chat_history (user_id,newchat_id, embedding, message, role) VALUES (?, ?, ?, ?, ?)",
                   (user_id, newchat_id, embedding_blob, message, role))
    conn.commit()
    conn.close()
 
 
# List of pronouns to track
PRONOUNS = {"he", "she", "his", "her", "him", "hers", "they", "them", "their", "theirs",
            "it", "its", "here", "there", "this", "that", "these", "those"}
USER_PRONOUNS= {"me", "my", "mine", "myself"}
 
def resolve_pronouns(question, chat_history):
    """
    If the question contains a pronoun, replace it with the entity from the last message.
    Otherwise, return the full chat history.
    """
    chat_response='true'
    if not chat_history:
        return chat_history,question,chat_response  # No chat history to refer to
 
    last_message = chat_history[0]  # Get the most recent chat message
    words = set(re.findall(r'\b\w+\b', question.lower()))
    # print(words,"words : ")  # Extract words from the question
 
    if words & PRONOUNS:  # If the question contains any pronoun
        Modified_question= chat_model.invoke(f"I will give you a message and a question containing pronouns. Rewrite the question by replacing pronouns with the correct entity from the message.\n\nMessage: \"{last_message}\"\nQuestion: \"{question}\"\nRewritten Question:").content
        return [last_message],Modified_question,chat_response # Use only the last message for context
   
    if words & USER_PRONOUNS:
        chat_response = chat_model.invoke(f"Sentence:{question},RETURN ONLY BOOLEAN ,Determine if a given sentence is asking about the user themselves, If the sentence is about the user , return false. Otherwise, return true.").content
   
 
    return chat_history,question,chat_response  # Otherwise, return the full chat history
 
 
 
# JWT Authentication
def generate_token(user_id):
    payload = {
        "user_id": user_id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }
    return pyjwt.encode(payload, SECRET_KEY, algorithm="HS256")
 
def verify_token(token):
    try:
        decoded = pyjwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return decoded["user_id"]
    except pyjwt.ExpiredSignatureError:
        return None
    except pyjwt.InvalidTokenError:
        return None
   
@app.route("/preview/<id>/<filename>")
def preview_file(filename,id):
    UPLOAD_FOLDER = f"temp/{id}"
    app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, mimetype='application/pdf')
    # return send_from_directory(app.config["UPLOAD_FOLDER"]"/"{id}, filename, mimetype='application/pdf')

@app.route("/download/<id>/<filename>")
def download_file(filename,id):
    UPLOAD_FOLDER = f"temp/{id}"
    app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=True)
 

@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username")
    if not username:
        return jsonify({"error": "Username is required"}), 400
 
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username) VALUES (?)", (username,))
        conn.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Username already exists"}), 400
 
    conn.close()
    return jsonify({"message": "User registered successfully"}), 201
 
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    if not username:
        return jsonify({"error": "Username is required"}), 400
 
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
 
    if not user:
        conn.close()
        return jsonify({"error": "User not found"}), 404
   
    user_id = user[0]
 
    # Fetch previous chat history
    cursor.execute("SELECT message, role FROM chat_history WHERE user_id = ? ORDER BY id DESC limit 50", (user_id,))
 
    chat_history = cursor.fetchall()
    chat_history.reverse()  # Reverse to maintain ASC order
    chat_history = [{"role": row[1], "content": row[0]} for row in chat_history]
   
    conn.close()
    token = generate_token(user_id)
   
    return jsonify({"message": "Login successful", "token": token, "chat_history": chat_history})
def retrieve_similar_context(user_id, newchat_id, query, top_k=1):
    print("---------------------------------",user_id, newchat_id, query)
 
    def get_top_matches(data):
        similarities = []
        query_embedding = embeddings_model.embed_query(query)
        query_vector = np.array(query_embedding, dtype=np.float32).reshape(1, -1)
        for text, embedding_blob in data:
            stored_embedding = np.frombuffer(embedding_blob, dtype=np.float32).reshape(1, -1)
            similarity = cosine_similarity(query_vector, stored_embedding)[0][0]
            similarities.append((similarity, text))
        similarities.sort(reverse=True, key=lambda x: x[0])
        return [text for _, text in similarities[:top_k]]
 
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
 
    cursor.execute("SELECT message, embedding FROM chat_history WHERE user_id = ? AND newchat_id = ?  ORDER BY id DESC", (user_id, newchat_id))
    chat_data = cursor.fetchall()##Embeddings,Text
    chat_history = [row[0] for row in chat_data] ## TEXT
    relevant_chat_history,modified_query,chat_response= resolve_pronouns(query, chat_history)
    doc_context=''
    meta_context=''
    top_match=''
    # print(chat_response," : CHAT RES BOOL")
   
    if (chat_response.lower()=="true"):
        cursor.execute("SELECT text_snippet, embedding FROM document_embeddings WHERE user_id = ?", (user_id,))
        doc_data = cursor.fetchall()
        top_match = get_top_matches(doc_data)
        doc_context = "\n".join([row[0] for row in doc_data])
        cursor.execute("SELECT file_name,file_path FROM user_storage WHERE user_id = ?", (user_id,))
        meta_data = cursor.fetchall()
        # meta_context = "\n".join([row[0] for row in meta_data])
        # file_paths="\n".join([row[1] for row in meta_data])
        meta_context =[{"name": row[0], "doc_preview_link": row[1]} for row in meta_data]
 
        # print(file_paths,"FILE PATHS")
 
        # print(meta_context,'DOC_name')
        # print(" G E N E R A L & &  D O C : ")
    conn.close()
 
   
    # Resolve pronouns (choose full chat history or only last message)
    # print(relevant_chat_history,"RELEVANT",modified_query," : MODIFY QUERY")
   
    def get_system_location():
        try:
            response = requests.get("http://ip-api.com/json/")
            data = response.json()
            location_info = {
                "Country": data.get("country"),
                "Region": data.get("regionName"),
                "City": data.get("city"),
                "Latitude": data.get("lat"),
                "Longitude": data.get("lon"),
                "ISP": data.get("isp"),
                "IP Address": data.get("query")
            }
            return location_info
        except Exception as e:
            return {"error": str(e)}
 
    # Example usage:
    location_data = get_system_location()
    # print(location_data)
   
    # Generate response template
    # print(top_match,'TOP_MATCH')
 
    context_template = generate_reply_template(previous_conversations=relevant_chat_history, other_information=doc_context,system_information=location_data,doc_metadata=meta_context)
    # print(get_top_matches(chat_data)," T o P  C H A T : ")
   
    # return get_top_matches(chat_data), get_top_matches(doc_data),context_template
    return top_match,context_template,modified_query
 
def store_embeddings(user_id, chunks, filename):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for chunk in chunks:
        embedding = embeddings_model.embed_query(chunk.page_content)
        embedding_blob = np.array(embedding, dtype=np.float32).tobytes()
        cursor.execute("INSERT INTO document_embeddings (user_id, filename, embedding, text_snippet) VALUES (?, ?, ?, ?)",
                       (user_id, filename, embedding_blob, chunk.page_content))
    conn.commit()
    conn.close()
 
# Helper functions
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {"pdf","docx","txt"}
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
 
def extract_text(file_path, file_extension):
    if file_extension == "pdf":
        loader = PyMuPDFLoader(file_path)
        return loader.load()
    else:
        extracted_text = textract.process(file_path).decode("utf-8")
        return [Document(page_content=extracted_text)]
 
def store_file_metadata(user_id, file_name, file_type, file_size,file_path):
    """Stores file details and updates used storage space."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
 
    cursor.execute("SELECT SUM(file_size) FROM user_storage WHERE user_id = ?", (user_id,))
    current_used_space = cursor.fetchone()[0] or 0
    new_used_space = current_used_space + file_size
 
    cursor.execute("""
        INSERT INTO user_storage (user_id, file_name, file_type, file_size, uploaded_at, used_space,file_path)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?,?)
    """, (user_id, file_name, file_type, file_size, new_used_space,file_path))
 
    conn.commit()
    conn.close()
 
MAX_USER_STORAGE = 30 * 1024 * 1024  # 30MB limit
 
def compute_file_hash(file_path):
    """Computes SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()
 
def get_existing_files(user_id):
    """Fetch filenames and file sizes from the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT file_name, file_size FROM user_storage WHERE user_id = ?", (user_id,))
    existing_files = {row[0]: row[1] for row in cursor.fetchall()}  # Dictionary {filename: size}
    conn.close()
    return existing_files
 
@app.route("/upload_documents", methods=["POST"])
def upload_documents():
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"error": "Missing token"}), 401
 
    user_id = verify_token(token)
    if not user_id:
        return jsonify({"error": "Invalid or expired token"}), 401
 
    if "files" not in request.files:
        return jsonify({"error": "No files uploaded"}), 400
 
    files = request.files.getlist("files")
    # print("PATH : ",os.path.abspath("vbhj"))
 
 
    # Fetch current user storage usage
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(file_size) FROM user_storage WHERE user_id = ?", (user_id,))
    current_used_space = cursor.fetchone()[0] or 0
    conn.close()
 
    documents = []
    # excluded =[]
    file_hashes = set()
    existing_files = get_existing_files(user_id)  # Get {filename: size} from DB
    # print(existing_files,'EXITFILES')
 
    os.makedirs(f"temp\\{user_id}", exist_ok=True)
    for file in files:
        if file.filename == "" or not allowed_file(file.filename):
            # print("NOT ALLOWED")
            return jsonify({"error": f"Invalid file format : {file.filename} "}), 400
        file_name = file.filename  # Secure filename
        file_extension = file_name.rsplit(".", 1)[1].lower()
        file_path = os.path.join(f"temp\\{user_id}", file_name)
        file.save(file_path)
        file_size = os.path.getsize(file_path)
 
        # Check if filename already exists in DB
        if file_name in existing_files:
            os.remove(file_path)
            return jsonify({"error": f"File '{file_name}' already exists."}), 400
 
        file_hash = compute_file_hash(file_path)
 
        # Check for duplicate file within the same batch
        if file_hash in file_hashes:
            os.remove(file_path)
            return jsonify({"error": f"Duplicate file detected: {file_name}. Remove duplicates from the list."}), 400
 
        # Check storage limit
        if current_used_space + file_size > MAX_USER_STORAGE:
            os.remove(file_path)
            return jsonify({"error": "Storage limit exceeded (30MB)"}), 400
 
        file_hashes.add(file_hash)
 
    for file in files:
            file_name = file.filename
            file_extension = file_name.rsplit(".", 1)[1].lower()
            file_path = os.path.join(f"temp\\{user_id}", file_name)
            file_size = os.path.getsize(file_path)
 
        #actual upload starts...
            extracted_text = extract_text(file_path, file_extension)
            # chat_model = ChatOpenAI(model="gpt-4o-mini")
            chat_response = chat_model.invoke(f"Text format of single resume doc:{extracted_text},##Format this resume without bullet points and **,##Don't give any extra text or ** or any highlighting string in response").content
            doc = Document(page_content=chat_response)
            documents.extend([doc])
            # base_url = "http://localhost:5000/preview/"
            # preview_link = f"{base_url}{user_id}/{file_name}"
            
            if file_name.lower().endswith(".pdf"):
                preview_link = f"http://localhost:5000/preview/{user_id}/{file_name}"
            elif file_name.lower().endswith(".docx"):
                preview_link = f"http://localhost:5000/download/{user_id}/{file_name}"
 
            store_file_metadata(user_id, file_name, file_extension, file_size,preview_link)
            # os.remove(file_path)    
 
        # Process embeddings
    # text_splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=50)
    # chunks = text_splitter.split_documents(documents)
    store_embeddings(user_id, documents, file_name)
 
    return jsonify({"message": "Documents uploaded and processed successfully"}), 200
 
@app.route("/get_user_details", methods=["GET"])
def get_user_details():
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"error": "Missing token"}), 401
 
    user_id = verify_token(token)
    if not user_id:
        return jsonify({"error": "Invalid or expired token"}), 401
   
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT username FROM users WHERE id = ?
    """, (user_id,))
 
    user_name = cursor.fetchone()
    # print("user: ", type (user_name[0]))
   
    conn.close()
 
    return jsonify({"username": user_name[0].upper()})
 
 
@app.route("/user_files", methods=["GET"])
def get_user_files():
    """Retrieve the list of uploaded files and total used space."""
    # if "user_id" not in session:
    #     return jsonify({"error": "User not logged in"}), 401
 
    # user_id = session["user_id"]
 
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"error": "Missing token"}), 401
 
    user_id = verify_token(token)
    if not user_id:
        return jsonify({"error": "Invalid or expired token"}), 401
 
 
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT file_name, file_type, file_size, uploaded_at, used_space,file_path FROM user_storage WHERE user_id = ?
    """, (user_id,))
 
    files = [{"file_name": row[0], "file_type": row[1], "file_size": row[2],
              "uploaded_at": row[3], "used_space": row[4],"file_path":row[5]} for row in cursor.fetchall()]
   
    conn.close()
    return jsonify({"files": files})
 
 
@app.route("/ask", methods=["POST"])
def ask():
    token = request.headers.get("Authorization")
    # print("token----",token)
    if not token:
        return jsonify({"error": "Missing token"}), 401
 
    user_id = verify_token(token)
    # print("user id:--------------",user_id)
    if not user_id:
        return jsonify({"error": "Invalid or expired token"}), 401
 
    data = request.get_json()
 
    question = data.get("question")
    newchat_id=data.get("chatid")
    if not question:
        return jsonify({"error": "Question is required"}), 400
   
    #Diff
 
    # chat_model = ChatOpenAI(model="gpt-4o-mini")
    relevant_docs, context_template ,mdfy_question = retrieve_similar_context(user_id,newchat_id, question)
    chat_response = chat_model.invoke(f"{context_template}\nRelevant Docs: {relevant_docs}\n\nUser Query: {mdfy_question}").content
    # e_chat_response= chat_model.invoke(f"Add relevant attractive emojis to each sentence to this Context:{chat_response}")
    store_chat_embedding(user_id, newchat_id, question, "user")
    store_chat_embedding(user_id, newchat_id, chat_response, "assistant")
    # return jsonify({"answer": e_chat_response.content})
    return jsonify({"answer": chat_response})
 
 
 
@app.route("/get_chat_history", methods=["GET"])
def get_chat_history():
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"error": "Missing token"}), 401

    user_id = verify_token(token)
    if not user_id:
        return jsonify({"error": "Invalid or expired token"}), 401

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Fetch distinct chat IDs for the user
    cursor.execute("SELECT DISTINCT newchat_id FROM chat_history WHERE user_id = ?", (user_id,))
    chat_ids = [row[0] for row in cursor.fetchall()]

    # Retrieve messages grouped by chat_id
    chat_data = {}
    for chat_id in chat_ids:
        cursor.execute(
            "SELECT message, role FROM chat_history WHERE user_id = ? AND newchat_id = ? ORDER BY id ASC",
            (user_id, chat_id),
        )
        chat_history = cursor.fetchall()
        chat_data[chat_id] = [{"role": row[1], "content": row[0]} for row in chat_history]

    conn.close()

    return jsonify({"chat_history": chat_data}), 200
 
if __name__ == "__main__":
    app.run(debug=True)