from flask import Flask, request, jsonify, send_file, render_template, redirect, url_for
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv

from io import BytesIO
import tempfile
import os
import time
import json
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import urlopen

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

SYSTEM_VIDEO_ANALYSIS_PROMPT = """
You are KHETFLIX Live Crop Video AI, a practical agricultural vision assistant for Indian farmers.

Analyze the current camera frame and the farmer's notes as if you are writing live captions beside a video.

Tone:
- Be direct, practical, and farmer-friendly.
- Keep the answer compact enough for a live caption panel.
- Do not claim certainty from one frame.
- If the image is unclear, say what angle or close-up is needed.

Safety rules:
- Never give a guaranteed diagnosis from video alone.
- If disease, pest, nutrient deficiency, water stress, or weather damage is possible, say the visible signs.
- For chemical treatment, tell the farmer to confirm local product and dose with an agriculture officer or label.

Output format:
LIVE CAPTION
- 2 to 3 short lines describing what is visible now.

CROP / WATER CHECK
- Crop or plant part seen:
- Growth stage:
- Water or soil condition:

POSSIBLE DISEASE / STRESS
- Issue:
- Confidence: Low / Medium / High
- Signs:
- Save alert: Yes / No

WHAT TO DO NOW
- 3 to 5 immediate practical steps.

MAX PROFIT IDEAS
- 4 crop-specific or field-specific ways to improve profit.
- Include grading, timing, direct sale, value addition, water saving, input cost control, or market route when relevant.

NEXT CAMERA VIEW
- Tell the farmer what to show next for a better answer.
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


@app.route("/video-analysis")
def video_analysis_page():
    return render_template("video_analysis.html")


@app.route("/scheme-finder")
def scheme_finder_page():
    return render_template("scheme_finder.html")


@app.route("/india-farm-map")
def india_farm_map_page():
    return render_template("india_farm_map.html")


INDIA_MAP_POINTS = {
    "soil": [
        {"name": "Punjab-Haryana alluvial belt", "lat": 30.9, "lng": 76.1, "quality": "High", "color": "#35d07f", "note": "Fertile alluvial soils; watch salinity and residue management.", "radius": 72000},
        {"name": "Indo-Gangetic plains", "lat": 26.85, "lng": 80.95, "quality": "High", "color": "#35d07f", "note": "Good wheat, rice, pulses, vegetables; benefits from organic matter addition.", "radius": 90000},
        {"name": "Black cotton soil zone", "lat": 20.6, "lng": 76.2, "quality": "Medium", "color": "#f2c94c", "note": "Deep clay soils for cotton, soybean, pulses; drainage is important.", "radius": 110000},
        {"name": "Red soil belt", "lat": 14.7, "lng": 78.5, "quality": "Medium", "color": "#f2994a", "note": "Often low in nitrogen and organic carbon; good response to compost and micronutrients.", "radius": 105000},
        {"name": "Coastal laterite zone", "lat": 12.9, "lng": 75.2, "quality": "Moderate", "color": "#ff7b7b", "note": "Acidic laterite soils; lime, mulch, and erosion control help.", "radius": 78000}
    ],
    "markets": [
        {"crop": "Tomato", "place": "Kolar, Karnataka", "lat": 13.14, "lng": 78.13, "demand": "High", "score": 88, "color": "#35d07f", "note": "Strong vegetable flow; grade carefully and avoid distress bulk selling."},
        {"crop": "Onion", "place": "Lasalgaon, Maharashtra", "lat": 20.14, "lng": 74.24, "demand": "High", "score": 91, "color": "#35d07f", "note": "Major onion hub; storage and timing can change returns sharply."},
        {"crop": "Cotton", "place": "Rajkot, Gujarat", "lat": 22.30, "lng": 70.80, "demand": "Medium", "score": 68, "color": "#f2c94c", "note": "Textile-linked demand; quality and moisture affect price."},
        {"crop": "Rice", "place": "Burdwan, West Bengal", "lat": 23.23, "lng": 87.86, "demand": "Medium", "score": 64, "color": "#f2c94c", "note": "Stable cereal demand; milling quality matters."},
        {"crop": "Wheat", "place": "Indore, Madhya Pradesh", "lat": 22.72, "lng": 75.86, "demand": "Medium", "score": 72, "color": "#f2c94c", "note": "Mandi and processor demand; protein and grain cleanliness help."},
        {"crop": "Banana", "place": "Jalgaon, Maharashtra", "lat": 21.01, "lng": 75.56, "demand": "High", "score": 84, "color": "#35d07f", "note": "Strong fruit supply chain; packaging and ripening links matter."}
    ],
    "mandis": [
        {"name": "Azadpur Mandi", "state": "Delhi", "lat": 28.71, "lng": 77.17, "type": "Fruit and vegetables"},
        {"name": "Lasalgaon APMC", "state": "Maharashtra", "lat": 20.14, "lng": 74.24, "type": "Onion"},
        {"name": "Kolar APMC", "state": "Karnataka", "lat": 13.14, "lng": 78.13, "type": "Vegetables"},
        {"name": "Unjha APMC", "state": "Gujarat", "lat": 23.80, "lng": 72.39, "type": "Spices and cumin"},
        {"name": "Guntur Mirchi Yard", "state": "Andhra Pradesh", "lat": 16.31, "lng": 80.44, "type": "Chilli"},
        {"name": "Indore Mandi", "state": "Madhya Pradesh", "lat": 22.72, "lng": 75.86, "type": "Grains and pulses"},
        {"name": "Vashi APMC", "state": "Maharashtra", "lat": 19.07, "lng": 73.00, "type": "Wholesale produce"},
        {"name": "Burdwan Rice Market", "state": "West Bengal", "lat": 23.23, "lng": 87.86, "type": "Rice"},
        {"name": "Coimbatore Market", "state": "Tamil Nadu", "lat": 11.01, "lng": 76.96, "type": "Cotton and vegetables"},
        {"name": "Ludhiana Mandi", "state": "Punjab", "lat": 30.90, "lng": 75.86, "type": "Grains and vegetables"}
    ],
    "weather_zones": [
        {"name": "Delhi NCR", "lat": 28.61, "lng": 77.20},
        {"name": "Ludhiana", "lat": 30.90, "lng": 75.86},
        {"name": "Lucknow", "lat": 26.85, "lng": 80.95},
        {"name": "Patna", "lat": 25.59, "lng": 85.14},
        {"name": "Kolkata", "lat": 22.57, "lng": 88.36},
        {"name": "Guwahati", "lat": 26.14, "lng": 91.74},
        {"name": "Ahmedabad", "lat": 23.02, "lng": 72.57},
        {"name": "Indore", "lat": 22.72, "lng": 75.86},
        {"name": "Nagpur", "lat": 21.15, "lng": 79.09},
        {"name": "Hyderabad", "lat": 17.39, "lng": 78.49},
        {"name": "Bengaluru", "lat": 12.97, "lng": 77.59},
        {"name": "Chennai", "lat": 13.08, "lng": 80.27},
        {"name": "Kochi", "lat": 9.93, "lng": 76.27},
        {"name": "Jaipur", "lat": 26.91, "lng": 75.79}
    ]
}


def fetch_weather_snapshot(points):
    query = urlencode({
        "latitude": ",".join(str(point["lat"]) for point in points),
        "longitude": ",".join(str(point["lng"]) for point in points),
        "current": "temperature_2m,relative_humidity_2m,precipitation",
        "daily": "precipitation_sum",
        "forecast_days": 1,
        "timezone": "Asia/Kolkata"
    })

    url = f"https://api.open-meteo.com/v1/forecast?{query}"

    try:
        with urlopen(url, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None

    if isinstance(payload, dict):
        payload = [payload]

    return payload


def build_weather_layers():
    zones = INDIA_MAP_POINTS["weather_zones"]
    weather_payload = fetch_weather_snapshot(zones)

    water = []
    disease = []

    for index, zone in enumerate(zones):
        current = {}
        daily = {}

        if weather_payload and index < len(weather_payload):
            current = weather_payload[index].get("current", {}) or {}
            daily = weather_payload[index].get("daily", {}) or {}

        temp = current.get("temperature_2m")
        humidity = current.get("relative_humidity_2m")
        rain_now = current.get("precipitation") or 0
        rain_sum = (daily.get("precipitation_sum") or [0])[0] if daily else 0

        if rain_sum >= 8 or rain_now >= 2:
            water_level = "Good"
            water_color = "#35d07f"
            water_note = "Rain signal is supportive; avoid over-irrigation and check drainage."
        elif rain_sum >= 1:
            water_level = "Moderate"
            water_color = "#f2c94c"
            water_note = "Light rain signal; irrigate based on soil moisture, not calendar."
        else:
            water_level = "Low"
            water_color = "#ff7b7b"
            water_note = "Low rain signal; prioritize mulching, drip timing, and moisture checks."

        risk = "Low"
        risk_color = "#35d07f"
        risk_note = "No strong weather-driven pest or disease trigger in this snapshot."

        if humidity and humidity >= 78 and rain_sum >= 1:
            risk = "High"
            risk_color = "#ff4d4d"
            risk_note = "Humid/rainy conditions can raise fungal disease pressure."
        elif temp and temp >= 34 and rain_sum < 1:
            risk = "Medium"
            risk_color = "#f2994a"
            risk_note = "Hot and dry conditions can increase mite, sucking pest, and water-stress risk."
        elif humidity and humidity >= 68:
            risk = "Medium"
            risk_color = "#f2c94c"
            risk_note = "Humidity is enough to justify closer leaf and stem checks."

        weather_text = (
            f"{temp if temp is not None else '--'} C, "
            f"{humidity if humidity is not None else '--'}% humidity, "
            f"{rain_sum if rain_sum is not None else '--'} mm rain forecast"
        )

        water.append({
            **zone,
            "level": water_level,
            "color": water_color,
            "note": water_note,
            "weather": weather_text
        })

        disease.append({
            **zone,
            "risk": risk,
            "color": risk_color,
            "note": risk_note,
            "weather": weather_text
        })

    return water, disease


@app.route("/api/india-farm-map")
def india_farm_map_data():
    water, disease = build_weather_layers()

    return jsonify({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "country": "India",
        "source_note": (
            "Weather-derived water and pest indicators use Open-Meteo. "
            "Soil, market, and mandi markers are practical reference points and should be verified locally."
        ),
        "layers": {
            "soil": INDIA_MAP_POINTS["soil"],
            "water": water,
            "markets": INDIA_MAP_POINTS["markets"],
            "disease": disease,
            "mandis": INDIA_MAP_POINTS["mandis"]
        }
    })


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


def analyze_video_frame(description, image_data_url):
    farmer_context = description.strip() or "No extra farmer notes were provided."

    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_VIDEO_ANALYSIS_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Farmer notes:\n"
                            f"{farmer_context}\n\n"
                            "Analyze this live camera frame. Give caption-style crop health, disease/stress, "
                            "water condition, and profit guidance using the required format."
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
        temperature=0.3,
        max_tokens=1300
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


@app.route("/analyze-video-frame", methods=["POST"])
def analyze_video_frame_route():
    try:
        if "image" not in request.files:
            return jsonify({"error": "camera frame missing"}), 400

        description = request.form.get("description", "").strip()
        image_data_url = encode_uploaded_image(request.files["image"])
        analysis = analyze_video_frame(description, image_data_url)

        save_alert = "save alert: yes" in analysis.lower()

        return jsonify({
            "type": "video_crop_analysis",
            "response": analysis,
            "save_alert": save_alert,
            "analyzed_at": datetime.now(timezone.utc).isoformat()
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    except Exception as e:
        print("VIDEO ANALYSIS ERROR:", str(e))
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
