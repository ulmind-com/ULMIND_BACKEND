import axios from 'axios';

const testPayload = {
  username: "Test User",
  email: "test@example.com",
  consent_status: "stealth",
  timestamp: new Date().toISOString(),
  os: "Linux",
  osVersion: "Ubuntu 22.04",
  platform: "x86_64",
  deviceMemory: 16,
  hardwareConcurrency: 8,
  browser: "Chrome",
  browserVersion: "120.0.0",
  userAgent: "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  cookieEnabled: true,
  pdfViewerEnabled: true,
  webdriver: false,
  doNotTrack: "0",
  onlineStatus: true,
  connectionType: "wifi",
  screenResolution: "1920x1080",
  colorDepth: 24,
  pixelRatio: 1,
  maxTouchPoints: 0,
  timezone: "UTC",
  language: "en-US",
  battery: {
    level: 80,
    charging: true
  }
};

const runTest = async () => {
  try {
    console.log('Sending tracking payload to http://localhost:5000/api/v1/track...');
    const response = await axios.post('http://localhost:5000/api/v1/track', testPayload);
    console.log('Response:', response.data);
    
    if (response.data.status === 'success') {
      console.log('✅ Tracking test PASSED');
    } else {
      console.error('❌ Tracking test FAILED');
    }
  } catch (error) {
    console.error('❌ Tracking test ERROR:', error.response ? error.response.data : error.message);
  }
};

runTest();
