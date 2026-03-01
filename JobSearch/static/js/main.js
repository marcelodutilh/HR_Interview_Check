/* ============================================================
   JobSearch — main.js
   ============================================================ */

"use strict";

// ---------------------------------------------------------------------------
// Toast notifications
// ---------------------------------------------------------------------------
var toastContainer = (function () {
  var el = document.createElement("div");
  el.className = "toast-container";
  document.body.appendChild(el);
  return el;
})();

function toast(msg, type) {
  var t = document.createElement("div");
  t.className = "toast" + (type ? " toast-" + type : "");
  t.textContent = msg;
  toastContainer.appendChild(t);
  setTimeout(function () { t.remove(); }, 3500);
}

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------
function setLoading(btn, loading) {
  if (loading) {
    btn.dataset.loading = "1";
    btn.disabled = true;
  } else {
    delete btn.dataset.loading;
    btn.disabled = false;
  }
}

function openPanel(panel, toggleBtn) {
  panel.classList.add("is-open");
  panel.setAttribute("aria-hidden", "false");
  if (toggleBtn) toggleBtn.setAttribute("aria-expanded", "true");
  var first = panel.querySelector("input");
  if (first) setTimeout(function () { first.focus(); }, 50);
}

function closePanel(panel, toggleBtn) {
  panel.classList.remove("is-open");
  panel.setAttribute("aria-hidden", "true");
  if (toggleBtn) toggleBtn.setAttribute("aria-expanded", "false");
}

// ---------------------------------------------------------------------------
// Index page — inline job search creation
// ---------------------------------------------------------------------------
(function initJobSearchCreator() {
  var toggleBtn   = document.getElementById("toggle-create-btn");
  var emptyBtn    = document.getElementById("empty-create-btn");
  var panel       = document.getElementById("create-search-panel");
  var cancelBtn   = document.getElementById("cancel-create-btn");
  var form        = document.getElementById("create-search-form");
  var submitBtn   = document.getElementById("create-submit-btn");
  var titleInput  = document.getElementById("new-title");
  var titleError  = document.getElementById("new-title-error");
  var grid        = document.getElementById("searches-grid");
  var emptyState  = document.getElementById("empty-state");

  if (!toggleBtn || !panel || !form) return;

  toggleBtn.addEventListener("click", function () {
    var isOpen = panel.classList.contains("is-open");
    if (isOpen) { closePanel(panel, toggleBtn); } else { openPanel(panel, toggleBtn); }
  });

  if (emptyBtn) {
    emptyBtn.addEventListener("click", function () { openPanel(panel, toggleBtn); });
  }

  cancelBtn.addEventListener("click", function () {
    closePanel(panel, toggleBtn);
    form.reset();
    titleError.hidden = true;
  });

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var title = titleInput.value.trim();
    titleError.hidden = true;

    if (!title) {
      titleError.textContent = "Title is required.";
      titleError.hidden = false;
      titleInput.focus();
      return;
    }

    setLoading(submitBtn, true);

    fetch("/api/job-searches", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: title,
        description: document.getElementById("new-description").value.trim()
      })
    })
    .then(function (res) { return res.json().then(function (d) { return { ok: res.ok, data: d }; }); })
    .then(function (result) {
      setLoading(submitBtn, false);
      if (!result.ok) {
        toast(result.data.error || "Could not create search.", "error");
        return;
      }
      var s = result.data;
      // Remove empty state if present
      if (emptyState) { emptyState.remove(); }
      // Create grid if it doesn't exist yet
      if (!grid) {
        grid = document.createElement("div");
        grid.className = "card-grid";
        grid.id = "searches-grid";
        panel.parentNode.insertBefore(grid, panel.nextSibling);
      }
      // Build and prepend new card
      var card = buildSearchCard(s);
      grid.insertBefore(card, grid.firstChild);
      closePanel(panel, toggleBtn);
      form.reset();
      toast("\"" + s.title + "\" created.", "success");
    })
    .catch(function () {
      setLoading(submitBtn, false);
      toast("Network error — please try again.", "error");
    });
  });

  function buildSearchCard(s) {
    var date = (s.created_at || "").slice(0, 10);
    var editUrl  = "/job-searches/" + s.id + "/edit";
    var viewUrl  = "/job-searches/" + s.id;
    var delUrl   = "/job-searches/" + s.id + "/delete";

    var card = document.createElement("div");
    card.className = "card";
    card.dataset.searchId = s.id;
    card.innerHTML =
      '<div class="card-body">' +
        '<h2 class="card-title"><a href="' + viewUrl + '">' + escHtml(s.title) + '</a></h2>' +
        (s.description
          ? '<p class="card-text text-muted">' + escHtml(s.description) + '</p>'
          : '') +
        '<div class="card-meta-row">' +
          '<span class="card-meta">' + date + '</span>' +
          '<span class="candidate-chip">0 candidates</span>' +
        '</div>' +
      '</div>' +
      '<div class="card-footer">' +
        '<a href="' + viewUrl + '" class="btn btn-sm">View</a>' +
        '<a href="' + editUrl + '" class="btn btn-sm btn-outline">Edit</a>' +
        '<form method="post" action="' + delUrl + '" onsubmit="return confirm(\'Delete this job search and all its data?\')">' +
          '<button class="btn btn-sm btn-danger">Delete</button>' +
        '</form>' +
      '</div>';
    return card;
  }
})();

// ---------------------------------------------------------------------------
// Detail page — inline candidate creation
// ---------------------------------------------------------------------------
(function initCandidateCreator() {
  var section   = document.getElementById("candidates-section");
  var toggleBtn = document.getElementById("toggle-add-candidate-btn");
  var panel     = document.getElementById("add-candidate-panel");
  var cancelBtn = document.getElementById("cancel-add-candidate-btn");
  var form      = document.getElementById("add-candidate-form");
  var submitBtn = document.getElementById("add-candidate-submit-btn");
  var nameInput = document.getElementById("cand-name");
  var nameError = document.getElementById("cand-name-error");
  var countBadge = document.getElementById("candidate-count-badge");
  var noMsg     = document.getElementById("no-candidates-msg");

  if (!toggleBtn || !panel || !form || !section) return;

  var searchId = section.dataset.searchId;

  toggleBtn.addEventListener("click", function () {
    var isOpen = panel.classList.contains("is-open");
    if (isOpen) { closePanel(panel, toggleBtn); } else { openPanel(panel, toggleBtn); }
  });

  cancelBtn.addEventListener("click", function () {
    closePanel(panel, toggleBtn);
    form.reset();
    nameError.hidden = true;
  });

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var name = nameInput.value.trim();
    nameError.hidden = true;

    if (!name) {
      nameError.textContent = "Name is required.";
      nameError.hidden = false;
      nameInput.focus();
      return;
    }

    setLoading(submitBtn, true);

    fetch("/api/job-searches/" + searchId + "/candidates", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: name,
        notes: document.getElementById("cand-notes").value.trim()
      })
    })
    .then(function (res) { return res.json().then(function (d) { return { ok: res.ok, data: d }; }); })
    .then(function (result) {
      setLoading(submitBtn, false);
      if (!result.ok) {
        toast(result.data.error || "Could not add candidate.", "error");
        return;
      }
      var c = result.data;
      // Remove "no candidates" message if present
      if (noMsg) { noMsg.remove(); }
      // Build table if it doesn't exist yet
      var table = document.getElementById("candidates-table");
      if (!table) {
        table = document.createElement("table");
        table.className = "table";
        table.id = "candidates-table";
        table.innerHTML =
          '<thead><tr>' +
            '<th>Name</th><th>Notes</th><th>Added</th><th>Actions</th>' +
          '</tr></thead>' +
          '<tbody id="candidates-tbody"></tbody>';
        section.appendChild(table);
      }
      var tbody = document.getElementById("candidates-tbody");
      tbody.insertBefore(buildCandidateRow(c, searchId), tbody.firstChild);
      // Update count badge
      if (countBadge) {
        var current = parseInt(countBadge.textContent, 10) || 0;
        countBadge.textContent = current + 1;
      }
      closePanel(panel, toggleBtn);
      form.reset();
      toast(escHtml(c.name) + " added.", "success");
    })
    .catch(function () {
      setLoading(submitBtn, false);
      toast("Network error — please try again.", "error");
    });
  });

  function buildCandidateRow(c, searchId) {
    var viewUrl = "/candidates/" + c.id;
    var editUrl = "/candidates/" + c.id + "/edit";
    var delUrl  = "/candidates/" + c.id + "/delete";
    var date    = (c.created_at || "").slice(0, 10);
    var notes   = (c.notes || "").slice(0, 80) + ((c.notes || "").length > 80 ? "…" : "");

    var tr = document.createElement("tr");
    tr.dataset.candidateId = c.id;
    tr.innerHTML =
      '<td><a href="' + viewUrl + '">' + escHtml(c.name) + '</a></td>' +
      '<td class="text-muted">' + escHtml(notes) + '</td>' +
      '<td>' + date + '</td>' +
      '<td>' +
        '<div class="btn-group">' +
          '<a href="' + viewUrl + '" class="btn btn-xs">View</a>' +
          '<a href="' + editUrl + '" class="btn btn-xs btn-outline">Edit</a>' +
          '<form method="post" action="' + delUrl + '" onsubmit="return confirm(\'Delete ' + escHtml(c.name) + '?\')">' +
            '<button class="btn btn-xs btn-danger">Delete</button>' +
          '</form>' +
        '</div>' +
      '</td>';
    return tr;
  }
})();

// ---------------------------------------------------------------------------
// Interview detail — follow-up chat with streaming
// ---------------------------------------------------------------------------
(function initChat() {
  var section    = document.getElementById("chat-section");
  var messagesEl = document.getElementById("chat-messages");
  var input      = document.getElementById("chat-input");
  var sendBtn    = document.getElementById("chat-send-btn");
  var welcome    = document.getElementById("chat-welcome");

  if (!section || !messagesEl || !input || !sendBtn) return;

  var interviewId = section.dataset.interviewId;
  var history     = [];   // [{role, content}] — kept in memory for the session
  var streaming   = false;

  // Send on button click or Enter (Shift+Enter = newline)
  sendBtn.addEventListener("click", sendMessage);
  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });

  function sendMessage() {
    if (streaming) return;
    var q = input.value.trim();
    if (!q) return;

    if (welcome) { welcome.remove(); welcome = null; }

    appendBubble("user", q);
    var assistantBubble = appendBubble("assistant", "");
    var contentEl = assistantBubble.querySelector(".chat-message-content");
    // Blinking cursor while waiting for first token
    contentEl.innerHTML = '<span class="chat-cursor"></span>';

    input.value = "";
    input.style.height = "auto";
    streaming = true;
    setLoading(sendBtn, true);

    var payload = { question: q, history: history };

    fetch("/interviews/" + interviewId + "/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
    .then(function (res) {
      if (!res.ok) {
        // Non-streaming error response
        return res.json().then(function (d) { throw new Error(d.error || "Server error"); });
      }

      var reader  = res.body.getReader();
      var decoder = new TextDecoder();
      var buffer  = "";
      var full    = "";

      function read() {
        return reader.read().then(function (chunk) {
          if (chunk.done) { finish(); return; }

          buffer += decoder.decode(chunk.value, { stream: true });
          // Split on double-newline (SSE event boundary)
          var parts = buffer.split("\n\n");
          buffer = parts.pop();            // last (possibly incomplete) fragment

          for (var i = 0; i < parts.length; i++) {
            var line = parts[i].trim();
            if (!line.startsWith("data: ")) continue;
            var raw = line.slice(6);
            var evt;
            try { evt = JSON.parse(raw); } catch (e) { continue; }

            if (evt.type === "text") {
              full += evt.text;
              contentEl.innerHTML = renderMarkdown(full);
              messagesEl.scrollTop = messagesEl.scrollHeight;
            } else if (evt.type === "done") {
              finish();
              return;
            } else if (evt.type === "error") {
              contentEl.innerHTML = '<em class="text-muted">Error: ' + escHtml(evt.error) + '</em>';
              done();
              return;
            }
          }
          return read();
        });
      }

      function finish() {
        history.push({ role: "user",      content: q    });
        history.push({ role: "assistant", content: full });
        done();
      }

      return read();
    })
    .catch(function (err) {
      contentEl.innerHTML = '<em class="text-muted">Error: ' + escHtml(err.message) + '</em>';
      done();
    });
  }

  function done() {
    streaming = false;
    setLoading(sendBtn, false);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function appendBubble(role, text) {
    var div = document.createElement("div");
    div.className = "chat-message chat-message--" + role;
    div.innerHTML =
      '<div class="chat-message-role">' + (role === "user" ? "You" : "Claude") + '</div>' +
      '<div class="chat-message-content">' + (text ? renderMarkdown(text) : "") + '</div>';
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
  }

  // Lightweight markdown renderer — safe because escHtml runs first.
  function renderMarkdown(text) {
    var s = escHtml(text);
    // Bold, italic, inline code
    s = s.replace(/\*\*(.+?)\*\*/g,  "<strong>$1</strong>");
    s = s.replace(/\*([^*\n]+?)\*/g, "<em>$1</em>");
    s = s.replace(/`([^`]+?)`/g,     "<code>$1</code>");
    // Unordered list lines (- item)
    s = s.replace(/(^|\n)([ \t]*[-*] .+)/g, function (_, pre, line) {
      return pre + "<li>" + line.replace(/^[ \t]*[-*] /, "") + "</li>";
    });
    s = s.replace(/(<li>[\s\S]*?<\/li>)/g, "<ul>$1</ul>");
    // Paragraphs and line breaks
    s = s.replace(/\n\n+/g, "</p><p>");
    s = s.replace(/\n/g,    "<br>");
    return "<p>" + s + "</p>";
  }
})();

// ---------------------------------------------------------------------------
// Interview detail — Re-analyse button
// ---------------------------------------------------------------------------
(function initReanalyse() {
  function wire(btn) {
    if (!btn) return;
    btn.addEventListener("click", function () {
      var interviewId = btn.dataset.interviewId;
      var originalText = btn.textContent;
      setLoading(btn, true);
      btn.textContent = "Analysing…";

      fetch("/interviews/" + interviewId + "/analyse", { method: "POST" })
        .then(function (res) { return res.json().then(function (d) { return { ok: res.ok, data: d }; }); })
        .then(function (result) {
          if (!result.ok) {
            setLoading(btn, false);
            btn.textContent = originalText;
            toast(result.data.error || "Analysis failed.", "error");
            return;
          }
          // Reload to show the fresh analysis
          window.location.reload();
        })
        .catch(function () {
          setLoading(btn, false);
          btn.textContent = originalText;
          toast("Network error — please try again.", "error");
        });
    });
  }

  wire(document.getElementById("reanalyse-btn"));
  wire(document.getElementById("reanalyse-btn-empty"));
})();

// ---------------------------------------------------------------------------
// Rubric editor — card-based builder
// ---------------------------------------------------------------------------
(function initRubricBuilder() {
  var container = document.getElementById("rubric-cards");
  var addBtn    = document.getElementById("add-competency");
  var hidden    = document.getElementById("competencies-json");
  var form      = document.getElementById("rubric-form");
  var emptyHint = document.getElementById("rubric-empty-hint");

  if (!container || !addBtn || !form) return;

  // Sync all card values into the hidden JSON field
  function syncToHidden() {
    var result = [];
    container.querySelectorAll(".rubric-card").forEach(function (card) {
      result.push({
        name:       card.querySelector(".comp-name-input").value.trim(),
        strong:     card.querySelector(".comp-strong").value.trim(),
        acceptable: card.querySelector(".comp-acceptable").value.trim(),
        weak:       card.querySelector(".comp-weak").value.trim(),
      });
    });
    hidden.value = JSON.stringify(result);
    if (emptyHint) emptyHint.style.display = result.length ? "none" : "";
  }

  // Attach listeners to a card's inputs and remove button
  function wireCard(card) {
    card.querySelector(".remove-comp").addEventListener("click", function () {
      card.remove();
      syncToHidden();
    });
    card.querySelectorAll("input, textarea").forEach(function (el) {
      el.addEventListener("input", syncToHidden);
    });
  }

  // Build a brand-new blank card element
  function buildCard(comp) {
    comp = comp || {};
    var card = document.createElement("div");
    card.className = "rubric-card";
    card.innerHTML =
      '<div class="rubric-card-header">' +
        '<span class="drag-handle" title="Drag to reorder">⠿</span>' +
        '<input type="text" class="comp-name-input"' +
               ' placeholder="Competency name (e.g. Communication)"' +
               ' value="' + escHtml(comp.name || "") + '" />' +
        '<button type="button" class="btn btn-xs btn-danger remove-comp">Remove</button>' +
      '</div>' +
      '<div class="rubric-levels">' +
        '<div class="rubric-level rubric-level--strong">' +
          '<div class="rubric-level-label">Strong</div>' +
          '<textarea class="comp-strong" rows="4"' +
                    ' placeholder="What does a strong response look like?">' +
            escHtml(comp.strong || "") +
          '</textarea>' +
        '</div>' +
        '<div class="rubric-level rubric-level--acceptable">' +
          '<div class="rubric-level-label">Acceptable</div>' +
          '<textarea class="comp-acceptable" rows="4"' +
                    ' placeholder="What does an acceptable response look like?">' +
            escHtml(comp.acceptable || "") +
          '</textarea>' +
        '</div>' +
        '<div class="rubric-level rubric-level--weak">' +
          '<div class="rubric-level-label">Weak</div>' +
          '<textarea class="comp-weak" rows="4"' +
                    ' placeholder="What does a weak response look like?">' +
            escHtml(comp.weak || "") +
          '</textarea>' +
        '</div>' +
      '</div>';
    wireCard(card);
    return card;
  }

  // Wire server-rendered cards
  container.querySelectorAll(".rubric-card").forEach(wireCard);

  // Hide empty hint if cards already exist
  if (emptyHint && container.querySelectorAll(".rubric-card").length) {
    emptyHint.style.display = "none";
  }

  addBtn.addEventListener("click", function () {
    var card = buildCard({});
    container.appendChild(card);
    card.querySelector(".comp-name-input").focus();
    syncToHidden();
    card.scrollIntoView({ behavior: "smooth", block: "nearest" });
  });

  form.addEventListener("submit", syncToHidden);
})();

// ---------------------------------------------------------------------------
// Auto-resize textareas
// ---------------------------------------------------------------------------
document.querySelectorAll("textarea").forEach(function (ta) {
  function resize() {
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 600) + "px";
  }
  ta.addEventListener("input", resize);
  if (ta.value) resize();
});

// ---------------------------------------------------------------------------
// Utility: HTML-escape for JS-built DOM strings
// ---------------------------------------------------------------------------
function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
