from flask import Flask, render_template, request, jsonify
import requests
import datetime
import os
import urllib.parse
import threading
import time

app = Flask(__name__)

# Airtable credentials
AIRTABLE_API_KEY = os.getenv('AIRTABLE_API_KEY')
AIRTABLE_BASE_ID = os.getenv('AIRTABLE_BASE_ID') 
AIRTABLE_RESPONSES_TABLE = os.getenv('AIRTABLE_TABLE_NAME') or "Survey Responses"
AIRTABLE_PROSPECTS_TABLE = os.getenv('AIRTABLE_PROSPECTS_TABLE') or "Prospects"

BASE_ID = AIRTABLE_BASE_ID
HQ_TABLE = AIRTABLE_PROSPECTS_TABLE
RESPONSES_TABLE = AIRTABLE_RESPONSES_TABLE

# --- GHL Setup ---
GHL_API_KEY = "d9d7d5e9-4322-4bc0-ad64-969e9194bfc2"
GHL_LOCATION_ID = "nxwUZI406A795cE76Wqs"
GHL_BASE = "https://rest.gohighlevel.com/v1"

# --- Airtable helpers ---
def _h():
    return {"Authorization": f"Bearer {AIRTABLE_API_KEY}", "Content-Type": "application/json"}

def _url(table, record_id=None):
    base = f"https://api.airtable.com/v0/{BASE_ID}/{urllib.parse.quote(table)}"
    return f"{base}/{record_id}" if record_id else base

def create_prospect_and_legacy_code(email, phone):
    payload = {"fields": {"Prospect Email": email, "Prospect Phone": phone, "Sync Status": "Pending"}}
    r = requests.post(_url(HQ_TABLE), headers=_h(), json=payload)
    r.raise_for_status()
    rec = r.json()
    rec_id = rec["id"]
    auto = rec.get("fields", {}).get("AutoNum")

    if auto is None:
        r2 = requests.get(_url(HQ_TABLE, rec_id), headers=_h())
        r2.raise_for_status()
        auto = r2.json().get("fields", {}).get("AutoNum")

    if auto is None:
        raise RuntimeError("AutoNum not found. Ensure Prospects has an Auto Number field named 'AutoNum'.")

    code_num = 1000 + int(auto)
    legacy_code = f"Legacy-X25-OP{code_num}"

    patch_payload = {"fields": {"Legacy Code": legacy_code}}
    requests.patch(_url(HQ_TABLE, rec_id), headers=_h(), json=patch_payload)

    return legacy_code, rec_id

def update_sync_status(record_id, status):
    """Update the Sync Status field in Airtable Prospects table"""
    patch_payload = {"fields": {"Sync Status": status}}
    requests.patch(_url(HQ_TABLE, record_id), headers=_h(), json=patch_payload)

# --- GHL helpers ---
def _ghl_h():
    return {"Authorization": f"Bearer {GHL_API_KEY}", "Content-Type": "application/json"}

def ghl_find_or_create_contact(email, phone):
    r = requests.get(f"{GHL_BASE}/contacts/", headers=_ghl_h(),
                     params={"locationId": GHL_LOCATION_ID, "email": email})
    r.raise_for_status()
    hits = r.json().get("contacts", [])
    if hits:
        return hits[0]["id"]

    if phone:
        r2 = requests.get(f"{GHL_BASE}/contacts/", headers=_ghl_h(),
                          params={"locationId": GHL_LOCATION_ID, "phone": phone})
        r2.raise_for_status()
        hits2 = r2.json().get("contacts", [])
        if hits2:
            return hits2[0]["id"]

    payload = {"locationId": GHL_LOCATION_ID, "email": email}
    if phone:
        payload["phone"] = phone
    r3 = requests.post(f"{GHL_BASE}/contacts/", headers=_ghl_h(), json=payload)
    r3.raise_for_status()
    return r3.json()["contact"]["id"]

def ghl_update_contact(email, phone, legacy_code, answers):
    cid = ghl_find_or_create_contact(email, phone)
    payload = {
        "id": cid,
        "locationId": GHL_LOCATION_ID,
        "customField": [
            {"id": "contact.legacy_code_id", "value": legacy_code},
            {"id": "contact.q1_reason_for_business", "value": answers[0]},
            {"id": "contact.q2_time_commitment", "value": answers[1]},
            {"id": "contact.q3_business_experience", "value": answers[2]},
            {"id": "contact.q4_startup_readiness", "value": answers[3]},
            {"id": "contact.q5_confidence_level", "value": answers[4]},
            {"id": "contact.q6_business_style_gem", "value": answers[5]}
        ]
    }
    r = requests.put(f"{GHL_BASE}/contacts/", headers=_ghl_h(), json=payload)
    r.raise_for_status()
    return r.json()

# --- Background worker ---
def delayed_ghl_update(email, phone, legacy_code, answers, prospect_id):
    print("Worker spawned: waiting 1 minute before GHL update...")
    time.sleep(60)
    try:
        ghl_update_contact(email, phone, legacy_code, answers)
        update_sync_status(prospect_id, "✅ Synced to GHL")
        print("✅ GHL updated successfully")
    except Exception as e:
        update_sync_status(prospect_id, f"❌ Error: {e}")
        print("❌ Error updating GHL:", e)

# --- Routes ---
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

        while len(answers) < 6:
            answers.append("No response provided")

        legacy_code, prospect_id = create_prospect_and_legacy_code(email, phone)

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
                "Prospects": [prospect_id]
            }
        }
        responses_url = _url(RESPONSES_TABLE)
        r3 = requests.post(responses_url, headers=_h(), json=survey_payload)
        if r3.status_code != 200:
            print(f"Error posting to Survey Responses: {r3.status_code} - {r3.text}")
        else:
            print("✅ Survey responses saved to Airtable")

        threading.Thread(target=delayed_ghl_update, args=(email, phone, legacy_code, answers, prospect_id)).start()

        return jsonify({"legacy_code": legacy_code, "status": "success", "message": "Survey submitted successfully!"})

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

    print(f"🚀 Starting Flask app with Base ID: {AIRTABLE_BASE_ID}")
    print(f"Survey Responses Table: {RESPONSES_TABLE}")
    print(f"HQ Table: {HQ_TABLE}")
    app.run(debug=True, host='0.0.0.0', port=5000)
