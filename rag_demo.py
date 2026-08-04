import sys

import chromadb
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


client_ai = OpenAI()
chroma_client = chromadb.Client()
collection = chroma_client.create_collection("airport_docs")

documents = [
    "AirportProject is a flight booking API built with Django REST Framework.",
    "The project uses Simple JWT for authorization and PostgreSQL as the database.",
    "Payment is implemented via Stripe Checkout Sessions.",
    "Project uses Docker for deployment.",
]

collection.add(
    documents=documents,
    ids=[f"doc{i}" for i in range(len(documents))],
)


def ask_rag(question):
    results = collection.query(query_texts=[question], n_results=1)
    context = "\n".join(results["documents"][0])

    prompt = f"""Context:
{context}

Question: {question}

Answer in one short sentence and only based on the context above.
If the context contains a direct fact, use it as the answer.
If the answer is not in the context, say you don't know."""

    response = client_ai.responses.create(
        model="gpt-5.4-nano",
        input=prompt,
    )
    return response.output_text


print(ask_rag("What database is used in the project?"))
print("---")
print(ask_rag("How is payment implemented?"))
print("---")
print(ask_rag("What's the weather like today?"))
