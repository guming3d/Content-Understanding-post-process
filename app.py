"""
app.py

Main control logic for the video transcription and analysis pipeline:
1. Transcribes videos to get word-level and sentence-level transcriptions
2. Uses Azure OpenAI to extract selling points from the transcriptions
3. Saves results to output files

Requirements:
- Azure Speech Service for transcription
- Azure OpenAI Service for selling points extraction
- ffmpeg for audio extraction
"""

import os
import glob
import logging
from dotenv import load_dotenv
import json
import time
from openai import AzureOpenAI

# Import the transcription functions from our module
from transcribe_videos import (
    extract_audio_from_video,
    transcribe_audio_with_word_timestamps,
    transcribe_audio_with_sentence_timestamps
)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

# Load environment variables
load_dotenv()
SPEECH_KEY = os.getenv('AZURE_SPEECH_KEY')
SPEECH_ENDPOINT = os.getenv('AZURE_SPEECH_ENDPOINT')
OPENAI_API_KEY = os.getenv('AZURE_OPENAI_API_KEY')
OPENAI_API_VERSION = os.getenv('AZURE_OPENAI_API_VERSION')
OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT')
OPENAI_DEPLOYMENT = os.getenv('AZURE_OPENAI_DEPLOYMENT')  # Deployment name for GPT-4.1

# Verify environment variables
required_vars = {
    'AZURE_SPEECH_KEY': SPEECH_KEY,
    'AZURE_SPEECH_ENDPOINT': SPEECH_ENDPOINT, 
    'AZURE_OPENAI_API_KEY': OPENAI_API_KEY,
    'AZURE_OPENAI_API_VERSION': OPENAI_API_VERSION,
    'AZURE_OPENAI_ENDPOINT': OPENAI_ENDPOINT,
    'AZURE_OPENAI_DEPLOYMENT': OPENAI_DEPLOYMENT
}

missing_vars = [var for var, value in required_vars.items() if not value]
if missing_vars:
    logging.error(f"Missing required environment variables: {', '.join(missing_vars)}")
    exit(1)

def extract_selling_points(transcription_text):
    """
    Use Azure OpenAI to extract selling points from the transcription text.
    
    Args:
        transcription_text (str): The sentence-level transcription text
        
    Returns:
        list: A list of extracted selling points
    """
    try:
        # Initialize Azure OpenAI client
        client = AzureOpenAI(
            api_key=OPENAI_API_KEY,
            api_version=OPENAI_API_VERSION,  # Update this as needed
            azure_endpoint=OPENAI_ENDPOINT
        )

        # Prepare the prompt
        prompt = f"""
        Extract the unique selling points from the following transcription. 
        Use exactly the same words as they appear in the transcription.
        Only include clear selling points, features, or benefits mentioned.
        Format each point as a separate item in a JSON array.
        
        Transcription:
        {transcription_text}
        """

        prompt2 = f"""
        Analyze this transcript, and list out the individual selling points mentioned in the transcript, the selling points should be short and consice.
        Format each point as a separate item in a JSON array.
                
        Transcription:
        {transcription_text}
        """

        prompt3 = f"""
        {transcription_text}
        """
        
        # Call the Azure OpenAI service
        # Dynamically set max_tokens based on the length of the transcription_text
        # Rough heuristic: 1 token ≈ 4 characters in English
        approx_tokens = max(256, min(len(transcription_text) // 4, 4096))

        response = client.chat.completions.create(
            model=OPENAI_DEPLOYMENT,
            messages=[
            # {"role": "system", "content": "You are an AI assistant that extracts selling points from transcriptions."},
            {"role": "system", "content": """
Your task is to analyze video transcript and extract the unique and individual selling points mentioned in the transcript. Only list the selling points, no other explanation need to be provided. Format each point as a separate item in a JSON array.
Make sure the selling points word is exactly the same as they appear in the transcript.
 
Here is a list of sample selling point for your reference:
Selling Points list:
 
Magical pockets set me free!
They come in multiple colors. 
So soft and super stretchy
Get dressed in effortless fashion!
Built-in shorts
Adjustable drawstrings
Stretchy & crazy comfortable!
Stretchy fabric
Built-in shorts provides
Designed straps
Fleece-lining to keep you cosy
Crossover waist design!
Built-in shorts with side pockets
Built-in shorts for easy coverage
Removable pads for customized support
Breathable material for hot days
4-way stretch for easy movement
Pullover hood gives easy coverage
Kangaroo pocket for accessible storage
Move freely without any discomfort
Doesn't rub against my skin
the fabric is soooo stretchy
Duper stretchy for easy movement
Inner lining for added coverage
100% sweat proof.
Easily pat it off
Super soft, super breathable. 
flattering shape and fit
Shows off my curves
So effortless, so elegant!
The comfiest built-in shorts! 
coverage for your underarm
backless and twist design
Yes, 100% squat proof.
Perfect for working out
Pockets to store items
comfortable to the touch
Deep pocket
So many fun colors
Soft and super stretchy
Perfect for everyday wear
The fabric is perfect 
Breathable and sweat-wicking
Basic wardrobe staple
Soft and stretchy 
Classic curved design
Slight flare design
Buttery soft fabric 
Roomy pockets! 
Teardrop back design 
comfortable double straps
UNATTRACTIVE SHAPE? GONE"
Hourglass bodyshape effect
INELASTIC FABRIC? GONE
Back waistband pocket
Round neck cut-out 
Adjustable shoulder straps
Side slit drawstring 
Multi-layer skirt design
Front slit design
Tie-back Backless design
Highlights your curves
Will not shrink 
Tight crotch jeans
Removable cups
Itchy skin
Twist design
Great value
Multi-layered design
Baggy knees
High-waisted band 
Adjustable straps 
Flattering silhouette
Drawstring design
U-shape neckline
Decorative straps 
U-neck racerback
 
New selling points may be mentioned in the transcript that are not included in the list above. In this case, use your best judgement.
             """},
            {"role": "user", "content": prompt3}
            ],
            temperature=0.7,
            max_tokens=approx_tokens,
            response_format={"type": "json_object"}
        )

        # Parse the response
        content = response.choices[0].message.content
        selling_points = json.loads(content).get("selling_points", [])
        
        return selling_points
    
    except Exception as e:
        logging.error(f"Error extracting selling points: {e}")
        return []

def match_selling_points_with_timestamps(word_segments, selling_points):
    """
    Match selling points with word-level timestamps.
    
    Args:
        word_segments (list): List of tuples (start_time, end_time, word)
        selling_points (list): List of selling point strings
        
    Returns:
        list: Selling points with timestamp information
    """
    result = []
    
    # Create a lowercase version of word_segments for case-insensitive matching
    word_data = [(start, end, word.lower()) for start, end, word in word_segments]
    
    for selling_point in selling_points:
        # Split the selling point into individual words and convert to lowercase
        point_words = selling_point.lower().split()
        
        # Skip empty selling points
        if not point_words:
            continue
            
        start_time = None
        end_time = None
        
        # Find consecutive sequences of words that match the selling point
        for i in range(len(word_data)):
            matched_words = 0
            for j in range(len(point_words)):
                if i + j >= len(word_data):
                    break
                
                # Check if the current word in the transcription matches the current word in the selling point
                # Allow partial matches (e.g., "7/8" might be transcribed as "seven eighths")
                if word_data[i + j][2] in point_words[j] or point_words[j] in word_data[i + j][2]:
                    matched_words += 1
                else:
                    break
            
            # If we have a match for all words or a significant portion
            if matched_words >= max(1, len(point_words) // 2):
                # Set start time from the first matched word
                if start_time is None:
                    start_time = word_data[i][0]
                
                # Update end time with the last matched word
                end_time = word_data[i + matched_words - 1][1]
                
                # For longer selling points, try to find matches for remaining words
                remaining_point_words = " ".join(point_words[matched_words:])
                if remaining_point_words:
                    for k in range(i + matched_words, len(word_data)):
                        if word_data[k][2] in remaining_point_words or any(pw in word_data[k][2] for pw in point_words[matched_words:]):
                            end_time = word_data[k][1]
        
        # If we found timestamps, add to results
        if start_time is not None and end_time is not None:
            result.append({
                "startTime": round(start_time, 2),
                "endTime": round(end_time, 2),
                "content": selling_point
            })
        else:
            # If no match was found, include the selling point without timestamps
            result.append({
                "startTime": None,
                "endTime": None,
                "content": selling_point
            })
    
    return result

def process_video(video_path):
    """
    Process a single video file:
    1. Extract audio from video
    2. Transcribe audio to get word and sentence level transcriptions
    3. Extract selling points from sentence transcription
    4. Match selling points with timestamps 
    5. Save results
    
    Args:
        video_path (str): Path to the video file
    """
    base = os.path.splitext(video_path)[0]
    word_txt_path = base + "_word.txt"
    sentence_txt_path = base + "_sentence.txt"
    selling_points_path = base + "_selling_points.json"
    audio_path = base + ".wav"  # Temporary audio file
    
    logging.info(f"Processing {video_path} ...")
    
    try:
        # Step 1: Extract audio from video
        extract_audio_from_video(video_path, audio_path)
        
        # Step 2: Get word-level timestamps
        word_segments = transcribe_audio_with_word_timestamps(audio_path, SPEECH_KEY, SPEECH_ENDPOINT)
        with open(word_txt_path, "w", encoding="utf-8") as f:
            for start, end, word in word_segments:
                f.write(f"[{start:.2f} - {end:.2f}] {word}\n")
        logging.info(f"Word-level transcription saved to {word_txt_path}")
        
        # Step 3: Get sentence-level timestamps
        sentence_segments = transcribe_audio_with_sentence_timestamps(audio_path, SPEECH_KEY, SPEECH_ENDPOINT)
        
        # Save sentence transcriptions
        with open(sentence_txt_path, "w", encoding="utf-8") as f:
            for start, end, sentence in sentence_segments:
                f.write(f"[{start:.2f} - {end:.2f}] {sentence}\n")
        logging.info(f"Sentence-level transcription saved to {sentence_txt_path}")
        
        # Step 4: Create plain text from sentence transcriptions for OpenAI processing
        transcription_text = "\n".join([sentence for _, _, sentence in sentence_segments])
        
        # Step 5: Extract selling points using Azure OpenAI
        selling_points = extract_selling_points(transcription_text)
        
        # Step 6: Match selling points with word-level timestamps
        timestamped_selling_points = match_selling_points_with_timestamps(word_segments, selling_points)
        
        # Save selling points with timestamps
        with open(selling_points_path, "w", encoding="utf-8") as f:
            json.dump({"selling_points": timestamped_selling_points}, f, indent=2)
        logging.info(f"Selling points with timestamps saved to {selling_points_path}")
        
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

def main():
    """
    Main function to process all videos in the input directory
    """
    input_dir = "inputs"
    video_files = glob.glob(os.path.join(input_dir, "*.mp4"))
    
    if not video_files:
        logging.info("No video files found in 'inputs' directory.")
        return
    
    logging.info(f"Found {len(video_files)} videos to process")
    
    for video_path in video_files:
        process_video(video_path)
        
    logging.info("All videos processed successfully")

if __name__ == "__main__":
    main()