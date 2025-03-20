import os
import openai
import sqlite3
import numpy as np
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# OpenAI API setup
openai_client = openai.Client(api_key=os.getenv("OPENAI_API_KEY"))
db_path = "ats.db"

def fetch_resume_chunks():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, text_snippet FROM document_embeddings")
    rows = cursor.fetchall()
    conn.close()
    return rows

def determine_role(resume_text):
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

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": prompt}],
        max_tokens=50
    )
    return response.choices[0].message.content.strip()

def visualize_embeddings_2d(embeddings, role_assignments):
    unique_roles = list(set(role_assignments))
    role_to_index = {role: i for i, role in enumerate(unique_roles)}

    # Convert embeddings to numpy
    embeddings_array = np.array(embeddings)

    # Scale embeddings before PCA
    scaler = StandardScaler()
    scaled_embeddings = scaler.fit_transform(embeddings_array)

    # Apply PCA
    pca = PCA(n_components=2)
    reduced_embeddings = pca.fit_transform(scaled_embeddings)

    # Assign distinct colors to roles
    colors = plt.colormaps.get_cmap("tab10")  # Corrected
    role_colors = [colors(i / len(unique_roles)) for i in range(len(unique_roles))]  # Sample colors

    fig, ax = plt.subplots(figsize=(10, 6))

    for i, role in enumerate(unique_roles):
        indices = [idx for idx, r in enumerate(role_assignments) if r == role]
        x_vals = reduced_embeddings[indices, 0] + np.random.uniform(-0.1, 0.1, len(indices))  # Small jitter
        y_vals = reduced_embeddings[indices, 1] + np.random.uniform(-0.1, 0.1, len(indices))

        ax.scatter(x_vals, y_vals, label=role, color=role_colors[i], alpha=0.7, edgecolors='black', linewidth=0.5)

    ax.set_xlabel("PCA Component 1")
    ax.set_ylabel("PCA Component 2")
    ax.set_title("2D Visualization of Auto-Categorized Roles")
    
    # Fix legend cropping issue
    ax.legend(loc="upper left", bbox_to_anchor=(1.05, 1), borderaxespad=0., fontsize=9)
    
    plt.grid(True)
    plt.tight_layout()
    plt.show()

def main():
    resume_chunks = fetch_resume_chunks()
    role_assignments = []
    embeddings = []

    for _, text in resume_chunks:
        role = determine_role(text)
        embeddings.append(np.random.rand(10))  # Mock 10D embeddings
        role_assignments.append(role)

    visualize_embeddings_2d(embeddings, role_assignments)

if __name__ == "__main__":
    main()