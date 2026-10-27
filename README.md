# Doc

An AI teaching assistant. You describe what you want to learn, optionally with your own files and photos of notes, and Doc plans a course as a map of topics. Inside each topic you get a lesson, practice tasks graded by the model, spaced-repetition reviews and a chat that knows the lesson. A course chat next to the map changes the course structure.

## Features

- **Course planning**: a map of topics (up to 3 levels, grouped into modules for bigger courses) generated from your request, your files and, when useful, the web. The map is checked by code and reviewed by a stronger model before it is saved, and the creation page shows each step live.
- **Lessons and tasks**: generated on the first visit, so only opened topics cost money. Both are checked and reviewed before they are saved. Lessons render Markdown, code and math (KaTeX).
- **Grading and reviews**: open answers are graded against hidden grading notes (correct, partially correct, incorrect, with feedback). Graded tasks come back for review on a 1, 3, 7, 14, 30 day ladder.
- **Adaptive learning**: lessons and tasks adapt to your results in the course, and "Practice this" creates a follow-up task aimed at what an answer missed.
- **About me and course goal**: describe your background once; every lesson, task and chat answer takes it into account. The goal of each course can be edited.
- **Chats**: a lesson chat (explains, adds subtopics and tasks, proposes regenerating the lesson or tasks) and a course chat (renames and moves topics, proposes adding or deleting topics or rebuilding the whole course). Changes that remove or rebuild content wait for a click on a confirmation card. Answers are streamed.
- **Your materials**: PDF, Word, Excel, PowerPoint, text files and images (transcribed by a vision model) are indexed for retrieval (RAG with pgvector) and used by chats, lessons and course planning.
- **Long context**: older chat messages are summarized, search queries are rewritten from recent messages, every file has a summary, and prompts stay within a token budget.

## Tech stack

- **Backend**: FastAPI, SQLAlchemy 2, Alembic, Pydantic, LlamaIndex (text splitting, PDF), MarkItDown (Office files)
- **Frontend**: React 19, React Router, Vite, Tailwind CSS 4 (JavaScript)
- **Database**: PostgreSQL 17 with pgvector
- **Models**: all through [OpenRouter](https://openrouter.ai): one model for lessons, tasks and chats, a stronger one for planning courses and one for reviews; `text-embedding-3-small` for embeddings
- **Infrastructure**: Docker Compose

## Project structure

- `backend/src`: API (`main.py`) and the logic: courses, chats, tasks, rebuilds, reviews and the OpenRouter client
- `backend/migrations`: Alembic migrations
- `backend/tests`: pytest tests; model calls are faked and real requests to OpenRouter are blocked
- `frontend/src`: pages, components and hooks
- `test-materials`: a sample PDF for trying out file uploads

## How to run

### Prerequisites

- Docker with Docker Compose
- An [OpenRouter](https://openrouter.ai) API key

### Steps

1. Clone the repository.
2. Create `backend/.env` from the template and add your API key:

   ```bash
   cp backend/.env_template backend/.env
   ```

3. Start the containers:

   ```bash
   docker-compose up --build
   ```

4. Create the database tables (first run, and after pulling new migrations):

   ```bash
   docker-compose exec backend uv run alembic upgrade head
   ```

### Access points

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API docs (Swagger): http://localhost:8000/docs

### Configuration (`backend/.env`)

| Variable | Meaning |
|---|---|
| `OPENROUTER_API_KEY` | Your OpenRouter key (required) |
| `MODEL` | Model for lessons, tasks, grading and chats |
| `PLANNING_MODEL` | Model for course maps and rebuilds (defaults to `MODEL`) |
| `PLANNING_REASONING_EFFORT` | Optional reasoning effort for planning, e.g. `high` |
| `REVIEW_MODEL` | Model that reviews lessons and tasks (defaults to `MODEL`) |
| `EMBEDDING_MODEL` | Model for embeddings |
| `DATABASE_URL` | Database connection for running the backend outside Docker |
| `WEB_SEARCH` | `off` turns web search off |
| `REVIEW` | `off` turns the reviews off (each review is an extra model call) |
| `CONTEXT_BUDGET_TOKENS` | Token budget of a chat request (default 60000) |

### Tests

```bash
cd backend
uv run pytest
```

### New npm packages

The frontend container has its own `node_modules`, so after adding a package install it in the container too:

```bash
docker-compose exec frontend npm install
```

## License

MIT
