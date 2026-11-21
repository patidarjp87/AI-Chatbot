"""list_models.py - Prints the Gemini models your API key is allowed to use.

Run from the project root:  python scripts/list_models.py
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

# Read the key from the .env file in the project root
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
for model in client.models.list():
    actions = getattr(model, "supported_actions", None) or []
    if "generateContent" in actions:  # only models that can write text
        print(model.name)