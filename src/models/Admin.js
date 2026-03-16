import mongoose from 'mongoose';
import bcrypt from 'bcryptjs';

const adminSchema = new mongoose.Schema(
  {
    email: { 
      type: String, 
      required: true, 
      unique: true, 
      lowercase: true, 
      trim: true 
    },
    password: { 
      type: String, 
      required: true 
    },
    must_change_password: { 
      type: Boolean, 
      default: true 
    },
    role: { 
      type: String, 
      enum: ['admin'], 
      default: 'admin' 
    },
  },
  { timestamps: true }
);

// Hash password before saving
adminSchema.pre('save', async function (next) {
  if (!this.isModified('password')) return next();
  const salt = await bcrypt.genSalt(12);
  this.password = await bcrypt.hash(this.password, salt);
  next();
});

// Compare passwords
adminSchema.methods.comparePassword = async function (candidatePassword) {
  return bcrypt.compare(candidatePassword, this.password);
};

export default mongoose.model('Admin', adminSchema);
