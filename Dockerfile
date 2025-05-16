# Use official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy app code
COPY . .

# Expose port (must match what you set in app.py)
EXPOSE 8533

# Default command to run the Streamlit app
CMD ["streamlit", "run", "frontend.py"]
