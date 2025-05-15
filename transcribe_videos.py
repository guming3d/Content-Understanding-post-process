"""
transcribe_videos.py

Transcribes all .mp4 videos in the 'inputs' directory using Azure Speech-to-Text (STT) service.
Saves transcriptions as .txt files in the same directory.

- Uses .env file for Azure credentials (endpoint and key)
- Extracts audio from video using ffmpeg
- Handles errors and logs progress
- Easy to understand and extend

References:
- Azure Speech SDK: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/quickstarts/setup-platform?tabs=linux%2Cmacos%2Cwindows&pivots=programming-language-python
- ffmpeg: https://ffmpeg.org/
"""
import os
import glob
import logging
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk

# Load Azure credentials from .env
load_dotenv()
SPEECH_KEY = os.getenv('AZURE_SPEECH_KEY')
SPEECH_ENDPOINT = os.getenv('AZURE_SPEECH_ENDPOINT')

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

if not SPEECH_KEY or not SPEECH_ENDPOINT:
    logging.error("Azure Speech credentials not set in .env file.")
    exit(1)

def extract_audio_from_video(video_path, audio_path):
    """
    Extracts audio from video using ffmpeg command line tool.
    Requires ffmpeg to be installed and available in PATH.
    """
    import subprocess
    try:
        # -y: overwrite output, -vn: no video, -acodec pcm_s16le: WAV format
        cmd = [
            "ffmpeg", "-y", "-i", video_path, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", audio_path
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        logging.error(f"Failed to extract audio from {video_path} using ffmpeg: {e}")
        raise

def transcribe_audio_with_word_timestamps(audio_path, speech_key, speech_endpoint):
    """
    Transcribes audio and returns a list of (start_time, end_time, text) tuples for each word
    from the top confidence STT result.
    """
    try:
        speech_config = speechsdk.SpeechConfig(subscription=speech_key, endpoint=speech_endpoint)
        audio_input = speechsdk.AudioConfig(filename=audio_path)
        speech_config.output_format = speechsdk.OutputFormat.Detailed
        recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_input)
        results = []
        done = False
        def handle_final(evt):
            if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                import json as _json
                j = _json.loads(evt.result.json)
                nbest_list = j.get('NBest', [])
                if nbest_list:  # Check if NBest list is not empty
                    n = nbest_list[0]  # Process only the top confidence NBest hypothesis
                    if 'Words' in n: # Check if the top hypothesis has words
                        for w in n.get('Words', []): # Iterate through words of the top hypothesis
                            start_time = w.get('Offset') / 10000000.0  # 100-nanosecond units to seconds
                            duration = w.get('Duration') / 10000000.0
                            end_time = start_time + duration
                            text = w.get('Word')
                            results.append((start_time, end_time, text))
        recognizer.recognized.connect(handle_final)
        recognizer.session_stopped.connect(lambda evt: setattr(recognizer, 'done', True))
        recognizer.canceled.connect(lambda evt: setattr(recognizer, 'done', True))
        recognizer.start_continuous_recognition()
        import time
        while not getattr(recognizer, 'done', False):
            time.sleep(0.5)
        recognizer.stop_continuous_recognition()
        return results
    except Exception as e:
        logging.error(f"Error during transcription with word timestamps: {e}")
        return []

def transcribe_audio_with_sentence_timestamps(audio_path, speech_key, speech_endpoint):
    """
    Transcribes audio and returns a list of (start_time, end_time, text) tuples for each recognized sentence
    from the top confidence STT result.
    """
    try:
        import json as _json # Ensure json is imported here as well
        speech_config = speechsdk.SpeechConfig(subscription=speech_key, endpoint=speech_endpoint)
        audio_input = speechsdk.AudioConfig(filename=audio_path)
        speech_config.output_format = speechsdk.OutputFormat.Detailed
        recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_input)
        results = []
        done = False
        def handle_final(evt):
            if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                j = _json.loads(evt.result.json)
                nbest_list = j.get('NBest', [])
                if nbest_list:  # Check if NBest list is not empty
                    n = nbest_list[0]  # Process only the top confidence result
                    if 'Words' in n and n['Words']: # Ensure there are words to derive sentence times
                        words = n['Words']
                        start_time = words[0]['Offset'] / 10000000.0
                        end_time = (words[-1]['Offset'] + words[-1]['Duration']) / 10000000.0
                        sentence_text = n.get('Display', n.get('Lexical', '')) # Get sentence text
                        results.append((start_time, end_time, sentence_text))
        recognizer.recognized.connect(handle_final)
        recognizer.session_stopped.connect(lambda evt: setattr(recognizer, 'done', True))
        recognizer.canceled.connect(lambda evt: setattr(recognizer, 'done', True))
        recognizer.start_continuous_recognition()
        import time
        while not getattr(recognizer, 'done', False):
            time.sleep(0.5)
        recognizer.stop_continuous_recognition()
        return results
    except Exception as e:
        logging.error(f"Error during transcription with sentence timestamps: {e}")
        return []

def main():
    input_dir = "inputs"
    video_files = glob.glob(os.path.join(input_dir, "*.mp4"))
    if not video_files:
        logging.info("No video files found in 'inputs' directory.")
        return
    for video_path in video_files:
        base = os.path.splitext(video_path)[0]
        word_txt_path = base + "_word.txt"
        sentence_txt_path = base + "_sentence.txt"
        audio_path = base + ".wav" # Keep .wav for temporary audio
        
        logging.info(f"Processing {video_path} ...")
        try:
            extract_audio_from_video(video_path, audio_path)
            
            # Get and save word-level timestamps
            word_segments = transcribe_audio_with_word_timestamps(audio_path, SPEECH_KEY, SPEECH_ENDPOINT)
            with open(word_txt_path, "w", encoding="utf-8") as f:
                for start, end, word in word_segments:
                    f.write(f"[{start:.2f} - {end:.2f}] {word}\n")
            logging.info(f"Word-level transcription saved to {word_txt_path}")

            # Get and save sentence-level timestamps
            sentence_segments = transcribe_audio_with_sentence_timestamps(audio_path, SPEECH_KEY, SPEECH_ENDPOINT)
            with open(sentence_txt_path, "w", encoding="utf-8") as f:
                for start, end, sentence in sentence_segments:
                    f.write(f"[{start:.2f} - {end:.2f}] {sentence}\n")
            logging.info(f"Sentence-level transcription saved to {sentence_txt_path}")
            
        except Exception as e:
            logging.error(f"Failed to process {video_path}: {e}")
        finally:
            # Clean up the temporary wav file
            if os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                    logging.info(f"Temporary audio file {audio_path} removed.")
                except Exception as e:
                    logging.warning(f"Could not remove temporary audio file {audio_path}: {e}")

if __name__ == "__main__":
    main()
