from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

client = OpenAI(
    base_url=os.getenv("BASE_URL"),
    api_key=os.getenv("API_KEY")
)
user_input = "What is Artificial Intelligence?"

response = client.chat.completions.create(
    model=os.getenv("MODEL"), 
    messages=[
        {"role": "user", "content": user_input}
    ]
)

print("Actual message:", response.choices[0].message.content)