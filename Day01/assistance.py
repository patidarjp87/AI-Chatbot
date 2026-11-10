from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

client = OpenAI(
    base_url=os.getenv("BASE_URL"),
    api_key=os.getenv("API_KEY")
)
while True:
    user_input = input("You: ")
    if user_input.lower() == "exit":
        print("Exiting the chat. Goodbye!")
        break
    response = client.chat.completions.create(
        model=os.getenv("MODEL"), 
        messages=[
            {"role": "user", "content": user_input}
        ],
    reasoning_effort="none",
    max_tokens=150
    )
    
    print("Actual message:", response.choices[0].message.content)