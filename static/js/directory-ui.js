// Directory: show friends on load, AJAX search, and CSRF-safe actions.
// Also adds "Call" that deep-links to "/?dial=+91..." so index auto-dials.

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("dir-search-form");
  const qInput = document.getElementById("dir-q");
  const contactsWrap = document.getElementById("dir-contacts");
  const resultsWrap = document.getElementById("dir-results");
  const resultsSection = document.getElementById("dir-results-section");
  const pendingWrap = document.getElementById("dir-pending");
  const pendingSection = document.getElementById("dir-pending-section");

  // --- CSRF helper (from Django cookie) ---
  function getCookie(name) {
    const m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return m ? decodeURIComponent(m.pop()) : '';
  }
  const csrftoken = getCookie('csrftoken');

  function cell(title, sub, actionsHTML) {
    const el = document.createElement("div");
    el.className = "cell";
    el.innerHTML = `
      <div class="cell__main">
        <div class="cell__title">${title}</div>
        <div class="cell__sub">${sub}</div>
      </div>
      <div class="cell__actions">${actionsHTML || ""}</div>
    `;
    return el;
  }

  // --- Friends (contacts) on load ---
  async function loadContacts() {
    try {
      const res = await fetch('/contacts/list', { credentials: 'same-origin' });
      if (!res.ok) throw new Error(res.status);
      const data = await res.json();
      const items = Array.isArray(data) ? data : (data.contacts || []);
      contactsWrap.replaceChildren();
      if (!items.length) {
        contactsWrap.innerHTML = '<p class="muted small">No friends yet. Search users and send a request.</p>';
        return;
      }
      items.forEach(c => {
        const name  = c.display_name || c.peer_display_name || c.username || 'User';
        const phone = c.phone || c.peer_phone || c.phone_number || '';
        const actions = `
          <a class="chip chip-success" href="/?dial=${encodeURIComponent(phone)}">Call</a>
          <form action="/contacts/block" method="post" style="display:inline;">
            <input type="hidden" name="csrfmiddlewaretoken" value="${csrftoken}">
            <input type="hidden" name="phone" value="${phone}">
            <button class="chip chip-danger" type="submit">Block</button>
          </form>`;
        contactsWrap.appendChild(cell(name, phone, actions));
      });
    } catch (e) {
      console.error('contacts load failed', e);
    }
  }

  // --- Search (AJAX) ---
  async function runSearch(q) {
    if (!q) return;
    const res = await fetch(`/directory/search?q=${encodeURIComponent(q)}`, { credentials: 'same-origin' });
    if (!res.ok) { console.error('search failed', res.status); return; }
    const data = await res.json();

    // Results
    resultsWrap.replaceChildren();
    const dir = Array.isArray(data.directory) ? data.directory : [];
    if (dir.length) {
      resultsSection.style.display = '';
      dir.forEach(u => {
        const phone = u.phone || u.phone_number || '';
        const name = u.display_name || u.username || 'User';
        const actions = `
          <a class="chip chip-success" href="/?dial=${encodeURIComponent(phone)}">Call</a>
          <form action="/contacts/request" method="post" style="display:inline;">
            <input type="hidden" name="csrfmiddlewaretoken" value="${csrftoken}">
            <input type="hidden" name="phone" value="${phone}">
            <button class="chip" type="submit">Add</button>
          </form>`;
        resultsWrap.appendChild(cell(name, phone, actions));
      });
    } else {
      resultsSection.style.display = 'none';
    }

    // Pending
    pendingWrap.replaceChildren();
    const pend = Array.isArray(data.pending) ? data.pending : [];
    if (pend.length) {
      pendingSection.style.display = '';
      pend.forEach(p => {
        const phone = p.peer_phone || p.phone || '';
        const name = p.peer_display_name || p.display_name || 'User';
        const actions = `
          <form action="/contacts/accept" method="post" style="display:inline;">
            <input type="hidden" name="csrfmiddlewaretoken" value="${csrftoken}">
            <input type="hidden" name="phone" value="${phone}">
            <button class="chip chip-success" type="submit">Accept</button>
          </form>`;
        pendingWrap.appendChild(cell(name, phone, actions));
      });
    } else {
      pendingSection.style.display = 'none';
    }
  }

  if (form) {
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      runSearch(qInput.value.trim());
    });
  }

  // Intercept POSTs from dynamic forms so the page doesn't navigate to JSON
  document.addEventListener('submit', async (e) => {
    const f = e.target;
    if (f.matches('form[action="/contacts/request"], form[action="/contacts/accept"], form[action="/contacts/block"]')) {
      e.preventDefault();
      const fd = new FormData(f);
      if (!fd.get('csrfmiddlewaretoken')) fd.set('csrfmiddlewaretoken', csrftoken);
      const res = await fetch(f.getAttribute('action'), {
        method: 'POST', body: fd, credentials: 'same-origin'
      });
      if (!res.ok) console.error('action failed', res.status);
      await loadContacts(); // refresh friends section
    }
  }, true);

  loadContacts();
});
