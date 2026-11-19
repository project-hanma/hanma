(function () {
  var STORAGE_KEY = "hanma-theme";
  var root = document.documentElement;
  var btn  = document.getElementById("themeToggle");
  var icon = document.getElementById("themeIcon");
  var lbl  = document.getElementById("themeLabel");

  if (!btn || !icon || !lbl) return;

  function currentTheme() {
    return root.getAttribute("data-theme") || "light";
  }

  function syncButton(theme) {
    if (theme === "dark") {
      icon.textContent = "\u2600";
      lbl.textContent = "Light";
    } else {
      icon.textContent = "\u263E";
      lbl.textContent = "Dark";
    }
  }

  // Sync button label to whatever the <head> script already applied
  syncButton(currentTheme());

  btn.addEventListener("click", function () {
    var next = currentTheme() === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem(STORAGE_KEY, next); } catch (e) {}
    syncButton(next);
  });
})();
