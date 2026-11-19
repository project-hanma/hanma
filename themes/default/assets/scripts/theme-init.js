(function () {
  var t = null;
  try { t = localStorage.getItem("hanma-theme"); } catch (e) {}
  if (t === "dark" || t === "light") {
    document.documentElement.setAttribute("data-theme", t);
  } else if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
    document.documentElement.setAttribute("data-theme", "dark");
  }
})();
