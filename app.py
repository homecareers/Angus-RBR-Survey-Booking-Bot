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
        
        print(f"Received survey data: Email={email}, Phone={phone}, Answers={len(answers)} responses")
        
        # Generate Legacy Code
        legacy_code = generate_legacy_code()
        
        # Map the new survey questions to Airtable fields
        # The new survey has these 6 questions:
        # 1. Future motivation (time freedom, income, career change, community, other)
        # 2. Time commitment (3-5, 5-10, 10-15, 15+ hours)
        # 3. Experience level (newbie, tried before unsuccessful, tried before successful)
        # 4. Readiness to start (right now, 30 days, 2-3 months, just exploring)
        # 5. Confidence level (1-10 scale)
        # 6. Team role preference (Pearl, Ruby, Sapphire, Emerald)
        
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
                "Q1 Future Motivation": answers[0][:100000] if len(answers[0]) > 100000 else answers[0],
                "Q2 Time Commitment": answers[1][:100000] if len(answers[1]) > 100000 else answers[1],
                "Q3 Experience Level": answers[2][:100000] if len(answers[2]) > 100000 else answers[2],
                "Q4 Readiness to Start": answers[3][:100000] if len(answers[3]) > 100000 else answers[3],
                "Q5 Confidence Level": answers[4][:100000] if len(answers[4]) > 100000 else answers[4],
                "Q6 Team Role Preference": answers[5][:100000] if len(answers[5]) > 100000 else answers[5]
            }
        }
        
        # Post to responses table
        response1 = requests.post(responses_url, headers=headers, json=payload_responses)
        if response1.status_code != 200:
            print(f"Error posting to responses table: {response1.status_code} - {response1.text}")
        else:
            print("Successfully posted to responses table")
        
        # Insert into Legacy Code HQ
        hq_url = f"https://api.airtable.com/v0/{BASE_ID}/{HQ_TABLE}"
        payload_hq = {
            "fields": {
                "Legacy Code": legacy_code,
                "Prospect Email": email,
                "Prospect Phone": phone,
                "Date Created": datetime.date.today().isoformat()
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
