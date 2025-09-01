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
    # Temporarily embed HTML to bypass templates folder issue
    return """<!DOCTYPE html>
<html>
<head>
  <title>ANGUS™ Survey Bot</title>
  <style>
    body { font-family: Arial, sans-serif; background: #111; color: #eee; margin: 0; padding: 20px; min-height: 100vh; }
    .chat-box { max-width: 600px; margin: 50px auto; background: #222; padding: 30px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }
    .message { margin: 15px 0; line-height: 1.6; animation: fadeIn 0.5s ease-in; }
    .bot { color: #0ff; font-weight: 500; }
    .user { color: #0f0; text-align: right; font-weight: 500; }
    .options { margin: 20px 0; }
    .options button { display: block; margin: 8px 0; width: 100%; padding: 12px 16px; border: none; border-radius: 8px; background: #444; color: #fff; cursor: pointer; font-size: 14px; transition: all 0.3s ease; text-align: left; }
    .options button:hover { background: #555; transform: translateY(-1px); box-shadow: 0 2px 8px rgba(0,255,255,0.2); }
    input { width: 100%; padding: 12px; margin-top: 15px; border: 2px solid #444; border-radius: 8px; background: #333; color: #fff; font-size: 16px; box-sizing: border-box; }
    input:focus { outline: none; border-color: #0ff; box-shadow: 0 0 10px rgba(0,255,255,0.3); }
    .completion { background: linear-gradient(45deg, #0ff, #0aa); color: #000; padding: 20px; border-radius: 8px; text-align: center; margin: 20px 0; font-weight: bold; }
    .legacy-code { font-size: 24px; margin: 15px 0; letter-spacing: 2px; }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
    .loading { color: #0ff; font-style: italic; }
    .loading::after { content: ''; animation: dots 1.5s infinite; }
    @keyframes dots { 0%, 20% { content: ''; } 40% { content: '.'; } 60% { content: '..'; } 80%, 100% { content: '...'; } }
  </style>
</head>
<body>
  <div class="chat-box" id="chat"></div>
  <script>
    const surveyFlow = [
      { question: "When you picture your future, which one gets you fired up the most?", options: ["🌴 More time freedom for adventures", "💰 Extra income (bye-bye money stress)", "🔄 Total career change (fresh chapter)", "🤝 Belonging to a mission-driven community", "✍️ Other"] },
      { question: "If building your future was a Netflix series, how many hours a week would you binge it?", options: ["🎬 3–5 hours (side hustle pilot season)", "📺 5–10 hours (mini-series)", "🍿 10–15 hours (serious season arc)", "🎥 15+ hours (full box set, I'm all in)"] },
      { question: "Every hero's got a storyline — which best describes yours so far?", options: ["✨ Total newbie (fresh chapter, blank page)", "😅 Tried before, but plot twist: it didn't work out", "🏆 Tried before and crushed it (looking for the sequel)"] },
      { question: "If I dropped a simple game plan in your lap today, when would you press play?", options: ["🚀 Right now, let's roll", "📆 Within 30 days", "⏳ 2–3 months out", "👀 Just exploring the trailer for now"] },
      { question: "On a 1–10 confidence scale, where are you right now?", options: ["1️⃣ 1","2️⃣ 2","3️⃣ 3","4️⃣ 4","5️⃣ 5","6️⃣ 6","7️⃣ 7","8️⃣ 8","9️⃣ 9","🔟 10"] },
      { question: "In a team setting, what lights you up the most?", options: ["🤝 Connecting & building relationships (Pearl)", "🎉 Recognition & being celebrated (Ruby)", "📊 Having clear systems & structure (Sapphire)", "💎 Hitting goals & building wealth (Emerald)"] }
    ];
    let answers = [], step = 0, currentEmail = '', currentPhone = '';
    function showBotMessage(msg) { document.getElementById("chat").innerHTML += '<div class="message bot">' + msg + '</div>'; document.getElementById("chat").scrollTop = document.getElementById("chat").scrollHeight; }
    function showUserMessage(msg) { document.getElementById("chat").innerHTML += '<div class="message user">' + msg + '</div>'; document.getElementById("chat").scrollTop = document.getElementById("chat").scrollHeight; }
    function showLoading() { document.getElementById("chat").innerHTML += '<div class="message loading" id="loading">ANGUS is thinking</div>'; document.getElementById("chat").scrollTop = document.getElementById("chat").scrollHeight; }
    function hideLoading() { const loadingDiv = document.getElementById('loading'); if (loadingDiv) loadingDiv.remove(); }
    function askNext() {
      if (step < surveyFlow.length) {
        showLoading();
        setTimeout(() => {
          hideLoading();
          let q = surveyFlow[step];
          showBotMessage('<strong>Question ' + (step + 1) + ' of 6:</strong><br><br>' + q.question);
          let optionsHTML = '<div class="options">';
          q.options.forEach(opt => {
            const escapedOpt = opt.replace(/'/g, "\\'");
            optionsHTML += '<button onclick="selectOption(\\''+escapedOpt+'\\')">' + opt + '</button>';
          });
          optionsHTML += '</div>';
          document.getElementById("chat").innerHTML += optionsHTML;
          document.getElementById("chat").scrollTop = document.getElementById("chat").scrollHeight;
        }, 1000);
      } else askForContact();
    }
    function selectOption(option) {
      document.querySelectorAll('.options').forEach(div => div.remove());
      showUserMessage(option);
      answers.push(option);
      step++;
      setTimeout(() => askNext(), 500);
    }
    function askForContact() {
      showLoading();
      setTimeout(() => {
        hideLoading();
        showBotMessage("Locked in! Last step — drop your best email:");
        document.getElementById("chat").innerHTML += '<input id="emailInput" type="email" placeholder="Enter your email address" onkeydown="if(event.key===\\'Enter\\'){saveEmail();}" autofocus>';
        document.getElementById("emailInput").focus();
      }, 1000);
    }
    function saveEmail() {
      const email = document.getElementById("emailInput").value.trim();
      if (!email || !/^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(email)) { alert("Please enter a valid email address"); return; }
      currentEmail = email;
      showUserMessage(email);
      document.getElementById("emailInput").remove();
      setTimeout(() => {
        showBotMessage("And your phone number:");
        document.getElementById("chat").innerHTML += '<input id="phoneInput" type="tel" placeholder="Enter your phone number" onkeydown="if(event.key===\\'Enter\\'){savePhone();}" autofocus>';
        document.getElementById("phoneInput").focus();
      }, 500);
    }
    function savePhone() {
      const phone = document.getElementById("phoneInput").value.trim();
      if (!phone) { alert("Please enter your phone number"); return; }
      currentPhone = phone;
      showUserMessage(phone);
      document.getElementById("phoneInput").remove();
      setTimeout(() => submitSurvey(), 500);
    }
    function submitSurvey() {
      showLoading();
      fetch("/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: currentEmail, phone: currentPhone, answers: answers })
      })
      .then(response => response.json())
      .then(data => {
        hideLoading();
        if (data.legacy_code) {
          const completionHTML = '<div class="completion"><h2>🎉 Boom! You\\'re officially in the game!</h2><div class="legacy-code">Your Legacy Code™: <strong>' + data.legacy_code + '</strong></div><p>Your personalized roadmap is being crafted by ANGUS™. Check your email in the next few minutes!</p><p style="margin-top: 15px; font-size: 14px;">Keep this code handy — you\\'ll need it to access your exclusive materials.</p></div>';
          document.getElementById("chat").innerHTML += completionHTML;
        } else showBotMessage("❌ Hmm, something went wrong. Can you try submitting again?");
      })
      .catch(error => { hideLoading(); console.error('Error:', error); showBotMessage("❌ Network error occurred. Please check your connection and try again."); });
    }
    window.onload = () => {
      showBotMessage("What\\'s up, legend?! I\\'m ANGUS™ — the strategist behind the curtain of The Real Brick Road™. My job? To hand you the playbook that works every single time. All I need is a few gut-punch honest answers. Don\\'t overthink it — just tap your choice and let\\'s roll.");
      setTimeout(() => askNext(), 2000);
    }
  </script>
</body>
</html>"""

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
    
    # ONLY change for Railway - use their PORT
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
