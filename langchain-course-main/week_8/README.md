week_8/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app instance, middleware, and startup event handlers
│   ├── config.py            # Centralized environment variable loading (OpenAI, DB URL, etc.)
│   ├── database.py          # SQLAlchemy engine, session maker, and Base class
│   ├── models/              # Database tables
│   │   ├── __init__.py
│   │   ├── chat.py          # Chat sessions and message history models
│   │   ├── tasks.py         # Background task status tracking model
│   │   └── documents.py     # pgvector document chunks and embeddings models
│   ├── routers/             # API endpoints split by domain
│   │   ├── __init__.py
│   │   ├── chat.py          # Chat session endpoints
│   │   ├── planner.py       # Planner agent run, resume, and status endpoints
│   │   └── documents.py     # RAG document ingestion and search endpoints
│   ├── agents/              # LangGraph graphs, workers, nodes, and tools
│   │   ├── __init__.py
│   │   ├── master_graph.py  # Master router graph
│   │   ├── planner_graph.py # Planner-Executor-Critic graph + Evaluator
│   │   ├── workers.py       # Worker subgraphs (country, politics, rag, etc.)
│   │   └── tools.py         # Custom tools and vector store bindings
│   └── services/            # Reusable business logic & background workers
│       ├── __init__.py
│       ├── rag_service.py   # Embedding generation and vector insertion logic
│       └── background.py    # Background task executor functions
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env


-------------------------------------------------------------------------------------
Double-Check Your Build Context:
In your docker-compose.yaml, your build context is set to parent (..), and your dockerfile points to week_8/Dockerfile. When COPY . . runs inside the Dockerfile, it copies everything from the root week_8/ folder into /app inside the container.

This means inside the container, your structure will look like:
/app
├── app/
│   ├── main.py
│   ├── config.py
│   └── ...
├── agentic-ai-developer-bootcamp-curriculum.pdf
├── pyproject.toml
└── uv.lock



-------------------------------------------------------------------------------------
In app.main:app, the two apps mean two completely different things:

The first app (before the dot) is the directory/folder name (app/). It tells Python: "Look inside the app folder."

The main is the file name (main.py without the .py). It tells Python: "Look inside main.py."

The second app (after the colon) is the variable name inside main.py where your FastAPI instance is created (e.g., app = FastAPI()). It tells Uvicorn: "Run this specific FastAPI object."

So translated to plain English, app.main:app means: "Go into the app folder, find main.py, and run the app variable inside it."
-----------------------------------------------------------------------------------
docker compose down -v
docker compose build --no-cache
docker compose up -d

docker compose ps   # You can check the health and status of your running services with:

-------------------------------------------------------------------------------------
TROUBLE SHOOT:
1. (base) PS E:\BuildAnAgent\langchain-course-main\week_8> docker compose up -d
[+] Running 4/4
 ✔ Network week_8_default        Created                                                                                                                 0.0s
 ✔ Volume week_8_pgadmin_data    Created                                                                                                                 0.0s
 ✔ Volume week_8_pgdata          Created                                                                                                                 0.0s
 ✘ Container postgres_vector_db  Error response from daemon: Conflict. The container name "/postgres_vector_db" is alr...  

How to fix it:
You just need to remove the conflicting old containers first. Run these commands in your terminal:

 docker rm -f postgres_vector_db pgadmin_gui agentic_fastapi_app

 2. To help me troubleshoot why FastAPI isn't working, what error message or status are you seeing?

Run this command in your terminal and share the output so we can pinpoint the exact issue:

docker compose logs web

3. agentic_fastapi_app  | sqlalchemy.exc.ProgrammingError: (psycopg2.errors.UndefinedObject) type "vector" does not exist
agentic_fastapi_app  | LINE 5:  embedding VECTOR(3072) NOT NULL,

How to Fix It Instantly:
You just need to tell PostgreSQL to create the vector extension on startup.

Wipe the old volume data so PostgreSQL starts completely fresh and can run initialization extensions properly:

docker compose down -v

Enable the extension automatically or run a quick command. Since ankane/pgvector automatically supports extensions, you can ensure it's enabled by running a quick SQL command or checking your connection.

Actually, the easiest way to ensure the extension is created when the database initializes is to drop and recreate the volume (which the down -v command above does), then restart your containers:

docker compose up -d --build

Verify the logs:
docker compose logs -f web

-----------------------------------------------------------------------------------------
planner-executor-critic-agent
"Write a step-by-step itinerary to explore historical locations in Chennai.",

rag-agent
 "What is covered in Week 3 of the bootcamp?",

----------------------------------------------------------------------------------------- 
For the webhook_url, you have two options depending on what you want to test:

Leave it empty or null (null): If you don't need a notification sent anywhere and just want the agent to execute in the background, you can remove "webhook_url": "string" completely from your JSON body, or set it to null.

Use a mock webhook inspector (Great for testing!): If you want to actually see the background agent push its final results to a live URL, you can go to a free request-inspector site like Webhook.site, copy the unique URL they give you, and paste it as the webhook_url value:
{
  "goal": "Write a step-by-step itinerary to explore historical locations in Chennai.",
  "city": "Chennai",
  "webhook_url": "https://webhook.site/7c8bc119-fb89-46f0-9a30-d9573ec0a6ca",
}

----------------------------------------------------------------------------------------
How to Trigger and Test Celery via FastAPI:
Open Swagger UI: Go to http://localhost:8000/docs in your browser.

Expand /run-planner-agent: Click on the POST endpoint to test it.

Pass execution_engine: "celery": In your request body JSON, set the engine explicitly:

{
  "goal": "Write a step-by-step itinerary to explore historical locations in Chennai.",
  "city": "Chennai",
  "webhook_url":  "https://webhook.site/7c8bc119-fb89-46f0-9a30-d9573ec0a6ca",
  "execution_engine": "celery"
}

Execute: Click Execute.

What Happens Behind the Scenes:
FastAPI receives the request and hits your conditional branch: if request.execution_engine == "celery":.

Instead of running a local background thread, it calls .delay(...) on your Celery task.

FastAPI immediately returns a 200 OK response with a task ID, handing the job off to the Redis broker.

Your Celery worker container instantly picks up the task from Redis, runs the LangGraph agent, and sends the final result payload to your webhook_url (just like you saw on Webhook.site earlier!).

You can watch your Celery worker process the job live in your terminal by running:

docker compose logs -f celery_worker


--------------------------------------------------------------------------------------------------
fastapi is not working:
You can check the latest container logs by running this command in your terminal:
docker compose logs fastapi

-------------------------------------------------------------------------------------------------------
How to ingest your PDF:
You can quickly trigger the ingestion by running a small one-off python command or script inside your container.

Run this command in your terminal to execute the ingestion function for that PDF:

docker compose exec web python -c "from app.services.rag_service import ingest_document; ingest_document('agentic-ai-developer-bootcamp-curriculum.pdf')"

-------------------------------------------------------------------------------------------------------
Flower
Using Flower for monitoring your Celery worker cluster is a fantastic choice. It gives you a real-time web-based dashboard (built on Tornado) where you can inspect task states, worker health, memory usage, execution times, and success/failure rates.

Spin up the monitoring dashboard
Rebuild and start your containers with the new service:
docker compose up -d --build flower

Access the Dashboard
Once running, open your browser and navigate to:
http://localhost:5555

From there, you'll see a clean interface tracking your run_planner_celery_task executions, queue latencies, and worker node resource status in real time
-------------------------------------------------------------------------------------------------------
PyTest:

We cannot run pytest directly inside the running Docker container (docker compose exec web pytest) for a couple of straightforward reasons:

Not Installed in Production Containers: To keep container images lightweight and secure, test dependencies like pytest and httpx are typically excluded from production Dockerfiles. The container only contains what is strictly necessary to run the FastAPI application server (uvicorn).

Missing Executable: Because pytest wasn't included during the image build or listed in the production runtime requirements, the container's shell throws the executable file not found in $PATH error.

How to Run Tests Successfully Now
Since running tests inside the container isn't set up out-of-the-box, the most practical approach is running pytest directly on your host machine (where you have Anaconda/Python and pytest installed), but targeting your local database configuration instead of Docker's internal "db" hostname.

You can set your host environment variable to point to localhost and run your tests seamlessly:

$env:DB_HOST="localhost"; pytest

$env:DB_HOST="localhost"; $env:POSTGRES_USER="postgres"; $env:POSTGRES_PASSWORD="venkatpalle"; $env:POSTGRES_DB="agent_db"; pytest

-------------------------------------------------------------------------------------------------------

streamlit run streamlit_app.py

