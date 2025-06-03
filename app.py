from flask import Flask, render_template, request
import os
import time
from dotenv import load_dotenv
from azure.ai.textanalytics import TextAnalyticsClient
from azure.core.credentials import AzureKeyCredential
import openai
import azure.cognitiveservices.speech as speechsdk

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Azure Text Analytics
text_analytics_client = TextAnalyticsClient(
    endpoint=os.getenv('AZURE_TEXT_ENDPOINT'),
    credential=AzureKeyCredential(os.getenv('AZURE_TEXT_KEY'))
)

# OpenAI legacy API
openai.api_key = os.getenv("OPENAI_API_KEY")

def analyze_sentiment(feedback_text):
    if not feedback_text.strip():
        return "Neutral"
    response = text_analytics_client.analyze_sentiment([feedback_text])[0]
    if hasattr(response, "sentiment"):
        return response.sentiment.capitalize()
    else:
        print("❌ Sentiment analysis error:", response)
        return "Neutral"

def generate_response(feedback_text, sentiment):
    prompt = f"A user gave {sentiment} feedback: '{feedback_text}'. Write a brief, empathetic response."
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=50,
    )
    return response['choices'][0]['message']['content']

def generate_audio(response_text):
    output_dir = "static/audio"
    os.makedirs(output_dir, exist_ok=True)

    timestamp = int(time.time() * 1000)
    filename = f"response_{timestamp}.mp3"
    output_path = os.path.join(output_dir, filename)

    speech_config = speechsdk.SpeechConfig(
        subscription=os.getenv("AZURE_SPEECH_KEY"),
        region=os.getenv("AZURE_SPEECH_REGION")
    )
    speech_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
    )
    audio_config = speechsdk.audio.AudioOutputConfig(filename=output_path)
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

    result = synthesizer.speak_text_async(response_text).get()

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        print("✅ Audio synthesized:", filename)
        return filename
    elif result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = speechsdk.CancellationDetails.from_result(result)
        print("❌ TTS canceled:", cancellation_details.reason)
        print("❌ Error:", cancellation_details.error_details)
        return None

@app.route('/', methods=['GET', 'POST'])
def index():
    sentiment = response_text = audio_file = None
    if request.method == 'POST':
        feedback = request.form['feedback']

        if not feedback.strip():
            sentiment = "Neutral"
            response_text = "You submitted empty feedback. Please enter something."
            return render_template('index.html', sentiment=sentiment, response=response_text, audio_file=None)

        sentiment = analyze_sentiment(feedback)
        response_text = generate_response(feedback, sentiment)
        audio_file = generate_audio(response_text)
        print("Audio file returned to UI:", audio_file)

    return render_template('index.html', sentiment=sentiment, response=response_text, audio_file=audio_file)

