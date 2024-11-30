from flask import Flask, render_template, jsonify, Response, request
import azure.cognitiveservices.speech as speechsdk
import os
from dotenv import load_dotenv
import queue
import threading
import json

load_dotenv()

app = Flask(__name__)

# Global queue for storing translations
translation_queue = queue.Queue()
is_translating = False

class SpeechTranslator:
    def __init__(self):
        self.speech_config = None
        self.translation_recognizer = None
        self.is_translating = False

    def configure_translator(self, input_language, output_language):
        self.speech_config = speechsdk.translation.SpeechTranslationConfig(
            subscription=os.getenv('SPEECH_KEY'),
            region=os.getenv('SPEECH_REGION')
        )
        self.speech_config.speech_recognition_language = input_language
        self.speech_config.add_target_language(output_language)

    def start_translation(self):
        if not self.speech_config:
            raise ValueError("Speech config not set. Call configure_translator first.")

        self.is_translating = True
        audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
        self.translation_recognizer = speechsdk.translation.TranslationRecognizer(
            translation_config=self.speech_config,
            audio_config=audio_config
        )

        def handle_translation_result(evt):
            if evt.result.reason == speechsdk.ResultReason.TranslatedSpeech:
                output_language = list(self.speech_config.target_languages)[0]
                translation = evt.result.translations[output_language]
                translation_queue.put(translation)

        self.translation_recognizer.recognized.connect(handle_translation_result)
        self.translation_recognizer.start_continuous_recognition()

    def stop_translation(self):
        if self.translation_recognizer:
            self.is_translating = False
            self.translation_recognizer.stop_continuous_recognition()

translator = SpeechTranslator()

@app.route('/')
def home():
    return render_template('index5.html')

@app.route('/start_translation', methods=['POST'])
def start_translation():
    global is_translating
    is_translating = True

    data = request.get_json()
    input_language = data.get('input_language', 'hi-IN')  # Default to English
    output_language = data.get('output_language', 'en')  # Default to English

    translator.configure_translator(input_language, output_language)
    translator.start_translation()

    return jsonify({'status': 'started'})

@app.route('/stop_translation', methods=['POST'])
def stop_translation():
    global is_translating
    is_translating = False
    translator.stop_translation()
    return jsonify({'status': 'stopped'})

@app.route('/stream')
def stream():
    def generate():
        while True:
            try:
                if not is_translating:
                    break
                # Try to get a translation from the queue with a timeout
                translation = translation_queue.get(timeout=0.1)
                yield f"data: {json.dumps({'translation': translation})}\n\n"
            except queue.Empty:
                continue
    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
