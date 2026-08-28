import os
from dotenv import load_dotenv

load_dotenv()

# Provider Configurations
REASONING_PROVIDER = os.getenv("REASONING_PROVIDER", "").lower()
SUMMARIZATION_PROVIDER = os.getenv("SUMMARIZATION_PROVIDER", "").lower()

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

# Conditional Validation: Only require keys for the providers you actually use!
if "openai" in [REASONING_PROVIDER, SUMMARIZATION_PROVIDER] and not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is required because OpenAI is selected in your providers.")

if "gemini" in [REASONING_PROVIDER, SUMMARIZATION_PROVIDER] and not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY (or GEMINI_API_KEY) is required because Gemini is selected in your providers.")

# Check if we are running inside a Docker container (Docker typically sets a .dockerenv file or hostname)
is_docker = os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER", False)

# If running locally for pytest, use localhost; otherwise, default to "db" for Docker
if os.getenv("PYTEST_CURRENT_TEST") or "pytest" in os.environ.get("_", ""):
    DB_HOST = "localhost"
elif is_docker:
    DB_HOST = os.getenv("DB_HOST", "db")
else:
    DB_HOST = os.getenv("DB_HOST", "localhost")

DB_PORT = os.getenv("DB_PORT", "5432")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
POSTGRES_DB = os.getenv("POSTGRES_DB", "agent_db")

DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{DB_HOST}:{DB_PORT}/{POSTGRES_DB}"