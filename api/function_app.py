import azure.functions as func
import logging
import json
import sys
import os

from engine import TaxEngine

app = func.FunctionApp()

# Create a single global instance of the engine to reuse across invocations.
try:
    engine = TaxEngine()
except Exception as e:
    logging.error(f"Failed to initialize TaxEngine: {e}")
    engine = None

@app.route(route="chat", auth_level=func.AuthLevel.ANONYMOUS, methods=["POST"])
def chat(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')
    
    if engine is None:
        return func.HttpResponse(
            "Server misconfigured: Engine failed to initialize. Check API keys.", 
            status_code=500
        )
        
    try:
        req_body = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON payload", status_code=400)
        
    question = req_body.get('question')
    entry_date = req_body.get('entry_date')
    income_type = req_body.get('income_type')
    
    if not question:
        return func.HttpResponse("Please pass a 'question' parameter", status_code=400)
        
    # Evaluate Residency
    is_exempt = engine.evaluate_5_year_rule(entry_date) if entry_date else False
    
    # Contextualize query with residency status if entry_date was provided
    if entry_date:
        residency_str = ("a Nonresident Alien (Exempt Individual)" 
                         if is_exempt else "a Resident Alien for Tax Purposes")
        full_query = f"[User context: I am likely {residency_str}]. {question}"
    else:
        full_query = question

    # Get answer from LangChain
    try:
        response = engine.query(full_query)
        answer = response["answer"]
        
        # Format the context for the frontend
        context_data = []
        if "context" in response:
            for i, text in enumerate(response["context"]):
                context_data.append({
                    "id": i + 1,
                    "content": text,
                    "metadata": {}
                })
                
        return func.HttpResponse(
            json.dumps({
                "answer": answer,
                "context": context_data,
                "is_exempt": is_exempt
            }),
            mimetype="application/json"
        )
    except Exception as e:
        logging.error(f"Error querying engine: {e}")
        return func.HttpResponse(f"Error processing query: {str(e)}", status_code=500)
