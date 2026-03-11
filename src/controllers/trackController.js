import geoip from 'geoip-lite';
import Tracking from '../models/Tracking.js';
import { validateTrack } from '../validators/trackValidator.js';

export const trackData = async (req, res) => {
  try {
    const { error } = validateTrack(req.body);
    if (error) {
      return res.status(400).json({
        status: 'error',
        message: 'Validation failed',
        details: error.details.map((d) => d.message),
      });
    }

    // Get IP from request (handling proxies)
    const ip = req.headers['x-forwarded-for'] || req.socket.remoteAddress;
    const clientIp = ip.split(',')[0].trim();

    // Geo-IP Enrichment
    const geo = geoip.lookup(clientIp);

    // Prepare data to save
    const trackingData = new Tracking({
      ...req.body,
      ip: clientIp,
      geo: geo ? geo : undefined,
    });

    await trackingData.save();

    res.status(200).json({
      status: 'success',
      message: 'Tracking data synchronized',
    });
  } catch (error) {
    console.error(`Tracking Error: ${error.message}`);
    res.status(500).json({
      status: 'error',
      message: 'Internal server error',
    });
  }
};
