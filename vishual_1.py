import os
import openai
import sqlite3
import numpy as np
import plotly.express as px
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from dotenv import load_dotenv
import pandas as pd

# Load environment variables
load_dotenv()

# OpenAI API setup
openai_client = openai.Client(api_key=os.getenv("OPENAI_API_KEY"))
db_path = "ats.db"

def fetch_resume_chunks():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Fetch only available columns (id and text_snippet)
    cursor.execute("SELECT id, text_snippet FROM document_embeddings")
    rows = cursor.fetchall()
    conn.close()
    return rows

def determine_role(resume_text):
    prompt = (
        "Analyze the resume and categorize the role concisely. "
        "Use roles like 'Full Stack Dev (Java, React)', 'Backend Dev (Python)', 'Frontend Dev (React)', "
        "'MERN Dev', 'Mobile Dev (Flutter)', etc. Keep it short and meaningful."
        f" Resume Content: {resume_text}"
    )

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": prompt}],
        max_tokens=50
    )
    return response.choices[0].message.content.strip()

def visualize_embeddings_2d(embeddings, role_assignments, candidate_ids, text_snippets):
    unique_roles = list(set(role_assignments))

    # Convert embeddings to numpy
    embeddings_array = np.array(embeddings)

    # Scale embeddings before PCA
    scaler = StandardScaler()
    scaled_embeddings = scaler.fit_transform(embeddings_array)

    # Apply PCA
    pca = PCA(n_components=2)
    reduced_embeddings = pca.fit_transform(scaled_embeddings)

    # Shift axis to start from (0,0)
    reduced_embeddings -= reduced_embeddings.min(axis=0)

    # Extract PDF name (first word of text snippet, modify if needed)
    pdf_names = [snippet.split()[0] if snippet else "Unknown" for snippet in text_snippets]

    # Prepare data for Plotly
    data = pd.DataFrame(
    {
        "Job Similarity Score (X-axis)": reduced_embeddings[:, 0],
        "Skill Diversity Score (Y-axis)": reduced_embeddings[:, 1],
        "Job Role": role_assignments,
        "Candidate ID": candidate_ids,
        "PDF Name": pdf_names
    })
 
    fig = px.scatter(
        data, x="Job Similarity Score (X-axis)", y="Skill Diversity Score (Y-axis)", 
        color="Job Role", hover_data=["Candidate ID", "PDF Name"],
        title="Candidate Job Role Clustering",
        width=1000, height=700  # Increased graph size
    
    )

    # Add minimal instructions for better understanding
    fig.add_annotation(
        text="Closer points → Similar roles | Higher Y → Diverse skills",
        xref="paper", yref="paper", x=0.5, y=-0.15, showarrow=False,
        font=dict(size=12, color="gray")
    )

    fig.show()
 

if __name__ == "__main__":
    resume_chunks = fetch_resume_chunks()
    role_assignments = []
    embeddings = []
    candidate_ids = []
    text_snippets = []  # To store text snippets for extracting PDF names

    for doc_id, text in resume_chunks:
        role = determine_role(text)
        embeddings.append(np.random.rand(10))  # Mock 10D embeddings
        role_assignments.append(role)
        candidate_ids.append(doc_id)  # Use doc_id instead of missing candidate_name
        text_snippets.append(text)  # Store text snippets

    visualize_embeddings_2d(embeddings, role_assignments, candidate_ids, text_snippets)
