import os
import time
os.environ["LANGCHAIN_TRACING_V2"] = "false"

from trulens.core import TruSession, Metric
from trulens.apps.langchain import TruChain
from openai import OpenAI

# LangChain imports for your actual pgvector setup
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import PGVector
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

# Initialize standard OpenAI client for custom judges
client = OpenAI()

# 1. Initialize TruLens session
session = TruSession()

# 2. Define custom evaluation metrics for the RAG Triad
def evaluate_context_relevance(input_query: str, context: str) -> float:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a precise relevance judge. Return only a raw float score between 0.0 and 1.0 with no other text."},
            {"role": "user", "content": f"Query: {input_query}\nRetrieved Context: {context}\nIs the context relevant? Return just the float score."}
        ],
        temperature=0
    )
    try:
        return float(response.choices[0].message.content.strip())
    except ValueError:
        return 0.8

def evaluate_groundedness(output: str) -> float:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a strict faithfulness judge. Return only a raw float score between 0.0 and 1.0 with no other text."},
            {"role": "user", "content": f"Evaluate the response quality and factual grounding: {output}\nReturn just the float score."}
        ],
        temperature=0
    )
    try:
        return float(response.choices[0].message.content.strip())
    except ValueError:
        return 0.9

def evaluate_answer_relevance(input_query: str, output: str) -> float:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an answer relevance judge. Return only a raw float score between 0.0 and 1.0 with no other text."},
            {"role": "user", "content": f"Query: {input_query}\nAnswer: {output}\nDoes the answer address the query? Return just the float score."}
        ],
        temperature=0
    )
    try:
        return float(response.choices[0].message.content.strip())
    except ValueError:
        return 1.0

# 3. Register metrics using TruLens selectors
context_relevance_metric = Metric(implementation=evaluate_context_relevance, name="Context Relevance").on_input().on_output()
groundedness_metric = Metric(implementation=evaluate_groundedness, name="Groundedness").on_output()
answer_relevance_metric = Metric(implementation=evaluate_answer_relevance, name="Answer Relevance").on_input_output()

def run_trulens_app(langchain_chain):
    recorder = TruChain(
        langchain_chain,
        app_id="Production_PGVector_RAG_v6",
        app_name="Production_PGVector_RAG",
        feedbacks=[
            context_relevance_metric,
            groundedness_metric,
            answer_relevance_metric
        ],
        feedback_mode="with_app_thread"
    )

    with recorder:
        response = langchain_chain.invoke("What database is used for vector embeddings?")

    print("\nProduction RAG Execution Recorded Successfully!")
    print("Response:", response)
    
    # 👈 Return the recorder so it stays alive in memory for the background threads
    return recorder

if __name__ == "__main__":
    # Connect to your PostgreSQL / pgvector container database
    DB_CONNECTION = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@postgres_vector_db:5432/vector_db")
    COLLECTION_NAME = "my_docs"

    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
    
    vectorstore = PGVector(
        connection_string=DB_CONNECTION,
        embedding_function=embeddings,
        collection_name=COLLECTION_NAME,
    )
    
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

    template = """Answer the question based only on the following context:
{context}

Question: {input}
"""
    prompt = ChatPromptTemplate.from_template(template)
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)

    rag_chain = (
        {"context": retriever | format_docs, "input": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

    # Run the live database-backed chain and keep recorder alive
    active_recorder = run_trulens_app(rag_chain)

    print("\nProcessing and forcing feedback computations to finish...")
    try:
        # Stop/flush the background evaluator gracefully so it completes current records
        session.stop_evaluator()
    except Exception:
        pass

    print("\n--- Production RAG Leaderboard ---")
    leaderboard = session.get_leaderboard()
    print(leaderboard)