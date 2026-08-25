import os
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

def get_llm(tier: str = "reasoning", temperature: float = 0.7):
    """
    Dynamically initializes and returns an LLM instance (OpenAI or Gemini) 
    strictly based on environment variable configurations. No hardcoded fallbacks.

    Configuration Guidelines in .env:
    --------------------------------------------------
    - REASONING_PROVIDER=openai (or gemini)
    - SUMMARIZATION_PROVIDER=openai (or gemini)
    --------------------------------------------------
    """
    # Explicitly map the tier to its corresponding environment variable
    env_var_name = f"{tier.upper()}_PROVIDER"
    provider = os.getenv(env_var_name)

    if not provider:
        raise ValueError(
            f"Configuration Error: '{env_var_name}' is not set in your environment variables. "
            f"Please explicitly specify either 'openai' or 'gemini' for the '{tier}' tier."
        )

    provider = provider.lower()

    # Instantiate the requested model based on the explicit configuration
    if provider == "gemini":
        return ChatGoogleGenerativeAI(
            model=os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
            google_api_key=os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"),
            temperature=temperature
        )
    elif provider == "openai":
        return ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            temperature=temperature
        )
    else:
        raise ValueError(
            f"Invalid provider '{provider}' specified for {env_var_name}. "
            f"Supported providers are 'openai' or 'gemini'."
        )