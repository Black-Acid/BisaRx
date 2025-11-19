# from langchain_community.document_loaders import PyPDFLoader, TextLoader
# from langchain_text_splitters import RecursiveCharacterTextSplitter
# from langchain_community.embeddings import HuggingFaceEmbeddings
# from langchain_community.vectorstores import FAISS
# from pathlib import Path
# import os

# # === STEP 1: Load your pharmacology book ===

# pdf_paths = os.path.abspath("theBook.pdf")
# print(pdf_paths)
# pdf_path = Path(pdf_paths)
# loader = PyPDFLoader(pdf_path)
# documents = loader.load()

# # === STEP 2: Split the book into smaller chunks ===
# splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
# docs = splitter.split_documents(documents)

# # === STEP 3: Generate embeddings (local, small model) ===
# print("🔍 Generating embeddings (MiniLM-L6-v2)...")
# embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# # === STEP 4: Build FAISS vector index ===
# print("⚙️ Building FAISS vector index...")
# vectorstore = FAISS.from_documents(docs, embeddings)

# # === STEP 5: Save FAISS index locally ===
# index_path = Path("theBook_faiss_index")
# vectorstore.save_local(index_path)

# print(f"✅ Index successfully built and saved at '{index_path}'")


# pdf_paths = os.path.abspath("theBook_faiss_index")
# print(pdf_paths)