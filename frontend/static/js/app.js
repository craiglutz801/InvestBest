// InvestBest — shared JS
document.addEventListener('DOMContentLoaded', function () {
  // Optional: global fetch wrapper for API calls
  window.investBestApi = function (path, options) {
    return fetch(path, { headers: { 'Accept': 'application/json', ...(options?.headers || {}) }, ...options });
  };
});
