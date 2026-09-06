import os
os.environ["LANGCHAIN_TRACING_V2"] = "false"

from ragas import evaluate, RunConfig
from datasets import Dataset
from ragas.metrics import Faithfulness, AnswerRelevancy, ContextRecall
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

def run_rag_evaluation():
    data = {
        "question": [
            "What topics are covered in Week 3 of the bootcamp?",
            "What database is used for vector embeddings?"
        ],
        "answer": [
            "In Week 3 of the bootcamp, the focus is on LangChain, LlamaIndex, and RAG Basics, covering document loading, chunking strategies, embeddings, and vector stores.",
            "The project uses PostgreSQL with pgvector for storing and querying vector embeddings."
        ],
        "contexts": [
            [
                "Week 3 Curriculum: LangChain, LlamaIndex, and RAG Basics. Topics include document loading, chunking strategy, embeddings, vector stores, and retrievers."
            ],
            [
                "Infrastructure Stack: PostgreSQL configured with the pgvector extension is used as the primary vector database backend for semantic search."
            ]
        ],
        "ground_truth": [
            "Week 3 covers LangChain, LlamaIndex, and RAG Basics including document loading, chunking, embeddings, and vector stores.",
            "PostgreSQL with pgvector is used for vector embeddings."
        ]
    }

    dataset = Dataset.from_dict(data)

    print("Initializing OpenAI judge models for full evaluation...")
    
    eval_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    eval_embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    config = RunConfig(timeout=120, max_workers=2, max_retries=3)

    print("Running Ragas evaluation metrics (Faithfulness, Answer Relevancy, Context Recall)...")
    result = evaluate(
        dataset=dataset,
        metrics=[
            Faithfulness(llm=eval_llm),
            AnswerRelevancy(llm=eval_llm, embeddings=eval_embeddings),
            ContextRecall(llm=eval_llm),
        ],
        llm=eval_llm,
        embeddings=eval_embeddings,
        run_config=config,
    )

    print("\n--- RAG Evaluation Results ---")
    print(result)
    
    df = result.to_pandas()
    print("\n--- Detailed Results DataFrame ---")
    print(df[["faithfulness", "answer_relevancy", "context_recall"]])

if __name__ == "__main__":
    run_rag_evaluation()