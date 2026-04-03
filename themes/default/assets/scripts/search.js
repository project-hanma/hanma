(function () {
  var input = document.getElementById("searchInput");
  var drop  = document.getElementById("searchDropdown");
  if (!input || !drop) return;

  var INDEX_URL = input.getAttribute("data-search-url");
  var _data = null;
  var _loading = false;

  function loadIndex(cb) {
    if (_data) { cb(_data); return; }
    if (_loading) return;
    _loading = true;
    var xhr = new XMLHttpRequest();
    xhr.open("GET", INDEX_URL);
    xhr.onload = function () {
      try { _data = xhr.status === 200 ? JSON.parse(xhr.responseText) : []; }
      catch (e) { _data = []; }
      _loading = false;
      cb(_data);
    };
    xhr.onerror = function () { _data = []; _loading = false; cb(_data); };
    xhr.send();
  }

  function esc(s) {
    return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;")
                    .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  }

  function render(results) {
    drop.innerHTML = "";
    if (!results.length) {
      var li = document.createElement("li");
      li.className = "search-no-results";
      li.textContent = "No results.";
      drop.appendChild(li);
    } else {
      var searchBase = new URL(INDEX_URL, location.href);
      results.slice(0, 8).forEach(function (r) {
        var li = document.createElement("li");
        var a  = document.createElement("a");
        a.href = new URL(r.url, searchBase).href;
        a.innerHTML = esc(r.title) +
          (r.description ? '<span class="search-desc">' + esc(r.description) + '</span>' : "");
        li.appendChild(a);
        drop.appendChild(li);
      });
    }
    drop.classList.add("open");
  }

  function filter(data, q) {
    q = q.toLowerCase();
    return data.filter(function (r) {
      return r.title.toLowerCase().indexOf(q) !== -1 ||
             (r.description && r.description.toLowerCase().indexOf(q) !== -1) ||
             (r.tags && r.tags.some(function (t) { return t.toLowerCase().indexOf(q) !== -1; }));
    });
  }

  input.addEventListener("input", function () {
    var q = input.value.trim();
    if (!q) { drop.classList.remove("open"); drop.innerHTML = ""; return; }
    loadIndex(function (data) { render(filter(data, q)); });
  });

  document.addEventListener("click", function (e) {
    if (!input.contains(e.target) && !drop.contains(e.target)) {
      drop.classList.remove("open");
    }
  });

  input.addEventListener("keydown", function (e) {
    if (e.key === "Escape") { drop.classList.remove("open"); input.value = ""; }
  });
})();
