# AIDE-X

AIDE-X is a next-generation Generative AI system that transforms natural language requests (emails, tickets, user inputs) into structured workflows and executes them automatically.

It bridges the gap between AI understanding and real-world task execution using a multi-agent architecture and confidence-based decision engine.

Key Features
 1. Natural Language Understanding (NLP + LLM)
 2. Dynamic Workflow Generation (No rule-based logic)
 3. Multi-Agent AI System
 4. Automation Confidence Score (Safe execution)
 5. Real-time Task Processing
 6. Scalable & Modular Architecture

How It Works :
1. User Input (Text / Email) -> AI Processing (Intent + Entity Extraction) -> Structured JSON Output -> Multi-Agent Validation -> Workflow Execution ->Response / Action

Tech Stack:
1. Backend:
   1. Python
   2. FastAPI
   3. SQLAlchemy
3. Frontend: React.js
5. AI:
   1. LLM (OpenAI-compatible API)
   2. NLP & NER
7. Database: SQLite / PostgreSQL

Installation & Setup:
1️. Clone the Repository:
1. git clone https://github.com/your-username/aide-x.git
2. cd aide-x
2️. Backend Setup:
   1. cd backend
   2. pip install -r requirements.txt

Run server: python -m uvicorn main:app --reload

3️. Frontend Setup:
   1. cd frontend
   2. npm install
   3. npm start

Conclusion:
    AIDE-X transforms traditional automation into an intelligent autonomous decision system, enabling faster, safer, and more efficient operations across industries.

Contributing:
    Contributions are welcome! Feel free to fork, improve, and submit a PR.

Authors:
1. Saravana Kumar S | B.E CSE | Software Developer
2. Rajkumar R | B.E CSE | AI Enthusiast | Quantum Computing 
3. Thasneem Y | B.E CSE | Full Stack Developer
4. Sruthi B   | B.E CSE | Full Stack Developer
