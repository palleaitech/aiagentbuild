from langchain_openai import ChatOpenAI
from langchain_google_genai  import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError("OPENAI_API_KEY is not set in the environment variables.") 

llm_openai = ChatOpenAI(model_name="gpt-4o", temperature=0.7, openai_api_key=api_key)

print("===================================METHOD 1============================================")
m1 = "who is prime minister of india?"

messages = [
    SystemMessage(content="You are a helpful assistant."),  
    HumanMessage(content=m1)
]

response = llm_openai.invoke(messages)
print(type(response))
print(response.content)

print("===================================METHOD 2============================================")
#-----------------------------------------------------------------------------#
chat_history = [SystemMessage(content="You are a trivia master.")]
chat_history.append(HumanMessage(content="What is the capital of France?"))
response = llm_openai.invoke(chat_history)
chat_history.append(response)
chat_history.append(HumanMessage(content="What is the capital of Germany?"))
response = llm_openai.invoke(chat_history)
chat_history.append(response)

for msg in chat_history:
    print(f"{msg.type}: {msg.content}")

print("===================================METHOD 3============================================")

m2 = ["what is climate in india?", "what is climate in usa?", "what is climate in australia?"]

system_message = SystemMessage(content="You are a helpful assistant.")  

for question in m2:
    message=[HumanMessage(content=question), system_message]
    response = llm_openai.invoke(message)
    print(f"Q: {question} A: {response.content}")
