import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import morgan from 'morgan';
import rateLimit from 'express-rate-limit';
import dotenv from 'dotenv';

dotenv.config();

const app = express();

// Middleware
app.use(helmet());
app.use(morgan('dev'));
app.use(express.json());

// CORS configuration
const corsOptions = {
  origin: process.env.CORS_ORIGIN === '*' ? '*' : process.env.CORS_ORIGIN,
  optionsSuccessStatus: 200,
};
app.use(cors(corsOptions));

// Rate Limiting
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // limit each IP to 100 requests per windowMs
  message: {
    status: 'error',
    message: 'Too many requests from this IP, please try again after 15 minutes',
  },
});
app.use('/api/', limiter);

// Import Routes
import trackRoutes from './routes/trackRoutes.js';
import projectRoutes from './routes/projectRoutes.js';
import authRoutes from './routes/authRoutes.js';
import swaggerUi from 'swagger-ui-express';
import { readFileSync } from 'fs';
import { load } from 'js-yaml';
import { fileURLToPath } from 'url';
import path from 'path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const swaggerDocument = load(readFileSync(path.join(__dirname, 'swagger.yaml'), 'utf8'));

// Mount Routes
app.use('/api/v1/track', trackRoutes);
app.use('/api/v1/projects', projectRoutes);
app.use('/api/v1/auth', authRoutes);
app.use('/api-docs', swaggerUi.serve, swaggerUi.setup(swaggerDocument));

// Health Check Endpoint
app.get('/health', (req, res) => {
  res.status(200).json({ status: 'success', message: 'Server is healthy' });
});

export default app;
