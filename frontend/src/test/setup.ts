import "@testing-library/jest-dom/vitest";

// jsdom does not persist sessionStorage between tests reliably; explicit reset.
beforeEach(() => {
  window.sessionStorage.clear();
  window.localStorage.clear();
});
