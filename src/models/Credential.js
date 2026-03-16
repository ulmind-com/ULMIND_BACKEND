import mongoose from 'mongoose';

const credentialSchema = new mongoose.Schema(
  {
    project_id: { type: mongoose.Schema.Types.ObjectId, ref: 'Project', required: true },
    name: { type: String, required: true },
    encrypted_value: { type: String, required: true },
    iv: { type: String, required: true },
  },
  { timestamps: true }
);

export default mongoose.model('Credential', credentialSchema);
