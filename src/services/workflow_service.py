import os
import json
import re
import numpy as np
from openai import OpenAI
import faiss
import logging
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END
from decouple import config
from src.models.booking import Booking
from src.db import db

logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=config("OPENAI_API_KEY"))

# Sample restaurant info
restaurant_info = [
    "The restaurant is open from 10 AM to 10 PM every day.",
    "We offer a variety of dishes including pasta, pizza, salads, and desserts.",
    "Our address is 123 Main St, City, State.",
    "We have vegetarian and vegan options available.",
    "Reservations can be made online or by calling us."
]

class EmbeddingManager:
    def __init__(self):
        self.embeddings = None
        self.index = None
        self.dimension = None

    def initialize_embeddings(self):
        """Initialize embeddings and FAISS index for restaurant info."""
        try:
            self.embeddings = [
                client.embeddings.create(model="text-embedding-3-small", input=chunk).data[0].embedding
                for chunk in restaurant_info
            ]
            self.embeddings = np.array(self.embeddings).astype('float32')
            self.dimension = self.embeddings.shape[1]
            self.index = faiss.IndexFlatL2(self.dimension)
            self.index.add(self.embeddings)
            logger.info("Embeddings and FAISS index initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize embeddings: {e}")
            self.embeddings = []
            self.index = None
            self.dimension = None

# Global embedding manager
embedding_manager = EmbeddingManager()

class State(TypedDict):
    text: Optional[str]
    intent: Optional[str]
    response: Optional[str]
    booking_time: Optional[str]
    booking_phone: Optional[str]
    booking_id: Optional[str]
    awaiting_confirmation: Optional[bool]
    in_booking_flow: Optional[bool]
    in_update_flow: Optional[bool]
    in_retrieve_flow: Optional[bool]
    awaiting_further_assistance: Optional[bool]

def classify_intent_node(state: State) -> dict:
    text = state["text"]
    current_state = {
        "in_booking_flow": state.get("in_booking_flow", False),
        "in_update_flow": state.get("in_update_flow", False),
        "in_retrieve_flow": state.get("in_retrieve_flow", False),
        "has_booking_time": bool(state.get("booking_time")),
        "has_booking_phone": bool(state.get("booking_phone")),
        "has_booking_id": bool(state.get("booking_id")),
        "awaiting_confirmation": state.get("awaiting_confirmation", False),
        "awaiting_further_assistance": state.get("awaiting_further_assistance", False)
    }
    
    prompt = f"""
    Classify the intent of this user message: '{text}'.
    Possible intents: create_booking, retrieve_booking, update_booking, general_info, confirm_assistance.
    - 'create_booking': User wants to make a new reservation (e.g., "Book a table for 7 PM").
    - 'retrieve_booking': User wants to check an existing booking (e.g., "What's my booking details?").
    - 'update_booking': User wants to modify an existing booking (e.g., "Change my booking to 2 PM").
    - 'general_info': User asks for general information or says goodbye (e.g., "What are your hours?").
    - 'confirm_assistance': User responds to "Is there anything else I can help with?" (e.g., "No").
    
    Context:
    - Current state: {json.dumps(current_state)}.
    - If awaiting_confirmation is true, treat responses like 'Yes', 'No' as part of create_booking.
    - If in_booking_flow is true and has_booking_time is true but has_booking_phone is false, treat ambiguous responses as part of create_booking.
    - If user says goodbye and awaiting_confirmation is false, prefer 'general_info'.
    
    Respond with only the intent label.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "You are an intent classifier."}, {"role": "user", "content": prompt}]
        )
        intent = response.choices[0].message.content.strip()
        logger.info(f"Classified intent: {intent} for text: '{text}'")
    except Exception as e:
        logger.error(f"Error classifying intent: {e}")
        intent = "general_info"
        logger.info(f"Defaulting to intent: {intent}")

    reset_confirmation = intent == "create_booking" and not current_state["awaiting_confirmation"]
    
    return {
        "intent": intent,
        "in_booking_flow": intent == "create_booking" or (current_state["in_booking_flow"] and not current_state["awaiting_confirmation"] and not intent == "general_info"),
        "in_update_flow": intent == "update_booking",
        "in_retrieve_flow": intent == "retrieve_booking",
        "awaiting_confirmation": False if reset_confirmation else current_state["awaiting_confirmation"],
        "awaiting_further_assistance": intent == "confirm_assistance" and not current_state["in_booking_flow"]
    }

def normalize_time(time_str: str) -> str:
    if not time_str:
        return time_str
    if re.match(r'^\d{1,2}:\d{2}$', time_str):
        hour, minute = map(int, time_str.split(":"))
        period = "AM" if hour < 12 else "PM"
        hour = hour % 12
        if hour == 0:
            hour = 12
        return f"{hour}:{minute:02d} {period}"
    match = re.match(r'^\d{1,2}(:\d{2})?\s*(AM|PM|am|pm|a\.m\.|p\.m\.)$', time_str, re.IGNORECASE)
    if match:
        hour = int(match.group(0).split(":")[0]) if ":" in time_str else int(match.group(0).split()[0])
        minute = match.group(1)[1:] if match.group(1) else "00"
        period = match.group(2).replace("a.m.", "AM").replace("p.m.", "PM").upper()
        return f"{hour}:{minute} {period}"
    return time_str

def create_booking_node(state: State) -> dict:
    text = state["text"]
    current_time = state.get("booking_time")
    current_phone = state.get("booking_phone")
    awaiting_confirmation = state.get("awaiting_confirmation", False)

    logger.info(f"Processing create_booking: text='{text}', time={current_time}, phone={current_phone}, awaiting={awaiting_confirmation}")

    if awaiting_confirmation:
        text_lower = text.lower()
        confirmation_phrases = ["yes", "correct", "right", "sounds good", "confirm", "okay"]
        rejection_phrases = ["no", "wrong", "not right", "change it"]
        
        confirmation = None
        if any(phrase in text_lower for phrase in confirmation_phrases):
            confirmation = "yes"
        elif any(phrase in text_lower for phrase in rejection_phrases):
            confirmation = "no"
        else:
            try:
                prompt = f"""
                Does the user confirm the booking in this message: '{text}'? Respond with 'yes' or 'no'.
                """
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "system", "content": "You are a confirmation detector."}, {"role": "user", "content": prompt}]
                )
                confirmation = response.choices[0].message.content.strip().lower()
            except Exception as e:
                logger.error(f"Error detecting confirmation: {e}")
                confirmation = "no"

        if confirmation == "yes":
            booking_id = db.session.query(db.func.max(Booking.booking_id)).scalar() or 0
            booking_id += 1
            booking = Booking(
                booking_id=booking_id,
                phone_number=current_phone,
                time=current_time
            )
            try:
                db.session.add(booking)
                db.session.commit()
                logger.info(f"Booking saved: ID {booking_id}, Phone {current_phone}, Time {current_time}")
                response_text = f"Great, your booking is confirmed with ID {booking_id} for {current_time}. We'll call {current_phone} to confirm. Is there anything else I can help you with?"
                return {
                    "response": response_text,
                    "booking_time": None,
                    "booking_phone": None,
                    "booking_id": None,
                    "awaiting_confirmation": False,
                    "in_booking_flow": False,
                    "awaiting_further_assistance": True
                }
            except Exception as e:
                logger.error(f"Error saving booking: {e}")
                response_text = "Sorry, there was an issue saving your booking. Please try again."
                return {
                    "response": response_text,
                    "booking_time": None,
                    "booking_phone": None,
                    "awaiting_confirmation": False,
                    "in_booking_flow": True
                }
        else:
            response_text = "Okay, let's try again. What time would you like to book for?"
            return {
                "response": response_text,
                "booking_time": None,
                "booking_phone": None,
                "awaiting_confirmation": False,
                "in_booking_flow": True
            }

    prompt = f"""
    Extract the booking details from this message: '{text}'.
    Return a JSON object with keys: 'phone_number', 'time'.
    If a value is not found, use null.
    For 'time', format as 'H AM/PM' or 'H:MM AM/PM'.
    For 'phone_number', expect formats like '123-456-7890'.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "You are a booking details extractor."}, {"role": "user", "content": prompt}]
        )
        booking_details = json.loads(response.choices[0].message.content.strip())
    except Exception as e:
        logger.error(f"Error extracting booking details: {e}")
        booking_details = {"phone_number": None, "time": None}

    phone_number = booking_details["phone_number"] or current_phone
    raw_time = booking_details["time"] or current_time
    time = normalize_time(raw_time) if raw_time else None

    if phone_number and not re.match(r'^\d{3}-\d{3}-\d{4}$', phone_number):
        response_text = "Phone number should be in format 123-456-7890. Could you repeat it?"
        return {
            "response": response_text,
            "booking_time": time,
            "booking_phone": current_phone,
            "awaiting_confirmation": False,
            "in_booking_flow": True
        }

    if time and not re.match(r'^\d{1,2}(:\d{2})?\s*(AM|PM)$', time, re.IGNORECASE):
        response_text = "Time should be like '7 PM' or '7:00 PM'. Could you repeat it?"
        return {
            "response": response_text,
            "booking_time": current_time,
            "booking_phone": phone_number,
            "awaiting_confirmation": False,
            "in_booking_flow": True
        }

    if not phone_number and not time:
        response_text = "What time would you like, and what's your phone number?"
        return {
            "response": response_text,
            "booking_time": current_time,
            "booking_phone": current_phone,
            "awaiting_confirmation": False,
            "in_booking_flow": True
        }

    if not phone_number:
        response_text = f"Got {time} for your booking. Can I have your phone number?"
        return {
            "response": response_text,
            "booking_time": time,
            "booking_phone": current_phone,
            "awaiting_confirmation": False,
            "in_booking_flow": True
        }

    if not time:
        response_text = f"Thanks for the number, {phone_number}. What time would you like?"
        return {
            "response": response_text,
            "booking_time": current_time,
            "booking_phone": phone_number,
            "awaiting_confirmation": False,
            "in_booking_flow": True
        }

    response_text = f"Booking for {time} under {phone_number}. Does that sound right?"
    return {
        "response": response_text,
        "booking_time": time,
        "booking_phone": phone_number,
        "awaiting_confirmation": True,
        "in_booking_flow": True
    }

def retrieve_booking_node(state: State) -> dict:
    text = state["text"]
    current_phone = state.get("booking_phone")
    current_booking_id = state.get("booking_id")

    prompt = f"""
    Extract the booking details from this message: '{text}'.
    Return a JSON object with keys: 'phone_number', 'booking_id'.
    If a value is not found, use null.
    For 'phone_number', expect formats like '123-456-7890'.
    For 'booking_id', return a numeric string or null.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "You are a booking details extractor."}, {"role": "user", "content": prompt}]
        )
        data = json.loads(response.choices[0].message.content.strip())
    except Exception as e:
        logger.error(f"Error extracting booking details: {e}")
        data = {"phone_number": None, "booking_id": None}

    phone_number = data.get("phone_number") or current_phone
    booking_id = data.get("booking_id") or current_booking_id

    if not phone_number and not booking_id:
        response_text = "Please provide your phone number or booking ID."
        return {
            "response": response_text,
            "booking_phone": current_phone,
            "booking_id": current_booking_id,
            "in_retrieve_flow": True
        }

    booking = None
    try:
        if booking_id:
            booking = db.session.query(Booking).filter_by(booking_id=int(booking_id)).first()
        elif phone_number:
            booking = db.session.query(Booking).filter_by(phone_number=phone_number).first()
    except Exception as e:
        logger.error(f"Error querying booking: {e}")

    if booking:
        response_text = f"Your booking ID is {booking.booking_id} for {booking.time}, registered under {booking.phone_number}. Would you like to update this booking?"
        return {
            "response": response_text,
            "booking_phone": booking.phone_number,
            "booking_id": str(booking.booking_id),
            "booking_time": booking.time,
            "in_retrieve_flow": False,
            "awaiting_further_assistance": True
        }
    else:
        response_text = "No booking found. Would you like to create a new booking?"
        return {
            "response": response_text,
            "booking_phone": phone_number,
            "booking_id": None,
            "in_booking_flow": True
        }

def update_booking_node(state: State) -> dict:
    text = state["text"]
    current_time = state.get("booking_time")
    current_phone = state.get("booking_phone")
    current_booking_id = state.get("booking_id")
    awaiting_confirmation = state.get("awaiting_confirmation", False)

    if awaiting_confirmation:
        text_lower = text.lower()
        if any(phrase in text_lower for phrase in ["yes", "correct", "right", "sounds good"]):
            try:
                booking = db.session.query(Booking).filter_by(booking_id=int(current_booking_id)).first()
                if booking:
                    booking.phone_number = current_phone
                    booking.time = current_time
                    db.session.commit()
                    response_text = f"Booking updated to {current_time} for {current_phone}. Anything else?"
                    return {
                        "response": response_text,
                        "booking_time": None,
                        "booking_phone": None,
                        "booking_id": None,
                        "awaiting_confirmation": False,
                        "in_update_flow": False,
                        "awaiting_further_assistance": True
                    }
            except Exception as e:
                logger.error(f"Error updating booking: {e}")
                response_text = "Sorry, there was an issue updating your booking. Please try again."
                return {
                    "response": response_text,
                    "booking_time": None,
                    "booking_phone": None,
                    "booking_id": current_booking_id,
                    "awaiting_confirmation": False,
                    "in_update_flow": True
                }
        response_text = "Okay, what time or phone number would you like to update to?"
        return {
            "response": response_text,
            "booking_time": None,
            "booking_phone": None,
            "booking_id": current_booking_id,
            "awaiting_confirmation": False,
            "in_update_flow": True
        }

    prompt = f"""
    Extract the booking update details from this message: '{text}'.
    Return a JSON object with keys: 'phone_number', 'time', 'booking_id'.
    If a value is not found, use null.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "You are a booking details extractor."}, {"role": "user", "content": prompt}]
        )
        data = json.loads(response.choices[0].message.content.strip())
    except Exception as e:
        logger.error(f"Error extracting update details: {e}")
        data = {"phone_number": None, "time": None, "booking_id": None}

    phone_number = data.get("phone_number") or current_phone
    raw_time = data.get("time") or current_time
    booking_id = data.get("booking_id") or current_booking_id
    time = normalize_time(raw_time) if raw_time else None

    if not phone_number and not booking_id:
        response_text = "Please provide your phone number or booking ID."
        return {
            "response": response_text,
            "booking_time": time,
            "booking_phone": current_phone,
            "booking_id": booking_id,
            "in_update_flow": True
        }

    booking = None
    try:
        if booking_id:
            booking = db.session.query(Booking).filter_by(booking_id=int(booking_id)).first()
        elif phone_number:
            booking = db.session.query(Booking).filter_by(phone_number=phone_number).first()
    except Exception as e:
        logger.error(f"Error querying booking for update: {e}")

    if not booking:
        response_text = "No booking found. Would you like to create a new booking?"
        return {
            "response": response_text,
            "booking_time": time,
            "booking_phone": phone_number,
            "booking_id": None,
            "in_booking_flow": True
        }

    response_text = f"Update booking to {time} under {phone_number}. Does that sound right?"
    return {
        "response": response_text,
        "booking_time": time,
        "booking_phone": phone_number,
        "booking_id": booking_id or str(booking.booking_id),
        "awaiting_confirmation": True,
        "in_update_flow": True
    }

def general_info_node(state: State) -> dict:
    text = state["text"]
    if any(phrase in text.lower() for phrase in ["bye", "goodbye", "thank you"]):
        response_text = "Thank you for calling! Goodbye."
        return {"response": response_text, "in_booking_flow": False}

    # Initialize embeddings if not already done
    if not embedding_manager.index:
        embedding_manager.initialize_embeddings()

    if not embedding_manager.index:
        response_text = "Sorry, I'm having trouble accessing restaurant information. Please try again later."
        return {"response": response_text, "in_booking_flow": False}

    try:
        response = client.embeddings.create(model="text-embedding-3-small", input=text)
        query_embedding = np.array([response.data[0].embedding]).astype('float32')
        distances, indices = embedding_manager.index.search(query_embedding, 1)
        relevant_chunks = [restaurant_info[i] for i in indices[0]]
        prompt = f"User query: '{text}'\nRelevant information: {' '.join(relevant_chunks)}\nGenerate a concise response."
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": prompt}]
        )
        response_text = response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Error processing general info: {e}")
        response_text = "Sorry, I couldn't process your request. Could you repeat that?"

    return {"response": response_text, "in_booking_flow": False}

def confirm_assistance_node(state: State) -> dict:
    text = state["text"]
    prompt = f"""
    Does the user need further assistance based on: '{text}'?
    Return a JSON object with key 'needs_assistance' and value 'yes', 'no', or 'unsure'.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "You are an assistance detector."}, {"role": "user", "content": prompt}]
        )
        data = json.loads(response.choices[0].message.content.strip())
        needs_assistance = data.get("needs_assistance", "unsure")
    except Exception as e:
        logger.error(f"Error detecting assistance needs: {e}")
        needs_assistance = "unsure"

    if needs_assistance == "no":
        response_text = "Thank you for calling! Goodbye."
        return {"response": response_text, "in_booking_flow": False}
    elif needs_assistance == "yes":
        response_text = "Great, what else can I help you with?"
        return {"response": response_text, "in_booking_flow": False}
    else:
        response_text = "Is there anything else I can assist you with?"
        return {"response": response_text, "awaiting_further_assistance": True}

def route_intent(state: State):
    intent = state["intent"]
    return intent

graph = StateGraph(State)
graph.add_node("classify_intent", classify_intent_node)
graph.add_node("create_booking", create_booking_node)
graph.add_node("retrieve_booking", retrieve_booking_node)
graph.add_node("update_booking", update_booking_node)
graph.add_node("general_info", general_info_node)
graph.add_node("confirm_assistance", confirm_assistance_node)
graph.add_conditional_edges("classify_intent", route_intent, {
    "create_booking": "create_booking",
    "retrieve_booking": "retrieve_booking",
    "update_booking": "update_booking",
    "general_info": "general_info",
    "confirm_assistance": "confirm_assistance"
})
graph.add_edge("create_booking", END)
graph.add_edge("retrieve_booking", END)
graph.add_edge("update_booking", END)
graph.add_edge("general_info", END)
graph.add_edge("confirm_assistance", END)
graph.set_entry_point("classify_intent")
app = graph.compile()

def process_text(text: str, state: dict = None) -> tuple[str, dict]:
    if state is None:
        state = {"text": text, "in_booking_flow": False}
    else:
        state["text"] = text
    try:
        result = app.invoke(state)
        logger.info(f"Process_text result: {result}")
        return result["response"], result
    except Exception as e:
        logger.error(f"Error in process_text: {e}")
        return "Sorry, something went wrong. Please try again.", state