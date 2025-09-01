from flask import Flask, render_template, request, jsonify
import requests
import datetime
import os
import urllib.parse

app = Flask(__name__)

# Airtable credentials - properly get environment variables
AIRTABLE_API_KEY = os.getenv('AIRTABLE_API_KEY')
AIRTABLE_BASE_ID = os.getenv('AIRTABLE_BASE_ID') 
AIRTABLE_RESPONSES_TABLE = os.getenv('AIRTABLE_TABLE_NAME') or "Survey Responses"
AIRTABLE_PROSPECTS_TABLE = os.getenv('AIRTABLE_PROSPECTS_TABLE') or "Prospects"

BASE_ID = AIRTABLE_BASE_ID
HQ_TABLE = AIRTABLE_PROSPECTS_TABLE
RESPONSES_TABLE = AIRTABLE_RESPONSES_TABLE

def _h():
    return {"Authorization": f"Bearer {AIRTABLE_API_KEY}", "Content-Type": "application/json"}

def _url(table, record_id=None):
    base = f"https://api.airtable.com/v0/{BASE_ID}/{urllib.parse.quote(table)}"
    return f"{base}/{record_id}" if record_id else base

def create_prospect_and_legacy_code(email, phone):
    """
    1) Create a Prospect row to reserve AutoNum
    2) Read AutoNum -> compute Legacy Code (1000 + AutoNum)
    3) Patch Prospect row with computed Legacy Code
    4) Return (legacy_code, prospect_record_id)
    """
    payload = {"fields": {"Prospect Email": email, "Prospect Phone": phone}}
    r = requests.post(_url(HQ_TABLE), headers=_h(), json=payload)
    r.raise_for_status()
    rec = r.json()
    rec_id = rec["id"]
    auto = rec.get("fields", {}).get("AutoNum")

    # Fetch again if AutoNum not present yet
    if auto is None:
        r2 = requests.get(_url(HQ_TABLE, rec_id), headers=_h())
        r2.raise_for_status()
        auto = r2.json().get("fields", {}).get("AutoNum")

    if auto is None:
        raise RuntimeError("AutoNum not found. Ensure Prospects has an Auto Number field named 'AutoNum'.")

    code_num = 1000 + int(auto)  # Example: AutoNum=58 -> Legacy-X25-OP1058
    legacy_code = f"Legacy-X25-OP{code_num}"

    # Patch the record with the Legacy Code
    patch_payload = {"fields": {"Legacy Code": legacy_code}}
    requests.patch(_url(HQ_TABLE, rec_id), headers=_h(), json=patch_payload)

    return legacy_code, rec_id

@app.route("/")
def index():
    return render_template("chat.html")

@app.route("/submit", methods=["POST"])
def submit():
    try:
        data = request.json
        email = data["email"]
        phone = data["phone"]
        answers = data["answers"]

        print(f"Received survey data: Email={email}, Phone={phone}, Answers={len(answers)} responses")

        # Ensure 6 answers
        while len(answers) < 6:
            answers.append("No response provided")

        # Create Prospect first (AutoNum → Legacy Code)
        legacy_code, prospect_id = create_prospect_and_legacy_code(email, phone)

        # Insert into Survey Responses (linked back to Prospect)
        survey_payload = {
            "fields": {
                "Date Submitted": datetime.datetime.now().isoformat(),
                "Legacy Code": legacy_code,
                "Q1 Reason for Business": answers[0],
                "Q2 Time Commitment": answers[1],
                "Q3 Business Experience": answers[2],
                "Q4 Startup Readiness": answers[3],
                "Q5 Confidence Level": answers[4],
                "Q6 Business Style (GEM)": answers[5],
                "Prospects": [prospect_id]   # Linked Record
            }
        }
        responses_url = _url(RESPONSES_TABLE)
        r3 = requests.post(responses_url, headers=_h(), json=survey_payload)
        if r3.status_code != 200:
            print(f"Error posting to responses table: {r3.status_code} - {r3.text}")
        else:
            print("Successfully posted to Survey Responses")

        print(f"Survey completed successfully. Legacy Code: {legacy_code} (created in Airtable only)")
        
        # Return success with dummy legacy_code so frontend shows success message
        return jsonify({
            "legacy_code": "SUBMITTED", 
            "status": "success", 
            "message": "Survey submitted successfully!"
        })

    except Exception as e:
        print(f"Error in submit route: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route("/health")
def health():
    required_vars = [AIRTABLE_API_KEY, AIRTABLE_BASE_ID]
    missing_vars = [var for var in required_vars if not var]
    if missing_vars:
        return jsonify({"status": "unhealthy", "message": "Missing required environment variables"}), 500

    return jsonify({
        "status": "healthy",
        "base_id": AIRTABLE_BASE_ID,
        "tables": {"responses": RESPONSES_TABLE, "hq": HQ_TABLE}
    })

@app.route("/test-airtable")
def test_airtable():
    try:
        url = _url(HQ_TABLE) + "?maxRecords=1"
        r = requests.get(url, headers=_h())
        return jsonify({
            "status": "success" if r.status_code == 200 else "error",
            "status_code": r.status_code,
            "response": r.json() if r.status_code == 200 else r.text
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})

if __name__ == "__main__":
    if not AIRTABLE_API_KEY:
        print("ERROR: AIRTABLE_API_KEY environment variable is required")
        exit(1)
    if not AIRTABLE_BASE_ID:
        print("ERROR: AIRTABLE_BASE_ID environment variable is required")
        exit(1)

    print(f"Starting Flask app with Base ID: {AIRTABLE_BASE_ID}")
    print(f"Responses Table: {RESPONSES_TABLE}")
    print(f"HQ Table: {HQ_TABLE}")
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
