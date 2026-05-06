import gradio as gr
from src.engine import TaxEngine

# Initialize the engine
engine = TaxEngine()

def chat_function(message, history, entry_date):
    """
    Gradio chat function. 
    message: current user message
    history: previous conversation history
    entry_date: additional state/input from the user
    """
    # Use engine to query the LLM
    try:
        response = engine.query(message, entry_date_str=entry_date)
        
        answer = response["answer"]
        contexts = response.get("context", [])
        
        # Format the contexts as sources
        if contexts:
            source_text = "\n\n### Sources:\n"
            for i, ctx in enumerate(contexts):
                # The context is a string according to engine.py
                source_text += f"**Source {i+1}**:\n{ctx[:200]}...\n\n"
            answer += source_text
            
        return answer
    except Exception as e:
        return f"An error occurred: {str(e)}"

# Custom CSS for a better UI
custom_css = """
#component-0 { max-width: 800px; margin: auto; }
"""

with gr.Blocks(css=custom_css, title="F-1 Scholar Tax Navigator") as demo:
    gr.Markdown("# 🎓 F-1 Scholar Tax Navigator")
    gr.Markdown("A specialized Retrieval-Augmented Generation (RAG) system built to navigate the complexities of 2025 IRS tax regulations for international students on F-1, J-1, M-1, and Q-1 visas.")
    
    with gr.Accordion("Step 1: Determine Residency Status", open=True):
        gr.Markdown("To accurately assist you, please enter your initial date of entry into the U.S. on your F-1 visa.")
        entry_date_input = gr.Textbox(label="Entry Date (YYYY-MM-DD)", placeholder="e.g. 2021-08-15")
        status_output = gr.Markdown()
        
        def check_status(date_str):
            is_exempt = engine.evaluate_5_year_rule(date_str)
            status = "Nonresident Alien (Exempt Individual)" if is_exempt else "Resident Alien for Tax Purposes"
            return f"**Estimated Status for 2025**: {status}"
            
        entry_date_input.change(fn=check_status, inputs=entry_date_input, outputs=status_output)

    gr.Markdown("### Step 2: Ask Your Tax Question")
    chat_interface = gr.ChatInterface(
        fn=chat_function,
        additional_inputs=[entry_date_input]
    )

if __name__ == "__main__":
    demo.launch()
