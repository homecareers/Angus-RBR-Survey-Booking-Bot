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

# Function to generate Legacy Code
def generate_legacy_code():
    url = f"https://api.airtable.com/v0/{BASE_ID}/{HQ_TABLE}?maxRecords=1&sort[0][field]=AutoNum&sort[0][direction]=desc"
    headers = {"Authorization": f"Bearer {AIRTABLE_API_KEY}"}
    
    try:
        response = requests.get(url, headers=headers).json()
        if response.get("records"):
            last_code = response["records"][0]["fields"].get("Legacy Code", "Legacy-X25-OP1110")
            last_num = int(last_code.split("OP")[-1])
        else:
            last_num = 1110  # starting number
        new_code = f"Legacy-X25-OP{last_num + 1}"
        return new_code
    except Exception as e:
        print(f"Error generating legacy code: {e}")
        # Return a fallback code with timestamp
        timestamp = int(datetime.datetime.now().timestamp())
        return f"Legacy-X25-OP{timestamp % 10000}"

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
        
        # Generate Legacy Code
        legacy_code = generate_legacy_code()
        
        # Insert into Legacy Builder Responses
        responses_url = f"https://api.airtable.com/v0/{BASE_ID}/{RESPONSES_TABLE}"
        headers = {"Authorization": f"Bearer {AIRTABLE_API_KEY}", "Content-Type": "application/json"}
        
        # Ensure answers are strings and handle long text properly
        processed_answers = []
        for answer in answers:
            if isinstance(answer, str):
                # Trim to Airtable's long text limit if needed (100,000 chars)
                processed_answers.append(answer[:100000] if len(answer) > 100000 else answer)
            else:
                processed_answers.append(str(answer))
        
        payload_responses = {
            "fields": {
                "Legacy Code": legacy_code,
                "Date Submitted": datetime.date.today().isoformat(),
                "Q1 Reason for Business": processed_answers[0],
                "Q2 Time Commitment": processed_answers[1],
                "Q3 Business Experience": processed_answers[2],
                "Q4 Startup Readiness": processed_answers[3],
                "Q5 Confidence Level": processed_answers[4],
                "Q6 Business Style (GEM)": processed_answers[5]
            }
        }
        
        # Post to responses table
        response1 = requests.post(responses_url, headers=headers, json=payload_responses)
        if response1.status_code != 200:
            print(f"Error posting to responses table: {response1.text}")
        
        # Insert into Legacy Code HQ
        hq_url = f"https://api.airtable.com/v0/{BASE_ID}/{HQ_TABLE}"
        payload_hq = {
            "fields": {
                "Legacy Code": legacy_code,
                "Prospect Email": email,
                "Prospect Phone": phone
            }
        }
        
        # Post to HQ table
        response2 = requests.post(hq_url, headers=headers, json=payload_hq)
        if response2.status_code != 200:
            print(f"Error posting to HQ table: {response2.text}")
        
        return jsonify({"legacy_code": legacy_code, "status": "success"})
    
    except Exception as e:
        print(f"Error in submit route: {e}")
        return jsonify({"error": "An error occurred processing your request"}), 500

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
    
    return jsonify({"status": "healthy"})

if __name__ == "__main__":
    # Check for required environment variables on startup
    if not AIRTABLE_API_KEY:
        print("ERROR: AIRTABLE_API_KEY environment variable is required")
        exit(1)
    if not AIRTABLE_BASE_ID:
        print("ERROR: AIRTABLE_BASE_ID environment variable is required")
        exit(1)
        
    print(f"Starting Flask app with Base ID: {AIRTABLE_BASE_ID}")
    app.run(debug=True, host='0.0.0.0', port=5000)
