from pathlib import Path
import uuid
import logging
from decouple import config
from google.cloud import texttospeech
from google.oauth2 import service_account

logger = logging.getLogger(__name__)

AUDIO_FILES_DIR = Path("static/audio_files")
AUDIO_FILES_DIR.mkdir(exist_ok=True)

# Set up Google TTS
credentials = service_account.Credentials.from_service_account_file(config('GOOGLE_CREDENTIALS_FILE'))
tts_client = texttospeech.TextToSpeechClient(credentials=credentials)

voice = texttospeech.VoiceSelectionParams(
    language_code="en-US",
    name="en-US-Neural2-J",
    ssml_gender=texttospeech.SsmlVoiceGender.MALE
)

audio_config = texttospeech.AudioConfig(
    audio_encoding=texttospeech.AudioEncoding.MP3,
    speaking_rate=1.0,
    pitch=0.0
)

def text_to_speech(text):
    """Convert text to speech using Google TTS"""
    try:
        synthesis_input = texttospeech.SynthesisInput(text=text)
        response = tts_client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
        filename = f"tts_{uuid.uuid4()}.mp3"
        filepath = AUDIO_FILES_DIR / filename
        with open(filepath, "wb") as out:
            out.write(response.audio_content)
        logger.info(f"Text-to-Speech audio saved to {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"Error in Text-to-Speech: {e}")
        return None