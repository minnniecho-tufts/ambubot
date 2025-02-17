import requests
from llmproxy import generate  # LLM API for symptom analysis

# Get User's Location (Free)
def get_user_location():
    """Fetches the user's approximate location based on IP address."""
    try:
        response = requests.get("https://ipinfo.io/json")
        data = response.json()
        loc = data.get("loc", "")  # Example: "42.4184,-71.1062"

        if not loc:
            return None, "Could not determine location. Please enter manually."
        
        return loc, f"📍 Detected your location: {data.get('city')}, {data.get('region')}, {data.get('country')}"

    except Exception as e:
        return None, f"Error retrieving location: {e}"

# Find Nearby Hospitals (OpenStreetMap)
def find_nearest_hospitals_osm(location):
    """Fetches hospitals within a 20km radius using OpenStreetMap Overpass API and filters out children's & mental health hospitals."""
    lat, lon = location.split(",")

    overpass_query = f"""
    [out:json];
    (
      node["amenity"="hospital"](around:20000, {lat}, {lon});
      node["healthcare"="hospital"](around:20000, {lat}, {lon});
      node["building"="hospital"](around:20000, {lat}, {lon});
      node["urgent_care"="yes"](around:20000, {lat}, {lon});
    );
    out center;
    """
    overpass_url = "https://overpass-api.de/api/interpreter"

    try:
        response = requests.get(overpass_url, params={"data": overpass_query})
        hospitals = response.json().get("elements", [])

        if not hospitals:
            return "❌ No hospitals found nearby. Please call emergency services."

        # **Exclude Children's & Mental Health hospitals**
        excluded_keywords = ["child", "pediatric", "mental", "psychiatric", "rehabilitation"]

        hospital_list = "\n🏥 **Top 3 Nearby General Hospitals:**\n"
        filtered_hospitals = []

        for hospital in hospitals:
            name = hospital.get("tags", {}).get("name", "Unnamed Hospital")

            # ✅ Convert name to lowercase before checking exclusions
            name_lower = name.lower()

            # **Exclude hospitals containing unwanted keywords**
            if any(exclude in name_lower for exclude in excluded_keywords):
                continue  

            filtered_hospitals.append(name)

            if len(filtered_hospitals) == 3:  # Stop after 3 valid hospitals
                break

        if not filtered_hospitals:
            return "❌ No general hospitals found nearby. Please call emergency services."

        for i, name in enumerate(filtered_hospitals):
            hospital_list += f"{i+1}. **{name}**\n"

        return hospital_list

    except Exception as e:
        return f"⚠️ Error retrieving hospital data from OpenStreetMap: {e}"

def is_health_related(user_input):
    """Uses LLM to determine if the user's input is health-related."""
    response = generate(
        model="4o-mini",
        system="""
            You are an AI that classifies whether a user's input is related to health concerns.
            - If the input describes symptoms, medical conditions, or requests medical advice, respond with "Yes".
            - If the input is unrelated (e.g., asking about weather, sports, school, jokes), respond with "No".
            - Only return "Yes" or "No" with no extra words.
        """,
        query=f"User input: '{user_input}'. Is this related to health concerns?",
        temperature=0.0,
        lastk=0,
        session_id="IntentCheck"
    )
    
    return response.strip().lower() == "yes"  # Ensures it only returns True for health-related inputs

# Use LLM to Analyze Symptoms & Provide Treatment Advice
def analyze_symptoms(symptoms, duration, severity):
    """Uses an LLM to generate a response with symptom analysis and treatment suggestions."""
    response = generate(
        model="4o-mini",
        system="""
            You are a virtual healthcare assistant. 
            - Your job is to analyze symptoms and suggest treatment steps.
            - If symptoms are mild, recommend home remedies or self-care.
            - If symptoms are moderate, suggest over-the-counter medications or when to see a doctor.
            - If symptoms are severe, recommend immediate medical attention.
            - Provide clear, step-by-step instructions on how to manage the symptoms before visiting a hospital.
            - Keep responses **concise**, **easy to understand**, and **helpful**.
        """,
        query=f"My symptoms are: {symptoms}. Duration: {duration}. Severity: {severity}/10. What should I do?",
        temperature=0.2,
        lastk=0,
        session_id="HealthcareChat"
    )

    return response

def gather_symptom_details():
    """Conversationally gathers symptom details with LLM filtering for relevance."""
    
    while True:
        symptoms = input("🩺 What symptoms are you experiencing? (e.g., headache, fever, nausea, chest pain): ").strip()

        # **Step 1: Ensure input is health-related**
        if not is_health_related(symptoms):
            print("⚠️ I'm here to assist with **health-related concerns only**. Please describe any symptoms you're experiencing.")
            continue  # Re-prompt user for valid input

        # **Step 2: Follow-up questions for relevant symptoms**
        follow_up_questions = {
            "cough": "Do you have a fever along with your cough? (yes/no): ",
            "fever": "Do you also have chills or body aches? (yes/no): ",
            "nausea": "Have you vomited or felt dizzy? (yes/no): ",
            "headache": "Is the headache severe and persistent? (yes/no): ",
            "pain": "Where exactly is the pain? (e.g., chest, stomach, back, joint): ",
            "fatigue": "Are you also feeling weak or dizzy? (yes/no): ",
            "cold": "Do you have congestion or a sore throat? (yes/no): ",
            "vomiting": "Have you had trouble keeping food down? (yes/no): ",
            "dizziness": "Do you feel lightheaded or have trouble balancing? (yes/no): ",
            "shortness of breath": "Is the shortness of breath sudden or getting worse? (yes/no): ",
            "stomachache": "Have you also had nausea, vomiting, or diarrhea? (yes/no): "
        }

        collected_details = {}
        matched = False

        # **Step 3: Ask follow-up questions based on detected symptoms**
        for keyword, question in follow_up_questions.items():
            if keyword in symptoms.lower():
                follow_up = input(question).strip().lower()
                collected_details[keyword] = follow_up
                matched = True

        # **Step 4: If no known symptoms detected, ask for more details**
        if not matched:
            general_followup = input("Can you describe your symptoms in more detail? (e.g., where is the pain, any other discomfort?): ").strip()
            symptoms += f" | Additional details: {general_followup}"

        # **Step 5: Combine user input with follow-up responses**
        for symptom, response in collected_details.items():
            symptoms += f" | {symptom} follow-up: {response}"

        return symptoms  # Return validated symptom description

# Chatbot Interaction
if __name__ == '__main__':
    print("Welcome to AMBUBOT")
    print("DR. Doc Bot is here to assist you!")
    print("Type 'bye' to exit.\n")

    while True:
        # Step 1: Conversational Symptom Collection
        symptoms = gather_symptom_details()
        
        if symptoms.lower() in ['bye']:
            print("Thank you for using the Healthcare Assistant Chatbot. Take care!")
            break

        # Step 2: Ask for additional clarifying details
        duration = input("📅 Step 2: How long have you had these symptoms? (e.g., 1 day, 3 days, 1 week): ")
        severity = input("⚖️ Step 3: On a scale of 1-10, how severe are your symptoms? (1 = mild, 10 = severe): ")
        
        try:
            severity = int(severity)
            if severity < 1 or severity > 10:
                print("Please enter a number between 1 and 10.")
                continue
        except ValueError:
            print("Invalid input. Please enter a number between 1 and 10.")
            continue
        
        # Step 3: Analyze Symptoms and Provide Treatment Steps
        print("\n🧠 **Analyzing Symptoms & Providing Treatment Advice...**\n")
        treatment_advice = analyze_symptoms(symptoms, duration, severity)
        print(treatment_advice)

        # Step 4: If needed, Find Nearby Hospitals
        if severity >= 1 or "chest pain" in symptoms.lower() or "difficulty breathing" in symptoms.lower():
            location, location_message = get_user_location()
            print("\n" + location_message)
            
            if location:
                hospital_list = find_nearest_hospitals_osm(location)
                print("\n" + hospital_list + "\n")
            else:
                print("❌ Please enter a valid location next time.\n")


# import requests
# import webbrowser

# # Use ipinfo.io to get user's approximate location (FREE)
# def get_user_location():
#     """Fetches the user's approximate location based on IP address."""
#     try:
#         response = requests.get("https://ipinfo.io/json")
#         data = response.json()
#         location = data.get("loc", "")  # Example: "40.7128,-74.0060"
        
#         if not location:
#             return None, "Could not determine location. Please enter manually."
        
#         return location, f"Detected your location: {data.get('city')}, {data.get('region')}, {data.get('country')}"

#     except Exception as e:
#         return None, f"Error retrieving location: {e}"

# # Open Waze for Hospital Search
# def open_waze_for_hospitals(location):
#     """Opens Waze to search for the nearest hospital based on detected location."""
#     if location:
#         waze_url = f"https://www.waze.com/ul?ll={location}&q=hospital&navigate=yes"
#         webbrowser.open(waze_url)
#         return f"Waze is opening with hospital directions near {location}!"
#     return "Could not determine location. Please try again."

# if __name__ == '__main__':
#     print("Welcome to the Healthcare Assistant Chatbot!")
#     print("Type 'bye' to exit.\n")

#     while True:
#         # Step 1: Ask for symptoms
#         symptoms = input("Step 1: What symptoms are you experiencing? (e.g., headache, fever, nausea): ")
        
#         if symptoms.lower() in ['bye']:
#             print("Thank you for using the Healthcare Assistant Chatbot. Take care!")
#             break

#         # Step 2: Ask for additional clarifying details
#         duration = input("Step 2: How long have you had these symptoms? (e.g., 1 day, 3 days, 1 week): ")
#         severity = input("Step 3: On a scale of 1-10, how severe are your symptoms? (1 = mild, 10 = severe): ")
        
#         try:
#             severity = int(severity)
#             if severity < 1 or severity > 10:
#                 print("Please enter a number between 1 and 10.")
#                 continue
#         except ValueError:
#             print("Invalid input. Please enter a number between 1 and 10.")
#             continue
        
#         # Step 3: Use LLM to analyze symptoms
#         print("\nAnalyzing symptoms...\n")
        
#         # Step 4: Determine if hospital lookup is needed
#         if severity >= 6 or "chest pain" in symptoms.lower() or "difficulty breathing" in symptoms.lower():
#             # Get user's approximate location (FREE)
#             location, location_message = get_user_location()
#             print("\n" + location_message)
            
#             # Open Waze for hospital directions
#             hospital_message = open_waze_for_hospitals(location)
#             print("\n" + hospital_message)

# # import requests
# # from llmproxy import generate

# # # API Keys (Replace with your actual keys)
# # GOOGLE_MAPS_API_KEY = "your_google_maps_api_key"

# # GEOCODING_API_URL = "https://maps.googleapis.com/maps/api/geocode/json"
# # PLACES_API_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"

# # def get_coordinates_from_place(place_name):
# #     """Converts a place name (e.g., 'Tufts University') into latitude and longitude."""
# #     params = {"address": place_name, "key": GOOGLE_MAPS_API_KEY}

# #     try:
# #         response = requests.get(GEOCODING_API_URL, params=params)
# #         data = response.json()

# #         print("Geocoding API Response:", data)  # DEBUGGING OUTPUT

# #         if data["status"] == "OK":
# #             location = data["results"][0]["geometry"]["location"]
# #             lat, lng = location["lat"], location["lng"]
# #             return f"{lat},{lng}", f"Detected location for {place_name}: {lat}, {lng}"
# #         else:
# #             return None, f"Error: {data.get('status')}. Could not determine location."

# #     except Exception as e:
# #         return None, f"Error retrieving location: {e}"

# # def find_nearest_hospital(user_location):
# #     """Fetches the nearest hospital based on location (lat,lng)."""
# #     params = {
# #         "location": user_location,
# #         "radius": 5000,  # 5km search radius
# #         "type": "hospital",
# #         "key": GOOGLE_MAPS_API_KEY
# #     }

# #     try:
# #         response = requests.get(PLACES_API_URL, params=params)
# #         data = response.json()

# #         print("Places API Response:", data)  # DEBUGGING OUTPUT

# #         hospitals = data.get("results", [])
        
# #         if not hospitals:
# #             return "No hospitals found nearby. Please call emergency services."

# #         nearest_hospital = hospitals[0]
# #         return f"Nearest hospital: {nearest_hospital['name']}, Address: {nearest_hospital['vicinity']}"
    
# #     except Exception as e:
# #         return f"Error retrieving hospital data: {e}"

# # if __name__ == '__main__':
# #     print("Welcome to the Healthcare Assistant Chatbot!")
# #     print("Type 'bye' to exit.\n")

# #     while True:
# #         # Step 1: Ask for symptoms
# #         symptoms = input("Step 1: What symptoms are you experiencing? (e.g., headache, fever, nausea): ")
        
# #         if symptoms.lower() in ['bye']:
# #             print("Thank you for using the Healthcare Assistant Chatbot. Take care!")
# #             break

# #         # Step 2: Ask for additional clarifying details
# #         duration = input("Step 2: How long have you had these symptoms? (e.g., 1 day, 3 days, 1 week): ")
# #         severity = input("Step 3: On a scale of 1-10, how severe are your symptoms? (1 = mild, 10 = severe): ")
        
# #         try:
# #             severity = int(severity)
# #             if severity < 1 or severity > 10:
# #                 print("Please enter a number between 1 and 10.")
# #                 continue
# #         except ValueError:
# #             print("Invalid input. Please enter a number between 1 and 10.")
# #             continue
        
# #         # Step 3: Use LLM to analyze symptoms
# #         symptom_analysis = generate(
# #             model='4o-mini',
# #             system='''
# #                 You are a healthcare assistant chatbot.
# #                 - Ask clarifying questions before making recommendations.
# #                 - If symptoms are mild, suggest home remedies or monitoring.
# #                 - If symptoms are moderate, advise the user on when to see a doctor.
# #                 - If symptoms are severe, recommend seeking urgent medical care.
# #                 - If symptoms indicate a medical emergency (e.g., chest pain, difficulty breathing), direct the user to the nearest hospital.
# #                 - Be polite and empathetic.
# #                 - Provide recommendations in bullet points.
# #             ''',
# #             query=f"User symptoms: {symptoms}, Duration: {duration}, Severity: {severity}/10. What should they do?",
# #             temperature=0.0,
# #             lastk=0,
# #             session_id='GenericSession'
# #         )

# #         print("\nChatbot Response:")
# #         print(symptom_analysis)
# #         print("\n")

# #         # Step 4: Determine if hospital lookup is needed
# #         if severity >= 8 or "chest pain" in symptoms.lower() or "difficulty breathing" in symptoms.lower():
# #             # Ask for user's place name instead of latitude/longitude
# #             place_name = input("Step 4: Please enter your location (e.g., 'Tufts University', 'Harvard', 'MIT'): ")
# #             location, location_message = get_coordinates_from_place(place_name)
            
# #             print("\n" + location_message)
            
# #             if location:
# #                 hospital_info = find_nearest_hospital(location)
# #                 print("\nHospital Recommendation:")
# #                 print(hospital_info)
# #                 print("\n")
# #             else:
# #                 print("Please enter a valid location next time.\n")

# # # import requests
# # # from llmproxy import generate

# # # # API Keys (Replace with your actual keys)
# # # GOOGLE_MAPS_API_KEY = "your_google_maps_api_key"

# # # GEOCODING_API_URL = "https://maps.googleapis.com/maps/api/geocode/json"
# # # PLACES_API_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"

# # # def get_coordinates_from_place(place_name):
# # #     """Converts a place name (e.g., 'Tufts University') into latitude and longitude."""
# # #     params = {"address": place_name, "key": GOOGLE_MAPS_API_KEY}

# # #     try:
# # #         response = requests.get(GEOCODING_API_URL, params=params)
# # #         data = response.json()

# # #         if data["status"] == "OK":
# # #             location = data["results"][0]["geometry"]["location"]
# # #             lat, lng = location["lat"], location["lng"]
# # #             return f"{lat},{lng}", f"Detected location for {place_name}: {lat}, {lng}"
# # #         else:
# # #             return None, "Could not determine location. Please enter a different place name."
    
# # #     except Exception as e:
# # #         return None, f"Error retrieving location: {e}"

# # # def find_nearest_hospital(user_location):
# # #     """Fetches the nearest hospital based on location (lat,lng)."""
# # #     params = {
# # #         "location": user_location,
# # #         "radius": 5000,  # 5km search radius
# # #         "type": "hospital",
# # #         "key": GOOGLE_MAPS_API_KEY
# # #     }

# # #     try:
# # #         response = requests.get(PLACES_API_URL, params=params)
# # #         data = response.json()
# # #         hospitals = data.get("results", [])
        
# # #         if not hospitals:
# # #             return "No hospitals found nearby. Please call emergency services."

# # #         nearest_hospital = hospitals[0]
# # #         return f"Nearest hospital: {nearest_hospital['name']}, Address: {nearest_hospital['vicinity']}"
    
# # #     except Exception as e:
# # #         return f"Error retrieving hospital data: {e}"

# # # if __name__ == '__main__':
# # #     print("Welcome to the Healthcare Assistant Chatbot!")
# # #     print("Type 'bye' to exit.\n")

# # #     while True:
# # #         # Step 1: Ask for symptoms
# # #         symptoms = input("Step 1: What symptoms are you experiencing? (e.g., headache, fever, nausea): ")
        
# # #         if symptoms.lower() in ['bye']:
# # #             print("Thank you for using the Healthcare Assistant Chatbot. Take care!")
# # #             break

# # #         # Step 2: Ask for additional clarifying details
# # #         duration = input("Step 2: How long have you had these symptoms? (e.g., 1 day, 3 days, 1 week): ")
# # #         severity = input("Step 3: On a scale of 1-10, how severe are your symptoms? (1 = mild, 10 = severe): ")
        
# # #         try:
# # #             severity = int(severity)
# # #             if severity < 1 or severity > 10:
# # #                 print("Please enter a number between 1 and 10.")
# # #                 continue
# # #         except ValueError:
# # #             print("Invalid input. Please enter a number between 1 and 10.")
# # #             continue
        
# # #         # Step 3: Use LLM to analyze symptoms
# # #         symptom_analysis = generate(
# # #             model='4o-mini',
# # #             system='''
# # #                 You are a healthcare assistant chatbot.
# # #                 - Ask clarifying questions before making recommendations.
# # #                 - If symptoms are mild, suggest home remedies or monitoring.
# # #                 - If symptoms are moderate, advise the user on when to see a doctor.
# # #                 - If symptoms are severe, recommend seeking urgent medical care.
# # #                 - If symptoms indicate a medical emergency (e.g., chest pain, difficulty breathing), direct the user to the nearest hospital.
# # #                 - Be polite and empathetic.
# # #                 - Provide recommendations in bullet points.
# # #             ''',
# # #             query=f"User symptoms: {symptoms}, Duration: {duration}, Severity: {severity}/10. What should they do?",
# # #             temperature=0.0,
# # #             lastk=0,
# # #             session_id='GenericSession'
# # #         )

# # #         print("\nChatbot Response:")
# # #         print(symptom_analysis)
# # #         print("\n")

# # #         # Step 4: Determine if hospital lookup is needed
# # #         if severity >= 8 or "chest pain" in symptoms.lower() or "difficulty breathing" in symptoms.lower():
# # #             # Ask for user's place name instead of latitude/longitude
# # #             place_name = input("Step 4: Please enter your location (e.g., 'Tufts University', 'Harvard', 'MIT'): ")
# # #             location, location_message = get_coordinates_from_place(place_name)
            
# # #             print("\n" + location_message)
            
# # #             if location:
# # #                 hospital_info = find_nearest_hospital(location)
# # #                 print("\nHospital Recommendation:")
# # #                 print(hospital_info)
# # #                 print("\n")
# # #             else:
# # #                 print("Please enter a valid location next time.\n")


# # # # import requests
# # # # from llmproxy import generate

# # # # # Google Maps API Key (Replace with your actual key)
# # # # GOOGLE_MAPS_API_KEY = "your_google_maps_api_key"
# # # # PLACES_API_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"

# # # # def find_nearest_hospital(user_location):
# # # #     """Fetches the nearest hospital based on the user's latitude, longitude."""
# # # #     params = {
# # # #         "location": user_location,
# # # #         "radius": 5000,  # 5km search radius
# # # #         "type": "hospital",
# # # #         "key": GOOGLE_MAPS_API_KEY
# # # #     }
# # # #     try:
# # # #         response = requests.get(PLACES_API_URL, params=params)
# # # #         data = response.json()
# # # #         hospitals = data.get("results", [])
        
# # # #         if not hospitals:
# # # #             return "No hospitals found nearby. Please call emergency services."

# # # #         nearest_hospital = hospitals[0]
# # # #         return f"Nearest hospital: {nearest_hospital['name']}, Address: {nearest_hospital['vicinity']}"
    
# # # #     except Exception as e:
# # # #         return f"Error retrieving hospital data: {e}"

# # # # if __name__ == '__main__':
# # # #     print("Welcome to the Healthcare Assistant Chatbot!")
# # # #     print("Type 'bye' to exit.\n")

# # # #     while True:
# # # #         # Step 1: Ask for symptoms
# # # #         symptoms = input("Step 1: What symptoms are you experiencing? (e.g., headache, fever, nausea): ")
        
# # # #         if symptoms.lower() in ['bye']:
# # # #             print("Thank you for using the Healthcare Assistant Chatbot. Take care!")
# # # #             break

# # # #         # Step 2: Ask for additional clarifying details
# # # #         duration = input("Step 2: How long have you had these symptoms? (e.g., 1 day, 3 days, 1 week): ")
# # # #         severity = input("Step 3: On a scale of 1-10, how severe are your symptoms? (1 = mild, 10 = severe): ")
        
# # # #         try:
# # # #             severity = int(severity)
# # # #             if severity < 1 or severity > 10:
# # # #                 print("Please enter a number between 1 and 10.")
# # # #                 continue
# # # #         except ValueError:
# # # #             print("Invalid input. Please enter a number between 1 and 10.")
# # # #             continue
        
# # # #         # Step 3: Use LLM to analyze symptoms
# # # #         symptom_analysis = generate(
# # # #             model='4o-mini',
# # # #             system='''
# # # #                 You are a healthcare assistant chatbot.
# # # #                 - Ask clarifying questions before making recommendations.
# # # #                 - If symptoms are mild, suggest home remedies or monitoring.
# # # #                 - If symptoms are moderate, advise the user on when to see a doctor.
# # # #                 - If symptoms are severe, recommend seeking urgent medical care.
# # # #                 - If symptoms indicate a medical emergency (e.g., chest pain, difficulty breathing), direct the user to the nearest hospital.
# # # #                 - Be polite and empathetic.
# # # #                 - Provide recommendations in bullet points.
# # # #             ''',
# # # #             query=f"User symptoms: {symptoms}, Duration: {duration}, Severity: {severity}/10. What should they do?",
# # # #             temperature=0.0,
# # # #             lastk=0,
# # # #             session_id='GenericSession'
# # # #         )

# # # #         print("\nChatbot Response:")
# # # #         print(symptom_analysis)
# # # #         print("\n")

# # # #         # Step 4: Determine if hospital lookup is needed
# # # #         if severity >= 8 or "chest pain" in symptoms.lower() or "difficulty breathing" in symptoms.lower():
# # # #             user_location = input("Step 4: Please enter your location (latitude,longitude) so I can find the nearest hospital: ")
# # # #             hospital_info = find_nearest_hospital(user_location)
# # # #             print("\nHospital Recommendation:")
# # # #             print(hospital_info)
# # # #             print("\n")


# # # # # from llmproxy import generate

# # # # # #models (anthropic.claude-3-haiku-20240307-v1:0) (4o-mini) (azure-phi3)

# # # # # # if __name__ == '__main__':
# # # # # #     response = generate(model = '4o-mini',
# # # # # #         system = 'Answer my question',
# # # # # #         query = 'plan a trip to greece for me',
# # # # # #         temperature=0.0,
# # # # # #         lastk=0,
# # # # # #         session_id='GenericSession')

# # # # # #     print(response)

# # # # # # high level goal: to be able to immediatley advise patients in need depending on 
# # # # # # their symptoms 
# # # # # # 
# # # # # if __name__ == '__main__':
# # # # #     print("Welcome to the Healthcare Assistant Chatbot!")
# # # # #     print("Type 'bye' to end the conversation.\n")
    
# # # # #     while True:
# # # # #         # Prompt the user for input
# # # # #         user_query = input("You: ")
        
# # # # #         # Check if the user wants to exit
# # # # #         if user_query.lower() in ['bye']:
# # # # #             print("Thank you for using the Healthcare Assistant Chatbot. Take care!")
# # # # #             break
        
# # # # #         # Generate a response based on the input
# # # # #         response = generate (
# # # # #             model='4o-mini',
# # # # #             system= '''
# # # # #                 You are a healthcare assistant chatbot. 
# # # # #                 - Your job is to assess symptoms provided by the user and suggest actionable next steps.
# # # # #                 - If symptoms are mild, suggest home remedies or monitoring.
# # # # #                 - If symptoms are severe, recommend consulting a doctor.
# # # # #                 - Do not provide a diagnosis or answer unrelated questions.
# # # # #                 - If the user input is unclear, ask clarifying questions.
# # # # #                 - Ask the user for their details if it will help with treatment reccomendations
# # # # #                 - put the reccomendations in bullet point form
# # # # #                 - Be nice! 
# # # # #                 - Respond briefly and in simple language that is easy to understand.
# # # # #                 ''',
# # # # #             query=user_query,
# # # # #             temperature=0.0,
# # # # #             lastk=0,
# # # # #             session_id='GenericSession'
# # # # #         )
        
# # # # #         # Print the chatbot's response
# # # # #         print("\nChatbot Response:")
# # # # #         print(response)
# # # # #         print("\n")


# # # # # #quetions that model preform the same 
# # # # # # '1 + 1'
# # # # # # all models produced 2, claude gave a short answer, azure gave long explanations, 
# # # # # # mini gave the shortest answer

# # # # # #quetions that model preform different  
# # # # # # 'how many letter-r does the word strawberry have'
# # # # # # azure-phi3 did some complicated math 
# # # # # # 'plan a trip to greece for me'
# # # # # # - not good: azure gave me step bullet points but didnt plan anything for me 
# # # # # # - good: claude gave me an itenerary by day, quite detailed
# # # # # # - very good: 4o-mini gave by day itinerary with morning, afternoon, and evening plans 

# # # # # # try use streamlit 

# # # # # # come up with a simple scenario in healthcare and write a program 
# # # # # # pick a use case and build a prgram for it use prompt engineering