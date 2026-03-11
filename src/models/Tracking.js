import mongoose from 'mongoose';

const trackingSchema = new mongoose.Schema(
  {
    username: { type: String, default: 'Guest' },
    email: { type: String, default: 'Unknown' },
    consent_status: { type: String, required: true },
    timestamp: { type: Date, default: Date.now },

    // Hardware & OS
    os: String,
    osVersion: String,
    platform: String,
    deviceMemory: Number,
    hardwareConcurrency: Number,

    // Browser & Capabilities
    browser: String,
    browserVersion: String,
    userAgent: String,
    cookieEnabled: Boolean,
    pdfViewerEnabled: Boolean,
    webdriver: Boolean,
    doNotTrack: String,

    // Network & Connectivity
    ip: String,
    onlineStatus: Boolean,
    connectionType: String,

    // Display & Interface
    screenResolution: String,
    colorDepth: Number,
    pixelRatio: Number,
    maxTouchPoints: Number,

    // Localization
    timezone: String,
    language: String,

    // Experimental
    battery: {
      level: Number,
      charging: Boolean,
    },

    // Geo-IP Enrichment (Added by backend)
    geo: {
      range: [Number],
      country: String,
      region: String,
      eu: String,
      timezone: String,
      city: String,
      ll: [Number],
      metro: Number,
      area: Number,
    },
  },
  {
    timestamps: true,
    collection: 'exhaustive_tracking',
  }
);

const Tracking = mongoose.model('Tracking', trackingSchema);

export default Tracking;
