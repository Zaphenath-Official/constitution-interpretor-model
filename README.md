
# ⚖️ Kenyan Legal Interpreter AI

A high-performance, locally optimized full-stack application that translates complex Kenyan Gazettes, Acts, and Case Law into plain-spoken, contextual English. 

Built using a hybrid architecture combining **Retrieval-Augmented Generation (RAG)** with a parameter-efficient, **fine-tuned Gemma-2-2B-it model** using **Unsloth (QLoRA)**.

---

## 🚀 Key Features
* **Zero-Hallucination Retrieval (RAG):** Uses `ChromaDB` as a semantic vector database to fetch exact, verified statutory text before generating explanations.
* **Domain-Specific Language Model:** Fine-tuned on a custom dataset of 1,500 Kenyan legal records using 4-bit quantization for fast local inference.
* **Async Python Backend:** Built with `FastAPI` for rapid data processing and streaming model responses.
* **Modern UI:** Responsive `React` dashboard built with Tailwind CSS.

---

## 🏗️ System Architecture & Data Flow

1. **User Query:** User inputs a legal question (e.g., *"What does Section 3 of the Land Act mean for tenant rights?"*).
2. **Vector Retrieval (RAG):** The query is vectorized and matched against the local `ChromaDB` legal corpus.
3. **Context Assembly:** The raw, verified legal sections retrieved are injected into the prompt context.
4. **Fine-Tuned LLM Inference:** The query + context is passed to the fine-tuned `Gemma-2-2B-it` model, which explains the legal jargon in plain terms.
5. **UI Stream:** The explanation streams back to the React frontend.

---

## 🧠 ML & Fine-Tuning Pipeline
* **Base Model:** `unsloth/gemma-2-2b-it-bnb-4bit` (4-bit quantized to run efficiently on limited VRAM).
* **Dataset:** 1,500 custom-curated rows containing Kenyan Gazettes, Case Law, and local legislations.
* **Method:** Parameter-Efficient Fine-Tuning (PEFT/QLoRA) optimized via **Unsloth** to target $W_q, W_k, W_v, W_o$ projection gates.
* **Training Platform:** PyTorch / Torch.

---

## 🛠️ Tech Stack & Dependencies

* **Frontend:** React, Tailwind CSS, Lucide Icons, Axios
* **Backend:** FastAPI, Python 3.10+, Uvicorn
* **Database & Vectors:** ChromaDB, Supabase (for system logs)
* **ML Library:** Unsloth, PyTorch, Transformers

---

## ⚙️ Quick Start

### 1. Backend Setup
```bash
# Clone the repository
git clone [https://github.com/yourusername/kenyan-legal-ai.git](https://github.com/yourusername/kenyan-legal-ai.git)
cd kenyan-legal-ai/backend

# Create virtual environment & install dependencies
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
pip install -r requirements.txt

# Run the FastAPI server
uvicorn main:app --reload
