import sys
from src.engine import TaxEngine

def main():
    if len(sys.argv) < 2:
        print("Usage: python ask.py \"Your tax question here\"")
        sys.exit(1)
        
    question = sys.argv[1]
    print("[*] Initializing F-1 Tax Engine...")
    
    try:
        engine = TaxEngine()
        # Mock the session data assuming a standard F-1 student arriving in 2020
        # (Since there is no GUI to prompt them)
        engine.session_data["entry_date"] = "2020-08-15" 
        engine.session_data["income_type"] = "w2"
        engine.evaluate_5_year_rule()
        
        print(f"\nQuestion: {question}")
        print("Retrieving answer...\n")
        
        response = engine.query(question)
        
        print("=== Answer ===")
        print(response.get("answer", "No answer generated."))
        
        print("\n=== Sources ===")
        if "context" in response:
            for i, doc in enumerate(response["context"]):
                title = doc.metadata.get('title', 'Unknown Source')
                form = doc.metadata.get('form_type', 'N/A')
                print(f"[{i+1}] {title} (Type: {form})")
                print(f"    Excerpt: {doc.page_content[:150]}...\n")
        else:
            print("No sources retrieved.")
            
    except Exception as e:
        print(f"\n[X] Error running engine: {e}")

if __name__ == "__main__":
    main()
