from flask import Flask, request, jsonify, send_file, render_template, redirect, url_for
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv

from io import BytesIO
import tempfile
import os
import time

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer
)

from reportlab.lib.styles import getSampleStyleSheet
import base64

# ---------------- LOAD ----------------

load_dotenv()

app = Flask(__name__)

CORS(app)

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

# ---------------- MEMORY ----------------

sessions = {}

# ── FIX 1: Session cleanup to prevent memory leak ──────────────────────────
# Sessions older than 2 hours are purged automatically

SESSION_TTL = 7200  # seconds

def cleanup_sessions():
    now = time.time()
    expired = [
        sid for sid, s in sessions.items()
        if now - s.get("created_at", now) > SESSION_TTL
    ]
    for sid in expired:
        del sessions[sid]


# ---------------- QUESTIONS ----------------

QUESTIONS = {

    "English": [

        "What is your land location (district/state)?",
        "What type of soil do you have?",
        "How many acres of land do you own?",
        "What is your water source (borewell/rain/river)?",
        "How much water is available per day?",
        "What season are you planning to farm in?",
        "What is your budget for this crop cycle?",
        "Do you prefer organic or chemical farming?",
        "Have you grown crops before? If yes, which ones?",
        "Any past crop failures or issues?",
        "What is your market access (local/mandi/online)?",
        "Any pest or disease issues in past?",
        "Do you have labor available?",
        "Do you want short-term profit or long-term profit?"
    ],

    "Kannada": [

        "ನಿಮ್ಮ ಜಮೀನು ಯಾವ ಜಿಲ್ಲೆ/ರಾಜ್ಯದಲ್ಲಿ ಇದೆ?",
        "ನಿಮ್ಮ ಮಣ್ಣಿನ ಪ್ರಕಾರ ಏನು?",
        "ನಿಮ್ಮ ಬಳಿ ಎಷ್ಟು ಎಕರೆ ಜಮೀನು ಇದೆ?",
        "ನಿಮ್ಮ ನೀರಿನ ಮೂಲ ಏನು? (ಬೋರ್‌ವೆಲ್/ಮಳೆ/ನದಿ)",
        "ಪ್ರತಿದಿನ ಎಷ್ಟು ನೀರು ಲಭ್ಯವಿದೆ?",
        "ಯಾವ ಹಂಗಾಮಿನಲ್ಲಿ ಕೃಷಿ ಮಾಡಲು ಯೋಜಿಸುತ್ತಿದ್ದೀರಿ?",
        "ಈ ಬೆಳೆ ಚಕ್ರಕ್ಕೆ ನಿಮ್ಮ ಬಜೆಟ್ ಎಷ್ಟು?",
        "ನೀವು ಸಸ್ಯಸಹಜ ಅಥವಾ ರಾಸಾಯನಿಕ ಕೃಷಿಯನ್ನು ಇಷ್ಟಪಡುತ್ತೀರಾ?",
        "ಈ ಮೊದಲು ಯಾವ ಬೆಳೆಗಳನ್ನು ಬೆಳೆದಿದ್ದೀರಿ?",
        "ಹಿಂದೆ ಬೆಳೆ ವಿಫಲವಾದ ಅನುಭವ ಇದೆಯೆ?",
        "ನಿಮ್ಮ ಮಾರುಕಟ್ಟೆ ಪ್ರವೇಶ ಯಾವ ರೀತಿಯದು?",
        "ಹಿಂದೆ ಕೀಟ ಅಥವಾ ರೋಗ ಸಮಸ್ಯೆಗಳಿದ್ದವೆಯೆ?",
        "ನಿಮ್ಮ ಬಳಿ ಕಾರ್ಮಿಕರ ಸಹಾಯ ಇದೆಯೆ?",
        "ನೀವು ಅಲ್ಪಾವಧಿ ಅಥವಾ ದೀರ್ಘಾವಧಿ ಲಾಭ ಬಯಸುತ್ತೀರಾ?"
    ],

    "Hindi": [

        "आपकी जमीन किस जिला/राज्य में है?",
        "आपकी मिट्टी का प्रकार क्या है?",
        "आपके पास कितने एकड़ जमीन है?",
        "आपका पानी का स्रोत क्या है?",
        "प्रतिदिन कितना पानी उपलब्ध है?",
        "आप किस मौसम में खेती करना चाहते हैं?",
        "इस फसल चक्र के लिए आपका बजट कितना है?",
        "क्या आप जैविक या रासायनिक खेती पसंद करते हैं?",
        "क्या आपने पहले कोई फसल उगाई है?",
        "क्या पहले कोई फसल खराब हुई थी?",
        "आपकी मार्केट पहुँच कैसी है?",
        "क्या पहले कीट या रोग की समस्या हुई थी?",
        "क्या आपके पास मजदूर उपलब्ध हैं?",
        "क्या आप कम समय का या लंबे समय का लाभ चाहते हैं?"
    ],

    "Tamil": [

        "உங்கள் நிலம் எந்த மாவட்டம்/மாநிலத்தில் உள்ளது?",
        "உங்கள் மண் வகை என்ன?",
        "உங்களிடம் எத்தனை ஏக்கர் நிலம் உள்ளது?",
        "உங்கள் நீர் மூலம் என்ன?",
        "ஒரு நாளுக்கு எவ்வளவு தண்ணீர் கிடைக்கிறது?",
        "எந்த பருவத்தில் விவசாயம் செய்ய திட்டமிடுகிறீர்கள்?",
        "இந்த பயிர் சுழற்சிக்கான உங்கள் பட்ஜெட் என்ன?",
        "நீங்கள் இயற்கை அல்லது இரசாயன விவசாயத்தை விரும்புகிறீர்களா?",
        "முன்பு எந்த பயிர்களை வளர்த்துள்ளீர்கள்?",
        "முன்பு பயிர் தோல்வி ஏற்பட்டதா?",
        "உங்கள் சந்தை அணுகல் எப்படி உள்ளது?",
        "முன்பு பூச்சி அல்லது நோய் பிரச்சனை இருந்ததா?",
        "உங்களிடம் தொழிலாளர்கள் உள்ளனரா?",
        "குறுகிய கால அல்லது நீண்ட கால லாபம் வேண்டுமா?"
    ]
}

for question_list in QUESTIONS.values():
    if len(question_list) < 15:
        question_list.append(
            "Do you have storage, transport, packaging, or processing options after harvest?"
        )

# ---------------- SYSTEM PROMPT ----------------

SYSTEM_CROP_PROMPT = """
You are KHETFLIX AI, a practical agricultural planning assistant for Indian farmers.

Tone:
- Be clear, structured, and human.
- Do not be chatty.
- Use short headings, numbered lists, and field-ready language.
- Continue in the farmer's selected language when possible.
- If exact numbers are uncertain, give practical ranges and say they depend on local market, seed, weather, and management.

Workflow:
1. The app asks exactly 15 farmer-profile questions.
2. After those 15 answers, suggest exactly 15 crop options.
3. Do NOT give a full roadmap at the crop-options stage.
4. Ask the farmer to choose one crop by name or number.
5. After the farmer chooses one crop, give the full roadmap.

Crop-options output format after the 15 answers:
Title: 15 Crop Options for Your Farm
For each crop, use exactly this structure:
1. Crop name
   - Why it fits:
   - Profit potential:
   - Main risk:
   - Best selling route:
End with: "Choose one crop by number or name, and I will make the full phase-wise roadmap."

Roadmap output format after crop selection:
Title: Full Farming Roadmap for [Crop]

1. Farm Fit Summary
- Why this crop fits the farmer profile
- Expected investment range
- Expected yield range
- Expected selling window

2. Phase-wise Roadmap
Phase 1: Planning and Land Preparation
- Time:
- Actions:
- Inputs needed:
- Cost control tip:

Phase 2: Soil, Seed, and Planting
- Time:
- Actions:
- Inputs needed:
- Mistakes to avoid:

Phase 3: Irrigation and Nutrition
- Time:
- Water plan:
- Fertilizer/manure plan:
- Monitoring checklist:

Phase 4: Pest, Disease, and Weather Risk
- Common risks:
- Early warning signs:
- Organic/low-cost prevention:
- Chemical control caution:

Phase 5: Harvest and Post-harvest Handling
- Harvest signs:
- Sorting/grading:
- Storage/transport:
- Quality protection:

Phase 6: Selling and Profit Improvement
- Where to sell:
- How to negotiate:
- Best timing:
- Record keeping:

3. Do's
- Give 8 practical do's.

4. Don'ts
- Give 8 practical don'ts.

5. Profit Boost Ideas
- Explain value addition and smarter selling.
- Include crop-specific examples. Example: for strawberry, sell graded berries in small branded boxes, supply cafes/bakeries, make jam/pulp, offer farm-pick experiences, and sell premium clean packaging instead of only loose bulk sale.
- Include packaging, grading, direct selling, local partnerships, processing, storage, and waste reduction ideas where relevant.

6. Weekly Farmer Checklist
- Week-by-week or stage-by-stage checklist.

7. Final Practical Advice
- 5 concise lines only.
"""

SYSTEM_PROGRESSIVE_FEEDBACK_PROMPT = """
You are KHETFLIX Progressive Feedback AI, an agricultural vision assistant for Indian farmers.

Analyze the uploaded crop image together with the farmer's description. Give practical field guidance.

Tone:
- Be human, direct, and structured.
- Do not sound like a generic AI report.
- Use short practical lines a farmer can act on.

Safety rules:
- Do not claim certainty from image alone.
- If disease, pest, nutrient deficiency, water stress, or weather damage is possible, say what visual signs suggest it.
- Ask for local extension officer/lab confirmation when chemical treatment or severe disease is suspected.
- If the image is unclear, say exactly what better photo is needed.

Output format:
Title: Crop Health Feedback

1. What I Can See
- 3 to 5 simple observations from the image.

2. Most Likely Issue
- Name the likely issue.
- Confidence: Low / Medium / High.
- Why I think so:

3. What To Do Today
- 4 to 6 immediate steps for the next 24-48 hours.

4. Treatment Options
Organic / low-cost:
- Practical options.
Chemical caution:
- Only suggest broad caution-based guidance.
- Tell farmer to confirm local dose and product with an agriculture officer or label.

5. Do's
- 5 practical do's.

6. Don'ts
- 5 practical don'ts.

7. How To Stop It Spreading
- Field hygiene, water, spacing, removal, monitoring.

8. Send Next Photo Like This
- Tell exactly what photo and details to send next.
"""

# ---------------- HELPERS ----------------

def create_session():
    return {
        "language": None,
        "step": 0,
        "answers": [],
        "history": [],
        "crop_recommendation_done": False,
        "final_report": None,
        "created_at": time.time()   # FIX 1: track creation time for TTL cleanup
    }


def speech_to_text(audio_path):
    with open(audio_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
    return transcript.text


def text_to_speech(text):
    response = client.audio.speech.create(
        model="tts-1",          # FIX 2: was "gpt-4o-mini-tts" — invalid model name
        voice="nova",
        input=text
    )
    audio_bytes = BytesIO(response.content)
    audio_bytes.seek(0)
    return audio_bytes


# ---------------- ROOT ----------------

@app.route("/")
def index_page():
    return render_template("index.html")


@app.route("/status")
def status():
    return jsonify({"status": "running"})


@app.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "POST":
        return redirect(url_for("home_page"))
    return render_template("login.html")


@app.route("/home")
def home_page():
    return render_template("home.html")


@app.route("/chatbot")
def chatbot_page():
    return render_template("chatbot.html")


@app.route("/voicebot")
def voicebot_page():
    return render_template("voicebot.html")


@app.route("/progressive-feedback")
def progressive_feedback_page():
    return render_template("progressive_feedback.html")


@app.route("/scheme-finder")
def scheme_finder_page():
    return render_template("scheme_finder.html")


def encode_uploaded_image(image_file):
    allowed_types = {
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/webp"
    }

    mimetype = image_file.mimetype or ""

    if mimetype not in allowed_types:
        raise ValueError("Please upload a PNG, JPG, JPEG, or WEBP crop image.")

    image_bytes = image_file.read()

    if not image_bytes:
        raise ValueError("Uploaded image is empty.")

    max_size = 12 * 1024 * 1024
    if len(image_bytes) > max_size:
        raise ValueError("Image is too large. Please upload an image below 12 MB.")

    encoded = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mimetype};base64,{encoded}"


def analyze_crop_image(description, image_data_url):
    farmer_context = description.strip()

    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROGRESSIVE_FEEDBACK_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Farmer description:\n"
                            f"{farmer_context}\n\n"
                            "Analyze this crop photo using the required Crop Health Feedback format. "
                            "Keep it human, practical, and structured."
                        )
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_data_url,
                            "detail": "high"
                        }
                    }
                ]
            }
        ],
        temperature=0.35,
        max_tokens=1800
    )

    return completion.choices[0].message.content


# ---------------- CHAT ENGINE ----------------

def process_chat(session_id, user_message):

    # Run cleanup on every request (lightweight)
    cleanup_sessions()                          # FIX 1: prevent memory leak

    if session_id not in sessions:
        sessions[session_id] = create_session()

    session = sessions[session_id]

    # START
    if user_message.lower().strip() == "start":
        return {
            "type": "question",
            "response":
            "Please select your preferred language:\nEnglish / Kannada / Hindi / Tamil"
        }

    # LANGUAGE SELECTION
    if session["language"] is None:

        # FIX 3: normalize input — strip whitespace + title-case to handle
        # "english", "ENGLISH", " kannada ", etc.
        lang = user_message.strip().title()

        # "Tamil" → "Tamil" ✅  "HINDI" → "Hindi" ✅  "kannada " → "Kannada" ✅
        if lang not in QUESTIONS:
            return {
                "type": "question",
                "response":
                "Invalid language. Please choose one of:\nEnglish / Kannada / Hindi / Tamil"
            }

        session["language"] = lang

        first_question = QUESTIONS[lang][0]

        session["history"].append({
            "role": "assistant",
            "content": first_question
        })

        return {
            "type": "question",
            "response": first_question
        }

    # SAVE USER ANSWER
    session["history"].append({
        "role": "user",
        "content": user_message
    })

    # QUESTION FLOW
    if not session["crop_recommendation_done"]:

        session["answers"].append(user_message)

        # FIX 4: read step BEFORE incrementing to avoid off-by-one index error.
        # Old code did step += 1 then used step as index → skipped Q1, crashed on last Q.
        current_step = session["step"]
        session["step"] += 1
        next_step     = session["step"]

        # MORE QUESTIONS REMAIN
        if next_step < len(QUESTIONS[session["language"]]):

            next_question = QUESTIONS[session["language"]][next_step]

            session["history"].append({
                "role": "assistant",
                "content": next_question
            })

            return {
                "type": "question",
                "response": next_question
            }

        # ALL QUESTIONS ANSWERED — build profile & call AI
        profile = f"Language: {session['language']}\n"

        for i in range(len(session["answers"])):
            profile += (
                f"\nQuestion: {QUESTIONS[session['language']][i]}"
                f"\nAnswer: {session['answers'][i]}\n"
            )

        recommendation_request = (
            "The farmer has now answered all 15 profile questions.\n"
            "Return only the structured list of exactly 15 crop options using the required crop-options format.\n"
            "Do not generate the full roadmap yet.\n\n"
            f"{profile}"
        )

        completion = client.chat.completions.create(
            model="gpt-4o-mini",        # FIX 5: was "gpt-4.1-mini" — does not exist
            messages=[
                {"role": "system", "content": SYSTEM_CROP_PROMPT},
                {"role": "user",   "content": recommendation_request}
            ],
            temperature=0.45,
            max_tokens=2600
        )

        ai_response = completion.choices[0].message.content

        session["history"].append({
            "role": "assistant",
            "content": ai_response
        })

        session["crop_recommendation_done"] = True

        return {
            "type": "crop_list",
            "response": ai_response
        }

    # CROP SELECTED — generate full roadmap
    selected_crop_request = {
        "role": "user",
        "content": (
            "The farmer has selected this crop from the 15 options:\n"
            f"{user_message}\n\n"
            "Now generate the complete phase-wise roadmap using the required roadmap output format. "
            "Be structured, practical, and not chatty."
        )
    }

    completion = client.chat.completions.create(
        model="gpt-4o-mini",            # FIX 5: same invalid model fix
        messages=[
            {"role": "system", "content": SYSTEM_CROP_PROMPT},
            *session["history"][-20:],
            selected_crop_request
        ],
        temperature=0.45,
        max_tokens=4200
    )

    ai_response = completion.choices[0].message.content

    session["history"].append({
        "role": "assistant",
        "content": ai_response
    })

    # FIX 6: always update final_report so PDF is available immediately after roadmap
    session["final_report"] = ai_response

    return {
        "type": "final_roadmap",
        "response": ai_response
    }


# ---------------- TEXT CHAT ----------------

@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()

        user_message = data.get("message", "").strip()
        session_id   = data.get("session_id", "").strip()

        if not session_id:
            return jsonify({"error": "session_id required"}), 400

        if not user_message:
            return jsonify({"error": "message cannot be empty"}), 400

        result = process_chat(session_id, user_message)
        return jsonify(result)

    except Exception as e:
        print("CHAT ERROR:", str(e))
        return jsonify({"error": str(e)}), 500


# ---------------- VOICE CHAT ----------------

@app.route("/voice-chat", methods=["POST"])
def voice_chat():

    audio_path = None   # FIX 7: initialize before try so finally block is safe

    try:
        if "audio" not in request.files:
            return jsonify({"error": "audio missing"}), 400

        session_id = request.form.get("session_id", "").strip()

        if not session_id:
            return jsonify({"error": "session_id missing"}), 400

        audio_file = request.files["audio"]

        # SAVE TEMP AUDIO
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".webm"
        ) as temp_audio:
            audio_path = temp_audio.name
            audio_file.save(audio_path)

        # STT
        user_text = speech_to_text(audio_path)
        print("USER:", user_text)

        # CHAT PROCESS
        result    = process_chat(session_id, user_text)
        ai_text   = result["response"]

        # TTS
        audio_response = text_to_speech(ai_text)

        return send_file(
            audio_response,
            mimetype="audio/mpeg",
            as_attachment=False
        )

    except Exception as e:
        print("VOICE ERROR:", str(e))
        return jsonify({"error": str(e)}), 500

    finally:
        # FIX 7: always clean up temp file even if STT/TTS throws
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)


# ---------------- PROGRESSIVE FEEDBACK ----------------

@app.route("/analyze-crop", methods=["POST"])
def analyze_crop():
    try:
        if "image" not in request.files:
            return jsonify({"error": "crop image missing"}), 400

        description = request.form.get("description", "").strip()

        if len(description) < 12:
            return jsonify({
                "error": "Please describe the crop, symptoms, location, age, and recent weather or spraying."
            }), 400

        image_data_url = encode_uploaded_image(request.files["image"])
        analysis = analyze_crop_image(description, image_data_url)

        return jsonify({
            "type": "progressive_feedback",
            "response": analysis
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    except Exception as e:
        print("PROGRESSIVE FEEDBACK ERROR:", str(e))
        return jsonify({"error": str(e)}), 500


# ---------------- PDF ----------------

@app.route("/download_pdf", methods=["POST"])
def download_pdf():
    try:
        data       = request.get_json()
        session_id = data.get("session_id", "").strip()

        if session_id not in sessions:
            return jsonify({"error": "Invalid session"}), 400

        session = sessions[session_id]

        # FIX 6: guard — final_report may not exist yet
        if not session.get("final_report"):
            return jsonify({
                "error": "No farming report generated yet. "
                         "Please complete crop selection first."
            }), 400

        buffer = BytesIO()
        doc    = SimpleDocTemplate(buffer)
        styles = getSampleStyleSheet()

        content = [
            Paragraph("Khetflix AI Farming Report", styles["Title"]),
            Spacer(1, 20),
            Paragraph(
                session["final_report"].replace("\n", "<br/>"),
                styles["BodyText"]
            )
        ]

        doc.build(content)
        buffer.seek(0)

        return send_file(
            buffer,
            as_attachment=True,
            download_name="khetflix_report.pdf",
            mimetype="application/pdf"
        )

    except Exception as e:
        print("PDF ERROR:", str(e))
        return jsonify({"error": str(e)}), 500


# ---------------- RESET ----------------

@app.route("/reset", methods=["POST"])
def reset():
    try:
        data       = request.get_json()
        session_id = data.get("session_id", "").strip()

        if session_id in sessions:
            del sessions[session_id]

        return jsonify({"message": "reset successful"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------- RUN ----------------

if __name__ == "__main__":
    app.run(
        debug=True,
        threaded=True,
        host="0.0.0.0",
        port=5000
    )
