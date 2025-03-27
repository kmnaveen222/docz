import sqlite3
import numpy as np
import pandas as pd
import plotly.express as px
from sklearn.manifold import TSNE
from sklearn.preprocessing import MinMaxScaler
from sklearn.cluster import MeanShift
import os
import openai

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# OpenAI API key setup
openai_client = openai.Client(api_key=os.getenv("OPENAI_API_KEY"))

def fetch_resume_chunks():
    """Fetch resume chunks from the database and assigns a default job role."""
    conn = sqlite3.connect("ats.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, text_snippet FROM document_embeddings")
    data = cursor.fetchall()
    
    conn.close()

    resume_chunks = []
    for row in data:
        resume_id, text_snippet = row
        resume_chunks.append({
            "id": resume_id,
            "text_snippet": text_snippet,
            "job_role": "Unknown"  # Assign default value
        })

    return resume_chunks

def fetch_embeddings():
    """Fetches embeddings from the database."""
    conn = sqlite3.connect("ats.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, embedding FROM document_embeddings")
    data = cursor.fetchall()
    
    conn.close()

    embeddings = {}
    for row in data:
        resume_id, embedding_blob = row
        # embedding = np.frombuffer(embedding_blob, dtype=np.float32)
        # embeddings[resume_id] = embedding

        if embedding_blob:  # Ensure it's not None
            embedding = np.frombuffer(embedding_blob, dtype=np.float32)
            embeddings[resume_id] = embedding
        else:
            print(f"Warning: Resume ID {resume_id} has no embedding data!")

    if not embeddings:
        print("Error: No embeddings found in the database!")

    return embeddings

def assign_job_roles(resume_chunks):
    """Assigns job roles dynamically using GPT-4o mini based on provided criteria."""
    for chunk in resume_chunks:
        resume_text = chunk["text_snippet"]

        # Prompt for role detection
        prompt = (
            "Analyze the provided resume content and determine the appropriate role based on the following criteria:\n"
            "- If both frontend and backend skills are present, categorize the role as Full Stack Developer only if both primary skills are covered (e.g., Full Stack Developer (Java, React.js)).\n"
            "- If multiple backend-related skills are mentioned without primary frontend skills, categorize the role as Backend Developer only.\n"
            "- If only backend-related skills are mentioned in the resume, categorize the role as Backend Developer and specify the primary backend language in brackets (e.g., Backend Developer (Java)).\n"
            "- If only frontend skills are present, categorize the role as Frontend Developer and specify the primary frontend skill in brackets (e.g., Frontend Developer (React.js)).\n"
            "- If frontend frameworks like React.js, Angular, Vue.js, or Next.js are present along with a backend language, categorize the role as Full Stack Developer. Avoid mentioning HTML, CSS, JavaScript, JSP, JDBC, or Spring Boot unless they are part of a recognized frontend framework/library.\n"
            "- If a resume mentions 'Full Stack' but no recognized frontend skill like React or Angular is present, categorize it as Backend Developer.\n"
            "- If a resume mentions 'Frontend Developer' but only backend skills are present, categorize it as Backend Developer.\n"
            "- Exclude HTML, CSS, JSP, JDBC, and Spring Boot unless directly associated with a framework/library.\n"
            "- If MERN stack skills are mentioned, categorize the role as MERN Developer.\n"
            "- If App Developer skills are mentioned, mention the role as Flutter, React Native, or Native Developer (e.g., Android/iOS Developer).\n"
            "- If multiple backend or frontend languages are mentioned, prioritize the one with more hands-on experience, work experience, and project involvement as the primary language.\n"
            "- If the role is unclear, infer the appropriate role by examining skills, project experience, and work experience.\n"
            "- Ensure flexibility to identify other roles like ServiceNow Developer, Salesforce Developer, DevOps Engineer, etc., based on resume content.\n"
            "Return only the role in two words or less, or in the specified format (e.g., Full Stack Developer (Java, React.js)). If unsure, return 'Others'.\n"
            f"Resume Content: {resume_text}"
        )

        # OpenAI GPT-4o mini API call
        try:
            response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": prompt}],
            max_tokens=50
        )
            chunk["job_role"] = response.choices[0].message.content.strip()
        except Exception as e:
            chunk["job_role"] = "Unknown"
            print(f"Error assigning role for resume ID {chunk['id']}: {e}")

    return resume_chunks

def visualize_embeddings_2d(embeddings, resume_chunks):
    """Visualizes embeddings in 2D using t-SNE and MeanShift Clustering for better grouping."""
    
    # Convert embeddings dictionary to list
    resume_ids = list(embeddings.keys())
    # embedding_matrix = np.array([embeddings[resume_id] for resume_id in resume_ids])

    embedding_matrix = np.array([embeddings[resume_id] for resume_id in resume_ids if resume_id in embeddings])

    # Check if embedding_matrix is empty before proceeding
    if embedding_matrix.size == 0:
        print("Error: No valid embeddings to visualize!")
        return
    
    if embedding_matrix.ndim == 1:
        embedding_matrix = embedding_matrix.reshape(-1, 1)  # Ensure 2D format

    # Normalize embeddings for better clustering
    scaler = MinMaxScaler()
    embedding_matrix = scaler.fit_transform(embedding_matrix)

    # Reduce dimensions using t-SNE (Lower perplexity for tighter clustering)
    tsne = TSNE(n_components=2, perplexity=3, learning_rate=100, random_state=42)
    reduced_embeddings = tsne.fit_transform(embedding_matrix)

    # Apply MeanShift Clustering (Automatically detects clusters)
    clustering = MeanShift()
    cluster_labels = clustering.fit_predict(reduced_embeddings)

    # Convert to DataFrame
    df = pd.DataFrame(reduced_embeddings, columns=["X", "Y"])
    df["Candidate ID"] = resume_ids
    df["Job Role"] = [chunk["job_role"] for chunk in resume_chunks]

    # Assign each job role a separate cluster (Forces grouping)
    job_roles = df["Job Role"].unique()
    job_role_map = {role: i for i, role in enumerate(job_roles)}
    df["Job Role Cluster"] = df["Job Role"].map(job_role_map)

    # Plot using Plotly
    fig = px.scatter(
        df, x="X", y="Y",
        color="Job Role",
        hover_data=["Candidate ID", "Job Role"],
        title="Candidate Job Role Clustering (Optimized)",
        labels={"X": "X Axis", "Y": "Y Axis"}
    )

    fig.show()

def main():
    """Main function to run the visualization."""
    
    resume_chunks = fetch_resume_chunks()
    embeddings = fetch_embeddings()
    resume_chunks = assign_job_roles(resume_chunks)
    visualize_embeddings_2d(embeddings, resume_chunks)

if __name__ == "__main__":
    main()
