import os
import json
import streamlit as st
from groq import Groq
from dotenv import load_dotenv

# Load environment variables for local development
load_dotenv()

# Get API key from environment variable OR Streamlit secrets
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY and "GROQ_API_KEY" in st.secrets:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]

# Initialize Groq Client
client = Groq(api_key=GROQ_API_KEY)


def process_meeting_audio(
    audio_file_path: str,
    language: str = "English",
    summary_format: str = "Detailed",
    tone: str = "Technical",
    custom_hint: str = "",
) -> dict:
    """
    1. Transcribes audio using Groq Whisper Large V3 with auto-detection (prevents 500 errors).
    2. Translates and structures insights using Groq Llama 3.3 70B into target language.
    """
    try:
        # 1. Transcribe Audio using Whisper-Large-V3 (Auto-detect language to avoid Groq 500 errors)
        with open(audio_file_path, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(os.path.basename(audio_file_path), file),
                model="whisper-large-v3",
                response_format="text"
            )
        
        transcript_text = transcription

        # 2. Extract and translate structured meeting intelligence using Llama 3.3 70B
        prompt = f"""
        You are ConvoCraft AI, an expert multilingual meeting assistant.
        Analyze the following meeting transcript and produce the structured output strictly in the requested target language.

        LANGUAGE REQUIREMENT:
        - Target Output Language: {language}
        - If Target Output Language is 'Telugu', you MUST translate and write ALL text inside the JSON values (summary, key_decisions, tasks, next_agenda) in clean Telugu script (తెలుగు).
        - If Target Output Language is 'Hindi', write ALL text inside JSON values in Devanagari Hindi script (हिंदी).
        - If Target Output Language is 'English', write in English.

        USER PREFERENCES:
        - Summary Format: {summary_format}
        - Tone/Persona: {tone}
        - Custom Focus/Guidance: {custom_hint if custom_hint else 'None'}

        TRANSCRIPT:
        "{transcript_text}"

        STRICT OUTPUT SCHEMA (JSON):
        Return ONLY a valid JSON object matching this exact structure without markdown backticks, code blocks, or extra prose:

        {{
          "summary": "Full meeting summary adhering strictly to format, tone, and translated into {language}",
          "key_decisions": ["Key decision 1 in {language}", "Key decision 2 in {language}"],
          "action_items": [
            {{
              "task": "Specific task description in {language}",
              "assignee": "Person responsible or 'Unassigned'",
              "deadline": "YYYY-MM-DD or 'Not specified'",
              "priority": "High / Medium / Low"
            }}
          ],
          "next_agenda": ["Agenda item 1 in {language}", "Agenda item 2 in {language}"]
        }}
        """

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a precise AI meeting assistant that strictly outputs valid JSON objects."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )

        # Parse and return JSON response
        return json.loads(response.choices[0].message.content)

    except Exception as e:
        print(f"Error processing audio with Groq: {e}")
        return {
            "summary": f"Failed to process meeting audio with Groq. Error: {e}",
            "key_decisions": [],
            "action_items": [],
            "next_agenda": []
        }


def chat_with_meeting(summary_text: str, user_question: str) -> str:
    """
    Answers user questions based on the meeting summary and context using Groq Llama 3.3.
    """
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": "You are ConvoCraft AI, an intelligent meeting assistant. Answer the user's question accurately using ONLY the meeting details provided below. Keep your answers clear, professional, and concise."
                },
                {
                    "role": "user",
                    "content": f"Meeting Details:\n{summary_text}\n\nQuestion: {user_question}"
                }
            ],
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error answering question: {e}"
