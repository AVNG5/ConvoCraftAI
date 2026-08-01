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
    1. Transcribes audio using Groq Whisper Large V3 with explicit language hints.
    2. Analyzes text using Groq Llama 3.3 70B to generate structured meeting insights in the requested target language.
    """
    try:
        # Map target languages to Whisper ISO language codes
        lang_code_map = {
            "English": "en",
            "Telugu": "te",
            "Hindi": "hi"
        }
        target_code = lang_code_map.get(language, "en")

        # 1. Transcribe Audio using Whisper-Large-V3
        with open(audio_file_path, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(os.path.basename(audio_file_path), file),
                model="whisper-large-v3",
                language=target_code,  # Direct language hint for Whisper
                response_format="text"
            )
        
        transcript_text = transcription

        # 2. Extract structured meeting intelligence using Llama 3.3 70B
        prompt = f"""
        You are ConvoCraft AI, an expert meeting assistant.
        Analyze the following transcript and extract structured insights based on these preferences:

        CRITICAL LANGUAGE REQUIREMENT:
        - Target Output Language: {language}
        - If Target Output Language is 'Telugu', write ALL text values in the JSON output (summary, key_decisions, action item tasks, next_agenda) strictly using Telugu script (తెలుగు).
        - If Target Output Language is 'Hindi', write ALL text values using Hindi script (हिंदी).

        User Preferences:
        - Summary Format: {summary_format}
        - Tone/Persona: {tone}
        - Custom Focus/Guidance: {custom_hint if custom_hint else 'None'}

        Transcript:
        "{transcript_text}"

        Strict Output Schema (JSON):
        Return ONLY a valid JSON object matching this exact structure without markdown backticks, code blocks, or extra prose:

        {{
          "summary": "Meeting summary adhering strictly to format, tone, and written in {language}",
          "key_decisions": ["Decision 1 in {language}", "Decision 2 in {language}"],
          "action_items": [
            {{
              "task": "Specific task description written in {language}",
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
            model="llama-3.3-70b-versatile",
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
