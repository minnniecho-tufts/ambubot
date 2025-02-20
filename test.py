# import requests

# # Define the base URL
# BASE_URL = "https://interim-cherise-minnie-1dd97906.koyeb.app/query"

# # # Test if the web application is running
# # response_main = requests.get(BASE_URL)
# # print('Web Application Response:\n', response_main.text, '\n\n')

# # Test the LLMProxy endpoint with a health query
# data = {"text": "hi"}
# response_llmproxy = requests.post(f"{BASE_URL}/query", json=data)
# print('LLMProxy Response:\n', response_llmproxy.text)
import requests

# Define the base URL of your deployed Koyeb app
BASE_URL = "https://interim-cherise-minnie-1dd97906.koyeb.app"

# Function to test if the application is running
def check_server():
    try:
        response = requests.get(BASE_URL)
        if response.status_code == 200:
            print("✅ Server is running.")
        else:
            print(f"⚠️ Unexpected response from server: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Server check failed: {e}")

# Function to test the query endpoint
def test_query(text):
    data = {"text": text}
    try:
        response = requests.post(f"{BASE_URL}/query", json=data)
        print(f"🔹 Input: {text}")
        print(f"🔹 Response: {response.json()}\n")
    except requests.exceptions.RequestException as e:
        print(f"❌ Query request failed: {e}")

# Run tests
if __name__ == "__main__":
    check_server()  # Ensure server is running
    test_query("hi")  # First query
    test_query("I have a headache")  # Symptom input
    test_query("Two days ago")  # Follow-up 1
    test_query("It’s dull")  # Follow-up 2
    test_query("No nausea")  # Follow-up 3
