from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

client = OpenAI(
    base_url=os.getenv("BASE_URL"),
    api_key=os.getenv("API_KEY")
)

response = client.chat.completions.create(
    model=os.getenv("MODEL"), 
    messages=[
        {"role": "user", "content": "What is Artificial Intelligence?"}
    ]
)

# print("Generated message:", response.output_text)

# print("#" * 20)

print("Actual message:", response.choices[0].message.content)