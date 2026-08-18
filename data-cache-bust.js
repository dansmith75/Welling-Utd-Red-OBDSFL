// Always fetch generated football JSON fresh so GitHub Pages/browser caches do not
// leave the dashboard showing old attendance after UPDATE-WELLING publishes.
(() => {
  const nativeFetch = window.fetch.bind(window);

  window.fetch = (input, init = {}) => {
    if (typeof input !== "string") return nativeFetch(input, init);

    const isDashboardData = /(^|\/)data\/(players|matches|goals|assists|events|attendance|minutes)\.json(?:\?|$)/i.test(input);
    if (!isDashboardData) return nativeFetch(input, init);

    const separator = input.includes("?") ? "&" : "?";
    const freshUrl = `${input}${separator}v=${Date.now()}`;
    return nativeFetch(freshUrl, { ...init, cache: "no-store" });
  };
})();
