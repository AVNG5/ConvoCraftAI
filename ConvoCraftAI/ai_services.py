import os
import json
import streamlit as st
from groq import Groq
from dotenv import load_dotenv

# Load environment variables (for local development)
load_dotenv()

# Safely retrieve the Groq API key across local (.env) and Streamlit Cloud (st.secrets)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    try:
        GROQ_API_KEY = st.secrets.get("GROQ_API_KEY")
    except Exception:
        GROQ_API_KEY = None

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
    1. Transcribes audio using Groq Whisper Large V3.
    2. Analyzes text using Groq GPT-OSS 20B to generate structured meeting insights.
    """
    try:
        # 1. Transcribe Audio using Whisper-Large-V3
        with open(audio_file_path, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(os.path.basename(audio_file_path), file.read()),
                model="whisper-large-v3",
                response_format="text"
            )
        
        transcript_text = transcription

        # 2. Extract structured meeting intelligence using GPT-OSS 20B
        prompt = f"""
        You are ConvoCraft AI, an expert meeting assistant.
        Analyze the following transcript and extract structured insights based on these preferences:

        User Preferences:
        - Target Output Language: {language} (Provide ALL summary text and extracted items in {language})
        - Summary Format: {summary_format}
        - Tone/Persona: {tone}
        - Custom Focus/Guidance: {custom_hint if custom_hint else 'None'}

        Transcript:
        "{transcript_text}"

        Strict Output Schema (JSON):
        Return ONLY a valid JSON object matching this exact structure without markdown backticks, code blocks, or extra prose:

        {{
          "summary": "String (Meeting summary adhering strictly to format, tone, and language)",
          "key_decisions": ["Decision 1", "Decision 2"],
          "action_items": [
            {{
              "task": "Specific task description",
              "assignee": "Person responsible or 'Unassigned'",
              "deadline": "YYYY-MM-DD or 'Not specified'",
              "priority": "High / Medium / Low"
            }}
          ],
          "next_agenda": ["Agenda item 1", "Agenda item 2"]
        }}
        """

        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": "You are a precise AI meeting assistant that strictly outputs JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )

        # Parse JSON response
        result = json.loads(response.choices[0].message.content)
        result["success"] = True
        return result

    except Exception as e:
        print(f"Error processing audio with Groq: {e}")
        return {
            "success": False,
            "error": str(e),
            "summary": "",
            "key_decisions": [],
            "action_items": [],
            "next_agenda": []
        }


def chat_with_meeting(summary_text: str, user_question: str) -> str:
    """
    Answers user questions based on the meeting summary and context using Groq GPT-OSS 20B.
    """
    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
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
