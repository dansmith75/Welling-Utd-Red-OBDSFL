// Compatibility shim for the 2026 repository rename to welling-dashboard.
// This keeps any legacy hard-coded GitHub API request working while the codebase
// is progressively cleaned up.
(() => {
  const nativeFetch = window.fetch.bind(window);
  const oldGalleryApi = "https://api.github.com/repos/dansmith75/welling-utd-red-obdsfl/contents/gallery";
  const newGalleryApi = "https://api.github.com/repos/dansmith75/welling-dashboard/contents/gallery";

  window.fetch = (input, init) => {
    if (typeof input === "string" && input === oldGalleryApi) {
      return nativeFetch(newGalleryApi, init);
    }

    return nativeFetch(input, init);
  };
})();
