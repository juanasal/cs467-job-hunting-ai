/*
GenAI attribution:
Developed with assistance from ChatGPT (OpenAI).
Prompt: Implement JH-022 frontend validation for optional
annual USD salary bounds and maximum recommendation count.
Follow the JH-002 data contract and JH-018 backend limits.
Preserve decimal salary precision and support empty salary fields.
Reviewed and adapted for the CS467 Job Hunting AI project.
*/

export const MAX_SALARY = 9999999999.99;
export const MAX_RESULT_COUNT = 4294967295;

function isEmptySalary(value) {
  return value === null || value === undefined || value === "";
}

function validateSalary(value, label) {
  if (isEmptySalary(value)) {
    return "";
  }

  const text = String(value);

  if (!/^\d+(?:\.\d{1,2})?$/.test(text)) {
    return `${label} must be a non-negative number with no more than two decimal places.`;
  }

  const amount = Number(text);

  if (!Number.isFinite(amount) || amount > MAX_SALARY) {
    return `${label} cannot exceed $9,999,999,999.99.`;
  }

  return "";
}

export function validatePreferenceLimits(preferences) {
  const minimumError = validateSalary(
    preferences.salary_min,
    "Minimum salary"
  );

  if (minimumError) {
    return minimumError;
  }

  const maximumError = validateSalary(
    preferences.salary_max,
    "Maximum salary"
  );

  if (maximumError) {
    return maximumError;
  }

  if (
    !isEmptySalary(preferences.salary_min) &&
    !isEmptySalary(preferences.salary_max) &&
    Number(preferences.salary_min) >
      Number(preferences.salary_max)
  ) {
    return "Minimum salary cannot exceed maximum salary.";
  }

  const countText = String(preferences.result_count);
  const count = Number(countText);

  if (
    !/^\d+$/.test(countText) ||
    !Number.isSafeInteger(count) ||
    count < 1 ||
    count > MAX_RESULT_COUNT
  ) {
    return "Maximum number of recommendations must be a whole number between 1 and 4,294,967,295.";
  }

  return "";
}

export function serializeSalary(value) {
  return isEmptySalary(value) ? null : String(value);
}