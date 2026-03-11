import Joi from 'joi';

const trackSchema = Joi.object({
  username: Joi.string().allow('', null),
  email: Joi.string().email().allow('', 'Unknown', null),
  consent_status: Joi.string().valid('accepted', 'declined', 'stealth').required(),
  timestamp: Joi.string().isoDate(),

  // Hardware & OS
  os: Joi.string().allow('', null),
  osVersion: Joi.string().allow('', null),
  platform: Joi.string().allow('', null),
  deviceMemory: Joi.number().allow(null),
  hardwareConcurrency: Joi.number().allow(null),

  // Browser & Capabilities
  browser: Joi.string().allow('', null),
  browserVersion: Joi.string().allow('', null),
  userAgent: Joi.string().allow('', null),
  cookieEnabled: Joi.boolean(),
  pdfViewerEnabled: Joi.boolean(),
  webdriver: Joi.boolean(),
  doNotTrack: Joi.string().allow('', null),

  // Network & Connectivity
  ip: Joi.string().allow('', null),
  onlineStatus: Joi.boolean(),
  connectionType: Joi.string().allow('', null),

  // Display & Interface
  screenResolution: Joi.string().allow('', null),
  colorDepth: Joi.number().allow(null),
  pixelRatio: Joi.number().allow(null),
  maxTouchPoints: Joi.number().allow(null),

  // Localization
  timezone: Joi.string().allow('', null),
  language: Joi.string().allow('', null),

  // Experimental
  battery: Joi.object({
    level: Joi.number().allow(null),
    charging: Joi.boolean(),
  }).allow(null),
});

export const validateTrack = (data) => {
  return trackSchema.validate(data, { abortEarly: false, allowUnknown: true });
};
