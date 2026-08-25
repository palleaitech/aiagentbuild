import os
from dotenv import load_dotenv

load_dotenv()

# General Configs
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in the environment variables.")

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