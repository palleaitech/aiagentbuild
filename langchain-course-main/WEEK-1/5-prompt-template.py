from urllib import response

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

# LLM
llm = ChatOpenAI(model="gpt-4o", temperature=0.7, openai_api_key=api_key)

prompt_template = ChatPromptTemplate.from_messages([
    ("system", "You are {role}. your nam eis {name} use your name while responding to the user."),  
    ("human", "Tell me about {topic} in {style} style.")
])

user_input = "What is the capital of France?"

templated_prompt = prompt_template.invoke({
    "role": "A helpful assistant",
    "name": "LangChain Assistant",
    "topic": "Python programming",
    "style": "concise"
})

response = llm.invoke(templated_prompt)

print(f"LLM Response: {response.content}")

print("-----------------------------------------------------------------------------")

first_prompt = ChatPromptTemplate.from_template("Summarize {topic} in one sentence.")
second_prompt = ChatPromptTemplate.from_template("Expand this into a short story: {summary}")

Topic = input("Enter a topic for summarization and story generation: ")
summary = llm.invoke(first_prompt.format(topic=Topic)).content
story = llm.invoke(second_prompt.format(summary=summary)).content

print("Summary:", summary)
print("-----------------------------------------------------------------------------")
print("Story:", story)


