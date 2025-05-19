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
load_dotenv(override=True)
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

        prompt = f"""
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
Your task is to analyze video transcript and extract the unique and individual selling points mentioned in the transcript. Only list the selling points, no other explanation need to be provided. Pur each selling point as a separate item in a JSON array.
Make sure the selling points word is exactly the same as they appear in the transcript. Long transcript sentences can be broken down into multiple selling points.
 
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
            {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            # max_tokens=approx_tokens,
            max_tokens=200,
            top_p=1,
            response_format={"type": "json_object"}
        )

        # Parse the response
        content = response.choices[0].message.content
        print(content)
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
    
    # Track which words have already been matched
    matched_positions = [False] * len(word_data)
    
    # Process selling points in order (we'll sort by timestamp at the end)
    for selling_point in selling_points:
        # Split the selling point into individual words and convert to lowercase
        point_words = selling_point.lower().split()
        
        # Skip empty selling points
        if not point_words:
            continue
            
        start_time = None
        end_time = None
        matched_indices = []
        
        # First pass: try to find a match using only unmatched words
        for i in range(len(word_data)):
            # Skip if this position is already matched or if there aren't enough words left
            if matched_positions[i] or i + len(point_words) > len(word_data):
                continue
                
            matched_words = 0
            curr_indices = []
            
            for j in range(len(point_words)):
                if i + j >= len(word_data) or matched_positions[i + j]:
                    break
                
                # Check if the current word in the transcription matches the current word in the selling point
                # Allow partial matches (e.g., "7/8" might be transcribed as "seven eighths")
                if word_data[i + j][2] in point_words[j] or point_words[j] in word_data[i + j][2]:
                    matched_words += 1
                    curr_indices.append(i + j)
                else:
                    break
            
            # If we have a match for all words or a significant portion
            if matched_words >= max(1, len(point_words) // 2):
                # Set start time from the first matched word
                start_time = word_data[i][0]
                
                # Update end time with the last matched word
                end_time = word_data[i + matched_words - 1][1]
                matched_indices = curr_indices
                
                # For longer selling points, try to find matches for remaining words
                remaining_point_words = " ".join(point_words[matched_words:])
                if remaining_point_words:
                    for k in range(i + matched_words, len(word_data)):
                        if matched_positions[k]:
                            continue
                            
                        if word_data[k][2] in remaining_point_words or any(pw in word_data[k][2] for pw in point_words[matched_words:]):
                            end_time = word_data[k][1]
                            matched_indices.append(k)
                
                # We found a match, so break out of the loop
                break
        
        # Second pass: if no match found in unmatched regions, try anywhere
        if start_time is None:
            for i in range(len(word_data)):
                # Skip if there aren't enough words left
                if i + len(point_words) > len(word_data):
                    continue
                    
                matched_words = 0
                curr_indices = []
                
                for j in range(len(point_words)):
                    if i + j >= len(word_data):
                        break
                    
                    # Check if current word matches
                    if word_data[i + j][2] in point_words[j] or point_words[j] in word_data[i + j][2]:
                        matched_words += 1
                        curr_indices.append(i + j)
                    else:
                        break
                
                # If we have a match
                if matched_words >= max(1, len(point_words) // 2):
                    # Set start time from the first matched word
                    start_time = word_data[i][0]
                    
                    # Update end time with the last matched word
                    end_time = word_data[i + matched_words - 1][1]
                    matched_indices = curr_indices
                    
                    # For longer selling points, try to find matches for remaining words
                    remaining_point_words = " ".join(point_words[matched_words:])
                    if remaining_point_words:
                        for k in range(i + matched_words, len(word_data)):
                            if word_data[k][2] in remaining_point_words or any(pw in word_data[k][2] for pw in point_words[matched_words:]):
                                end_time = word_data[k][1]
                                matched_indices.append(k)
                    
                    break
        
        # If we found timestamps, add to results and mark words as matched
        if start_time is not None and end_time is not None:
            result.append({
                "startTime": round(start_time, 2),
                "endTime": round(end_time, 2),
                "content": selling_point
            })
            
            # Mark the matched positions as used
            for idx in matched_indices:
                matched_positions[idx] = True
        else:
            # If no match was found, include the selling point without timestamps
            result.append({
                "startTime": None,
                "endTime": None,
                "content": selling_point
            })
    
    # Sort results by start time (None values at the end)
    result.sort(key=lambda x: (x["startTime"] is None, x["startTime"]))
    
    return result

def merge_segments_by_selling_points(content_json, selling_points_json, time_deviation_ms=0, min_overlap_percentage=0.2):
    """
    Merge video segments based on selling points timestamps with optional time deviation
    
    Args:
        content_json: Content understanding output JSON
        selling_points_json: Selling points with timestamps JSON
        time_deviation_ms: Time deviation in milliseconds to allow for overlap matching (default: 0ms)
        min_overlap_percentage: Minimum percentage of overlap required (0.0-1.0) to consider a match (default: 0.2)
    
    Returns:
        Dictionary with merged segments, final segments and unmerged content
    """
    result = {
        "merged_segments": [],
        "unmerged_segments": [],
        "final_segments": []
    }
    
    # Get video segments from content understanding output
    video_segments = content_json["result"]["contents"]
    
    # Track which segments have been merged
    merged_segment_indices = set()
    
    # Process each selling point
    for selling_point in selling_points_json["selling_points"]:
        # Skip if no timestamps
        if selling_point["startTime"] is None or selling_point["endTime"] is None:
            # Add to result as a selling point without timestamp information
            result["merged_segments"].append({
                "startTimeMs": None,
                "endTimeMs": None,
                "content": selling_point["content"],
                "overlapping_segments": []
            })
            logging.info(f"Skipping timing match for selling point without timestamps: {selling_point['content']}")
            continue
        
        # Convert to milliseconds for comparison
        start_time_ms = int(selling_point["startTime"] * 1000)
        end_time_ms = int(selling_point["endTime"] * 1000)
        selling_point_duration = end_time_ms - start_time_ms
        
        # Find overlapping segments with time deviation
        overlapping_segments = []
        for i, segment in enumerate(video_segments):
            # Check if segments overlap with time deviation
            segment_start = segment["startTimeMs"]
            segment_end = segment["endTimeMs"]
            segment_duration = segment_end - segment_start
            
            # Calculate overlap
            overlap_start = max(segment_start, start_time_ms - time_deviation_ms)
            overlap_end = min(segment_end, end_time_ms + time_deviation_ms)
            
            if overlap_start < overlap_end:  # There is some overlap
                # Calculate overlap duration
                overlap_duration = overlap_end - overlap_start
                
                # Calculate overlap percentage relative to the shorter duration
                shorter_duration = min(segment_duration, selling_point_duration)
                overlap_percentage = overlap_duration / shorter_duration
                
                # Only consider as overlapping if percentage is above threshold
                if overlap_percentage >= min_overlap_percentage:
                    overlapping_segments.append({
                        "startTimeMs": segment["startTimeMs"],
                        "endTimeMs": segment["endTimeMs"],
                        "sellingPoint": segment["fields"].get("sellingPoint", {}).get("valueString", ""),
                        "description": segment["fields"].get("description", {}).get("valueString", "")
                    })
                    # Mark this segment as merged
                    merged_segment_indices.add(i)
                    logging.info(f"Merged segment {i} with selling point '{selling_point['content']}', overlap: {overlap_percentage:.2f}")
                else:
                    logging.info(f"Skipped merging segment {i} with selling point '{selling_point['content']}', insufficient overlap: {overlap_percentage:.2f}")
        
        # Create merged segment
        merged_segment = {
            "startTimeMs": start_time_ms,
            "endTimeMs": end_time_ms,
            "content": selling_point["content"],
            "overlapping_segments": overlapping_segments
        }
        
        result["merged_segments"].append(merged_segment)
    
    # Only include segments that weren't merged in the unmerged_segments list
    for i, segment in enumerate(video_segments):
        if i not in merged_segment_indices:
            result["unmerged_segments"].append({
                "startTimeMs": segment["startTimeMs"],
                "endTimeMs": segment["endTimeMs"],
                "sellingPoint": segment["fields"].get("sellingPoint", {}).get("valueString", ""),
                "description": segment["fields"].get("description", {}).get("valueString", "")
            })
    
    # Create final segments from merged segments with overlapping segments
    for merged_segment in result["merged_segments"]:
        if merged_segment["overlapping_segments"]:
            # Get startTimeMs from first overlapping segment
            start_time_ms = merged_segment["overlapping_segments"][0]["startTimeMs"]
            
            # Get endTimeMs from last overlapping segment
            end_time_ms = merged_segment["overlapping_segments"][-1]["endTimeMs"]
            
            # Create final segment
            final_segment = {
                "startTimeMs": start_time_ms,
                "endTimeMs": end_time_ms,
                "sellingPoint": merged_segment["content"]
            }
            
            result["final_segments"].append(final_segment)
    
    # Add all unmerged segments to final_segments as well
    for unmerged_segment in result["unmerged_segments"]:
        final_segment = {
            "startTimeMs": unmerged_segment["startTimeMs"],
            "endTimeMs": unmerged_segment["endTimeMs"],
            "sellingPoint": unmerged_segment["sellingPoint"]
        }
        result["final_segments"].append(final_segment)
    
    return result

def visualize_segments(content_json, selling_points_json, merged_segments, output_path=None):
    """
    Visualize the original video segments, selling points, merged segments, and final segments
    
    Args:
        content_json: Original content understanding output JSON
        selling_points_json: Selling points with timestamps JSON
        merged_segments: Result from merge_segments_by_selling_points
        output_path: Path to save the visualization (if None, display instead)
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches
        import numpy as np
        from matplotlib.lines import Line2D
        
        # Get video segments
        video_segments = content_json["result"]["contents"]
        selling_points = selling_points_json["selling_points"]
        
        # Calculate time range for the plot
        max_time_ms = max([segment["endTimeMs"] for segment in video_segments])
        
        # Set up the figure and axes
        fig, ax = plt.subplots(figsize=(15, 8))
        
        # Define colors
        colors = {
            'original': 'lightblue',
            'merged': 'lightgreen',
            'unmerged': 'lightgray',
            'selling_point': 'coral',
            'final_segment': 'purple'  # New color for final segments
        }
        
        # Track y position for plotting
        y_pos = 0
        y_height = 0.8
        y_gap = 1.5
        
        # Plot section titles
        ax.text(-max_time_ms * 0.05, y_pos + y_height/2, "Video Segments", 
                fontsize=10, va='center', ha='right', fontweight='bold')
        
        # Plot original video segments
        for i, segment in enumerate(video_segments):
            start = segment["startTimeMs"]
            end = segment["endTimeMs"]
            label = segment["fields"].get("sellingPoint", {}).get("valueString", "")
            
            # Check if this segment was merged
            was_merged = any(i for merged_segment in merged_segments["merged_segments"] 
                           if merged_segment["overlapping_segments"] and 
                           any(os["startTimeMs"] == segment["startTimeMs"] and os["endTimeMs"] == segment["endTimeMs"] 
                              for os in merged_segment["overlapping_segments"]))
            
            color = colors['merged'] if was_merged else colors['unmerged']
            
            # Draw the segment as a rectangle
            rect = patches.Rectangle((start, y_pos), end - start, y_height, 
                                    facecolor=color, edgecolor='black', alpha=0.7)
            ax.add_patch(rect)
            
            # Add segment label
            if label:
                ax.text((start + end) / 2, y_pos + y_height/2, label, 
                        ha='center', va='center', fontsize=8)
            
            y_pos += y_gap
        
        # Add space between sections
        y_pos += y_gap
        
        # Plot section titles for selling points
        ax.text(-max_time_ms * 0.05, y_pos + y_height/2, "Selling Points", 
                fontsize=10, va='center', ha='right', fontweight='bold')
        
        # Plot selling points with timestamps
        for point in selling_points:
            if point["startTime"] is not None and point["endTime"] is not None:
                start = int(point["startTime"] * 1000)
                end = int(point["endTime"] * 1000)
                
                # Draw the segment as a rectangle
                rect = patches.Rectangle((start, y_pos), end - start, y_height, 
                                        facecolor=colors['selling_point'], edgecolor='black', alpha=0.7)
                ax.add_patch(rect)
                
                # Add segment label
                ax.text((start + end) / 2, y_pos + y_height/2, point["content"][:20] + "...", 
                        ha='center', va='center', fontsize=8)
            else:
                # For selling points without timestamps
                ax.text(0, y_pos + y_height/2, f"No timestamp: {point['content'][:20]}...", 
                        ha='left', va='center', fontsize=8, style='italic')
            
            y_pos += y_gap
        
        # Add space between sections
        y_pos += y_gap
        
        # Plot section titles for merged segments
        ax.text(-max_time_ms * 0.05, y_pos + y_height/2, "Merged Segments", 
                fontsize=10, va='center', ha='right', fontweight='bold')
        
        # Plot merged segments
        for merged_segment in merged_segments["merged_segments"]:
            if merged_segment["startTimeMs"] is not None and merged_segment["endTimeMs"] is not None:
                start = merged_segment["startTimeMs"]
                end = merged_segment["endTimeMs"]
                
                # Draw the segment as a rectangle
                rect = patches.Rectangle((start, y_pos), end - start, y_height, 
                                        facecolor=colors['selling_point'], edgecolor='black', alpha=0.7)
                ax.add_patch(rect)
                
                # Add segment label
                ax.text((start + end) / 2, y_pos + y_height/2, merged_segment["content"][:20] + "...", 
                        ha='center', va='center', fontsize=8)
                
                # Draw lines connecting to original segments
                for overlap in merged_segment["overlapping_segments"]:
                    # Find index of the original segment
                    for i, segment in enumerate(video_segments):
                        if segment["startTimeMs"] == overlap["startTimeMs"] and segment["endTimeMs"] == overlap["endTimeMs"]:
                            # Draw a line from this merged segment to the original segment
                            original_y = i * y_gap + y_height/2
                            merged_y = y_pos + y_height/2
                            
                            mid_x = (overlap["startTimeMs"] + overlap["endTimeMs"]) / 2;
                            
                            ax.add_line(Line2D([mid_x, mid_x], [original_y, merged_y], 
                                              color='black', linestyle='--', alpha=0.5))
                            break
            else:
                # For selling points without timestamps
                ax.text(0, y_pos + y_height/2, f"No matches: {merged_segment['content'][:20]}...", 
                        ha='left', va='center', fontsize=8, style='italic')
            
            y_pos += y_gap
            
        # Add space between sections
        y_pos += y_gap
        
        # Plot section titles for final segments
        ax.text(-max_time_ms * 0.05, y_pos + y_height/2, "Final Segments", 
                fontsize=10, va='center', ha='right', fontweight='bold')
        
        # Plot final segments
        for final_segment in merged_segments["final_segments"]:
            start = final_segment["startTimeMs"]
            end = final_segment["endTimeMs"]
            
            # Draw the segment as a rectangle
            rect = patches.Rectangle((start, y_pos), end - start, y_height, 
                                    facecolor=colors['final_segment'], edgecolor='black', alpha=0.7)
            ax.add_patch(rect)
            
            # Add segment label
            selling_point = final_segment["sellingPoint"]
            if selling_point:
                display_text = selling_point[:20] + "..." if len(selling_point) > 20 else selling_point
                ax.text((start + end) / 2, y_pos + y_height/2, display_text, 
                        ha='center', va='center', fontsize=8)
            
            y_pos += y_gap
        
        # Set axis limits and labels
        ax.set_xlim(-max_time_ms * 0.05, max_time_ms * 1.05)
        ax.set_ylim(-y_gap, y_pos + y_gap)
        ax.set_xlabel('Time (ms)')
        ax.set_title('Video Segment Merging Visualization')
        
        # Remove y-axis ticks and labels
        ax.set_yticks([])
        
        # Add legend
        legend_elements = [
            patches.Patch(facecolor=colors['unmerged'], edgecolor='black', alpha=0.7, label='Unmerged segment'),
            patches.Patch(facecolor=colors['merged'], edgecolor='black', alpha=0.7, label='Merged segment'),
            patches.Patch(facecolor=colors['selling_point'], edgecolor='black', alpha=0.7, label='Selling point'),
            patches.Patch(facecolor=colors['final_segment'], edgecolor='black', alpha=0.7, label='Final segment')
        ]
        ax.legend(handles=legend_elements, loc='upper right')
        
        # Save or display the plot
        if output_path:
            plt.tight_layout()
            plt.savefig(output_path)
            logging.info(f"Visualization saved to {output_path}")
        else:
            plt.tight_layout()
            plt.show()
            
    except ImportError:
        logging.warning("Matplotlib not installed. Visualization skipped.")
    except Exception as e:
        logging.error(f"Error creating visualization: {e}")

def process_video(video_path):
    """
    Process a single video file:
    1. Extract audio from video
    2. Transcribe audio to get word and sentence level transcriptions
    3. Extract selling points from sentence transcription
    4. Match selling points with timestamps 
    5. Save results
    6. Merge video segments based on selling points
    7. Visualize the merging (optional)
    
    Args:
        video_path (str): Path to the video file
    """
    base = os.path.splitext(video_path)[0]
    word_txt_path = base + "_word.txt"
    sentence_txt_path = base + "_sentence.txt"
    selling_points_path = base + "_selling_points.json"
    merged_segments_path = base + "_merged_segments.json"
    visualization_path = base + "_segments_visualization.png"
    content_json_path = video_path + ".json"  # Assuming content understanding output is named as video_name.mp4.json
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
        
        # Step 7: Merge video segments based on selling points if content JSON exists
        if os.path.exists(content_json_path):
            try:
                with open(content_json_path, 'r') as f:
                    content_json = json.load(f)
                
                with open(selling_points_path, 'r') as f:
                    selling_points_json = json.load(f)
                
                # Using min_overlap_percentage of 0.2 (20%) to avoid merging segments with minimal overlap
                merged_segments = merge_segments_by_selling_points(content_json, selling_points_json, 
                                                                  time_deviation_ms=0, 
                                                                  min_overlap_percentage=0.2)
                
                with open(merged_segments_path, 'w') as f:
                    json.dump(merged_segments, f, indent=2)
                
                logging.info(f"Merged segments saved to {merged_segments_path}")
                
                # Step 8: Create visualization
                visualize_segments(content_json, selling_points_json, merged_segments, visualization_path)
                
            except Exception as e:
                logging.error(f"Failed to merge video segments: {e}")
        else:
            logging.warning(f"Content understanding output file {content_json_path} not found. Skipping segment merging.")
        
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