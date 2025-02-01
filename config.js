const fs = require('fs');
const path = require('path');
require('dotenv').config();

const credentialsPath = path.join(__dirname, 'credentials.json');
let credentials = fs.readFileSync(credentialsPath, 'utf-8');

credentials = credentials.replace(/\${NGROK_URL}/g, process.env.NGROK_URL);

fs.writeFileSync(credentialsPath, credentials);
