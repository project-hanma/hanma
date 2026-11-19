(function () {
  var toggle = document.getElementById("mobileMenuToggle");
  var sidebar = document.querySelector(".glass-sidebar");
  if (!toggle || !sidebar) return;
  toggle.addEventListener("click", function () {
    var expanded = toggle.getAttribute("aria-expanded") === "true";
    toggle.setAttribute("aria-expanded", String(!expanded));
    sidebar.classList.toggle("mobile-open");
  });
})();
