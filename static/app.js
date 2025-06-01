// Video Analysis Platform - Frontend Application

class VideoAnalysisApp {
    constructor() {
        this.selectedVideo = null;
        this.ws = null;
        this.currentResults = null;
        
        this.initializeWebSocket();
        this.bindEvents();
        this.loadVideos();
    }

    initializeWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.updateConnectionStatus(true);
        };
        
        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            this.updateConnectionStatus(false);
            // Reconnect after 3 seconds
            setTimeout(() => this.initializeWebSocket(), 3000);
        };
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'status_update') {
                this.handleStatusUpdate(data);
            }
        };
    }

    updateConnectionStatus(connected) {
        const statusEl = document.getElementById('connection-status');
        const indicator = statusEl.querySelector('div');
        const text = statusEl.querySelector('span');
        
        if (connected) {
            indicator.className = 'w-2 h-2 bg-green-500 rounded-full mr-2';
            text.textContent = 'Connected';
        } else {
            indicator.className = 'w-2 h-2 bg-red-500 rounded-full mr-2';
            text.textContent = 'Disconnected';
        }
    }

    bindEvents() {
        // Process button
        document.getElementById('process-btn').addEventListener('click', () => {
            this.processVideo();
        });
        
        // Tab navigation
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.switchTab(e.target.dataset.tab);
            });
        });
        
        // Close button for results modal
        const closeButton = document.querySelector('#results-panel .close-btn') || 
                           document.querySelector('#results-panel button[aria-label="Close"]') ||
                           document.querySelector('#results-panel [data-close]');
        
        if (closeButton) {
            closeButton.addEventListener('click', () => {
                document.getElementById('results-panel').classList.add('hidden');
            });
        }
    }

    async loadVideos() {
        try {
            const response = await fetch('/api/videos');
            const videos = await response.json();
            
            const videoList = document.getElementById('video-list');
            videoList.innerHTML = '';
            
            if (videos.length === 0) {
                videoList.innerHTML = '<p class="text-gray-500 text-sm">No videos found in inputs directory</p>';
                return;
            }
            
            videos.forEach(video => {
                const videoEl = document.createElement('div');
                videoEl.className = 'video-item';
                videoEl.innerHTML = `
                    <div class="flex items-center justify-between">
                        <div class="flex items-center">
                            <i class="fas fa-file-video text-gray-400 mr-3"></i>
                            <div>
                                <p class="font-medium text-gray-900">${video.name}</p>
                                <p class="text-xs text-gray-500">${video.size_mb} MB</p>
                            </div>
                        </div>
                    </div>
                `;
                
                videoEl.addEventListener('click', () => {
                    this.selectVideo(video, videoEl);
                });
                
                videoList.appendChild(videoEl);
            });
        } catch (error) {
            console.error('Error loading videos:', error);
        }
    }

    selectVideo(video, element) {
        // Update UI
        document.querySelectorAll('.video-item').forEach(el => {
            el.classList.remove('selected');
        });
        element.classList.add('selected');
        
        this.selectedVideo = video;
        document.getElementById('process-btn').disabled = false;
        
        // Hide welcome message
        document.getElementById('welcome-message').classList.add('hidden');
        
        // Check if results exist
        this.checkExistingResults(video.name);
    }

    async checkExistingResults(videoName) {
        try {
            const response = await fetch(`/api/results/${videoName}`);
            const results = await response.json();
            
            if (Object.keys(results).length > 0) {
                this.currentResults = results;
                this.displayResults();
            }
        } catch (error) {
            console.error('Error checking results:', error);
        }
    }

    async processVideo() {
        if (!this.selectedVideo) return;
        
        const processBtn = document.getElementById('process-btn');
        processBtn.disabled = true;
        processBtn.innerHTML = '<i class="fas fa-spinner spinner mr-2"></i>Processing...';
        
        const enableContentUnderstanding = document.getElementById('enable-content-understanding').checked;
        
        try {
            const response = await fetch('/api/process', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    video_name: this.selectedVideo.name,
                    enable_content_understanding: enableContentUnderstanding
                })
            });
            
            if (response.ok) {
                document.getElementById('processing-status').classList.remove('hidden');
                document.getElementById('results-panel').classList.add('hidden');
            }
        } catch (error) {
            console.error('Error starting processing:', error);
            alert('Failed to start processing');
        } finally {
            processBtn.disabled = false;
            processBtn.innerHTML = '<i class="fas fa-play mr-2"></i>Start Processing';
        }
    }

    handleStatusUpdate(data) {
        if (data.video_name !== this.selectedVideo?.name) return;
        
        const statusEl = document.getElementById('processing-status');
        const messageEl = document.getElementById('status-message');
        const progressBar = document.getElementById('progress-bar');
        const progressPercent = document.getElementById('progress-percent');
        
        messageEl.textContent = data.message;
        progressBar.style.width = `${data.progress}%`;
        progressPercent.textContent = `${data.progress}%`;
        
        if (data.status === 'completed') {
            statusEl.classList.add('hidden');
            this.loadResults();
        } else if (data.status === 'error') {
            statusEl.classList.add('bg-red-50');
            progressBar.classList.add('bg-red-600');
        }
    }

    async loadResults() {
        if (!this.selectedVideo) return;
        
        try {
            const response = await fetch(`/api/results/${this.selectedVideo.name}`);
            const results = await response.json();
            
            this.currentResults = results;
            this.displayResults();
        } catch (error) {
            console.error('Error loading results:', error);
        }
    }

    displayResults() {
        document.getElementById('results-panel').classList.remove('hidden');
        
        // Display selling points
        this.displaySellingPoints();
        
        // Display transcription
        this.displayTranscription();
        
        // Display segments
        this.displaySegments();
        
        // Load visualization
        this.loadVisualization();
    }

    displaySellingPoints() {
        const container = document.getElementById('selling-points-content');
        container.innerHTML = '';
        
        if (!this.currentResults.selling_points) {
            container.innerHTML = '<p class="text-gray-500">No selling points found</p>';
            return;
        }
        
        const sellingPoints = this.currentResults.selling_points.selling_points;
        
        sellingPoints.forEach((point, index) => {
            const card = document.createElement('div');
            card.className = 'selling-point-card';
            
            const hasTimestamp = point.startTime !== null && point.endTime !== null;
            const timestampHtml = hasTimestamp 
                ? `<span class="text-xs text-gray-500">${point.startTime.toFixed(2)}s - ${point.endTime.toFixed(2)}s</span>`
                : '<span class="text-xs text-gray-400 italic">No timestamp</span>';
            
            card.innerHTML = `
                <div class="flex items-start justify-between">
                    <div class="flex-1">
                        <p class="text-gray-900">${point.content}</p>
                        ${timestampHtml}
                    </div>
                    <span class="ml-2 text-xs font-medium text-gray-500">#${index + 1}</span>
                </div>
            `;
            
            container.appendChild(card);
        });
    }

    displayTranscription() {
        const container = document.getElementById('sentence-transcription');
        
        if (!this.currentResults.sentence_transcription) {
            container.innerHTML = '<p class="text-gray-500">No transcription available</p>';
            return;
        }
        
        container.innerHTML = `<pre class="whitespace-pre-wrap">${this.currentResults.sentence_transcription}</pre>`;
    }

    displaySegments() {
        const container = document.getElementById('segments-content');
        container.innerHTML = '';
        
        if (!this.currentResults.merged_segments) {
            container.innerHTML = '<p class="text-gray-500">No segment data available</p>';
            return;
        }
        
        const segments = this.currentResults.merged_segments;
        
        // Display final segments
        if (segments.final_segments && segments.final_segments.length > 0) {
            const finalSegmentsDiv = document.createElement('div');
            finalSegmentsDiv.innerHTML = `
                <h3 class="font-medium text-gray-900 mb-3">Final Segments</h3>
                <div class="space-y-2">
                    ${segments.final_segments.map((seg, i) => `
                        <div class="flex items-center space-x-3 p-3 bg-purple-50 rounded-lg">
                            <span class="text-sm font-medium text-purple-700">${i + 1}</span>
                            <div class="flex-1">
                                <p class="text-sm text-gray-900">${seg.sellingPoint || 'No selling point'}</p>
                                <p class="text-xs text-gray-500">${(seg.startTimeMs/1000).toFixed(2)}s - ${(seg.endTimeMs/1000).toFixed(2)}s</p>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
            container.appendChild(finalSegmentsDiv);
        }
    }

    async loadVisualization() {
        const container = document.getElementById('visualization-content');
        
        try {
            const response = await fetch(`/api/visualization/${this.selectedVideo.name}`);
            
            if (response.ok) {
                container.innerHTML = `<img src="/api/visualization/${this.selectedVideo.name}" alt="Segment Visualization" class="max-w-full rounded-lg shadow-md">`;
            } else {
                container.innerHTML = '<p class="text-gray-500">No visualization available</p>';
            }
        } catch (error) {
            container.innerHTML = '<p class="text-gray-500">Failed to load visualization</p>';
        }
    }

    switchTab(tabName) {
        // Update tab buttons
        document.querySelectorAll('.tab-btn').forEach(btn => {
            if (btn.dataset.tab === tabName) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
        
        // Update tab content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.add('hidden');
        });
        
        const activeTab = document.getElementById(`${tabName}-tab`);
        if (activeTab) {
            activeTab.classList.remove('hidden');
        }
    }
}

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new VideoAnalysisApp();
});
