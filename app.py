from flask import Flask, render_template, request, jsonify
import requests
import datetime
import os
import urllib.parse
import time
import re

app = Flask(__name__)

# Airtable credentials
AIRTABLE_API_KEY = os.getenv('AIRTABLE_API_KEY')
AIRTABLE_BASE_ID = os.getenv('AIRTABLE_BASE_ID')
AIRTABLE_RESPONSES_TABLE = os.getenv('AIRTABLE_TABLE_NAME') or "Survey Responses"
AIRTABLE_PROSPECTS_TABLE = os.getenv('AIRTABLE_PROSPECTS_TABLE') or "Prospects"

BASE_ID = AIRTABLE_BASE_ID
HQ_TABLE = AIRTABLE_PROSPECTS_TABLE
RESPONSES_TABLE = AIRTABLE_RESPONSES_TABLE

# GHL credentials
GHL_API_KEY = os.getenv("GHL_API_KEY") or "d9d7d5e9-4322-4bc0-ad64-969e9194bfc2"
GHL_LOCATION_ID = os.getenv("GHL_LOCATION_ID") or "nxwUZI406A795cE76Wqs"

# Airtable helpers
def _h():
    return {"Authorization": f"Bearer {AIRTABLE_API_KEY}", "Content-Type": "application/json"}

def _url(table, record_id=None):
    base = f"https://api.airtable.com/v0/{BASE_ID}/{urllib.parse.quote(table)}"
    return f"{base}/{record_id}" if record_id else base

def sanitize_phone(phone):
    """Convert messy phone numbers into +1XXXXXXXXXX format"""
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)  # Strip non-numeric
    if len(digits) == 10:
        return "+1" + digits
    elif len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    elif digits.startswith("+"):
        return digits
    else:
        return "+" + digits  # Fallback

def create_prospect_and_legacy_code(email, phone):
    """Create a Prospect row, assign Legacy Code, return (legacy_code, prospect_id)"""
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
        raise RuntimeError("AutoNum not found. Ensure Prospects table has an Auto Number field named 'AutoNum'.")

    code_num = 1000 + int(auto)  # Example: AutoNum=59 → Legacy-X25-OP1059
    legacy_code = f"Legacy-X25-OP{code_num}"

    # Patch the record with Legacy Code
    patch_payload = {"fields": {"Legacy Code": legacy_code}}
    requests.patch(_url(HQ_TABLE, rec_id), headers=_h(), json=patch_payload)

    return legacy_code, rec_id

def update_ghl_contact(email, phone, legacy_code, answers):
    """Update/Create contact in GHL with survey answers + Legacy Code"""
    url = "https://rest.gohighlevel.com/v1/contacts"
    headers = {"Authorization": f"Bearer {GHL_API_KEY}", "Content-Type": "application/json"}

    clean_phone = sanitize_phone(phone)

    payload = {
        "locationId": GHL_LOCATION_ID,
        "email": email,
        "phone": clean_phone,
        "customField": {
            "q1_reason_for_business": answers[0],
            "q2_time_commitment": answers[1],
            "q3_business_experience": answers[2],
            "q4_startup_readiness": answers[3],
            "q5_confidence_level": answers[4],
            "q6_business_style_gem": answers[5],
            "legacy_code_id": legacy_code
        }
    }

    r = requests.post(url, headers=headers, json=payload)
    if r.status_code != 200:
        raise RuntimeError(f"GHL sync failed: {r.status_code} - {r.text}")
    return r.json()

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

        print(f"📩 Received survey: {email}, {phone}, {len(answers)} answers")

        # Ensure 6 answers
        while len(answers) < 6:
            answers.append("No response provided")

        # Create Prospect + Legacy Code
        legacy_code, prospect_id = create_prospect_and_legacy_code(email, phone)

        # Insert into Survey Responses (linked to Prospect)
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
        r3 = requests.post(_url(RESPONSES_TABLE), headers=_h(), json=survey_payload)
        if r3.status_code != 200:
            print(f"⚠️ Error posting Survey Response: {r3.status_code} - {r3.text}")

        # Wait before syncing to GHL
        print("⏳ Waiting 60s before syncing to GHL...")
        time.sleep(60)

        try:
            update_ghl_contact(email, phone, legacy_code, answers)
            sync_status = "✅ Synced to GHL"
        except Exception as e:
            sync_status = f"❌ {e}"
            print(f"⚠️ {sync_status}")

        # Update sync status in Airtable
        patch_payload = {"fields": {"Sync Status": sync_status}}
        requests.patch(_url(HQ_TABLE, prospect_id), headers=_h(), json=patch_payload)

        return jsonify({"status": "success", "message": "Survey submitted successfully!"})

    except Exception as e:
        print(f"🔥 Error in /submit: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route("/health")
def health():
    required_vars = [AIRTABLE_API_KEY, AIRTABLE_BASE_ID, GHL_API_KEY, GHL_LOCATION_ID]
    missing_vars = [v for v in required_vars if not v]
    if missing_vars:
        return jsonify({"status": "unhealthy", "missing": missing_vars}), 500
    return jsonify({"status": "healthy", "base_id": AIRTABLE_BASE_ID})

if __name__ == "__main__":
    if not AIRTABLE_API_KEY:
        print("❌ ERROR: AIRTABLE_API_KEY required")
        exit(1)
    if not AIRTABLE_BASE_ID:
        print("❌ ERROR: AIRTABLE_BASE_ID required")
        exit(1)
    if not GHL_API_KEY:
        print("❌ ERROR: GHL_API_KEY required")
        exit(1)
    if not GHL_LOCATION_ID:
        print("❌ ERROR: GHL_LOCATION_ID required")
        exit(1)

    print(f"🚀 Starting Flask app with Airtable Base: {AIRTABLE_BASE_ID}")
    print(f"Responses Table: {RESPONSES_TABLE}, HQ Table: {HQ_TABLE}")
    app.run(debug=True, host='0.0.0.0', port=5000)
