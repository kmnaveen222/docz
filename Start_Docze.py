import subprocess
import time
import webbrowser
import os
from dotenv import load_dotenv
load_dotenv()

# Optional: adjust to your paths
FLASK_PATH = "backend.py"
STREAMLIT_PATH = "frontend.py"

# Get Python path from environment variable
PYTHON_PATH = os.getenv('PYTHON_PATH', 'python')

# # Step 1: Start Docker containers
# try:
#     print("🔧 Starting Docker containers...")
#     subprocess.run(["docker-compose", "up", "-d"], check=True)
#     print("✅ Docker containers started.")
# except subprocess.CalledProcessError as e:
#     print("❌ Failed to start Docker containers.")
#     print(e)
#     exit(1)

# Step 2: Launch Flask backend
print("🚀 Starting Flask backend...")
flask_process = subprocess.Popen(
    [PYTHON_PATH, FLASK_PATH],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

# Step 3: Wait for Flask to be ready
time.sleep(20)

# Step 4: Launch Streamlit frontend
print("🚀 Launching Streamlit frontend...")
streamlit_process = subprocess.Popen([PYTHON_PATH, "-m", "streamlit", "run", STREAMLIT_PATH])

# Step 5: Optional: open Streamlit in browser
time.sleep(8)
webbrowser.open("https://localhost:8501")

# Step 6: Keep the launcher alive
try:
    flask_process.wait()
    streamlit_process.wait()
except KeyboardInterrupt:
    print("\n🛑 Terminating processes...")

    # Terminate backend and frontend
    flask_process.terminate()
    streamlit_process.terminate()

   # Step 7: Gracefully stop Docker containers (without removing volumes/images)
    # print("🧹 Stopping Docker containers...")
    # subprocess.run(["docker-compose", "stop"])

    # print("✅ Docker containers stopped (not removed). Clean exit.")