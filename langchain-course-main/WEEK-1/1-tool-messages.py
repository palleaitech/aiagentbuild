from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain_google_genai  import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError("OPENAI_API_KEY is not set in the environment variables.") 

llm_openai = ChatOpenAI(model_name="gpt-4o", temperature=0.7, openai_api_key=api_key)

# print("===================================METHOD 1 MANUALLY INVOKING THE TOOL ============================================")
@tool
def get_prime_minister_of_india() -> str:
    """
    Get the current Prime Minister of India.
    """
    messages = [
        SystemMessage(content="You are a helpful assistant."),  
        HumanMessage(content="Who is the current Prime Minister of India?")
    ]
    response = llm_openai.invoke(messages)
    #print(f"DEBUG: LLM returned: {response.content}")
    return response.content

@tool
def get_capital_of_country(country: str) -> str:
    """
    Get the capital of a given country.
    """
    messages = [
        SystemMessage(content="You are a helpful assistant."),  
        HumanMessage(content=f"What is the capital of {country}?")
    ]
    response = llm_openai.invoke(messages)
    #print(f"DEBUG: LLM returned: {response.content}")
    return response.content

@tool
def get_climate_of_country(country: str) -> str:
    """
    Get the climate of a given country.
    """
    messages = [
        SystemMessage(content="You are a helpful assistant."),  
        HumanMessage(content=f"What is the climate in {country}?")
    ]
    response = llm_openai.invoke(messages)
    #print(f"DEBUG: LLM returned: {response.content}")
    return response.content 

tools = [get_prime_minister_of_india, get_capital_of_country, get_climate_of_country]
print("================================NO BINDING TOOLS WITH LLM ============================================")
#llm_openai = llm_openai.bind_tools(tools)

# call each tool and print the response
for t in tools:
    if t.name == "get_prime_minister_of_india":
        response = t.invoke({})
        print(f"Prime Minister of India: {response}")
    elif t.name == "get_capital_of_country":
        country = "France"
        response = t.invoke({"country": country})
        print(f"Capital of {country}: {response}")
    elif t.name == "get_climate_of_country":
        country = "India"
        response = t.invoke({"country": country})
        print(f"Climate in {country}: {response}")
        


        