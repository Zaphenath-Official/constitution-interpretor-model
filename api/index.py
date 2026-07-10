import os
import re
import json
import time
import pypdf
import requests
import chromadb
import asyncio
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from urllib.parse import urljoin
from llama_cpp import Llama
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from chromadb.utils import embedding_functions

# FIX: Imported the background thread task scheduler tools
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# Initialize Flask Framework
app = Flask(__name__)
CORS(app)

# =====================================================================
# GLOBAL SCALING FACTOR (CONTROL PANEL)
# =====================================================================
PRODUCTION_MODE = False  # Set to True for full deployment execution

if not PRODUCTION_MODE:
    LIMIT_PAGES = 1       # Experimental sample constraints
    LIMIT_PER_PAGE = 2
else:
    LIMIT_PAGES = None    # Continuous scale boundaries
    LIMIT_PER_PAGE = None

# --- SYSTEM DIRECTORY MATRIX CONFIGURATION ---
DATA_DIR = "data"
VECTOR_DB_DIR = os.path.join(DATA_DIR, "legal_ai_vector_db")
COLLECTION_NAME = "kenya_legal_documents"
MASTER_MANIFEST_PATH = os.path.join(DATA_DIR, "data_manifest.json")
SYNC_MANIFEST_PATH = os.path.join(DATA_DIR, "sync_kenya_gazette_manifest.json")
TARGET_CATEGORY = "kenya_gazette"
GAZETTE_PDF_DIR = os.path.join(DATA_DIR, "scraped_raw_pdfs", TARGET_CATEGORY)

os.makedirs(GAZETTE_PDF_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# Point directly to your local single extracted GGUF file location
GGUF_MODEL_PATH = os.path.join("models", "llama-3-8b-instruct.Q4_K_M.gguf")

print("--> Bootstrapping local fast RAG engine...")

# =====================================================================
# STEP 1: INITIALIZE CHROMADB CLIENT
# =====================================================================
embedding_function = embedding_functions.DefaultEmbeddingFunction()
chroma_client = chromadb.PersistentClient(path=VECTOR_DB_DIR)
collection = chroma_client.get_or_create_collection(
    name=COLLECTION_NAME, 
    embedding_function=embedding_function
)
print(f"✅ Bound to ChromaDB collection: '{COLLECTION_NAME}' ({collection.count()} chunks available)")

# =====================================================================
# STEP 2: LOAD THE COMPILED GGUF VIA LLAMA.CPP
# =====================================================================
print(f"--> Loading standalone optimized model from: {GGUF_MODEL_PATH}")
if not os.path.exists(GGUF_MODEL_PATH):
    print(f"[WARN] Local GGUF file missing at {GGUF_MODEL_PATH}. API will boot but RAG queries will return mock text.")
    llm = None
else:
    llm = Llama(
        model_path=GGUF_MODEL_PATH,
        n_ctx=2048,
        n_threads=4  # Adjust to match half of your computer's CPU core count
    )
    print("✅ Standalone fine-tuned model successfully initialized into local RAM memory.")

# =====================================================================
# CORE PIPELINE WORKING MODULES
# =====================================================================

def load_master_manifest():
    """Reads the global cross-category database manifest safely using string memory reads."""
    if not os.path.exists(MASTER_MANIFEST_PATH):
        return {"system_metadata": {"last_updated": "", "total_indexed": 0, "total_downloaded": 0}, "registry": {}}
    with open(MASTER_MANIFEST_PATH, "r", encoding="utf-8") as f:
        content = f.read().strip()
        if not content:
            return {"system_metadata": {"last_updated": "", "total_indexed": 0, "total_downloaded": 0}, "registry": {}}
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"system_metadata": {"last_updated": "", "total_indexed": 0, "total_downloaded": 0}, "registry": {}}

def get_new_gazette_entries():
    """Scrapes Kenya Law portal dynamically matching the current calendar year."""
    # FIX: Dynamically fetch current calendar year from host engine
    current_calendar_year = datetime.now(timezone.utc).year
    base_url = f"https://kenyalaw.org{current_calendar_year}?q=&sort=-date"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    
    known_urls = set()
    master_manifest = load_master_manifest()
    
    for item in master_manifest.get("registry", {}).values():
        if item.get("source_url"):
            known_urls.add(item["source_url"])
            
    weekly_history = []
    if os.path.exists(SYNC_MANIFEST_PATH):
        try:
            with open(SYNC_MANIFEST_PATH, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    weekly_history = json.loads(content)
                    for entry in weekly_history:
                        known_urls.add(entry.get("url"))
        except Exception as e:
            print(f"--> [Warning] Could not read sync manifest layout: {e}")

    try:
        print(f"--> Scraping chronological feed at: {base_url}")
        response = requests.get(base_url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        delta_items = []
        table_rows = soup.find_all("tr")
        
        for row in table_rows:
            title_td = row.find("td", class_="cell-title")
            if not title_td:
                continue
                
            anchor = title_td.find("a", href=True)
            if not anchor:
                continue
                
            view_url = urljoin(base_url, anchor["href"])
            title_text = anchor.get_text(strip=True)
            
            download_link = None
            if "/source" in view_url or ".pdf" in view_url.lower():
                download_link = view_url
            else:
                try:
                    time.sleep(0.5)
                    sub_res = requests.get(view_url, headers=headers, timeout=15)
                    sub_soup = BeautifulSoup(sub_res.text, "html.parser")
                    download_btn = sub_soup.find("a", class_=lambda c: c and "btn-primary" in c and "btn-shrink-sm" in c)
                    
                    if download_btn and download_btn.get("href"):
                        download_link = urljoin(view_url, download_btn["href"])
                    else:
                        for sub_link in sub_soup.find_all("a", href=True):
                            if "/source" in sub_link["href"].lower():
                                download_link = urljoin(view_url, sub_link["href"])
                                break
                    if not download_link:
                        download_link = view_url
                except Exception as sub_err:
                    continue
            
            # Catch camelCase and lowercase paths safely
            if download_link and download_link not in known_urls:
                url_clean = view_url.strip("/")
                segments = url_clean.split("/")
                doc_id = segments[-1] if segments[-1].replace("-", "").isalnum() else str(hash(view_url) % 100000)
                
                delta_items.append({
                    "id": doc_id,
                    "url": download_link,
                    "view_url": view_url,
                    "title": title_text,
                    "scraped_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                })
                
                # Enforce experimental ceiling constraints during sample validation runs
                if LIMIT_PER_PAGE is not None and len(delta_items) >= LIMIT_PER_PAGE:
                    break
                    
        return delta_items, weekly_history, master_manifest
    except Exception as e:
        print(f"❌ Scraping index failure: {e}")
        return [], weekly_history, master_manifest

def download_gazette_pdf(item):
    """Streams the target PDF file straight into your specific raw folder path."""
    local_filename = f"gazette_{item['id']}.pdf"
    destination_path = os.path.join(GAZETTE_PDF_DIR, local_filename)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    try:
        response = requests.get(item['url'], headers=headers, stream=True, timeout=30)
        response.raise_for_status()
        with open(destination_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return destination_path
    except Exception as e:
        if os.path.exists(destination_path):
            os.remove(destination_path)
        return None

def extract_and_chunk_pdf(file_path, doc_id):
    """Parses raw text layers and prepares overlap chunking for legal retention."""
    try:
        reader = pypdf.PdfReader(file_path)
        full_text = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                full_text.append(text)
                
        compiled_text = "\n".join(full_text)
        if not compiled_text.strip():
            return [], [], []
            
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1400,
            chunk_overlap=250,
            length_function=len
        )
        chunks = text_splitter.split_text(compiled_text)
        
        documents, metadatas, ids = [], [], []
        for index, chunk in enumerate(chunks):
            documents.append(chunk)
            metadatas.append({
                "source_doc_id": doc_id,
                "category": TARGET_CATEGORY,
                "sync_date": datetime.now(timezone.utc).strftime("%Y-%m-%d")
            })
            ids.append(f"sync_gazette_{doc_id}_chunk_{index}")
            
        return documents, metadatas, ids
    except Exception as e:
        return [], [], []

def run_sync_logic_internal():
    """Execution encapsulation block for the Friday Sync engine."""
    print(f"\n⏰ [{datetime.now(timezone.utc).isoformat()}] AUTOMATED SYNC TASK TRIGGERED...")
    new_items, weekly_history, master_manifest = get_new_gazette_entries()
    if not new_items:
        print("🎉 No new items detected this week. System matches master logs completely.")
        return 0

    processed_count = 0
    for item in new_items:
        downloaded_path = download_gazette_pdf(item)
        if not downloaded_path:
            continue
            
        docs, metas, ids = extract_and_chunk_pdf(downloaded_path, item['id'])
        if docs:
            collection.upsert(documents=docs, metadatas=metas, ids=ids)
            print(f"    ✅ Embedded and upserted {len(docs)} chunks successfully.")
            
        doc_key = f"ke_gazette_id_{item['id']}"
        master_manifest["registry"][doc_key] = {
            "category": TARGET_CATEGORY,
            "title": item["title"],
            "source_url": item["url"],
            "local_path": downloaded_path,
            "downloaded": True,
            "downloaded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        }
        
        master_manifest["system_metadata"]["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        master_manifest["system_metadata"]["total_indexed"] = len(master_manifest["registry"])
        master_manifest["system_metadata"]["total_downloaded"] = sum(
            1 for entry in master_manifest["registry"].values() if entry.get("downloaded")
        )
        
        with open(MASTER_MANIFEST_PATH, "w", encoding="utf-8") as f:
            json.dump(master_manifest, f, indent=2, ensure_ascii=False)

        weekly_history.append(item)
        with open(SYNC_MANIFEST_PATH, "w", encoding="utf-8") as f:
            json.dump(weekly_history, f, indent=4, ensure_ascii=False)
        
        processed_count += 1
    print(f"✓ [{datetime.now(timezone.utc).isoformat()}] Sync task concluded. Processed {processed_count} new entries.")
    return processed_count

# =====================================================================
# STEP 4: INITIALIZE AUTOMATED CRON SCHEDULER (THE FRIDAY AUTOMATION)
# =====================================================================
# BackgroundScheduler runs on its own isolated CPU thread away from Flask
scheduler = BackgroundScheduler()

# CRON TRIGGER RULES: Fires every Friday ('fri') at 23:00 (11:00 PM) 
friday_trigger = CronTrigger(
    day_of_week='fri',
    hour=23,
    minute=0,
    timezone='Africa/Nairobi'  # Locks onto local EAT timezone mapping securely
)

# Bind our execution sync module to the active engine thread
scheduler.add_job(
    func=run_sync_logic_internal,
    trigger=friday_trigger,
    id="weekly_kenya_gazette_sync_job",
    name="Scrapes and vectorizes fresh Friday Gazette data releases automatically",
    replace_existing=True
)

# Start the background ticking clock engine
scheduler.start()
print("⏰ Background Task Scheduler engine successfully initialized and ticking.")

# =====================================================================
# FLASK WEB ENDPOINT ROUTING (STREAM CONFIGURED)
# =====================================================================

@app.route("/api/ask", methods=["POST"])
def ask_legal_ai_endpoint():
    """POST endpoint that streams semantic legal explanations via GGUF RAG in real-time."""
    data = request.get_json() or {}
    question = data.get("question", "").strip()
    top_k = int(data.get("top_k", 3))
    
    if not question:
        return jsonify({"error": "Empty search question provided"}), 400
        
    search_results = collection.query(query_texts=[question], n_results=top_k)
    retrieved_docs = search_results.get("documents", [[]]) if search_results.get("documents") else []
    retrieved_metas = search_results.get("metadatas", [[]]) if search_results.get("metadatas") else []
    
    if not retrieved_docs or not retrieved_docs[0]:
        context_str = "No specific background context available from internal database logs."
    else:
        context_str = ""
        for i, (doc, meta) in enumerate(zip(retrieved_docs[0], retrieved_metas[0])):
            source_id = meta.get("source_doc_id", "Unknown Gazette")
            context_str += f"[Source Document {source_id} (Chunk {i+1})]\n{doc}\n\n"
            
    if llm is None:
        def generate_mock_stream():
            mock_text = "**MOCK LAW HEADLINE:** MODEL NOT DETECTED LOCALLY\n\nSimulation connection verified."
            for word in mock_text.split(" "):
                time.sleep(0.05)
                yield word + " "
        return Response(generate_mock_stream(), mimetype="text/event-stream")
        
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
    
    response_chunks = llm(
        formatted_prompt,
        max_tokens=512,
        temperature=0.1,
        top_p=0.9,
        stop=["<|eot_id|>", "user", "system"],
        stream=True
    )
    
    def generate_tokens():
        try:
            for chunk in response_chunks:
                token = chunk["choices"][0]["text"]
                if token:
                    yield token
        except Exception as stream_err:
            yield f"\n[STREAM ERROR: {str(stream_err)}]"

    return Response(generate_tokens(), mimetype="text/event-stream")

@app.route("/api/sync", methods=["GET"])
def trigger_sync_endpoint():
    """GET endpoint to manually trigger a fresh delta sync run loop instantly."""
    try:
        added_records = run_sync_logic_internal()
        return jsonify({
            "status": "success",
            "msg": f"Manual synchronization cycle run completed successfully. Added {added_records} items."
        })
    except Exception as e:
        return jsonify({"status": "failed", "error": str(e)}), 500

if __name__ == "__main__":
    try:
        # Run Flask main server thread blocks natively on port 5000
        app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
    finally:
        # Shutdown scheduler thread cleanly when server process is killed
        if scheduler.running:
            scheduler.shutdown()

