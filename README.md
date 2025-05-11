Voice Agent
   A production-ready voice agent application for handling customer calls, built with Flask, PostgreSQL, LangGraph, and Docker. Supports booking management, call transcription, and conversation state persistence.
Prerequisites

Python 3.9+
Docker and Docker Compose
Git
PostgreSQL client (e.g., psql or pgAdmin)

Setup

Clone the Repository:
git clone https://github.com/your-username/voice-agent-prod.git
cd voice-agent-prod


Set Up Environment:Copy .env.example to .env and update with your credentials:
cp .env.example .env


Start PostgreSQL:
docker-compose up -d


Install Dependencies:Create a virtual environment and install requirements:
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt


Verify PostgreSQL:Connect to the database:
psql -h localhost -U voice_agent_user -d voice_agent

Password: VoIc3Ag3NT2025


Next Steps

Define database schema in src/models/.
Implement Flask routes in src/api/routes.py.
Set up LangGraph workflow in src/services/workflow_service.py.

License
   MIT
