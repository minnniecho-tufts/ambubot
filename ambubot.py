import os
import requests
from flask import Flask, request, jsonify
from llmproxy import generate, pdf_upload

app = Flask(__name__)

user_data = { }
user_step = { }

pdf_path = os.getenv("PDF_PATH", "HealingRemedies-compressed4mb.pdf")
session_id_ = os.getenv("SESSION_ID", "ambubot-home-remedies")

# Upload PDF if not uploaded
if "pdf_uploaded" not in app.config:
    response = pdf_upload(path=pdf_path, session_id=session_id_, strategy="smart")
    app.config["pdf_uploaded"] = True
    print(response)

def is_health_related(user_input):
    """Checks if a message is related to health concerns."""
    response = generate(
        model="4o-mini",
        system="""
            Determine if a user's message is health-related.
            Respond with only "Yes" or "No".
        """,
        query=f"User input: '{user_input}'",
        temperature=0.0,
        lastk=0,
        session_id="IntentCheck",
        rag_usage=False
    )
    return response.get("response", "").strip().lower() == "yes"

def analyze_symptoms(symptoms):
    """Provides home remedies based on symptoms."""
    response = generate(
        model="4o-mini",
        system="""
            Provide home remedies for given symptoms.
            If no remedy is found in the document, provide general self-care advice.
        """,
        query=f"Symptoms: {symptoms}. What home remedies can I try?",
        temperature=0.2,
        lastk=0,
        session_id=session_id_,
        rag_usage=True,
        rag_threshold=0.2,
        rag_k=3
    )
    return response.get("response", "⚠️ Sorry, I couldn't process your request.")

def ask_followup(symptoms):
    """Generates exactly 3 follow-up questions about symptoms."""
    response = generate(
        model="4o-mini",
        system="Generate exactly 3 follow-up questions about the provided symptom.",
        query=f"User symptoms: {symptoms}. What follow-up questions should I ask?",
        temperature=0.2,
        lastk=0,
        session_id="FollowUpBot",
        rag_usage=False
    )
    return response.get("response", "").split("\n")[:3]  # Ensure exactly 3 questions

def get_coordinates_from_location(location):
    """Converts a user-entered location to latitude and longitude."""
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={location}&format=json"
        headers = {"User-Agent": "AmbuBot/1.0"}
        response = requests.get(url, headers=headers, timeout=5)
        data = response.json()
        if data:
            return data[0]["lat"], data[0]["lon"]
        return None, None
    except Exception:
        return None, None

def find_nearest_hospitals_osm(location):
    """Finds nearby hospitals using OpenStreetMap."""
    lat, lon = get_coordinates_from_location(location)
    if not lat or not lon:
        return ["❌ Unable to find coordinates for the entered location."]

    overpass_query = f"""
    [out:json];
    (
      node["amenity"="hospital"](around:20000, {lat}, {lon});
    );
    out center;
    """
    try:
        response = requests.get("https://overpass-api.de/api/interpreter", params={"data": overpass_query})
        hospitals = response.json().get("elements", [])
        hospital_names = [h.get("tags", {}).get("name", "Unnamed Hospital") for h in hospitals]
        return [f"🏥 {h}" for h in hospital_names[:3]] if hospital_names else ["❌ No hospitals found nearby."]
    except Exception as e:
        return [f"⚠️ Error retrieving hospital data: {e}"]

@app.route('/query', methods=['POST'])
def main():
    """Handles conversation flow with proper step tracking."""
    data = request.get_json()
    user = data.get("user_name", "Unknown")
    message = data.get("text", "").strip()

    print(f"Message from {user}: {message}")

    # Ensure user step tracking exists
    if user not in user_step:
        user_step[user] = 0  # Initialize step
        user_data[user] = {"symptoms": "", "followups": [], "answers": []}

    print(f"User step: {user_step[user]}")

    ### **Step 0: Initial Greeting and Symptom Collection**
    if user_step[user] == 0:
        if not is_health_related(message):
            return jsonify({"text": "🏥 AMBUBOT - Virtual Healthcare Assistant \n 🔹 HELLO! I'm Dr. Doc Bot. Describe your symptoms, and I'll provide easy at-home remedies! \n 📝 Enter your symptoms below: "})
        
        # Store symptoms and generate follow-up questions
        user_data[user]["symptoms"] = message
        user_data[user]["followups"] = ask_followup(message)
        user_step[user] = 1  # Move to the follow-up phase

        return jsonify({"text": f"🤖 Follow-up question 1: {user_data[user]['followups'][0]}"})

    ### **Step 1-3: Handling Follow-Up Answers**
    if 1 <= user_step[user] <= 3:
        user_data[user]["answers"].append(message)  # Store user's answer

        if user_step[user] < 3:
            next_question = user_data[user]["followups"][user_step[user]]  # Get next question
            user_step[user] += 1  # Move to the next follow-up question
            return jsonify({"text": f"🤖 Follow-up question {user_step[user]}: {next_question}"})

        # **Step 4: Provide Remedy After Last Follow-Up**
        remedy = analyze_symptoms(" ".join([user_data[user]["symptoms"]] + user_data[user]["answers"]))

        # Reset conversation state after providing the remedy
        del user_data[user]  # Remove user conversation data
        del user_step[user]  # Remove user step tracking

        return jsonify({"text": f"🩺 {remedy}"})

    return jsonify({"text": "⚠️ Something went wrong. Please start over."})

# @app.route('/query', methods=['POST'])
# def main():
#     data = request.get_json()
#     user = data.get("user_name", "Unknown")
#     message = data.get("text", "").strip()

#     print(f"Message from {user}: {message}")

#     # Ignore bot messages and empty inputs
#     if data.get("bot") or not message:
#         return jsonify({"status": "ignored"})

#     # Check if the message is health-related
#     if not is_health_related(message):
#         return jsonify({"text": "🏥 AMBUBOT - Virtual Healthcare Assistant \n 🔹 HELLO! I'm Dr. Doc Bot. Describe your symptoms, and I'll provide easy at-home remedies! \n 📝 Enter your symptoms below: "})

#     ask_3 = True

#     if ask_3:
#         ask_3 = False 
#         # Ask follow-up questions
#         followup_questions = ask_followup(message)

#         if followup_questions:
#             return jsonify({"text": f"🤖 Follow-up questions:\n\n- " + "\n- ".join(followup_questions)})

#     remedy = analyze_symptoms(message, "unknown duration", "unknown severity")
#     return jsonify({"text": f"🩺 {remedy}"})

@app.route('/location', methods=['POST'])
def location_query():
    data = request.get_json()
    user_location = data.get("text", "").strip()

    if not user_location:
        return jsonify({"text": "⚠️ Please enter your location (City, State/Country)."})

    hospitals = find_nearest_hospitals_osm(user_location)
    return jsonify({"text": "\n".join(hospitals)})

@app.errorhandler(404)
def page_not_found(e):
    return "Not Found", 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)