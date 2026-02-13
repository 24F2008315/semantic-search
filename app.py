from fastapi import FastAPI
from pydantic import BaseModel
import requests
import sqlite3
from datetime import datetime
from openai import OpenAI
import os

app = FastAPI()
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

DB_FILE = "pipeline.db"

# ---------- Request Model ----------
class PipelineRequest(BaseModel):
    email: str
    source: str


# ---------- Database Setup ----------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original TEXT,
            analysis TEXT,
            sentiment TEXT,
            timestamp TEXT,
            source TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()


# ---------- Fetch UUID ----------
def fetch_uuid():
    try:
        response = requests.get("https://httpbin.org/uuid", timeout=5)
        response.raise_for_status()
        return response.json()["uuid"]
    except Exception as e:
        return {"error": str(e)}


# ---------- AI Enrichment ----------
def analyze_text(text):
    try:
        prompt = f"""
Text: {text}

1. Write a concise summary (1-2 sentences).
2. Classify sentiment as positive, negative, or neutral.

Respond in JSON:
{{"analysis": "...", "sentiment": "..."}}
"""
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )

        import json
        content = response.choices[0].message.content
        return json.loads(content)

    except Exception as e:
        return {"analysis": "AI processing failed", "sentiment": "neutral", "error": str(e)}


# ---------- Store in DB ----------
def store_result(original, analysis, sentiment, source):
    timestamp = datetime.utcnow().isoformat() + "Z"
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO results (original, analysis, sentiment, timestamp, source)
        VALUES (?, ?, ?, ?, ?)
    """, (original, analysis, sentiment, timestamp, source))
    conn.commit()
    conn.close()
    return timestamp


# ---------- API Endpoint ----------
@app.post("/pipeline")
def run_pipeline(request: PipelineRequest):

    items = []
    errors = []

    for _ in range(3):  # call API 3 times
        data = fetch_uuid()

        if isinstance(data, dict) and "error" in data:
            errors.append(data["error"])
            continue

        ai_result = analyze_text(data)

        timestamp = store_result(
            original=data,
            analysis=ai_result.get("analysis"),
            sentiment=ai_result.get("sentiment"),
            source=request.source
        )

        items.append({
            "original": data,
            "analysis": ai_result.get("analysis"),
            "sentiment": ai_result.get("sentiment"),
            "stored": True,
            "timestamp": timestamp
        })

    # Notification (console log mock)
    print(f"Notification sent to: {request.email}")
    print("Required notification recipient: 24f2008315@ds.study.iitm.ac.in")

    return {
        "items": items,
        "notificationSent": True,
        "processedAt": datetime.utcnow().isoformat() + "Z",
        "errors": errors
    }
