# Cipher - AI Interview Screening

Cipher is a role-based AI technical interview screening platform. It uses a React frontend and a FastAPI backend to conduct dynamic, realistic technical interviews. Instead of a generic chatbot or simple multiple-choice quiz, Cipher generates rigorous, scenario-based questions tailored specifically to the candidate's uploaded resume, the role they are applying for, and an internal technical knowledge base using Retrieval-Augmented Generation (RAG). 

After the interview session, the system evaluates the candidate's answers semantically and provides a structured, recruiter-style final report highlighting strengths, weaknesses, and areas for improvement.

## How to Run Locally

To run the Cipher platform on your system, you need to start both the backend server and the frontend development server.

### 1. Start the Backend

The backend is built with Python and FastAPI.

```bash
# Navigate to the project root
# Activate the virtual environment
source .venv/bin/activate

# Install the required packages
pip install -r backend/requirements.txt

# Start the FastAPI server
uvicorn backend.app.main:app --reload
```
The backend will now be running at `http://127.0.0.1:8000`.

*(Optional) If you have added or changed source material in the knowledge base (`backend/data/knowledge_base/source_docs`), you should rebuild the vector index before starting the server:*
```bash
python -m backend.scripts.ingest_knowledge
```

### 2. Start the Frontend

The frontend is built with React and Vite.

```bash
# Open a new terminal window
# Navigate to the frontend directory
cd frontend

# Install the Node dependencies
npm install

# Start the Vite development server
npm run dev
```
The frontend will now be running at `http://127.0.0.1:5173`.

### 3. Use the Application

1. Open your browser and navigate to `http://127.0.0.1:5173`.
2. Upload a sample resume (PDF or text).
3. Select a target role (e.g., Software Engineer, Backend Engineer, AI/ML Engineer).
4. Take the dynamically generated technical screening interview.
5. Review the final evaluation and session insights on the results dashboard.
