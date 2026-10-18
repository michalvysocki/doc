# Doc

Application for learning from documentation and research papers using AI. It generates study plans and courses based on uploaded files and links.

## Tech Stack

- Backend: FastAPI (Python)
- Frontend: React + Vite (TypeScript)
- Database: PostgreSQL + pgvector
- Infrastructure: Docker

## Project Structure

- /backend: API and AI logic
- /frontend: User interface
- docker-compose.yml: Container configuration

## How to Run

### Prerequisites

- Docker
- Docker Compose

### Steps

1. Clone the repository.
2. Create a .env file in the root folder with your API keys (e.g., OPENAI_API_KEY).
3. Run the following command in the terminal:

   ```bash
   docker-compose up --build

### Access Points

Frontend: http://localhost:5173

Backend API: http://localhost:8000

API Docs (Swagger): http://localhost:8000/docs

### Main Features

Uploading documents and searching links.
AI-powered search (RAG).
Automated generation of study plans.
Progress tracking in courses.

### License

MIT