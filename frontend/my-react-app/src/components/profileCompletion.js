/*
GenAI attribution:
Developed with assistance from ChatGPT (OpenAI).
Prompt: Extract JH-020 profile completion validation
into a reusable function for React components and tests.
Reviewed and adapted for the CS467 project.
*/

export function getMissingProfileFields({
  skills,
  educationLevel,
  experienceLevel,
}) {
  const missing = [];

  if (!skills.length) {
    missing.push("Add at least one skill.");
  }

  if (!educationLevel) {
    missing.push("Select your education level.");
  }

  if (!experienceLevel) {
    missing.push("Select your experience level.");
  }

  return missing;
}