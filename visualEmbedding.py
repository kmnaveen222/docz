import sqlite3
import numpy as np
import pandas as pd
import plotly.express as px
from sklearn.manifold import TSNE
from sklearn.preprocessing import MinMaxScaler
from sklearn.cluster import MeanShift
import os
import re
import openai
from dotenv import load_dotenv 

load_dotenv()

openai_client = openai.Client(api_key=os.getenv("OPENAI_API_KEY"))

# Extract candidate names 
def extract_candidate_name(text_snippet):
    """Extracts candidate names based on common name patterns."""
    patterns = [
        r'^(\w+\s\w+)',  # Matches common full names like "John Doe"
        r'(?:Name:|Candidate:|Profile:|^)([A-Z][a-z]+(?:\s[A-Z][a-z]+)+)',
        r'([A-Z][a-z]+\s[A-Z][a-z]+)'  # Loose matching for common name formats
    ]
    for pattern in patterns:
        match = re.search(pattern, text_snippet)
        if match:
            return match.group(1).strip()
    return "Unknown"

# Fetch resume chunks from the database and assign default job role
def fetch_resume_chunks():
    conn = sqlite3.connect("ats.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, text_snippet FROM document_embeddings")
    data = cursor.fetchall()
    
    conn.close()

    # Add default values for job roles and extract candidate names
    resume_chunks = []
    for row in data:
        resume_id, text_snippet = row
        resume_chunks.append({
            "id": resume_id,
            "text_snippet": text_snippet,
            "job_role": "Unknown",  # Assign default value
            "candidate_name": extract_candidate_name(text_snippet)  # Extract candidate name
        })

    return resume_chunks

# Fetch embeddings from the database for visualization
def fetch_embeddings():
    conn = sqlite3.connect("ats.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, embedding FROM document_embeddings")
    data = cursor.fetchall()
    
    conn.close()

    # Convert embedding blobs back to numpy arrays
    embeddings = {}
    for row in data:
        resume_id, embedding_blob = row
        embedding = np.frombuffer(embedding_blob, dtype=np.float32)
        embeddings[resume_id] = embedding

    return embeddings

# Assign job roles dynamically using GPT-4o mini based on resume content
def assign_job_roles(resume_chunks):
    for chunk in resume_chunks:
        resume_text = chunk["text_snippet"]

        # Detailed prompt for precise role detection
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

        # OpenAI call for role assignment
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

# Visualizes embeddings in 2D using t-SNE and MeanShift Clustering
def visualize_embeddings_2d(embeddings, resume_chunks):
    # Convert embeddings dictionary to a matrix for processing
    resume_ids = list(embeddings.keys())
    embedding_matrix = np.array([embeddings[resume_id] for resume_id in resume_ids])

    # Normalize embeddings for improved clustering accuracy
    scaler = MinMaxScaler()
    embedding_matrix = scaler.fit_transform(embedding_matrix)

    # Reduce dimensions to 2D using t-SNE for visualization
    tsne = TSNE(n_components=2, perplexity=3, learning_rate=100, random_state=42)
    reduced_embeddings = tsne.fit_transform(embedding_matrix)

    # MeanShift clustering to group similar roles
    clustering = MeanShift()
    cluster_labels = clustering.fit_predict(reduced_embeddings)

    # Prepare data for visualization
    df = pd.DataFrame(reduced_embeddings, columns=["X", "Y"])
    df["Candidate ID"] = resume_ids
    df["Candidate Name"] = [chunk["candidate_name"] for chunk in resume_chunks]
    df["Job Role"] = [chunk["job_role"] for chunk in resume_chunks]

    # Map job roles for better visual grouping
    job_roles = df["Job Role"].unique()
    job_role_map = {role: i for i, role in enumerate(job_roles)}
    df["Job Role Cluster"] = df["Job Role"].map(job_role_map)

    # Visualize the result using Plotly for interactive features
    fig = px.scatter(
        df, x="X", y="Y",
        color="Job Role",
        hover_data=["Candidate Name", "Candidate ID", "Job Role"],
        title="Candidate Job Role Clustering (Optimized)",
        labels={"X": "X Axis", "Y": "Y Axis"}
    )

    fig.show()

# Main execution point
def main():
    # Fetch data from the database
    resume_chunks = fetch_resume_chunks()
    embeddings = fetch_embeddings()

    # Assign job roles and visualize the result
    resume_chunks = assign_job_roles(resume_chunks)
    visualize_embeddings_2d(embeddings, resume_chunks)

if __name__ == "__main__":
    main()