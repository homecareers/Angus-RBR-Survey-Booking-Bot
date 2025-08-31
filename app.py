from flask import Flask, render_template, request, jsonify
import requests, datetime

app = Flask(__name__)

# Airtable credentials
AIRTABLE_API_KEY = "YOUR_API_KEY"
BASE_ID = "YOUR_BASE_ID"
RESPONSES_TABLE = "Legacy Builder Responses"
HQ_TABLE = "Legacy Code HQ"

# Function to generate Legacy Code
def generate_legacy_code():
    url = f"https://api.airtable.com/v0/{BASE_ID}/{HQ_TABLE}?maxRecords=1&sort[0][field]=AutoNum&sort[0][direction]=desc"
    headers = {"Authorization": f"Bearer {AIRTABLE_API_KEY}"}
    response = requests.get(url, headers=headers).json()

    if response["records"]:
        last_code = response["records"][0]["fields"].get("Legacy Code", "Legacy-X25-OP1110")
        last_num = int(last_code.split("OP")[-1])
    else:
        last_num = 1110  # starting number

    new_code = f"Legacy-X25-OP{last_num+1}"
    return new_code

@app.route("/")
def index():
    return render_template("chat.html")

@app.route("/submit", methods=["POST"])
def submit():
    data = request.json
    email = data["email"]
    phone = data["phone"]
    answers = data["answers"]

    # Generate Legacy Code
    legacy_code = generate_legacy_code()

    # Insert into Legacy Builder Responses
    responses_url = f"https://api.airtable.com/v0/{BASE_ID}/{RESPONSES_TABLE}"
    headers = {"Authorization": f"Bearer {AIRTABLE_API_KEY}", "Content-Type": "application/json"}
    payload_responses = {
        "fields": {
            "Legacy Code": legacy_code,
            "Date Submitted": datetime.date.today().isoformat(),
            "Q1 Reason for Business": answers[0],
            "Q2 Time Commitment": answers[1],
            "Q3 Business Experience": answers[2],
            "Q4 Startup Readiness": answers[3],
            "Q5 Confidence Level": answers[4],
            "Q6 Business Style (GEM)": answers[5]
        }
    }
    requests.post(responses_url, headers=headers, json=payload_responses)

    # Insert into Legacy Code HQ
    hq_url = f"https://api.airtable.com/v0/{BASE_ID}/{HQ_TABLE}"
    payload_hq = {
        "fields": {
            "Legacy Code": legacy_code,
            "Prospect Email": email,
            "Prospect Phone": phone
        }
    }
    requests.post(hq_url, headers=headers, json=payload_hq)

    return jsonify({"legacy_code": legacy_code})

if __name__ == "__main__":
    app.run(debug=True)
