from flask import Flask, Response, request
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client
import logging
import os
import time
import threading
from datetime import datetime
from pathlib import Path
from src.utils.logging import setup_logging
from src.utils.audio_buffer import CallSession
from src.services.twilio_service import text_to_speech
from src.services.workflow_service import process_text
from src.models.call import Call
from src.models.base import Base
from src.db import db
from decouple import config
from sqlalchemy.sql import text

setup_logging()
logger = logging.getLogger(__name__)
logger.info(f"Loaded OPENAI_API_KEY: {os.getenv('OPENAI_API_KEY')}")

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = config('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize db with the Flask app
db.init_app(app)

# Import models
from src.models.call import Call
from src.models.booking import Booking
from src.models.transcript import Transcript
from src.models.langgraph_state import LangGraphState

twilio_client = Client(config('TWILIO_ACCOUNT_SID'), config('TWILIO_AUTH_TOKEN'))

# Create tables and log database connection
with app.app_context():
    logger.info(f"Connected to database: {db.engine.url.database}")
    logger.info("Attempting to create database tables")
    try:
        db.create_all()
        logger.info("Tables created successfully")
        logger.info(f"Created tables: {Base.metadata.tables.keys()}")
    except Exception as e:
        logger.error(f"Failed to create tables: {str(e)}")

active_calls = {}

AUDIO_FILES_DIR = Path("static/audio_files")
AUDIO_FILES_DIR.mkdir(exist_ok=True)

def cleanup_old_audio_files():
    """Remove old audio files"""
    try:
        for file_path in AUDIO_FILES_DIR.glob('*.mp3'):
            if (datetime.now().timestamp() - file_path.stat().st_mtime) > 3600:
                os.remove(file_path)
                logger.info(f"Removed old audio file: {file_path}")
    except Exception as e:
        logger.error(f"Error cleaning up audio files: {e}")

def run_cleanup():
    """Run cleanup every 30 minutes"""
    while True:
        cleanup_old_audio_files()
        time.sleep(1800)

cleanup_thread = threading.Thread(target=run_cleanup, daemon=True)
cleanup_thread.start()

# NEW: Outbound Call Function
def make_outbound_call():
    """Make an outbound call to a number from numbers.txt after 1 minute."""
    logger.info("Starting outbound call process...")
    time.sleep(10)  # Wait 1 minute

    numbers_file = Path("numbers.txt")
    if not numbers_file.exists():
        logger.error("numbers.txt not found!")
        return

    with open(numbers_file, "r") as f:
        phone_number = f.readline().strip()  # Read the first line
        if not phone_number:
            logger.error("No phone number found in numbers.txt!")
            return

    logger.info(f"Making outbound call to {phone_number}...")

    # Create TwiML for the call
    response = VoiceResponse()
    response.say("You have a reservation today at 7 PM.", voice="Polly.Joanna")

    # Make the outbound call
    try:
        call = twilio_client.calls.create(
            to=phone_number,
            from_=config('TWILIO_PHONE_NUMBER'),
            twiml=str(response)
        )
        logger.info(f"Call initiated: {call.sid}")
    except Exception as e:
        logger.error(f"Error making outbound call: {e}")

# NEW: Trigger outbound call in a separate thread
outbound_thread = threading.Thread(target=make_outbound_call, daemon=True)
outbound_thread.start()

@app.route('/health')
def health():
    try:
        db.session.execute(text('SELECT 1'))
        return 'OK'
    except Exception as e:
        app.logger.error(f'Health check failed: {str(e)}')
        return 'Database connection failed'

@app.route('/answer', methods=['POST'])
def answer_call():
    call_sid = request.values.get('CallSid')
    caller_phone = request.values.get('From')

    active_calls[call_sid] = CallSession(call_sid, caller_phone)
    logger.info(f"New call received: {call_sid} from {caller_phone}")

    call = Call(call_sid=call_sid, caller_phone=caller_phone, status='initiated')
    db.session.add(call)
    db.session.commit()

    response = VoiceResponse()
    welcome_message = "Welcome to our customer support. How can I help you today?"
    tts_file = text_to_speech(welcome_message)

    if tts_file:
        audio_url = f"{config('BASE_URL')}/audio/{tts_file.name}"
        response.play(audio_url)
    else:
        response.say(welcome_message)

    gather = Gather(
        input='speech',
        action='/handle-user-input',
        speechTimeout='auto',
        speechModel='phone_call',
        enhanced=True,
        timeout=5
    )
    response.append(gather)
    response.redirect('/answer')

    return str(response)

@app.route('/audio/<path:filename>', methods=['GET'])
def static_audio(filename):
    audio_path = AUDIO_FILES_DIR / filename
    return Response(open(audio_path, 'rb').read(), mimetype='audio/mpeg')

@app.route('/handle-user-input', methods=['POST'])
def handle_user_input():
    call_sid = request.values.get('CallSid')
    speech_result = request.values.get('SpeechResult')

    if call_sid not in active_calls:
        active_calls[call_sid] = CallSession(call_sid)

    session = active_calls[call_sid]

    if speech_result:
        session.add_transcription('user', speech_result)
        try:
            response_text, new_state = process_text(speech_result, session.state)
            session.state = new_state
            session.add_transcription('assistant', response_text)
            session.save_state()

            response = VoiceResponse()
            tts_file = text_to_speech(response_text)
            if tts_file:
                audio_url = f"{config('BASE_URL')}/audio/{tts_file.name}"
                response.play(audio_url)
            else:
                response.say(response_text)

            gather = Gather(
                input='speech',
                action='/handle-user-input',
                speechTimeout='auto',
                speechModel='phone_call',
                enhanced=True,
                timeout=5
            )
            response.append(gather)

            follow_up_message = "Is there anything else I can help you with?"
            tts_follow_up = text_to_speech(follow_up_message)
            if tts_follow_up:
                response.play(f"{config('BASE_URL')}/audio/{tts_follow_up.name}")
            else:
                response.say(follow_up_message)

            goodbye_message = "Thank you for calling our customer support. Goodbye!"
            tts_goodbye = text_to_speech(goodbye_message)
            if tts_goodbye:
                response.play(f"{config('BASE_URL')}/audio/{tts_goodbye.name}")
            else:
                response.say(goodbye_message)

            response.hangup()

            return str(response)
        except Exception as e:
            logger.error(f"Error processing speech: {e}")
            response = VoiceResponse()
            response.say("I'm sorry, I'm having trouble understanding. Could you try again?")
            gather = Gather(
                input='speech',
                action='/handle-user-input',
                speechTimeout='auto',
                speechModel='phone_call',
                enhanced=True,
                timeout=5
            )
            response.append(gather)
            return str(response)
    else:
        response = VoiceResponse()
        response.say("I didn't catch that. Could you please repeat?")
        gather = Gather(
            input='speech',
            action='/handle-user-input',
            speechTimeout='auto',
            speechModel='phone_call',
            enhanced=True,
            timeout=5
        )
        response.append(gather)
        return str(response)

@app.route('/call-status', methods=['POST'])
def call_status():
    call_sid = request.values.get('CallSid')
    call_status = request.values.get('CallStatus')

    logger.info(f"Call {call_sid} status: {call_status}")

    if call_status == 'completed' and call_sid in active_calls:
        call = db.session.query(Call).filter_by(call_sid=call_sid).first()
        if call:
            call.status = 'completed'
            call.end_time = db.func.now()
            db.session.commit()
        active_calls[call_sid].save_transcript()
        del active_calls[call_sid]
        logger.info(f"Cleaned up call resources for {call_sid}")

    return '', 200