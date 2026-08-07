# Import LLM wrappers for OpenAI and Google Gemini
from langchain_openai import ChatOpenAI
from langchain_google_genai  import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

# Load environment variables from a .env file
from dotenv import load_dotenv
import os

# Load environment variables (like API keys) from .env file
load_dotenv()

# Fetch the OpenAI API key from environment variables
api_key = os.getenv("OPENAI_API_KEY")

# Safety check: if no API key is found, raise an error
if not api_key:
    raise ValueError("OPENAI_API_KEY is not set in the environment variables.") 

# Initialize OpenAI LLM with chosen model and temperature
llm_openai = ChatOpenAI(model_name="gpt-4o", temperature=0.7, openai_api_key=api_key)

# -------------------------------
# PromptManager Implementation
# -------------------------------
class PromptManager:
  def __init__(self): 
     # centralised prompt management for the application
     self.prompts = {
        "support system": ChatPromptTemplate.from_messages([
           ("system", "You are a helpful support agent. "),
            ("human", "{question}")
        ]),
        "travel_agent": ChatPromptTemplate.from_messages([
           ("system", "You are a travel agent. "),
            ("human", "plan a trip to {city} witha budget of {budget}.")
        ])
     }

  def get_prompt(self, name, **kwargs):
      """ Retrive and format by a name and keyword arguments. """
      if name not in self.prompts:
          raise ValueError(f"Prompt '{name}' not found.")
      return self.prompts[name].invoke(kwargs)
  
# -------------------------------
# Usage Example
# -------------------------------
pm = PromptManager()

# example 1: custom prompt for support system
support_prompt = pm.get_prompt("support system", question="How do I reset my password?")
response = llm_openai.invoke(support_prompt)
print("Support Response:", response.content)
print("---------------------------------------------------------------------")
#example 2: travel agent prompt
travel_prompt = pm.get_prompt("travel_agent", city="Paris", budget="$2000") 
response2 = llm_openai.invoke(travel_prompt)
print("Travel Response:", response2.content)








    
