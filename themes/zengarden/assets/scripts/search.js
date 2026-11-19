(function () {
  var input = document.getElementById("searchInput");
  var drop  = document.getElementById("searchDropdown");
  if (!input || !drop) return;

  var INDEX_URL = input.getAttribute("data-search-url");
  var _data = null;
  var _loading = false;
  var _pendingCb = null;
  var _debounceTimer = null;

  function prepareIndex(raw) {
    if (!Array.isArray(raw)) return [];
    return raw.map(function (r) {
      var title = r && r.title ? String(r.title) : "";
      var desc = r && r.description ? String(r.description) : "";
      var tags = r && Array.isArray(r.tags) ? r.tags.map(function (t) { return String(t); }) : [];
      return {
        title: title,
        description: desc,
        url: r && r.url ? String(r.url) : "",
        _title: title.toLowerCase(),
        _desc: desc.toLowerCase(),
        _tags: tags.map(function (t) { return t.toLowerCase(); })
      };
    });
  }

  function loadIndex(cb) {
    if (_data) { cb(_data); return; }
    _pendingCb = cb;
    if (_loading) return;
    _loading = true;
    var xhr = new XMLHttpRequest();
    xhr.open("GET", INDEX_URL);
    xhr.onload = function () {
      try { _data = xhr.status === 200 ? prepareIndex(JSON.parse(xhr.responseText)) : []; }
      catch (e) { _data = []; }
      _loading = false;
      var nextCb = _pendingCb;
      _pendingCb = null;
      if (nextCb) nextCb(_data);
    };
    xhr.onerror = function () {
      _data = [];
      _loading = false;
      var nextCb = _pendingCb;
      _pendingCb = null;
      if (nextCb) nextCb(_data);
    };
    xhr.send();
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
        var parsed;
        try { parsed = new URL(r.url, searchBase); } catch (e) { return; }
        if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return;

        var li = document.createElement("li");
        var a  = document.createElement("a");
        a.href = parsed.href;

        var titleNode = document.createTextNode(r.title);
        a.appendChild(titleNode);

        if (r.description) {
          var span = document.createElement("span");
          span.className = "search-desc";
          span.textContent = r.description;
          a.appendChild(span);
        }

        li.appendChild(a);
        drop.appendChild(li);
      });
    }
    drop.classList.add("open");
  }

  function filter(data, q) {
    q = q.toLowerCase();
    return data.filter(function (r) {
      return r._title.indexOf(q) !== -1 ||
             r._desc.indexOf(q) !== -1 ||
             r._tags.some(function (t) { return t.indexOf(q) !== -1; });
    });
  }

  input.addEventListener("input", function () {
    if (_debounceTimer !== null) {
      clearTimeout(_debounceTimer);
      _debounceTimer = null;
    }
    var q = input.value.trim();
    if (!q) {
      _pendingCb = null;
      drop.classList.remove("open");
      drop.innerHTML = "";
      return;
    }
    _debounceTimer = setTimeout(function () {
      _debounceTimer = null;
      var currentQuery = input.value.trim();
      if (!currentQuery) return;
      loadIndex(function (data) { render(filter(data, currentQuery)); });
    }, 100);
  });

  document.addEventListener("click", function (e) {
    if (!input.contains(e.target) && !drop.contains(e.target)) {
      drop.classList.remove("open");
    }
  });

  input.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      if (_debounceTimer !== null) {
        clearTimeout(_debounceTimer);
        _debounceTimer = null;
      }
      _pendingCb = null;
      drop.classList.remove("open");
      input.value = "";
    }
  });
})();
