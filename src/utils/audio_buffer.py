from pathlib import Path
from datetime import datetime
import wave
import json
import logging
from src.models.transcript import Transcript
from src.models.langgraph_state import LangGraphState
from src.api.routes import db

logger = logging.getLogger(__name__)

RECORDINGS_DIR = Path("static/call_recordings")
AUDIO_FILES_DIR = Path("static/audio_files")

class AudioBuffer:
    def __init__(self, call_sid):
        RECORDINGS_DIR.mkdir(exist_ok=True)
        self.chunks = []
        self.call_sid = call_sid
        self.file_path = RECORDINGS_DIR / f"{call_sid}_{datetime.now().strftime('%Y%m%d%H%M%S')}.wav"

    def add_chunk(self, chunk):
        """Add an audio chunk to the buffer"""
        if chunk:
            self.chunks.append(chunk)

    def save_to_file(self):
        """Save audio buffer to WAV file"""
        if not self.chunks:
            logger.info(f"No audio chunks to save for call {self.call_sid}")
            return None
        try:
            with wave.open(str(self.file_path), 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(8000)
                for chunk in self.chunks:
                    wf.writeframes(chunk)
            logger.info(f"Successfully saved recording to {self.file_path}")
            return str(self.file_path)
        except Exception as e:
            logger.error(f"Error saving audio file: {e}")
            return None

class CallSession:
    def __init__(self, call_sid, caller_phone=None):
        AUDIO_FILES_DIR.mkdir(exist_ok=True)
        self.call_sid = call_sid
        self.caller_phone = caller_phone
        self.start_time = datetime.now()
        self.audio_buffer = AudioBuffer(call_sid)
        self.state = None
        self.load_state()

    def load_state(self):
        """Load LangGraph state from database"""
        try:
            state_record = db.session.query(LangGraphState).filter_by(
                call_sid=self.call_sid, caller_phone=self.caller_phone
            ).order_by(LangGraphState.updated_at.desc()).first()
            if state_record:
                self.state = json.loads(state_record.state_json)
                logger.info(f"Loaded state for call {self.call_sid}")
        except Exception as e:
            logger.error(f"Error loading state: {e}")

    def save_state(self):
        """Save LangGraph state to database"""
        if self.state:
            try:
                state_record = LangGraphState(
                    call_sid=self.call_sid,
                    caller_phone=self.caller_phone or 'unknown',
                    state_json=json.dumps(self.state)
                )
                db.session.add(state_record)
                db.session.commit()
                logger.info(f"Saved state for call {self.call_sid}")
            except Exception as e:
                logger.error(f"Error saving state: {e}")
                db.session.rollback()

    def add_transcription(self, role, text):
        """Add a transcription entry to the database"""
        try:
            transcript = Transcript(
                call_sid=self.call_sid,
                role=role,
                text=text,
                timestamp=datetime.now()
            )
            db.session.add(transcript)
            db.session.commit()
            logger.info(f"[{role.upper()}]: {text}")
            return transcript
        except Exception as e:
            logger.error(f"Error saving transcript: {e}")
            db.session.rollback()
            return None

    def save_transcript(self):
        """Ensure all transcripts are saved"""
        audio_path = self.audio_buffer.save_to_file()
        if audio_path:
            logger.info(f"Call session completed and saved: {self.call_sid}")
        self.save_state()
        return audio_path