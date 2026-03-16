import express from 'express';
import { createProject, getProjects, updateProjectStatus } from '../controllers/projectController.js';
import protect from '../middleware/authMiddleware.js';

const router = express.Router();

// All project routes require a valid admin JWT
router.use(protect);

router.post('/', createProject);
router.get('/', getProjects);
router.patch('/:id/status', updateProjectStatus);

export default router;
