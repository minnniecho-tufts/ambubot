import os
import requests
from flask import Flask, request, jsonify, session
from llmproxy import generate, pdf_upload

app = Flask(__name__)

# Load environment variables
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

def analyze_symptoms(symptoms, duration, severity):
    """Provides home remedies based on symptoms."""
    response = generate(
        model="4o-mini",
        system="""
            Provide home remedies for given symptoms.
            If no remedy is found in the document, provide general self-care advice.
        """,
        query=f"Symptoms: {symptoms}. Duration: {duration}. Severity: {severity}/10. What home remedies can I try?",
        temperature=0.2,
        lastk=0,
        session_id=session_id_,
        rag_usage=True,
        rag_threshold=0.2,
        rag_k=3
    )
    return response.get("response", "⚠️ Sorry, I couldn't process your request.")

def ask_followup(symptoms):
    """Generates follow-up questions based on symptoms."""
    response = generate(
        model="4o-mini",
        system="""
            Generate up to 3 follow-up questions about the provided symptom.
            If fewer than 3 relevant questions exist, return only the necessary ones.
            If no follow-ups are needed, respond with 'No follow-ups needed'.
        """,
        query=f"User symptoms: {symptoms}. What follow-up questions should I ask?",
        temperature=0.2,
        lastk=0,
        session_id="FollowUpBot",
        rag_usage=False
    )
    followup_questions = response.get("response", "").split("\n")[:3]
    return followup_questions if followup_questions[0].lower() != "no follow-ups needed" else []

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
#         return jsonify({"text": "🤖 I'm here for healthcare-related questions. Ask me about symptoms and remedies!"})

#     # Ask follow-up questions
#     followup_questions = ask_followup(message)
#     if followup_questions:
#         return jsonify({"text": f"🤖 Follow-up questions:\n\n- " + "\n- ".join(followup_questions)})

#     # If no follow-ups, analyze symptoms directly
#     remedy = analyze_symptoms(message, "unknown duration", "unknown severity")
#     return jsonify({"text": f"🩺 {remedy}"})

@app.route('/query', methods=['POST'])
def main():
    """Handles symptom queries, asks 3 follow-up questions sequentially, ensuring valid answers before proceeding."""
    data = request.get_json()
    user = data.get("user_name", "Unknown")
    message = data.get("text", "").strip()

    print(f"Message from {user}: {message}")

    # Initialize user session if not set
    if "conversation_state" not in session:
        session["conversation_state"] = {}
    user_state = session["conversation_state"].get(user, {})

    # Default response structure
    response_data = {
        "text": "🏥 AMBUBOT - Virtual Healthcare Assistant",
        "message": "🔹 HELLO! I'm Dr. Doc Bot. Describe your symptoms, and I'll provide easy at-home remedies & nearby hospitals!",
        "prompt": "📝 Enter your symptoms below:"
    }

    # If first message, store the symptom and generate follow-ups
    if "symptoms" not in user_state:
        user_state["symptoms"] = message
        user_state["followups"] = ask_followup(message)
        user_state["followup_count"] = 0
        user_state["followup_answers"] = []
        session["conversation_state"][user] = user_state
        response_data["follow_up"] = f"🤖 Follow-up question 1: {user_state['followups'][0]}"
        return jsonify(response_data)

    # Get current follow-up question
    current_question_index = user_state["followup_count"]
    current_question = user_state["followups"][current_question_index]

    # Check if the answer is relevant
    if not is_answer_relevant(current_question, message):
        response_data["error"] = f"⚠️ Your answer doesn't seem relevant to: '{current_question}'. Please answer properly."
        return jsonify(response_data)

    # Store the valid answer
    user_state["followup_answers"].append(message)
    user_state["followup_count"] += 1
    session["conversation_state"][user] = user_state

    # If still more follow-ups needed, ask the next one
    if user_state["followup_count"] < 3:
        next_question = user_state["followups"][user_state["followup_count"]]
        response_data["follow_up"] = f"🤖 Follow-up question {user_state['followup_count'] + 1}: {next_question}"
        return jsonify(response_data)

    # After three valid follow-ups, provide remedy
    remedy = analyze_symptoms(user_state["symptoms"], user_state["followup_answers"])
    response_data["remedy"] = f"🩺 {remedy}"

    # Reset user session after completing the conversation
    session["conversation_state"].pop(user, None)

    return jsonify(response_data)

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
