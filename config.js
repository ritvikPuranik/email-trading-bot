const fs = require('fs');
const path = require('path');
require('dotenv').config();

const credentialsPath = path.join(__dirname, 'credentials.json');
let credentials = fs.readFileSync(credentialsPath, 'utf-8');

// Replace all environment variables
credentials = credentials.replace(/\${NGROK_URL}/g, process.env.NGROK_URL);
credentials = credentials.replace(/\${GOOGLE_CLIENT_ID}/g, process.env.GOOGLE_CLIENT_ID);
credentials = credentials.replace(/\${GOOGLE_CLIENT_SECRET}/g, process.env.GOOGLE_CLIENT_SECRET);
credentials = credentials.replace(/\${GOOGLE_PROJECT_ID}/g, process.env.GOOGLE_PROJECT_ID);

fs.writeFileSync(credentialsPath, credentials);
