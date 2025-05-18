FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN mkdir -p /app/static/call_recordings

COPY . .

# COPY numbers.txt /app/numbers.txt  

ENV FLASK_APP=src.api.routes:app
ENV FLASK_ENV=development

EXPOSE 5000

COPY voice-agent-tts-05f49acb929c.json /app/voice-agent-tts-05f49acb929c.json

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "src.api.routes:app"]