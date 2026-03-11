import express from 'express';
import { trackData } from '../controllers/trackController.js';

const router = express.Router();

router.post('/', trackData);

export default router;
