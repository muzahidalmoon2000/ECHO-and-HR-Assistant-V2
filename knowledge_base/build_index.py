import os
from langchain_community.document_loaders import PyMuPDFLoader, Docx2txtLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import OpenAIEmbeddings
from dotenv import load_dotenv

load_dotenv()  # Loads OPENAI_API_KEY

# ✅ Absolute paths based on current file location
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOCUMENTS_PATH = os.path.join(BASE_DIR, "documents")
INDEX_PATH = os.path.join(BASE_DIR, "faiss_index")

def load_documents(directory):
    docs = []
    if not os.path.exists(directory):
        print(f"❌ Directory does not exist: {directory}")
        return docs

    for file in os.listdir(directory):
        full_path = os.path.join(directory, file)
        try:
            if file.endswith(".pdf"):
                loader = PyMuPDFLoader(full_path)
            elif file.endswith(".docx"):
                loader = Docx2txtLoader(full_path)
            elif file.endswith(".txt"):
                loader = TextLoader(full_path)
            else:
                print(f"⚠️ Skipped unsupported file: {file}")
                continue

            file_docs = loader.load()
            docs.extend(file_docs)
            print(f"📄 Loaded {len(file_docs)} chunks from: {file}")
        except Exception as e:
            print(f"❌ Failed to load {file}: {e}")
    return docs

def build_index():
    print(f"🔄 Loading documents from: {DOCUMENTS_PATH}")
    documents = load_documents(DOCUMENTS_PATH)

    if not documents:
        print("❌ No documents loaded. Please add PDFs, DOCX, or TXT files.")
        return

    print(f"✅ Loaded {len(documents)} documents. Splitting into chunks...")
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
    texts = splitter.split_documents(documents)
    print(f"🧩 Split into {len(texts)} text chunks.")

    print("🔄 Creating vector embeddings...")
    embeddings = OpenAIEmbeddings()
    db = FAISS.from_documents(texts, embeddings)

    print(f"💾 Saving FAISS index to: {INDEX_PATH}")
    db.save_local(INDEX_PATH)
    print("✅ Index built and saved successfully.")

if __name__ == "__main__":
    build_index()
