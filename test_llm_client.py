from llm_client import LLMClient  # Import the LLMClient class

# Initialize the LLMClient
llm_client = LLMClient()

# Define test queries
test_queries = [
    "Make a playlist featuring both Drake and Travis Scott.",
    "I want a playlist of Bruno Mars’ top songs from 2021.",
    "Give me a playlist of chill lo-fi beats for concentration.",
    "Create a playlist of country songs with a modern twist."
]

# Loop through test queries and call the parse_user_input function
for query in test_queries:
    print(f"Testing query: '{query}'")
    
    # Call the parse_user_input method and capture the result
    extracted_info = llm_client.parse_user_input(query)
