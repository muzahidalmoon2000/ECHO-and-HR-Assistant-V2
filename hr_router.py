import os
from openai import OpenAI
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def classify_intent(user_query):
    """Use ChatGPT to classify the user's intent."""
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {
                "role": "system",
                "content": "Classify the user query as one of: HR_Admin, File_Operation, Email_Operation, General."
            },
            {
                "role": "user",
                "content": user_query
            }
        ],
        temperature=0
    )
    return response.choices[0].message.content.strip()

def search_hr_knowledge_base(user_query):
    """Search the FAISS index for HR/Admin-related answers."""
    base_path = os.path.dirname(os.path.abspath(__file__))
    index_path = os.path.join(base_path, "knowledge_base", "faiss_index")
    faiss_file = os.path.join(index_path, "index.faiss")

    if not os.path.exists(faiss_file):
        return "Knowledge base not found."

    embeddings = OpenAIEmbeddings()
    vector_store = FAISS.load_local(index_path, embeddings, allow_dangerous_deserialization=True)

    results = vector_store.similarity_search(user_query, k=3)
    if not results:
        return "No relevant information found."

    context = "\n\n".join([doc.page_content for doc in results])
    return context

def generate_answer_from_context(user_query, context):
    """Generate a helpful response using context and ChatGPT."""
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {
                "role": "system",
                "content": "You are an HR assistant. Use the following context to answer the user's question."
            },
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {user_query}"
            }
        ],
        temperature=0.2
    )
    return response.choices[0].message.content.strip()

def handle_query(user_query):
    """Route queries based on classified intent."""
    intent = classify_intent(user_query)

    if intent == "HR_Admin":
        context = search_hr_knowledge_base(user_query)
        if context.startswith("Knowledge base") or context.startswith("No relevant"):
            return context
        return generate_answer_from_context(user_query, context)

    return None  # Let app.py handle non-HR queries
