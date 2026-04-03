(function () {
  var STORAGE_KEY = "hanma-theme";
  var root = document.documentElement;
  var btn  = document.getElementById("themeToggle");
  var icon = document.getElementById("themeIcon");
  var lbl  = document.getElementById("themeLabel");

  function currentTheme() {
    return root.getAttribute("data-theme") || "light";
  }

  function syncButton(theme) {
    if (theme === "dark") {
      icon.innerHTML = "&#9728;";
      lbl.textContent = "Light";
    } else {
      icon.innerHTML = "&#9790;";
      lbl.textContent = "Dark";
    }
  }

  // Sync button label to whatever the <head> script already applied
  syncButton(currentTheme());

  btn.addEventListener("click", function () {
    var next = currentTheme() === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    localStorage.setItem(STORAGE_KEY, next);
    syncButton(next);
  });
})();
