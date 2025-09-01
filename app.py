from flask import Flask, render_template, request, jsonify
import requests
import datetime
import os

app = Flask(__name__)

# Airtable credentials - properly get environment variables
AIRTABLE_API_KEY = os.getenv('AIRTABLE_API_KEY')
AIRTABLE_BASE_ID = os.getenv('AIRTABLE_BASE_ID') 
AIRTABLE_TABLE_NAME = os.getenv('AIRTABLE_TABLE_NAME')
AIRTABLE_PROSPECTS_TABLE = os.getenv('AIRTABLE_PROSPECTS_TABLE')

# Define table names (you may need to adjust these based on your Airtable setup)
BASE_ID = AIRTABLE_BASE_ID
HQ_TABLE = AIRTABLE_PROSPECTS_TABLE or "Legacy Code HQ"
RESPONSES_TABLE = AIRTABLE_TABLE_NAME or "Legacy Builder Responses"

# Function to generate Legacy Code with better sequence handling
def generate_legacy_code():
    try:
        # Use timestamp-based approach for more reliability
        timestamp = int(datetime.datetime.now().timestamp())
        # Get last 4 digits and ensure it's above 1110
        base_num = timestamp % 10000
        if base_num < 1110:
            base_num += 1110
        
        new_code = f"Legacy-X25-OP{base_num}"
        
        # Double-check this code doesn't already exist
        url = f"https://api.airtable.com/v0/{BASE_ID}/{RESPONSES_TABLE}?filterByFormula={{Legacy Code}}='{new_code}'"
        headers = {"Authorization": f"Bearer {AIRTABLE_API_KEY}"}
        response = requests.get(url, headers=headers).json()
        
        # If code exists, add a small random number
        if response.get("records"):
            import random
            base_num += random.randint(1, 99)
            new_code = f"Legacy-X25-OP{base_num}"
        
        print(f"Generated Legacy Code: {new_code}")
        return new_code
        
    except Exception as e:
        print(f"Error generating legacy code: {e}")
        # Fallback with timestamp
        timestamp = int(datetime.datetime.now().timestamp())
        fallback_code = f"Legacy-X25-OP{timestamp % 10000 + 1110}"
        print(f"Using fallback Legacy Code: {fallback_code}")
        return fallback_code

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
        
        # Generate Legacy Code
        legacy_code = generate_legacy_code()
        
        # Map the new survey questions to Airtable fields
        # The new survey has these 6 questions mapped to original field names:
        # 1. Future motivation → Q1 Reason for Business  
        # 2. Time commitment → Q2 Time Commitment
        # 3. Experience level → Q3 Business Experience
        # 4. Readiness to start → Q4 Startup Readiness
        # 5. Confidence level → Q5 Confidence Level
        # 6. Team role preference → Q6 Business Style (GEM)
        
        # Ensure we have at least 6 answers
        while len(answers) < 6:
            answers.append("No response provided")
        
        # Insert into Legacy Builder Responses
        responses_url = f"https://api.airtable.com/v0/{BASE_ID}/{RESPONSES_TABLE}"
        headers = {"Authorization": f"Bearer {AIRTABLE_API_KEY}", "Content-Type": "application/json"}
        
        payload_responses = {
            "fields": {
                "Legacy Code": legacy_code,
                "Date Submitted": datetime.date.today().isoformat(),
                "Q1 Reason for Business": answers[0][:100000] if len(answers[0]) > 100000 else answers[0],
                "Q2 Time Commitment": answers[1][:100000] if len(answers[1]) > 100000 else answers[1],
                "Q3 Business Experience": answers[2][:100000] if len(answers[2]) > 100000 else answers[2],
                "Q4 Startup Readiness": answers[3][:100000] if len(answers[3]) > 100000 else answers[3],
                "Q5 Confidence Level": answers[4][:100000] if len(answers[4]) > 100000 else answers[4],
                "Q6 Business Style (GEM)": answers[5][:100000] if len(answers[5]) > 100000 else answers[5]
            }
        }
        
        # Post to responses table
        response1 = requests.post(responses_url, headers=headers, json=payload_responses)
        if response1.status_code != 200:
            print(f"Error posting to responses table: {response1.status_code} - {response1.text}")
        else:
            print("Successfully posted to responses table")
        
        # Insert into Legacy Code HQ (without Legacy Code field since it's computed)
        hq_url = f"https://api.airtable.com/v0/{BASE_ID}/{HQ_TABLE}"
        payload_hq = {
            "fields": {
                "Prospect Email": email,
                "Prospect Phone": phone
            }
        }
        
        # Post to HQ table
        response2 = requests.post(hq_url, headers=headers, json=payload_hq)
        if response2.status_code != 200:
            print(f"Error posting to HQ table: {response2.status_code} - {response2.text}")
        else:
            print("Successfully posted to HQ table")
        
        print(f"Survey completed successfully. Legacy Code: {legacy_code}")
        return jsonify({
            "legacy_code": legacy_code, 
            "status": "success",
            "message": "Survey submitted successfully!"
        })
    
    except Exception as e:
        print(f"Error in submit route: {e}")
        return jsonify({
            "error": "An error occurred processing your request",
            "status": "error"
        }), 500

# Health check endpoint
@app.route("/health")
def health():
    # Check if required environment variables are set
    required_vars = [AIRTABLE_API_KEY, AIRTABLE_BASE_ID]
    missing_vars = [var for var in required_vars if not var]
    
    if missing_vars:
        return jsonify({
            "status": "unhealthy", 
            "message": "Missing required environment variables"
        }), 500
    
    return jsonify({
        "status": "healthy",
        "base_id": AIRTABLE_BASE_ID,
        "tables": {
            "responses": RESPONSES_TABLE,
            "hq": HQ_TABLE
        }
    })

# Test endpoint to verify Airtable connection
@app.route("/test-airtable")
def test_airtable():
    try:
        url = f"https://api.airtable.com/v0/{BASE_ID}/{HQ_TABLE}?maxRecords=1"
        headers = {"Authorization": f"Bearer {AIRTABLE_API_KEY}"}
        response = requests.get(url, headers=headers)
        
        return jsonify({
            "status": "success" if response.status_code == 200 else "error",
            "status_code": response.status_code,
            "response": response.json() if response.status_code == 200 else response.text
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        })

if __name__ == "__main__":
    # Check for required environment variables on startup
    if not AIRTABLE_API_KEY:
        print("ERROR: AIRTABLE_API_KEY environment variable is required")
        exit(1)
    if not AIRTABLE_BASE_ID:
        print("ERROR: AIRTABLE_BASE_ID environment variable is required")
        exit(1)
        
    print(f"Starting Flask app with Base ID: {AIRTABLE_BASE_ID}")
    print(f"Responses Table: {RESPONSES_TABLE}")
    print(f"HQ Table: {HQ_TABLE}")
    app.run(debug=True, host='0.0.0.0', port=5000)
    
    if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
