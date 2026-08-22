# Step 1:This module centralizes your environment variables so every other module can easily import them.

import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is not set in the environment variables.")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in the environment variables.")
