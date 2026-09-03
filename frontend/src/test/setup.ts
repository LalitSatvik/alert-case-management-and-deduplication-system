import "@testing-library/jest-dom/vitest";

// Several tests mount a bare <MemoryRouter>, which emits React Router v7
// future-flag advisories. Silence only those known strings so real warnings
// still surface.
const origWarn = console.warn;
console.warn = (...args: unknown[]) => {
  if (typeof args[0] === "string" && args[0].includes("React Router Future Flag Warning")) return;
  origWarn(...args);
};
