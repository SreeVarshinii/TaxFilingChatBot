import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))

# Iterate over all available models and print their IDs
for model in client.models.list():
    # Check if the model is an embedding model (e.g., contains 'embedding' in the name)
    if 'embedding' in model.name:
        print(model.name)
