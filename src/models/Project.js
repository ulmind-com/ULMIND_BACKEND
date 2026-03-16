import mongoose from 'mongoose';

const projectSchema = new mongoose.Schema(
  {
    name: { type: String, required: true },
    description: { type: String },
    status: { 
      type: String, 
      enum: ['Planning', 'Active', 'On-Hold', 'Completed'], 
      default: 'Planning' 
    },
    manager_id: { type: String, required: true },
  },
  { timestamps: true }
);

export default mongoose.model('Project', projectSchema);
