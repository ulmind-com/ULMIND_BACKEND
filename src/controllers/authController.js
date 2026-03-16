import jwt from 'jsonwebtoken';
import Admin from '../models/Admin.js';

// Generate a JWT
const generateToken = (admin) => {
  return jwt.sign(
    { id: admin._id, email: admin.email, role: admin.role },
    process.env.JWT_SECRET,
    { expiresIn: '8h' }
  );
};

// POST /api/v1/auth/login
export const login = async (req, res) => {
  try {
    const { email, password } = req.body;
    if (!email || !password)
      return res.status(400).json({ error: 'Email and password are required' });

    const admin = await Admin.findOne({ email });
    if (!admin || !(await admin.comparePassword(password)))
      return res.status(401).json({ error: 'Invalid credentials' });

    const token = generateToken(admin);

    res.json({
      token,
      must_change_password: admin.must_change_password,
      email: admin.email,
    });
  } catch (err) {
    res.status(500).json({ error: 'Login failed' });
  }
};

// POST /api/v1/auth/change-password  (protected)
export const changePassword = async (req, res) => {
  try {
    const { current_password, new_password } = req.body;
    if (!current_password || !new_password)
      return res.status(400).json({ error: 'current_password and new_password are required' });

    const admin = await Admin.findById(req.admin.id);
    if (!admin) return res.status(404).json({ error: 'Admin not found' });

    const valid = await admin.comparePassword(current_password);
    if (!valid) return res.status(401).json({ error: 'Current password is incorrect' });

    if (new_password.length < 8)
      return res.status(400).json({ error: 'New password must be at least 8 characters' });

    admin.password = new_password;
    admin.must_change_password = false;
    await admin.save(); // pre-save hook will hash the new password

    res.json({ message: 'Password changed successfully' });
  } catch (err) {
    res.status(500).json({ error: 'Password change failed' });
  }
};

// GET /api/v1/auth/me  (protected)
export const getMe = async (req, res) => {
  try {
    const admin = await Admin.findById(req.admin.id).select('-password');
    if (!admin) return res.status(404).json({ error: 'Admin not found' });
    res.json(admin);
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch admin profile' });
  }
};
