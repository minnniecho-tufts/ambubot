import streamlit as st
import requests
import os
from llmproxy import generate, pdf_upload   

# Get environment variables
pdf_path = os.getenv("PDF_PATH", "HealingRemedies-compressed4mb.pdf")  # Default to a filename if not set
session_id_ = os.getenv("SESSION_ID", "ambubot-home-remedies")


# Initialize session state for PDF upload
if "pdf_uploaded" not in st.session_state:
    st.session_state.pdf_uploaded = False  # Set initial value

if not st.session_state.pdf_uploaded:
    response = pdf_upload(
        path=pdf_path,
        session_id= session_id_,
        strategy="smart"
    )
    st.session_state.pdf_uploaded = True  # Mark PDF as uploaded
    print(response)  

# Streamlit Page Config
st.set_page_config(page_title="AMBUBOT - Virtual Healthcare Assistant", page_icon="🏥")

st.title("🏥 AMBUBOT - Virtual Healthcare Assistant")
st.write("🔹 HELLO I'm Dr. Doc Bot, describe your symptoms and I'll provide easy at-home remedies & nearby hospitals!")

# Initialize session state
if "step" not in st.session_state:
    st.session_state.step = 1
if "symptoms" not in st.session_state:
    st.session_state.symptoms = ""
if "followup_answers" not in st.session_state:
    st.session_state.followup_answers = {}
if "duration" not in st.session_state:
    st.session_state.duration = ""
if "severity" not in st.session_state:
    st.session_state.severity = 5
if "followup_questions" not in st.session_state:
    st.session_state.followup_questions = []  # Ensure this is initialized as a list
if "followup_index" not in st.session_state:
    st.session_state.followup_index = 0  # Initialize follow-up index to track progress

def is_health_related(user_input):
    """Uses LLM to determine if the user's input is health-related, including descriptive follow-ups."""
    response = generate(
        model="4o-mini",
        system="""
            You are an AI that classifies whether a user's input is related to health concerns.
            - If the input describes symptoms, their characteristics (e.g., duration, severity, pattern), or medical conditions, respond with "Yes".
            - If the input is unrelated (e.g., asking about weather, sports, jokes), respond with "No".
            - If the input is a description of symptoms like "on and off", "come and go", or "sharp pain", respond with "Yes".
            - Only return "Yes" or "No" with no extra words.
        """,
        query=f"User input: '{user_input}'. Is this related to health concerns?",
        temperature=0.0,
        lastk=0,
        session_id="IntentCheck",
        rag_usage=False  # Disable RAG for this query
    )

    # Debugging: Print response
    print("LLM Response:", response)

    # Extract response correctly
    if isinstance(response, dict) and "response" in response:
        response_text = response["response"].strip().lower()
    else:
        response_text = str(response).strip().lower()

    return response_text == "yes"




# Function to get user location
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

# Function to find nearby hospitals
def find_nearest_hospitals_osm(location):
    """Fetches hospitals within a 20km radius using OpenStreetMap Overpass API."""
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
            return ["❌ No hospitals found nearby. Please call emergency services."]

        # **Exclude Children's & Mental Health hospitals**
        excluded_keywords = ["child", "pediatric", "mental", "psychiatric", "rehabilitation"]

        filtered_hospitals = [h.get("tags", {}).get("name", "Unnamed Hospital") for h in hospitals]
        filtered_hospitals = [h for h in filtered_hospitals if h and not any(ex in h.lower() for ex in excluded_keywords)]
        
        if not filtered_hospitals:
            return ["❌ No general hospitals found nearby. Please call emergency services."]

        return [f"🏥 {h}" for h in filtered_hospitals[:3]]  # Return list of hospitals

    except Exception as e:
        return [f"⚠️ Error retrieving hospital data: {e}"]

# Function to analyze symptoms
def analyze_symptoms(symptoms, duration, severity):
    """Uses an LLM with RAG to generate a response with symptom analysis and treatment suggestions from a PDF."""
    response = generate(
        model="4o-mini",
        system="""
            You are a virtual healthcare assistant specializing in home remedies.
            - Provide home treatments for the given symptoms based on the uploaded document.
            - If multiple remedies exist, suggest the most effective and commonly available options.
            - If no remedy is found in the document, provide general self-care advice.
            - Keep responses **concise**, **easy to understand**, and **practical**.
        """,
        query=f"My symptoms are: {symptoms}. Duration: {duration}. Severity: {severity}/10. What home remedies can I try?",
        temperature=0.2,
        lastk=0,
        session_id=session_id_,
        rag_usage=True,  # Ensure document retrieval
        rag_threshold= 0.2,
        rag_k=3)


    # Ensure response is a dict and extract the expected key
    if isinstance(response, dict) and "response" in response:
        return response["response"]
    else:
        return "⚠️ Sorry, I couldn't process your request. Please try again."



def ask_followup(symptoms):
    """Dynamically generate up to 3 follow-up questions based on symptoms."""
    response = generate(
        model="4o-mini",
        system="""
            You are a medical assistant that asks **only follow-up questions** related to the provided symptom.
            - Do not introduce new symptoms.
            - If the user reports "headache", ask about **headache specifics**.
            - If the user reports "cough", ask about **cough specifics** (e.g., phlegm, fever).
            - Generate exactly 3 follow-up questions.
            - If fewer than 3 relevant questions exist, return only what's necessary.
            - DON'T ask about severity on a scale or duration.
        """,
        query=f"User symptoms: {symptoms}. What follow-up questions should I ask?",
        temperature=0.2,
        lastk=0,
        session_id="FollowUpBot",
        rag_usage=False  # Ensure document retrieval is disabled
    )

    # Debugging: Print response to confirm structure
    print("LLM Response:", response)

    # Extract the correct response value
    if isinstance(response, dict) and "response" in response:
        response_text = response["response"].strip()
    else:
        response_text = str(response).strip()

    # Process the extracted response
    questions = response_text.split("\n") if response_text.lower() != "no follow-ups needed" else []
    
    return questions[:3]  # Limit to 3 follow-ups



def is_followup_related(question, user_answer):
    """Uses LLM to determine if the user's answer is relevant to the chatbot's follow-up question."""
    response = generate(
        model="4o-mini",
        system="""
            You are an AI that verifies if a user's answer correctly addresses a follow-up question about health symptoms.
            - If the answer is **directly related** to the question, respond with "Yes".
            - If the answer is **vague, off-topic, or does not answer the question**, respond with "No".
            - Consider common ways patients describe symptoms (e.g., "sharp pain" for headache severity).
            - Do not reject answers that provide symptom descriptions even if they are short (e.g., "mild", "on and off", "yes", "no").
            - Only return "Yes" or "No" with no extra words.
        """,
        query=f"Follow-up Question: {question}\nUser Answer: {user_answer}\nIs the answer relevant to the question?",
        temperature=0.0,
        lastk=0,
        session_id="FollowUpValidation",
        rag_usage=False  # Ensure no document retrieval
    )

    # Debugging: Print the response
    print("LLM Response:", response)

    # Extract the correct response value
    if isinstance(response, dict) and "response" in response:
        response_text = response["response"].strip()
    else:
        response_text = str(response).strip()

    return response_text.lower() == "yes"



# Streamlit UI for chatbot
def main():
    st.subheader("🩺 Describe Your Symptoms")

    if st.session_state.step == 1:
        st.session_state.symptoms = st.text_input("What symptoms are you experiencing?", placeholder="e.g., headache, fever, nausea")
        if st.button("Next"):
            if not st.session_state.symptoms or not is_health_related(st.session_state.symptoms):
                st.warning("⚠️ Please enter your symptoms.")

            else:
                st.session_state.followup_questions = ask_followup(st.session_state.symptoms)
                st.session_state.step = 2
                st.rerun()

    elif st.session_state.step == 2:
        st.write("🔍 Follow-up Questions")

        if st.session_state.followup_index < len(st.session_state.followup_questions):
            current_question = st.session_state.followup_questions[st.session_state.followup_index]
            user_response = st.text_input(current_question, value=st.session_state.followup_answers.get(current_question, ""))

            if st.button("Next"):
                if not user_response or not is_followup_related(current_question, user_response):
                    st.warning(f"⚠️ Please provide a valid answer for: {current_question}")
                else:
                    st.session_state.followup_answers[current_question] = user_response
                    st.session_state.followup_index += 1  # Move to the next follow-up question

                    if st.session_state.followup_index >= len(st.session_state.followup_questions):  # If all follow-ups are done
                        st.session_state.step = 3  # Move to Severity and Duration step
                    st.rerun()

        else:
            st.session_state.step = 3
            st.rerun()

    elif st.session_state.step == 3:
        st.session_state.duration = st.text_input("How long have you had these symptoms?", placeholder="e.g., 1 day, 3 days, 1 week")
        st.session_state.severity = st.slider("How severe are your symptoms? (1 = mild, 10 = severe)", 1, 10, 5)

        if st.button("Get Advice"):
            if not st.session_state.duration or not is_followup_related("How long have you had these symptoms?", st.session_state.duration):
                st.warning("⚠️ Please enter a valid duration (e.g., 1 day, 3 days, 1 week).")
            else:
                st.session_state.step = 4
                st.rerun()

    elif st.session_state.step == 4:
        st.write("🧠 **Analyzing Symptoms & Providing Treatment Advice...**")
        symptoms_details = f"{st.session_state.symptoms}. Follow-up: {st.session_state.followup_answers}"
        advice = analyze_symptoms(symptoms_details, st.session_state.duration, st.session_state.severity)
        st.success(advice)

        if st.session_state.severity >= 0 or "chest pain" in st.session_state.symptoms.lower() or "difficulty breathing" in st.session_state.symptoms.lower():
            st.write("📍 **Finding Nearby Hospitals...**")
            location, location_message = get_user_location()
            st.info(location_message)
            if location:
                hospitals = find_nearest_hospitals_osm(location)
                for hospital in hospitals:
                    st.success(hospital)
            else:
                st.error("❌ Unable to get location. Please enter manually.")

        st.button("Restart", on_click=lambda: st.session_state.update(step=1, symptoms="", followup_answers={}, duration="", severity=5))
        
if __name__ == "__main__":
    main()
