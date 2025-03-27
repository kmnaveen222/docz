
import os
import jwt as pyjwt
from datetime import datetime, timedelta
import openai
import re
import sqlite3
import numpy as np
import requests
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyMuPDFLoader
from sklearn.metrics.pairwise import cosine_similarity
from context_manager import generate_reply_template
# from werkzeug.utils import secure_filename
import textract
from langchain.schema import Document
import hashlib
import pytz
import threading
from flask_socketio import SocketIO
import logging
logging.getLogger("engineio").setLevel(logging.ERROR)  # Only show errors


# Load OpenAI API Key
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# Initialize Flask App
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*",
                   logger=False,
                   engineio_logger=False,
                   async_mode='threading')  # Enable CORS for frontend connections
SECRET_KEY = "your_secret_key"



# Database Setup
DB_PATH = "ats.db"

# Initialize Embedding Model
embeddings_model = OpenAIEmbeddings(model="text-embedding-ada-002")
# Initialize AI Model
chat_model = ChatOpenAI(model="gpt-4o-mini")

# Initialize Database
def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                password TEXT UNIQUE NOT NULL
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
    except sqlite3.Error as e:
        print(f"Database error1: {e}")
    finally:
        conn.close()

init_db()



# Store Chat Embedding
def store_chat_embedding(user_id, newchat_id, message, role):
    try:
        embedding = embeddings_model.embed_query(message)
        embedding_blob = np.array(embedding, dtype=np.float32).tobytes()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO chat_history (user_id, newchat_id, embedding, message, role) VALUES (?, ?, ?, ?, ?)",
                       (user_id, newchat_id, embedding_blob, message, role))
        conn.commit()
    except Exception as e:
        print(f"Error storing chat embedding: {e}")
    finally:
        conn.close()

# List of pronouns to track
PRONOUNS = {"he", "she", "his", "her", "him", "hers", "they", "them", "their", "theirs",
            "it", "its", "here", "there", "this", "that", "these", "those"}
USER_PRONOUNS= {"me", "my", "mine", "myself"}

# Resolve Pronouns
def resolve_pronouns(question, chat_history):
    try:
        """
        If the question contains a pronoun, replace it with the entity from the last message.
        Otherwise, return the full chat history.
        """
        chat_response='true'
        if not chat_history:
            return chat_history, question, chat_response

        last_message = chat_history[0]
        words = set(re.findall(r'\b\w+\b', question.lower()))

        if words & PRONOUNS:
            modified_question = chat_model.invoke(
                f"I will give you a message and a question containing pronouns. Rewrite the question by replacing pronouns with the correct entity from the message.\n\nMessage: \"{last_message}\"\nQuestion: \"{question}\"\nRewritten Question:").content
            return [last_message], modified_question, chat_response

        if words & USER_PRONOUNS:
            chat_response = chat_model.invoke(
                f"Sentence:{question},RETURN ONLY BOOLEAN ,Determine if a given sentence is asking about the user themselves, If the sentence is about the user , return false. Otherwise, return true.").content
            # return chat_history, question, chat_response

        return chat_history,question,chat_response
    except Exception as e:
        print(f"Error resolving pronouns: {e}")
        return chat_history, question, chat_response

# JWT Authentication
def generate_token(user_id):
    try:
        payload = {
            "user_id": user_id,
            "exp": datetime.utcnow() + timedelta(hours=24)
        }
        return pyjwt.encode(payload, SECRET_KEY, algorithm="HS256")
    except Exception as e:
        print(f"Error generating token: {e}")
        return None

def verify_token(token):
    try:
        decoded = pyjwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return decoded["user_id"]
    except pyjwt.ExpiredSignatureError:
        return None
    except pyjwt.InvalidTokenError:
        return None

# File Operations
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text(file_path, file_extension):
    try:
        if file_extension == "pdf":
            loader = PyMuPDFLoader(file_path)
            return loader.load()
        else:
            extracted_text = textract.process(file_path).decode("utf-8")
            return [Document(page_content=extracted_text)]
    except Exception as e:
        print(f"Error extracting text from file: {e}")
        return []


def store_file_metadata(user_id, file_name, file_type, file_size, file_path):
    try:
        """Stores file details and updates used storage space."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(file_size) FROM user_storage WHERE user_id = ?", (user_id,))
        current_used_space = cursor.fetchone()[0] or 0
        new_used_space = current_used_space + file_size
        # Get current time in IST
        ist = pytz.timezone('Asia/Kolkata')
        ist_time = datetime.now(ist).strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute("""
            INSERT INTO user_storage (user_id, file_name, file_type, file_size, uploaded_at, used_space, file_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, file_name, file_type, file_size , ist_time, new_used_space, file_path))
        conn.commit()
    except Exception as e:
        print(f"Error storing file metadata: {e}")
    finally:
        conn.close()

def compute_file_hash(file_path):
    try:
        """Computes SHA-256 hash of a file."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        print(f"Error computing file hash: {e}")
        return None

def get_existing_files(user_id):
    try:
        """Fetch filenames and file sizes from the database."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT file_name, file_size FROM user_storage WHERE user_id = ?", (user_id,))
        existing_files = {row[0]: row[1] for row in cursor.fetchall()}
        return existing_files
    except Exception as e:
        print(f"Error fetching existing files: {e}")
        return {}
    finally:
        conn.close()

def store_embeddings(user_id,doc,filename):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # for chunk in chunks:
    embedding = embeddings_model.embed_query(doc.page_content)
    embedding_blob = np.array(embedding, dtype=np.float32).tobytes()
    cursor.execute("INSERT INTO document_embeddings (user_id,filename, embedding, text_snippet) VALUES (?,?, ?, ?)",
                       (user_id,filename, embedding_blob, doc.page_content))
    conn.commit()
    conn.close()

def retrieve_similar_context(user_id, newchat_id, query, top_k=1):
    # print("---------------------------------",user_id, newchat_id, query)
 
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

@app.route("/get_user_details", methods=["GET"])
def get_user_details():
    try:
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
        conn.close()
    
        return jsonify({"username": user_name[0].upper()})
    except sqlite3.Error as e:
        # Handle database errors
        print(f"Database error in /get_user_details: {e}")
        return jsonify({"error": "Database error5 occurred"}), 500

    except Exception as e:
        # Handle any other unexpected errors
        print(f"Unexpected error in /get_user_details: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

# API Routes
@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    if not username:
        return jsonify({"error": "Username is required"}), 400
    if not password:
        return jsonify({"error": "Password is required"}), 400

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username,password) VALUES (?,?)", (username,password))
        conn.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Password already exists"}), 400
    except sqlite3.Error as e:
        return jsonify({"error": f"Database error2: {e}"}), 500
    finally:
        conn.close()
    return jsonify({"message": "User registered successfully"}), 201

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password=data.get("password")
    # print("LOGIN PAGE")

    if not username:
        return jsonify({"error": "Username is required ❗"}), 400
    if not password:
        return jsonify({"error": "Password is required ❗"}), 400

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT username,id FROM users WHERE password = ? ",(password,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"error": "User not found "}), 404

        user_name=user[0]
        # print("pass",user_password)

        if user_name!=username:
            return jsonify({"error": "Invalid username (or) password"}), 404
        
        user_id = user[1]
        # print("ID",user_id)


        cursor.execute("SELECT message, role FROM chat_history WHERE user_id = ? ORDER BY id DESC LIMIT 50", (user_id,))
        chat_history = cursor.fetchall()
        chat_history.reverse()
        chat_history = [{"role": row[1], "content": row[0]} for row in chat_history]

        token = generate_token(user_id)
        return jsonify({"message": "Login successful", "token": token, "chat_history": chat_history})
    except Exception as e:
        return jsonify({"error": f"Error during login: {e}"}), 500
    finally:
        conn.close()

MAX_USER_STORAGE = 30 * 1024 * 1024  # 30MB limit

# @socketio.on("connect")
# def handle_connect():
#     print("Client connected 🎉")

# @socketio.on("disconnect")
# def handle_disconnect():
#     print("Client disconnected ❌")

def process_upload(files, user_id):
    try:
        # print("--------------TRY Bk----------------")


        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(file_size) FROM user_storage WHERE user_id = ?", (user_id,))
        current_used_space = cursor.fetchone()[0] or 0

        # cursor.execute("SELECT username FROM users WHERE id = ?", (user_id,))
        # t_user_name=cursor.fetchone()[0]
        # print("Username :",t_user_name)

        conn.close()
        # print("🔹 Emitting upload started event")
        # socketio.emit("upload_status", {"t_user_name":t_user_name, "status": "Processing"})  # Send live updates

        existing_files = get_existing_files(user_id)
        updated_files = []
        total_files = 0
        file_hashes = set()
        os.makedirs(f"temp\\{user_id}", exist_ok=True)

        for file in files:
            file_name = file["filename"]
            file_contents = file["content"] 
            if file_name == "" or not allowed_file(file_name):
                # return jsonify({"error": f"Invalid file format : {file.filename} "}), 400
                # raise ValueError(f"Invalid file format: {file_name}")
                socketio.emit("upload_status", {"status": f"❗🥲 Invalid file format: {file_name}🙆🏻‍♂️","code":"400"})
                return
            
            file_extension = file_name.rsplit(".", 1)[1].lower()
            file_path = os.path.join(f"temp\\{user_id}", file_name)
            

            # Check if filename already exists in DB ,then remove
            if file_name in existing_files:
                os.remove(file_path)# REMOVE from folder
                
                #REMOVE from user_storage db
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("""DELETE FROM user_storage WHERE user_id = ? AND file_name = ? """, (user_id, file_name))

                #REMOVE from document_embeddings db
                cursor.execute("""DELETE FROM  document_embeddings WHERE user_id = ? AND filename = ? """, (user_id, file_name))
                conn.commit()
                conn.close()

                updated_files.append(file_name)

            # file.save(file_path)
             # Save file from memory
            with open(file_path, "wb") as f:
                f.write(file_contents)

            total_files+=1
            file_size = os.path.getsize(file_path)
            file_hash = compute_file_hash(file_path)

            # Check for duplicate file within the same batch
            if file_hash in file_hashes:
                os.remove(file_path)
                # return jsonify({"error": f"Duplicate file detected: {file_name}. Remove duplicates from the list."}), 400
                # raise ValueError(f"Duplicate file detected: {file_name}. Remove duplicates from the list.")
                socketio.emit("upload_status", {"status": f"❗🥲 Duplicate file detected: {file_name}. Remove duplicates from the list.","code":"400"})
                return
            
            # Check storage limit
            if current_used_space + file_size > MAX_USER_STORAGE:
                os.remove(file_path)
                # return jsonify({"error": "Storage limit exceeded (30MB)"}), 400
                # raise MemoryError("Storage limit exceeded (30MB)")
                socketio.emit("upload_status", {"status": "❗🥲 Storage limit exceeded🗄️ (30MB)","code":"400"})
                return

            file_hashes.add(file_hash)

        for file in files:

            # file_name = file.filename
            file_name = file["filename"]
            file_contents = file["content"]
            file_extension = file_name.rsplit(".", 1)[1].lower()
            file_path = os.path.join(f"temp\\{user_id}", file_name)
            file_size = os.path.getsize(file_path)

            extracted_text = extract_text(file_path, file_extension)
            chat_response = chat_model.invoke(f"Text format of single resume doc:{extracted_text},##Format this resume without bullet points and **,##Don't give any extra text or ** or any highlighting string in response").content
            doc = Document(page_content=chat_response)

            if file_name.lower().endswith(".pdf"):
                preview_link = f"http://localhost:5000/preview/{user_id}/{file_name}"
            elif file_name.lower().endswith(".docx"):
                preview_link = f"http://localhost:5000/download/{user_id}/{file_name}"

            store_file_metadata(user_id, file_name, file_extension, file_size, preview_link)
            store_embeddings(user_id, doc, file_name)

        if total_files==1:
            info_msg = "1 file uploaded successfully👍🏻"
        else:
            info_msg = "All files uploaded successfully👍🏻"

        if len(updated_files) == total_files:
            if len(updated_files) == 1:
                socketio.emit("upload_status", {"status": f"{len(updated_files)} file updated successfully 😉", "files_updated": updated_files,"code":"200"})
            else:
                socketio.emit("upload_status", {"status": f"{len(updated_files)} files updated successfully 😉", "files_updated": updated_files,"code":"200"})
            # return jsonify({"message": f"{len(updated_files)} files updated successfully 😉", "files_updated": updated_files}), 200
        elif len(updated_files) == 1:
            # return jsonify({"message": info_msg + f" and {len(updated_files)} files updated successfully 😉", "files_updated": updated_files}), 200
            socketio.emit("upload_status", {"status": f"{info_msg} and {len(updated_files)} file updated 😉", "files_updated": updated_files,"code":"200"})
        elif len(updated_files) != 0:
            # return jsonify({"message": info_msg + f" and {len(updated_files)} files updated successfully 😉", "files_updated": updated_files}), 200
            socketio.emit("upload_status", {"status": f"{info_msg} and {len(updated_files)} files updated 😉", "files_updated": updated_files,"code":"200"})
        else:
            socketio.emit("upload_status", {"status":f"{info_msg}","code":"200"})

    except Exception as e:
        # return jsonify({"error": f"Error uploading documents: {e}"}), 500
        print(f"Error uploading documents: {e}")
        socketio.emit("upload_status", {"status": f"Upload failed ❌: {str(e)}","code":"500"})
        
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
    
    # files = request.files.getlist("files")
    files_data = []
    for file in request.files.getlist("files"):
        files_data.append({
            "filename": file.filename,
            "content": file.read()  # Read file into memory before processing
        })
    try:
        upload_thread = threading.Thread(target=process_upload, args=(files_data, user_id))
        upload_thread.start() #Background thread
        return jsonify({"message": "⚡Your upload is blasting off in the background! We’ll notify you when it’s done."}), 200   
    except Exception as e:
        return jsonify({"error": f"Upload failed: {str(e)}"}), 500



    #----------------before threads
    # try:
    #     conn = sqlite3.connect(DB_PATH)
    #     cursor = conn.cursor()
    #     cursor.execute("SELECT SUM(file_size) FROM user_storage WHERE user_id = ?", (user_id,))
    #     current_used_space = cursor.fetchone()[0] or 0
    #     conn.close()

    #     existing_files = get_existing_files(user_id)
    #     updated_files = []
    #     total_files = 0
    #     info_msg = "All files uploaded successfully"
    #     file_hashes = set()
    #     os.makedirs(f"temp\\{user_id}", exist_ok=True)

    #     for file in files:
    #         if file.filename == "" or not allowed_file(file.filename):
    #             return jsonify({"error": f"Invalid file format : {file.filename} "}), 400
    #         file_name = file.filename  # Secure filename
    #         file_extension = file_name.rsplit(".", 1)[1].lower()
    #         file_path = os.path.join(f"temp\\{user_id}", file_name)
            

    #         # Check if filename already exists in DB ,then remove
    #         if file_name in existing_files:
    #             os.remove(file_path)# REMOVE from folder
                
    #             #REMOVE from user_storage db
    #             conn = sqlite3.connect(DB_PATH)
    #             cursor = conn.cursor()
    #             cursor.execute("""DELETE FROM user_storage WHERE user_id = ? AND file_name = ? """, (user_id, file_name))

    #             #REMOVE from document_embeddings db
    #             cursor.execute("""DELETE FROM  document_embeddings WHERE user_id = ? AND filename = ? """, (user_id, file_name))
    #             conn.commit()
    #             conn.close()

    #             updated_files.append(file_name)

    #         file.save(file_path)
    #         total_files+=1
    #         file_size = os.path.getsize(file_path)
    #         file_hash = compute_file_hash(file_path)

    #         # Check for duplicate file within the same batch
    #         if file_hash in file_hashes:
    #             os.remove(file_path)
    #             return jsonify({"error": f"Duplicate file detected: {file_name}. Remove duplicates from the list."}), 400

    #         # Check storage limit
    #         if current_used_space + file_size > MAX_USER_STORAGE:
    #             os.remove(file_path)
    #             return jsonify({"error": "Storage limit exceeded (30MB)"}), 400

    #         file_hashes.add(file_hash)

    #     for file in files:

    #         file_name = file.filename
    #         file_extension = file_name.rsplit(".", 1)[1].lower()
    #         file_path = os.path.join(f"temp\\{user_id}", file_name)
    #         file_size = os.path.getsize(file_path)

    #         extracted_text = extract_text(file_path, file_extension)
    #         chat_response = chat_model.invoke(f"Text format of single resume doc:{extracted_text},##Format this resume without bullet points and **,##Don't give any extra text or ** or any highlighting string in response").content
    #         doc = Document(page_content=chat_response)

    #         if file_name.lower().endswith(".pdf"):
    #             preview_link = f"http://localhost:5000/preview/{user_id}/{file_name}"
    #         elif file_name.lower().endswith(".docx"):
    #             preview_link = f"http://localhost:5000/download/{user_id}/{file_name}"

    #         store_file_metadata(user_id, file_name, file_extension, file_size, preview_link)
    #         store_embeddings(user_id, doc, file_name)

    #     if len(updated_files) == total_files:
    #         return jsonify({"message": f"{len(updated_files)} files updated successfully 🌟", "files_updated": updated_files}), 200
    #     if len(updated_files) != 0:
    #         return jsonify({"message": info_msg + f" and {len(updated_files)} files updated successfully 🌟", "files_updated": updated_files}), 200
    #     return jsonify({"message": info_msg}), 200
    # except Exception as e:
    #     return jsonify({"error": f"Error uploading documents: {e}"}), 500
    
    

@app.route("/ask", methods=["POST"])
def ask():
    try:
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
        
        relevant_docs, context_template ,mdfy_question = retrieve_similar_context(user_id,newchat_id, question)
        chat_response = chat_model.invoke(f"{context_template}\nRelevant Docs: {relevant_docs}\n\nUser Query: {mdfy_question}").content
        store_chat_embedding(user_id, newchat_id, question, "user")
        store_chat_embedding(user_id, newchat_id, chat_response, "assistant")
        return jsonify({"answer": chat_response})
    except Exception as e:
        print(f"Error in /ask route: {e}")
        return jsonify({"error": "An error occurred while processing your request"}), 500
 
@app.route("/get_chat_history", methods=["GET"])
def get_chat_history():
    try:
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
    except sqlite3.Error as e:
        print(f"Database error in /get_chat_history: {e}")
        return jsonify({"error": "Database error3 occurred"}), 500
    except Exception as e:
        print(f"Error in /get_chat_history route: {e}")
        return jsonify({"error": "An error occurred while fetching chat history"}), 500


 
@app.route("/user_files", methods=["GET"])
def get_user_files():
    """Retrieve the list of uploaded files and total used space."""
    try:
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"error": "Missing token"}), 401
    
        user_id = verify_token(token)
        if not user_id:
            return jsonify({"error": "Invalid or expired token"}), 401
    
    
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT file_name, file_type, uploaded_at FROM user_storage WHERE user_id = ?
        """, (user_id,))
    
        files = [{"file_name": row[0], "file_type": row[1],
                "uploaded_at": row[2]} for row in cursor.fetchall()]
    
        conn.close()
        return jsonify({"files": files})
    except sqlite3.Error as e:
        print(f"Database error in /user_files: {e}")
        return jsonify({"error": "Database error4 occurred"}), 500
    except Exception as e:
        print(f"Error in /user_files route: {e}")
        return jsonify({"error": "An error occurred while fetching user files"}), 500

if __name__ == "__main__":
    # app.run(debug=True)
    socketio.run(app)
    