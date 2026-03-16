/**
 * Admin Seeder
 * Run once: node seed/seedAdmins.js
 * Creates admin accounts with initial password "ulmind@123" (bcrypt hashed).
 * All admins will be forced to change their password on first login.
 */

import mongoose from 'mongoose';
import dotenv from 'dotenv';
import Admin from '../src/models/Admin.js';

dotenv.config();

const ADMIN_EMAILS = [
  'soumyajit.banerjee@ulmind.com',
  'arnab.senapati@ulmind.com',
  'samiran.samanta@ulmind.com',
  'sagnik.mondal@ulmind.com',
  'thirtha.ghosh@ulmind.in',
  'swastika.roy@ulmind.in',
  'roni.routh@ulmind.in',
];

const INITIAL_PASSWORD = 'ulmind@123';

const seed = async () => {
  try {
    await mongoose.connect(process.env.MONGO_URI);
    console.log('Connected to MongoDB');

    for (const email of ADMIN_EMAILS) {
      const existing = await Admin.findOne({ email });
      if (existing) {
        console.log(`SKIP: Admin already exists → ${email}`);
        continue;
      }

      const admin = new Admin({
        email,
        password: INITIAL_PASSWORD,
        must_change_password: true,
      });
      await admin.save();
      console.log(`CREATED: ${email}`);
    }

    console.log('\nSeeding complete.');
    process.exit(0);
  } catch (err) {
    console.error('Seeding failed:', err.message);
    process.exit(1);
  }
};

seed();
