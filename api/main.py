import os
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import chromadb
from chromadb.utils import embedding_functions

app = FastAPI(title="Kenyan Legal Interpreter API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CORRECTED PATH MATRIX ---
# Since 'data' is inside 'api', and Render uses 'api' as the root directory:
# Local path will just be "data/legal_ai_vector_db"
# For Render's persistent disk, we mount it directly to "/var/data" and point there.
RENDER_DISK_PATH = "/var/data"
DATA_DIR = RENDER_DISK_PATH if os.path.exists(RENDER_DISK_PATH) else "data"
VECTOR_DB_DIR = os.path.join(DATA_DIR, "legal_ai_vector_db")
COLLECTION_NAME = "kenya_legal_documents"

# Initialize ChromaDB
embedding_function = embedding_functions.DefaultEmbeddingFunction()
chroma_client = chromadb.PersistentClient(path=VECTOR_DB_DIR)
collection = chroma_client.get_collection(
    name=COLLECTION_NAME, 
    embedding_function=embedding_function
)

# RunPod Config
RUNPOD_ENDPOINT_ID = os.getenv("RUNPOD_ENDPOINT_ID")
RUNPOD_API_KEY = os.getenv("RUNPOD_API_KEY")

class QueryRequest(BaseModel):
    question: str

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "chunks_loaded": collection.count()}

@app.post("/api/chat")
async def chat_endpoint(request: QueryRequest):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")
        
    if not RUNPOD_ENDPOINT_ID or not RUNPOD_API_KEY:
        raise HTTPException(status_code=500, detail="Backend configuration missing RunPod keys.")

    # 1. Query ChromaDB 
    search_results = collection.query(query_texts=[question], n_results=3)
    retrieved_docs = search_results.get("documents", [[]])[0]
    retrieved_metas = search_results.get("metadatas", [[]])[0]
    
    if not retrieved_docs:
        context_str = "No specific background context available from internal database logs."
    else:
        context_str = ""
        for i, (doc, meta) in enumerate(zip(retrieved_docs, retrieved_metas)):
            source_id = meta.get("source_doc_id", "Unknown Gazette")
            context_str += f"[Source Document {source_id} (Chunk {i+1})]\n{doc}\n\n"
    
    # 2. Your custom Llama-3 instruction set
    SYSTEM_PROMPT = (
        "You are a warm, highly empathetic Kenyan Legal Interpreter AI. Your purpose is to "
        "translate dense, intimidating legal jargon into clear, narrative-driven explanations "
        "that everyday citizens can immediately relate to and understand. Always rely heavily "
        "on the provided context to form your answers."
    )
    
    llama3_prompt_blueprint = """<|start_header_id|>system<|end_header_id|>

{}<|eot_id|><|start_header_id|>user<|end_header_id|>

CONTEXT SOURCE TEXTS:
{}

USER QUESTION:
{}<|eot_id|><|start_header_id|>assistant<|end_header_id|>

"""
    formatted_prompt = llama3_prompt_blueprint.format(SYSTEM_PROMPT, context_str, question)
    
    # 3. Request inference handling from RunPod Serverless
    runpod_url = f"https://api.runpod.ai/v1/{RUNPOD_ENDPOINT_ID}/runsync"
    payload = {
        "input": {
            "prompt": formatted_prompt,
            "max_tokens": 512,
            "temperature": 0.1,
            "top_p": 0.9,
            "stop": ["<|eot_id|>", "user", "system"]
        }
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {RUNPOD_API_KEY}"
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(runpod_url, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
            
            ai_output = result.get("output", "Model failed to return a proper response.")
            return {"interpretation": ai_output}
            
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Inference cluster error: {str(e)}")