{
  "apiKey": "comp150-cdr-2025s-4srlRlceWnukwewcCw7vm7wLygCvdipGNEWgiRRs",
  "endPoint": "https://a061igc186.execute-api.us-east-1.amazonaws.com/dev"
}

from llmproxy import pdf_upload

if __name__ == '__main__':
    response = pdf_upload(path = 'greentim.pdf',
        strategy = 'smart')

    print(response)

from llmproxy import text_upload

if __name__ == '__main__':
    response = text_upload(text = """
        Once upon a time, in the faraway land of Citrusville, there was a man named Orange Jim.
        Now, Orange Jim wasn't your average Joe—oh no, he was really average in every sense, except for one glaring, fruit-inspired trait: he was the color orange.
        Not just a little orange but a deep, radiant orange, like a tangerine on a sunbeam, or the kind of sunset that makes you question the existence of sunsets.
        """,
        strategy = 'fixed')

    print(response)

from llmproxy import generate

if __name__ == '__main__':
    response = generate(model = '4o-mini',
        system = 'Answer my question in a funny manner',
        query = 'Who are the Jumbos?',
        temperature=0.0,
        lastk=0,
        session_id='GenericSession')

    print(response)
import json
import requests

# Read proxy config from config.json
with open('config.json', 'r') as file:
    config = json.load(file)

end_point = config['endPoint']
api_key = config['apiKey']

def generate(
	model: str,
	system: str,
	query: str,
	temperature: float | None = None,
	lastk: int | None = None,
	session_id: str | None = None
	):
	

    headers = {
        'x-api-key': api_key
    }

    request = {
        'model': model,
        'system': system,
        'query': query,
        'temperature': temperature,
        'lastk': lastk,
        'session_id': None,
    }

    msg = None

    try:
        response = requests.post(end_point, headers=headers, json=request)

        if response.status_code == 200:
            msg = json.loads(response.text)['result']
        else:
            msg = f"Error: Received response code {response.status_code}"
    except requests.exceptions.RequestException as e:
        msg = f"An error occurred: {e}"
    return msg	



def upload(multipart_form_data):

    headers = {
        'x-api-key': api_key
    }

    msg = None
    try:
        response = requests.post(end_point, headers=headers, files=multipart_form_data)
        
        if response.status_code == 200:
            msg = "Successfully uploaded. It may take a short while for the document to be added to your context"
        else:
            msg = f"Error: Received response code {response.status_code}"
    except requests.exceptions.RequestException as e:
        msg = f"An error occurred: {e}"
    
    return msg


def pdf_upload(
    path: str,    
    strategy: str | None = None,
    description: str | None = None,
    session_id: str | None = None
    ):
    
    params = {
        'description': description,
        'session_id': session_id,
        'strategy': strategy
    }

    multipart_form_data = {
        'params': (None, json.dumps(params), 'application/json'),
        'file': (None, open(path, 'rb'), "application/pdf")
    }

    response = upload(multipart_form_data)
    return response

def text_upload(
    text: str,    
    strategy: str | None = None,
    description: str | None = None,
    session_id: str | None = None
    ):
    
    params = {
        'description': description,
        'session_id': session_id,
        'strategy': strategy
    }


    multipart_form_data = {
        'params': (None, json.dumps(params), 'application/json'),
        'text': (None, text, "application/text")
    }


    response = upload(multipart_form_data)
    return response