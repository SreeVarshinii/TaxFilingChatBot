import chainlit as cl
from src.engine import TaxEngine

@cl.on_chat_start
async def on_chat_start():
    # Store the engine in user session
    engine = TaxEngine()
    cl.user_session.set("engine", engine)

    # Pre-Flight Questions for 5-Year Rule
    res_entry = await cl.AskUserMessage(
        content="Welcome to the F-1 Scholar Tax Navigator! To start, what was your initial date of entry into the U.S. on your F-1 visa? (Format: YYYY-MM-DD)",
        timeout=120
    ).send()
    
    if res_entry:
        engine.session_data["entry_date"] = res_entry["output"]
        
    res_income = await cl.AskUserMessage(
        content="Got it. What type of U.S. sourced income did you have in 2025? (e.g., W-2 wages, fellowship, 1042-S scholarship, None)",
        timeout=120
    ).send()

    if res_income:
        engine.session_data["income_type"] = res_income["output"]

    # Evaluate Residency
    is_exempt = engine.evaluate_5_year_rule()
    residency_status = "Nonresident Alien (Exempt Individual)" if is_exempt else "Resident Alien for Tax Purposes (or requires closer connection evaluation)"
    
    summary_msg = f"Based on your entry date, for 2025 you are likely considered a **{residency_status}**.\n\n"
    summary_msg += "You can now ask me any tax-related questions, and I will cite the exact 2025 IRS instructions!"
    
    await cl.Message(content=summary_msg).send()

@cl.on_message
async def on_message(message: cl.Message):
    engine: TaxEngine = cl.user_session.get("engine")
    
    # We create a message to stream explicitly
    msg = cl.Message(content="")
    await msg.send()
    
    # Call the retrieval chain
    # Note: To extract intermediate steps in Chainlit natively, we can use callbacks,
    # but the simplest way is to read the 'context' from the chain's dictionary return.
    response = engine.query(message.content)
    answer = response["answer"]
    context_docs = response.get("context", [])
    
    msg.content = answer
    
    # If chunks were retrieved, display them explicitly
    if context_docs:
        source_elements = []
        for i, doc in enumerate(context_docs):
            source_name = f"Source {i+1} ({doc.metadata.get('title', 'Unknown')})"
            text_excerpt = f"{doc.page_content}\n\n[Metadata: {doc.metadata}]"
            source_elements.append(
                cl.Text(name=source_name, content=text_excerpt, display="inline")
            )
        msg.elements = source_elements
    
    await msg.update()
