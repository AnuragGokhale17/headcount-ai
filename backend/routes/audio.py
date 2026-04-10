import os
import tempfile
import edge_tts
import asyncio
import ssl
from flask import Blueprint, request, jsonify, send_file
from werkzeug.utils import secure_filename

# Fix SSL Certificate verification errors for edge-tts (aiohttp uses create_default_context)
orig_create_default_context = getattr(ssl, '_original_create_default_context', ssl.create_default_context)
ssl._original_create_default_context = orig_create_default_context

def bypass_create_default_context(*args, **kwargs):
    ctx = orig_create_default_context(*args, **kwargs)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

ssl.create_default_context = bypass_create_default_context

audio_bp = Blueprint('audio', __name__)

_ai_engine = None

def init_audio_routes(ai_engine):
    global _ai_engine
    _ai_engine = ai_engine

@audio_bp.route("/api/ai_voice", methods=["POST"])
def ai_voice_api():
    # Robust check for JSON (prevents 415 errors)
    if not request.is_json:
        return jsonify({
            "error": "Mismatched Protocol. Your browser is sending an audio file, but the server now requires text transcription (JSON).",
            "fix": "Please rebuild your frontend (npm run build) and refresh your browser."
        }), 400
        
    data = request.get_json(silent=True)
    if not data or 'query' not in data:
        return jsonify({"error": "No query provided in JSON"}), 400
        
    query_text = data['query']
    print(f"🎙️ User asked (via Web Speech API): {query_text}")

    try:
        # 1. LLM Processing
        response_text = _ai_engine.handle_query(query_text)
        print(f"🧠 AI answered: {response_text}")

        import pyttsx3
        
        # Save temp audio file
        fd, tts_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        
        # Initialize the local text-to-speech engine
        engine = pyttsx3.init()
        
        # Try to find a Hindi or female voice if available, otherwise use default
        voices = engine.getProperty('voices')
        for voice in voices:
            if 'hi' in voice.languages or 'hindi' in getattr(voice, 'name', '').lower() or 'zira' in getattr(voice, 'name', '').lower():
                engine.setProperty('voice', voice.id)
                break
                
        # Generate the audio file locally (bypassing all firewalls)
        engine.save_to_file(response_text, tts_path)
        engine.runAndWait()

        # 3. Return Audio Response
        response = send_file(tts_path, mimetype="audio/wav")
        
        # Use ascii headers to avoid unicode issues for React
        safe_resp = ''.join([i if ord(i) < 128 else '' for i in response_text])
        response.headers['X-Response-Text'] = safe_resp
        
        # The frontend will play the audio and display the response text
        return response

    except Exception as e:
        print(f"Error in ai_voice_api: {e}")
        return jsonify({"error": str(e)}), 500
