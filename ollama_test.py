import time
import ollama

model_name = "qwen2.5:0.5b"

# Define the messages for the chat
messages = [
    {"role": "user", "content": "Tell me a short story about a space-faring cat."}
]

# Record start time
start_time = time.time()

# Generate a response
response = ollama.chat(model=model_name, messages=messages)

# Record end time
end_time = time.time()

# Calculate processing time
processing_time = end_time - start_time

# Print the model's response
print("Response:")
print(response["message"]["content"])
print(f"\nProcessing Time: {processing_time:.2f} seconds")
