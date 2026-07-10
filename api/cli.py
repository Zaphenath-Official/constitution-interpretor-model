import sys
import json
import requests

def ask_legal_ai_terminal():
    # Production configurations mapping to your local Flask instance
    backend_url = "http://127.0.0.1:5000"
    
    print("=" * 80)
    print("⚖️ KENYAN LEGAL INTERPRETER AI — TERMINAL INTERACTIVE INTERFACE")
    print("=" * 80)
    print("Type your legal questions below. Type 'exit' or 'quit' to close the session.\n")
    
    while True:
        try:
            # 1. Capture user terminal input prompt
            question = input("\n👤 YOU: ").strip()
            
            if not question:
                continue
                
            if question.lower() in ["exit", "quit"]:
                print("\n👋 Closing legal interpreter terminal session. Goodbye!")
                break
                
            # 2. Package request body payload
            payload = {
                "question": question,
                "top_k": 3
            }
            
            print("\n🤖 AI INTERPRETER: ", end="")
            sys.stdout.flush() # Force terminal buffer to print the header immediately
            
            # 3. Request connection stream over the wire
            # Setting stream=True allows python to read incoming data byte by byte
            response = requests.post(backend_url, json=payload, stream=True, timeout=60)
            response.raise_for_status()
            
            # 4. Read incoming HTTP chunks as they land in memory
            # Decode using utf-8 to piece character bytes back into words instantly
            for chunk in response.iter_content(chunk_size=128, decode_unicode=True):
                if chunk:
                    # Print out tokens on the same line without arbitrary spaces or tabs
                    sys.stdout.write(chunk)
                    sys.stdout.flush()
                    
            print("\n" + "_" * 80) # Line break helper separating query turns
            
        except requests.exceptions.ConnectionError:
            print("\n❌ Error: Failed to connect to the backend server. Is your Flask API running on port 5000?")
        except KeyboardInterrupt:
            print("\n\n👋 Session interrupted via keyboard shortcut. Exiting.")
            break
        except Exception as e:
            print(f"\n❌ An unexpected error occurred: {e}")

if __name__ == "__main__":
    ask_legal_ai_terminal()
