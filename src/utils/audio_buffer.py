import json
from datetime import datetime
from pathlib import Path
import wave
import logging
from src.models.transcript import Transcript
from src.models.langgraph_state import LangGraphState
from src.models.call import Call
from src.db import db

logger = logging.getLogger(__name__)

RECORDINGS_DIR = Path("static/call_recordings")
RECORDINGS_DIR.mkdir(exist_ok=True)

class CallSession:
    def __init__(self, call_sid, caller_phone=None):
        self.call_sid = call_sid
        self.caller_phone = caller_phone
        self.start_time = datetime.now()
        self.audio_buffer = AudioBuffer(call_sid)
        self.transcriptions = []  # Renamed to plural for clarity
        self.state = {}
        # Initialize call_id by querying the Call model
        call = db.session.query(Call).filter_by(call_sid=call_sid).first()
        if not call:
            logger.error(f"No Call record found for call_sid: {call_sid}")
            self.call_id = None
        else:
            self.call_id = call.id
            logger.info(f"Initialized CallSession with call_id: {call.id} for call_sid: {call_sid}")

    def add_transcription(self, role, text):
        entry = {
            'role': role,
            'text': text,
            'timestamp': datetime.now().isoformat()
        }
        self.transcriptions.append(entry)
        logger.info(f"[{role.upper()}]: {text}")

        if self.call_id:
            transcript = Transcript(
                call_id=self.call_id,
                role=role,
                text=text,
                timestamp=datetime.now()
            )
            db.session.add(transcript)
            try:
                db.session.commit()
                logger.info(f"Saved transcript to database for call_id {self.call_id}: {text}")
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error saving transcript to database: {e}")
        else:
            logger.warning(f"Cannot save transcript to database: No call_id for call_sid {self.call_sid}")

        return entry

    def save_transcript(self):
        if not self.transcriptions:
            logger.info(f"No transcriptions to save for call {self.call_sid}")
            return None

        # Save to JSON file (optional, can be removed if database is primary storage)
        transcript_path = RECORDINGS_DIR / f"{self.call_sid}_transcript.json"
        try:
            with open(transcript_path, 'w') as f:
                json.dump(self.transcriptions, f, indent=2)
            logger.info(f"Saved transcript to {transcript_path}")
        except Exception as e:
            logger.error(f"Error saving transcript to file: {e}")

        audio_path = self.audio_buffer.save_to_file()
        if audio_path:
            logger.info(f"Call session completed and saved: {self.call_sid}")
        return transcript_path

    def save_state(self):
        if not self.call_id:
            logger.error(f"No call_id found for call_sid: {self.call_sid}")
            return
        if not self.state:
            logger.info(f"No state to save for call_sid: {self.call_sid}")
            return
        try:
            state_record = db.session.query(LangGraphState).filter_by(call_id=self.call_id).first()
            if state_record:
                state_record.state = self.state
            else:
                state_record = LangGraphState(call_id=self.call_id, state=self.state)
                db.session.add(state_record)
            db.session.commit()
            logger.info(f"Saved LangGraph state for call_id {self.call_id}: {self.state}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error saving LangGraph state: {e}")

class AudioBuffer:
    def __init__(self, call_sid):
        self.chunks = []
        self.call_sid = call_sid
        self.file_path = RECORDINGS_DIR / f"{call_sid}_{datetime.now().strftime('%Y%m%d%H%M%S')}.wav"

    def add_chunk(self, chunk):
        if chunk:
            self.chunks.append(chunk)

    def save_to_file(self):
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