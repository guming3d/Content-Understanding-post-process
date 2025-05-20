document.addEventListener('DOMContentLoaded', function() {
    // DOM elements
    const videoPlayer = document.getElementById('video-player');
    const videoInput = document.getElementById('video-file');
    const jsonInput = document.getElementById('json-file');
    const timelineContainer = document.getElementById('timeline');
    const segmentInfo = document.getElementById('segment-info');
    const statusMessage = document.getElementById('status-message');
    
    // Variables to store data
    let segmentsData = null;
    let selectedSegment = null;
    let timeScale = 10;  // pixels per millisecond (will be adjusted based on video duration)
    
    // Event listeners for file inputs
    videoInput.addEventListener('change', handleVideoUpload);
    jsonInput.addEventListener('change', handleJsonUpload);
    
    // Video event listeners
    videoPlayer.addEventListener('loadedmetadata', updateTimelineScale);
    videoPlayer.addEventListener('timeupdate', updateTimeMarker);
    
    // Show status message
    function showStatus(message, isError = false) {
        statusMessage.textContent = message;
        statusMessage.className = 'status-message ' + (isError ? 'error' : 'success');
        statusMessage.classList.add('show');
        
        setTimeout(() => {
            statusMessage.classList.remove('show');
        }, 3000);
    }
    
    // Handle JSON file upload
    function handleJsonUpload(event) {
        const file = event.target.files[0];
        if (file) {
            const reader = new FileReader();
            
            reader.onload = function(e) {
                try {
                    const data = JSON.parse(e.target.result);
                    
                    if (!data || !data.merged_segments) {
                        throw new Error(`Invalid segment data format in ${file.name}`);
                    }
                    
                    segmentsData = data;
                    updateTimelineScale(); // Use this instead of renderTimeline directly
                    enableControls();
                    showStatus(`Segments loaded successfully from ${file.name}`);
                } catch (error) {
                    console.error('Error parsing JSON:', error);
                    showStatus(`Error: ${error.message}`, true);
                }
            };
            
            reader.onerror = function() {
                console.error('Error reading file');
                showStatus('Error reading JSON file', true);
            };
            
            reader.readAsText(file);
        }
    }
    
    // Handle video file upload
    function handleVideoUpload(event) {
        const file = event.target.files[0];
        if (file) {
            const videoURL = URL.createObjectURL(file);
            videoPlayer.src = videoURL;
            videoPlayer.load();
        }
    }
    
    // Update timeline scale based on video duration and container width
    function updateTimelineScale() {
        const videoDurationMs = videoPlayer.duration * 1000;
        if (videoDurationMs) {
            // Get the container width to scale the timeline properly
            const containerWidth = timelineContainer.clientWidth;
            
            // Leave some margin on the sides (10% of container width)
            const effectiveWidth = containerWidth * 0.9;
            
            // Calculate scale to make the timeline fit in the container
            timeScale = effectiveWidth / videoDurationMs;
            
            console.log(`Timeline scaled: container width=${containerWidth}px, duration=${videoDurationMs}ms, scale=${timeScale}`);
            
            // If segments are already loaded, render them with the new scale
            if (segmentsData) {
                renderTimeline();
            }
            
            // Add time markers
            addTimeMarkers(videoDurationMs);
        }
    }
    
    // Add time markers to the timeline
    function addTimeMarkers(durationMs) {
        // Clear existing markers
        const existingMarkers = timelineContainer.querySelectorAll('.time-marker');
        existingMarkers.forEach(marker => marker.remove());
        
        // Add markers every 5 seconds
        const intervalMs = 5000; // 5 seconds in ms
        for (let timeMs = 0; timeMs <= durationMs; timeMs += intervalMs) {
            const marker = document.createElement('div');
            marker.className = 'time-marker';
            marker.style.left = (timeMs * timeScale) + 'px';
            
            const label = document.createElement('div');
            label.textContent = formatTime(timeMs / 1000);
            label.style.position = 'absolute';
            label.style.top = '0';
            label.style.fontSize = '10px';
            
            marker.appendChild(label);
            timelineContainer.appendChild(marker);
        }
    }
    
    // Format time in seconds to MM:SS format
    function formatTime(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }
    
    // Update time marker during video playback
    function updateTimeMarker() {
        // Remove existing current time marker
        const existingCurrentMarker = timelineContainer.querySelector('.current-time');
        if (existingCurrentMarker) {
            existingCurrentMarker.remove();
        }
        
        // Create new marker at current time
        const currentTimeMs = videoPlayer.currentTime * 1000;
        const marker = document.createElement('div');
        marker.className = 'time-marker current-time';
        marker.style.left = (currentTimeMs * timeScale) + 'px';
        
        // Add timestamp label above the line
        const timeLabel = document.createElement('div');
        timeLabel.textContent = formatTime(videoPlayer.currentTime);
        timeLabel.className = 'time-label';
        marker.appendChild(timeLabel);
        
        timelineContainer.appendChild(marker);
    }
    
    // Render timeline with segments
    function renderTimeline() {
        // Clear existing segments
        const existingSegments = timelineContainer.querySelectorAll('.segment');
        existingSegments.forEach(segment => segment.remove());
        
        // Calculate y-position offsets for different segment types
        const positionOffsets = {
            'unmerged': 10,
            'selling': 50,
            'merged': 90,
            'final': 130
        };
        
        // Render unmerged segments
        if (segmentsData.unmerged_segments) {
            renderSegmentsGroup(segmentsData.unmerged_segments, 'unmerged', positionOffsets.unmerged);
        }
        
        // Render merged segments
        if (segmentsData.merged_segments) {
            for (const segment of segmentsData.merged_segments) {
                if (segment.startTimeMs !== null && segment.endTimeMs !== null) {
                    renderSegment({
                        startTimeMs: segment.startTimeMs,
                        endTimeMs: segment.endTimeMs,
                        sellingPoint: segment.content,
                        overlapping_segments: segment.overlapping_segments
                    }, 'selling-point', positionOffsets.selling);
                }
            }
        }
        
        // Render final segments
        if (segmentsData.final_segments) {
            renderSegmentsGroup(segmentsData.final_segments, 'final-segment', positionOffsets.final);
        }
    }
    
    // Render a group of segments
    function renderSegmentsGroup(segments, className, yPosition) {
        segments.forEach(segment => {
            renderSegment(segment, className, yPosition);
        });
    }
    
    // Render a single segment
    function renderSegment(segment, className, yPosition) {
        const startMs = segment.startTimeMs;
        const endMs = segment.endTimeMs;
        
        // Create segment element
        const segmentEl = document.createElement('div');
        segmentEl.className = 'segment ' + className;
        segmentEl.style.left = (startMs * timeScale) + 'px';
        segmentEl.style.width = ((endMs - startMs) * timeScale) + 'px';
        segmentEl.style.top = yPosition + 'px';
        
        // Set label (selling point or description)
        const label = segment.sellingPoint || segment.content || '';
        segmentEl.textContent = label;
        
        // If this is a final segment, apply special styling for white text
        if (className === 'final-segment') {
            segmentEl.classList.add('white-text');
        }
        
        // Store segment data for later use
        segmentEl.dataset.start = startMs;
        segmentEl.dataset.end = endMs;
        segmentEl.dataset.content = label;
        
        // Add click handler
        segmentEl.addEventListener('click', () => selectSegment(segmentEl, segment));
        
        // Add to timeline
        timelineContainer.appendChild(segmentEl);
    }
    
    // Select a segment
    function selectSegment(element, segmentData) {
        // Remove selection from previously selected segment
        const previouslySelected = timelineContainer.querySelector('.segment.selected');
        if (previouslySelected) {
            previouslySelected.classList.remove('selected');
        }
        
        // Add selection to new segment
        element.classList.add('selected');
        selectedSegment = segmentData;
        
        // Update segment info display
        updateSegmentInfo(segmentData);
    }
    
    // Update segment info display
    function updateSegmentInfo(segment) {
        const startTime = formatTime(segment.startTimeMs / 1000);
        const endTime = formatTime(segment.endTimeMs / 1000);
        const duration = (segment.endTimeMs - segment.startTimeMs) / 1000;
        
        let infoText = `Start: ${startTime}\n`;
        infoText += `End: ${endTime}\n`;
        infoText += `Duration: ${duration.toFixed(2)}s\n`;
        infoText += `Content: ${segment.sellingPoint || segment.content || 'N/A'}\n`;
        
        if (segment.description) {
            infoText += `Description: ${segment.description}\n`;
        }
        
        // Add overlapping segments if available
        if (segment.overlapping_segments && segment.overlapping_segments.length > 0) {
            infoText += `\nOverlapping Segments (${segment.overlapping_segments.length}):\n`;
            segment.overlapping_segments.forEach((overlap, index) => {
                infoText += `  ${index + 1}. ${overlap.sellingPoint} (${formatTime(overlap.startTimeMs / 1000)} - ${formatTime(overlap.endTimeMs / 1000)})\n`;
                if (overlap.description) {
                    infoText += `     Description: ${overlap.description}\n`;
                }
            });
        }
        
        segmentInfo.textContent = infoText;
    }
    
    // Enable controls
    function enableControls() {
        // Just keep the function for backward compatibility
    }
    
    // Add window resize event to adjust timeline when window size changes
    window.addEventListener('resize', debounce(function() {
        updateTimelineScale();
    }, 250));
    
    // Debounce function to limit how often the resize handler is called
    function debounce(func, wait) {
        let timeout;
        return function() {
            const context = this;
            const args = arguments;
            clearTimeout(timeout);
            timeout = setTimeout(function() {
                func.apply(context, args);
            }, wait);
        };
    }
});
