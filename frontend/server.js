const express = require('express');
const path = require('path');
const fs = require('fs');
const app = express();
const port = 3000;

// Serve static files from the frontend directory
app.use(express.static(path.join(__dirname)));

// Inputs directory path
const inputsDir = path.join(__dirname, '..', 'inputs');

// Serve files from the inputs directory
app.use('/inputs', express.static(inputsDir));

// Add a route to check for specific files
app.get('/check-file/:filename', (req, res) => {
  const filename = req.params.filename;
  const filePath = path.join(inputsDir, filename);
  
  fs.access(filePath, fs.constants.F_OK, (err) => {
    if (err) {
      // File doesn't exist
      res.json({ 
        exists: false, 
        error: err.message,
        searchPath: filePath
      });
    } else {
      // File exists
      res.json({ 
        exists: true, 
        path: filePath,
        size: fs.statSync(filePath).size
      });
    }
  });
});

// Add a route to list all files in the inputs directory
app.get('/list-inputs', (req, res) => {
  fs.readdir(inputsDir, (err, files) => {
    if (err) {
      res.status(500).json({ error: err.message });
    } else {
      res.json({ files: files });
    }
  });
});

// Start the server
app.listen(port, () => {
  console.log(`Video Segmentation UI server running at http://localhost:${port}`);
  console.log(`Serving inputs from: ${inputsDir}`);
  
  // List all segment JSON files in the inputs directory
  fs.readdir(inputsDir, (err, files) => {
    if (err) {
      console.log(`⚠️ Error reading inputs directory: ${err.message}`);
    } else {
      const segmentFiles = files.filter(file => file.endsWith('_merged_segments.json'));
      console.log(`Found ${segmentFiles.length} segment files in inputs directory:`);
      segmentFiles.forEach(file => {
        console.log(`  - ${file}`);
      });
    }
  });
});
