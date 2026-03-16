import Project from '../models/Project.js';

export const createProject = async (req, res) => {
  try {
    const project = new Project(req.body);
    await project.save();
    res.status(201).json(project);
  } catch (error) {
    res.status(500).json({ error: 'Failed to create project' });
  }
};

export const updateProjectStatus = async (req, res) => {
  try {
    const { id } = req.params;
    const { status } = req.body;
    const project = await Project.findByIdAndUpdate(id, { status }, { new: true });
    if (!project) return res.status(404).json({ error: 'Project not found' });
    res.json(project);
  } catch (error) {
    res.status(500).json({ error: 'Failed to update status' });
  }
};

export const getProjects = async (req, res) => {
  try {
    const projects = await Project.find();
    res.json(projects);
  } catch (error) {
    res.status(500).json({ error: 'Failed to retrieve projects' });
  }
};
