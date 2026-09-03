export const ALLOWED: Record<string, string[]> = {
  Open: ["In Progress"],
  "In Progress": ["Pending Info", "Closed"],
  "Pending Info": ["In Progress"],
  Closed: ["In Progress"],
  Merged: [],
};

export const DISPOSITIONS = [
  "No action",
  "Escalate",
  "Confirmed fraud",
  "Confirmed AML concern",
  "Duplicate",
];
