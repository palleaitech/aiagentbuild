from langchain_openai import ChatOpenAI
from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError("OPENAI_API_KEY is not set in the environment variables.") 

# Define a tool
@tool
def get_capital(country: str) -> str:
    """Return the capital of a given country."""
    capitals = {"france": "Paris", "india": "New Delhi"}
    return capitals.get(country.lower(), "Unknown")

tools = [get_capital]

# LLM
llm = ChatOpenAI(model="gpt-4o", temperature=0.7, openai_api_key=api_key)

# Prompt template
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant. Use tools when needed."),
    ("human", "{input}")
])

# Build a simple pipeline (Runnable)
agent = prompt | llm

# Run
result = agent.invoke({"input": "What is the capital of France?"})
print(result.content)
