/* 520 Minimart customer app. Plain JavaScript, no build step.
   Online (the store system answers): real accounts, live prices and sales, real reservations the cashier can look up.
   Offline or without the store system: the saved prices and the demo customers in data.json. */
(function () {
  'use strict';
  var KEY = 'mm-customer-v2';
  var data = null;
  var online = false;                       // the store system (PesoWeb) answered
  var ui = { tab: 'sale', search: '', cart: {}, msg: '', err: '', source: '', reg: false, messages: [], ticket: null, busy: false };

  function load() { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { return {}; } }
  function save(s) { try { localStorage.setItem(KEY, JSON.stringify(s)); } catch (e) { /* private mode */ } }
  var store = load();
  store.overrides = store.overrides || {};   // demo mode: userId -> { phone, password }
  store.orders = store.orders || [];         // reservations made on this phone
  store.seenMsg = store.seenMsg || 0;

  function esc(s) { return String(s === null || s === undefined ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function peso(n) { return '₱' + Number(n).toLocaleString('en-PH', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
  function digits(s) { return String(s || '').replace(/\D/g, ''); }
  function salePrice(p) {
    if (!p.offer) { return p.price; }
    return p.offer.price !== undefined ? p.offer.price : Math.round(p.price * (100 - p.offer.percentOff)) / 100;
  }
  function titleCase(s) { return String(s).toLowerCase().replace(/(^|[\s(\-\/])([a-z])/g, function (m, a, b) { return a + b.toUpperCase(); }); }
  function dayText(n) { return n < 0 ? Math.abs(n) + ' day(s) overdue' : n === 0 ? 'due today' : 'due in ' + n + ' day(s)'; }
  function dueDate(n) { var d = new Date(); d.setDate(d.getDate() + n); return d.toLocaleDateString('en-PH', { month: 'short', day: 'numeric', year: 'numeric' }); }
  function when(iso) { try { return new Date(iso).toLocaleString('en-PH', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }); } catch (e) { return ''; } }

  // The quick demo basket (product id -> quantity)
  var DEMO_BASKET = { '1367': 3, '1019': 2, '1370': 2, '1375': 1 };

  function api() {
    try { var o = localStorage.getItem('mm-api'); if (o) { return o; } } catch (e) { /* ignore */ }
    return (window.MM_API || '').replace(/\/+$/, '');   // '' = same address as the app (serve.py forwards the store's API)
  }

  // JSON call to the store system. Resolves { status, body } and never rejects on an HTTP error.
  function call(method, path, body) {
    var ctl = typeof AbortController === 'function' ? new AbortController() : null;
    var timer = setTimeout(function () { if (ctl) { ctl.abort(); } }, 8000);
    var headers = { 'Content-Type': 'application/json' };
    if (store.token) { headers.Authorization = 'Bearer ' + store.token; }
    return fetch(api() + path, { method: method, headers: headers, body: body ? JSON.stringify(body) : undefined, cache: 'no-store', signal: ctl ? ctl.signal : undefined })
      .then(function (r) { clearTimeout(timer); return r.json().catch(function () { return {}; }).then(function (b) { return { status: r.status, body: b }; }); });
  }

  // ---- install as an app on the phone
  var installEvent = null;
  var standalone = (window.matchMedia && matchMedia('(display-mode: standalone)').matches) || window.navigator.standalone === true;
  var isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent);
  window.addEventListener('beforeinstallprompt', function (e) { e.preventDefault(); installEvent = e; paintInstall(); });
  window.addEventListener('appinstalled', function () { installEvent = null; standalone = true; paintInstall(); });

  function paintInstall() {
    var slot = document.getElementById('installSlot');
    if (!slot) { return; }
    if (standalone) { slot.innerHTML = ''; return; }
    var how = installEvent ? '<button class="btn small" id="installBtn">Install app</button>' : '';
    var hint = installEvent ? 'Put it on your home screen like any other app.'
      : isIOS ? 'On iPhone: tap the Share button, then <b>Add to Home Screen</b>.'
      : 'Open the browser menu (three dots), then choose <b>Install app</b> or <b>Add to Home screen</b>.';
    slot.innerHTML = '<div class="card"><div class="row"><div class="grow"><b>Get the app</b><div class="muted">' + hint + '</div></div>' + how + '</div></div>';
    var b = document.getElementById('installBtn');
    if (b) { b.onclick = function () { installEvent.prompt(); installEvent.userChoice.then(function () { installEvent = null; paintInstall(); }); }; }
  }

  // ---- who is signed in
  function customer() {
    if (online && store.token && store.profile) {
      var p = store.profile;
      return { userId: p.userId || '', name: p.name, phone: p.phone, email: '', owes: [], real: true };
    }
    if (!store.session || !data) { return null; }
    var c = data.customers.filter(function (x) { return x.userId === store.session; })[0];
    if (!c) { return null; }
    var o = store.overrides[c.userId] || {};
    return Object.assign({}, c, { phone: o.phone || c.phone, password: o.password || c.password, real: false });
  }

  function demoLogin(who, pw) {
    var w = who.trim().toLowerCase(), d = digits(who);
    var c = data.customers.filter(function (x) {
      var o = store.overrides[x.userId] || {};
      return x.userId.toLowerCase() === w || (d.length >= 7 && digits(o.phone || x.phone) === d);
    })[0];
    if (!c) { return false; }
    var o = store.overrides[c.userId] || {};
    if ((o.password || c.password) !== pw) { return false; }
    store.session = c.userId; save(store); return true;
  }

  // ---------- views
  function viewLogin() {
    var reg = ui.reg && online;
    var tabs = '<div class="seg"><button type="button" data-seg="login" class="' + (reg ? '' : 'on') + '">Log in</button>' +
      '<button type="button" data-seg="register" class="' + (reg ? 'on' : '') + '">New customer</button></div>';
    var form = reg
      ? '<form id="regForm"><h3>Register</h3><p class="muted">First time here? Create your account to see the sales and reserve items.</p>' +
        '<label>Your name</label><input type="text" name="name" autocomplete="name" required>' +
        '<label>Mobile number</label><input type="tel" name="phone" autocomplete="tel" placeholder="09XX XXX XXXX" required>' +
        '<label>Password (at least 6 characters)</label><input type="password" name="pw" autocomplete="new-password" required>' +
        '<label>User ID (optional)</label><input type="text" name="uid" autocapitalize="none" placeholder="you can log in with your phone number instead">' +
        (ui.err ? '<div class="err">' + esc(ui.err) + '</div>' : '') +
        '<p><button class="btn" style="width:100%" type="submit"' + (ui.busy ? ' disabled' : '') + '>' + (ui.busy ? 'Please wait...' : 'Register') + '</button></p></form>'
      : '<form id="loginForm"><h3>Log in</h3>' +
        '<label>User ID or phone number</label><input type="text" name="who" autocomplete="username" autocapitalize="none" required>' +
        '<label>Password</label><input type="password" name="pw" autocomplete="current-password" required>' +
        (ui.err ? '<div class="err">' + esc(ui.err) + '</div>' : '') +
        '<p><button class="btn" style="width:100%" type="submit"' + (ui.busy ? ' disabled' : '') + '>' + (ui.busy ? 'Please wait...' : 'Log in') + '</button></p>' +
        (online ? '' : '<p class="muted">Demo: user ID <b>juan</b> or phone <b>09171234567</b>, password <b>demo123</b></p>') + '</form>';
    return '<div class="login"><img class="logo" src="icons/icon-192.png" alt="">' +
      '<h1 style="text-align:center">' + esc(data.store.name) + '</h1>' +
      '<p class="muted" style="text-align:center">Sales, clearance and your account</p>' +
      '<div id="installSlot"></div>' + (online ? tabs : '') + '<div class="card">' + form + '</div>' +
      '<p class="muted" style="text-align:center">' + (online ? 'Connected to the store' : 'Saved prices (not connected to the store)') + '</p></div>';
  }

  function productCard(p, showAdd) {
    var q = ui.cart[p.id] || 0;
    var o = p.offer;
    return '<div class="card"><div class="row"><div class="grow">' +
      (o ? '<span class="tag ' + (o.kind === 'clearance' ? 'clearance' : '') + '">' + (o.kind === 'clearance' ? 'CLEARANCE ' : 'SALE ') + o.percentOff + '% OFF</span> ' : '') +
      '<div><b>' + esc(p.name) + '</b></div>' +
      '<div><span class="price">' + peso(salePrice(p)) + '</span>' + (o ? '<span class="was">' + peso(p.price) + '</span>' : '') + '</div>' +
      (o ? '<div class="muted">' + esc(o.note || '') + ' · ends in ' + o.daysLeft + ' day(s)</div>' : '') +
      '</div>' + (showAdd ? (q ? '<div class="qty"><button data-dec="' + p.id + '">−</button><b>' + q + '</b><button data-inc="' + p.id + '">+</button></div>'
        : '<button class="btn small" data-inc="' + p.id + '">Add</button>') : '') +
      '</div></div>';
  }

  function messagesCard() {
    if (!ui.messages.length) { return ''; }
    return '<h3 style="margin:6px 0 8px">From the store</h3>' + ui.messages.slice(0, 3).map(function (m) {
      var fresh = m.id > store.seenMsg;
      return '<div class="card msg"><div class="row"><div class="grow"><b>' + esc(m.title) + '</b>' + (fresh ? ' <span class="tag ok">NEW</span>' : '') +
        '<div class="muted">' + esc(m.body) + '</div><div class="muted" style="font-size:12px">' + esc(when(m.createdAt)) + '</div></div></div></div>';
    }).join('');
  }

  function viewSale() {
    var list = data.products.filter(function (p) { return p.offer; }).sort(function (a, b) { return b.offer.percentOff - a.offer.percentOff; });
    var clr = list.filter(function (p) { return p.offer.kind === 'clearance'; });
    var rest = list.filter(function (p) { return p.offer.kind !== 'clearance'; });
    return (ui.msg ? '<div class="okmsg" style="margin:0 0 10px">' + esc(ui.msg) + '</div>' : '') +
      '<div class="banner"><img src="icons/sale.svg" alt=""></div>' +
      messagesCard() +
      '<div class="note">Rush to the store: clearance items are limited and end soon. Reserve them here, then pay at the cashier.</div>' +
      '<div class="card"><div class="row"><div class="grow"><b>Quick demo basket</b><div class="muted">Four sale items, ready to reserve</div></div>' +
      '<button class="btn small" id="demoBasket">Reserve it</button></div></div>' +
      '<div class="muted" style="margin:-4px 0 10px">' + esc(ui.source) + '</div>' +
      (clr.length ? '<h3 style="margin:6px 0 8px">Clearance (super discount)</h3>' + clr.map(function (p) { return productCard(p, true); }).join('') : '') +
      (rest.length ? '<h3 style="margin:6px 0 8px">On sale</h3>' + rest.map(function (p) { return productCard(p, true); }).join('') : '') +
      (!list.length ? '<p class="muted">No sale right now. Check back soon.</p>' : '');
  }

  function viewShop() {
    var s = ui.search.toLowerCase();
    var list = data.products.filter(function (p) { return !s || p.name.toLowerCase().indexOf(s) >= 0; }).slice(0, 60);
    return '<input type="search" id="search" placeholder="Search products" value="' + esc(ui.search) + '" style="margin-bottom:12px">' +
      (list.length ? list.map(function (p) { return productCard(p, true); }).join('') : '<p class="muted">No product found.</p>');
  }

  function cartLines() {
    return Object.keys(ui.cart).map(function (id) {
      var p = data.products.filter(function (x) { return String(x.id) === id; })[0];
      return p ? { p: p, q: ui.cart[id], price: salePrice(p) } : null;
    }).filter(Boolean);
  }

  function viewOrder() {
    var lines = cartLines(), total = lines.reduce(function (s, l) { return s + l.q * l.price; }, 0);
    var html = '';
    if (ui.err) { html += '<div class="err">' + esc(ui.err) + '</div>'; }
    if (ui.msg) { html += '<div class="okmsg">' + esc(ui.msg) + '</div>'; }
    html += '<h3 style="margin:6px 0 8px">Your basket</h3>';
    if (!lines.length) { html += '<p class="muted">Your basket is empty. Add items from Sale or Shop.</p>'; }
    else {
      html += lines.map(function (l) { return productCard(l.p, true); }).join('') +
        '<div class="card"><div class="row"><div class="grow"><b>Total</b></div><div class="price">' + peso(total) + '</div></div>' +
        '<p><button class="btn" style="width:100%" id="reserve"' + (ui.busy ? ' disabled' : '') + '>Reserve and pay at the store</button></p>' +
        '<p><button class="btn ghost" style="width:100%" disabled>Pay online (coming soon)</button></p></div>';
    }
    var c = customer();
    var mine = store.orders.filter(function (o) { return o.userId === (c ? c.userId || c.phone : ''); }).slice().reverse();
    if (mine.length) {
      html += '<h3 style="margin:14px 0 8px">My reservations</h3>' + mine.map(function (o) {
        return '<div class="card"><div class="row"><div class="grow"><b>' + esc(o.code) + '</b><div class="muted">' + o.items.length + ' item(s) · ' + peso(o.total) +
          '</div></div><button class="btn small" data-show="' + esc(o.code) + '">Show code</button></div></div>';
      }).join('');
    }
    return html;
  }

  function viewTicket(code) {
    var o = store.orders.filter(function (x) { return x.code === code; })[0];
    if (!o) { return viewOrder(); }
    return '<div class="card"><p class="muted" style="text-align:center">Show this to the cashier</p>' +
      '<div class="big">' + esc(o.code) + '</div><div class="qr" id="qr"></div>' +
      '<p class="muted" style="text-align:center">' + esc(data.store.name) + ' · ' + o.items.length + ' item(s) · ' + peso(o.total) + '</p>' +
      '<p class="muted" style="text-align:center">Cashier: key in <b>' + esc(o.code) + '</b> at the POS (Online order)</p></div>' +
      '<div class="card">' + o.items.map(function (i) { return '<div class="row"><div class="grow">' + esc(i.name) + ' × ' + i.qty + '</div><div>' + peso(i.price * i.qty) + '</div></div>'; }).join('') + '</div>' +
      '<p><button class="btn ghost" style="width:100%" id="back">Back</button></p>';
  }

  function viewOwes() {
    var c = customer(), total = c.owes.reduce(function (s, x) { return s + x.amount; }, 0);
    if (!c.owes.length) { return '<div class="card"><h3>You have no balance</h3><p class="muted">Nothing is owed to the store. Thank you!</p></div>'; }
    return '<div class="card"><div class="muted">Total you owe</div><div class="big" style="letter-spacing:0">' + peso(total) + '</div></div>' +
      c.owes.map(function (x) {
        return '<div class="card"><div class="row"><div class="grow"><b>' + esc(x.description) + '</b><div class="muted">' + esc(x.ref) + ' · deadline ' + dueDate(x.dueInDays) + '</div></div>' +
          '<div style="text-align:right"><div class="price">' + peso(x.amount) + '</div><span class="tag ' + (x.dueInDays < 0 ? 'bad' : x.dueInDays <= 3 ? 'warn' : 'ok') + '">' + dayText(x.dueInDays) + '</span></div></div></div>';
      }).join('') + '<p class="muted">Please pay at the store before the deadline.</p>';
  }

  function viewAccount() {
    var c = customer();
    return '<div id="installSlot"></div><div class="card"><h3>My details</h3>' +
      '<label>Name</label><input type="text" value="' + esc(c.name) + '" readonly>' +
      '<label>User ID (cannot be changed)</label><input type="text" value="' + esc(c.userId || 'Log in with your phone number') + '" readonly>' +
      (c.email ? '<label>Email (cannot be changed)</label><input type="text" value="' + esc(c.email) + '" readonly>' : '') +
      '</div><div class="card"><h3>Change phone number</h3><form id="phoneForm">' +
      '<label>Phone number</label><input type="tel" name="phone" value="' + esc(c.phone) + '" required>' +
      '<label>Password (to confirm)</label><input type="password" name="pw" required>' +
      '<p><button class="btn" type="submit">Save phone</button></p></form></div>' +
      '<div class="card"><h3>Change password</h3><form id="pwForm">' +
      '<label>Current password</label><input type="password" name="old" required>' +
      '<label>New password (at least 6 characters)</label><input type="password" name="pw1" required>' +
      '<label>Repeat new password</label><input type="password" name="pw2" required>' +
      '<p><button class="btn" type="submit">Save password</button></p></form></div>' +
      (ui.err ? '<div class="err">' + esc(ui.err) + '</div>' : '') + (ui.msg ? '<div class="okmsg">' + esc(ui.msg) + '</div>' : '') +
      '<p><button class="btn ghost" style="width:100%" id="logout">Log out</button></p>';
  }

  // ---------- render and events
  function render() {
    var app = document.getElementById('app');
    var c = data && customer();
    if (!c) { app.innerHTML = viewLogin(); bindLogin(); paintInstall(); return; }
    var owe = c.owes.reduce(function (s, x) { return s + x.amount; }, 0);
    var count = Object.keys(ui.cart).reduce(function (s, k) { return s + ui.cart[k]; }, 0);
    var body = ui.ticket ? viewTicket(ui.ticket) : ui.tab === 'sale' ? viewSale() : ui.tab === 'shop' ? viewShop() : ui.tab === 'order' ? viewOrder() : ui.tab === 'owes' ? viewOwes() : viewAccount();
    var fresh = ui.messages.filter(function (m) { return m.id > store.seenMsg; }).length;
    var tabs = [['sale', '🏷️', 'Sale'], ['shop', '🛒', 'Shop'], ['order', '🧺', 'Basket'], ['owes', '💳', 'My balance'], ['account', '👤', 'Account']];
    app.innerHTML = '<div class="top"><img src="icons/icon-diamond.png" width="26" height="26" alt=""><h1>' + esc(data.store.name) + '</h1><div class="who">Hi, ' + esc(c.name.split(' ')[0]) + '</div></div>' +
      '<div class="wrap">' + body + '</div><nav>' + tabs.map(function (t) {
        var dot = t[0] === 'order' && count ? '<span class="dot">' + count + '</span>'
          : t[0] === 'owes' && owe ? '<span class="dot">!</span>'
          : t[0] === 'sale' && fresh ? '<span class="dot">' + fresh + '</span>' : '';
        return '<button data-tab="' + t[0] + '" class="' + (ui.tab === t[0] && !ui.ticket ? 'on' : '') + '"><b>' + t[1] + '</b>' + t[2] + dot + '</button>';
      }).join('') + '</nav>';
    bindApp();
    paintInstall();
    if (ui.ticket) { drawQr(ui.ticket); }
    if (ui.tab === 'sale' && !ui.ticket && ui.messages.length) {      // the messages on screen are now seen
      var top = ui.messages.reduce(function (m, x) { return Math.max(m, x.id); }, 0);
      if (top > store.seenMsg) { store.seenMsg = top; save(store); }
    }
  }

  function drawQr(code) {
    var el = document.getElementById('qr');
    if (!el || typeof qrcode !== 'function') { return; }
    var c = customer();
    var qr = qrcode(0, 'M'); qr.addData('MM|' + code + '|' + (c ? c.userId || c.phone : '')); qr.make();
    el.innerHTML = qr.createSvgTag({ cellSize: 6, margin: 2, scalable: true });
  }

  function signedIn(token, profile) {
    store.token = token; store.profile = profile; store.session = null; save(store);
    ui.err = ''; ui.tab = 'sale'; ui.busy = false;
  }

  function bindLogin() {
    var lf = document.getElementById('loginForm');
    if (lf) {
      lf.onsubmit = function (e) {
        e.preventDefault(); var f = e.target; ui.err = '';
        if (!online) {
          if (demoLogin(f.who.value, f.pw.value)) { ui.tab = 'sale'; render(); } else { ui.err = 'User ID, phone number or password is not correct.'; render(); }
          return;
        }
        ui.busy = true; render();
        call('POST', '/api/customer-app/login', { who: f.who.value, password: f.pw.value }).then(function (r) {
          if (r.status === 200) { signedIn(r.body.token, r.body.profile); loadMessages(); ui.msg = ''; }
          else { ui.busy = false; ui.err = r.body.message || 'Could not log in.'; }
          render();
        }).catch(function () { ui.busy = false; ui.err = 'The store is not reachable. Try again.'; render(); });
      };
    }
    var rf = document.getElementById('regForm');
    if (rf) {
      rf.onsubmit = function (e) {
        e.preventDefault(); var f = e.target; ui.err = ''; ui.busy = true; render();
        call('POST', '/api/customer-app/register', { name: f.name.value, phone: f.phone.value, password: f.pw.value, userId: f.uid.value }).then(function (r) {
          if (r.status === 200) {
            signedIn(r.body.token, r.body.profile);
            ui.msg = 'Welcome, ' + r.body.profile.name.split(' ')[0] + '! You are now a registered customer. Here are today\'s sales.';
            loadMessages();
          } else { ui.busy = false; ui.err = r.body.message || 'Could not register.'; }
          render();
        }).catch(function () { ui.busy = false; ui.err = 'The store is not reachable. Try again.'; render(); });
      };
    }
    Array.prototype.forEach.call(document.querySelectorAll('[data-seg]'), function (b) {
      b.onclick = function () { ui.reg = b.dataset.seg === 'register'; ui.err = ''; render(); };
    });
  }

  function bindApp() {
    var app = document.getElementById('app');
    Array.prototype.forEach.call(app.querySelectorAll('[data-tab]'), function (b) { b.onclick = function () { ui.tab = b.dataset.tab; ui.ticket = null; ui.err = ''; ui.msg = ''; render(); window.scrollTo(0, 0); }; });
    Array.prototype.forEach.call(app.querySelectorAll('[data-inc]'), function (b) { b.onclick = function () { var id = b.dataset.inc; ui.cart[id] = (ui.cart[id] || 0) + 1; ui.msg = ''; render(); }; });
    Array.prototype.forEach.call(app.querySelectorAll('[data-dec]'), function (b) { b.onclick = function () { var id = b.dataset.dec; ui.cart[id] = (ui.cart[id] || 0) - 1; if (ui.cart[id] <= 0) { delete ui.cart[id]; } render(); }; });
    Array.prototype.forEach.call(app.querySelectorAll('[data-show]'), function (b) { b.onclick = function () { ui.ticket = b.dataset.show; render(); }; });
    var s = document.getElementById('search');
    if (s) { s.oninput = function () { ui.search = s.value; var pos = s.selectionStart; render(); var n = document.getElementById('search'); n.focus(); n.setSelectionRange(pos, pos); }; }
    var db = document.getElementById('demoBasket');
    if (db) { db.onclick = function () { ui.cart = Object.assign({}, DEMO_BASKET); reserve(); }; }
    var r = document.getElementById('reserve');
    if (r) { r.onclick = reserve; }
    var bk = document.getElementById('back');
    if (bk) { bk.onclick = function () { ui.ticket = null; render(); }; }
    var lo = document.getElementById('logout');
    if (lo) { lo.onclick = function () { store.session = null; store.token = null; store.profile = null; save(store); ui = { tab: 'sale', search: '', cart: {}, msg: '', err: '', source: ui.source, reg: false, messages: ui.messages, ticket: null, busy: false }; render(); }; }

    var pf = document.getElementById('phoneForm');
    if (pf) { pf.onsubmit = function (e) {
      e.preventDefault(); var c = customer(), f = e.target; ui.err = ''; ui.msg = '';
      if (c.real) {
        call('PUT', '/api/customer-app/me', { phone: f.phone.value, currentPassword: f.pw.value }).then(function (r) {
          if (r.status === 200) { store.profile = r.body; save(store); ui.msg = 'Phone number saved.'; } else { ui.err = r.body.message || 'Could not save.'; }
          render();
        });
        return;
      }
      if (f.pw.value !== c.password) { ui.err = 'Password is not correct.'; }
      else if (digits(f.phone.value).length < 10) { ui.err = 'Enter a valid phone number.'; }
      else { store.overrides[c.userId] = Object.assign({}, store.overrides[c.userId], { phone: f.phone.value.trim() }); save(store); ui.msg = 'Phone number saved.'; }
      render(); }; }

    var wf = document.getElementById('pwForm');
    if (wf) { wf.onsubmit = function (e) {
      e.preventDefault(); var c = customer(), f = e.target; ui.err = ''; ui.msg = '';
      if (f.pw1.value.length < 6) { ui.err = 'New password must be at least 6 characters.'; render(); return; }
      if (f.pw1.value !== f.pw2.value) { ui.err = 'The two new passwords are not the same.'; render(); return; }
      if (c.real) {
        call('PUT', '/api/customer-app/me', { currentPassword: f.old.value, newPassword: f.pw1.value }).then(function (r) {
          if (r.status === 200) { ui.msg = 'Password changed.'; } else { ui.err = r.body.message || 'Could not save.'; }
          render();
        });
        return;
      }
      if (f.old.value !== c.password) { ui.err = 'Current password is not correct.'; }
      else { store.overrides[c.userId] = Object.assign({}, store.overrides[c.userId], { password: f.pw1.value }); save(store); ui.msg = 'Password changed.'; }
      render(); }; }
  }

  function remember(code, lines, total) {
    var c = customer();
    store.orders = store.orders.filter(function (o) { return o.code !== code; });
    store.orders.push({ code: code, userId: c ? c.userId || c.phone : '', createdAt: new Date().toISOString(), total: total, items: lines });
    save(store);
    ui.cart = {}; ui.ticket = code; ui.busy = false; ui.err = '';
  }

  function reserve() {
    var lines = cartLines(); if (!lines.length || ui.busy) { return; }
    var c = customer();
    if (c && c.real) {
      ui.busy = true;
      call('POST', '/api/customer-app/reserve', { lines: lines.map(function (l) { return { productId: l.p.id, quantity: l.q }; }) }).then(function (r) {
        if (r.status === 200) {
          remember(r.body.code, r.body.lines.map(function (l) { return { id: l.productId, name: titleCase(l.name), qty: l.qty, price: l.price }; }), r.body.total);
        } else { ui.busy = false; ui.err = r.body.message || 'Could not reserve. Try again.'; ui.tab = 'order'; }
        render();
      }).catch(function () { ui.busy = false; ui.err = 'The store is not reachable. Try again.'; ui.tab = 'order'; render(); });
      return;
    }
    // demo mode: a code kept on this phone only (the fixed demo reference when it is the quick basket)
    var isDemo = Object.keys(DEMO_BASKET).length === Object.keys(ui.cart).length &&
      Object.keys(DEMO_BASKET).every(function (k) { return ui.cart[k] === DEMO_BASKET[k]; });
    var code = isDemo ? 'R4821' : 'R' + String(Math.floor(1000 + Math.random() * 9000));
    remember(code, lines.map(function (l) { return { id: l.p.id, name: l.p.name, qty: l.q, price: l.price }; }),
      lines.reduce(function (s, l) { return s + l.q * l.price; }, 0));
    render();
  }

  // ---------- data
  function liveProducts(feed) {
    return feed.products.map(function (p) {
      var o = p.offer;
      return { id: p.id, name: titleCase(p.name), price: p.price,
        offer: o ? { kind: o.kind, percentOff: o.percentOff, price: o.price, daysLeft: o.daysLeft, note: o.note } : undefined };
    });
  }

  function fetchFeed() {
    return call('GET', '/api/customer-app/offers').then(function (r) {
      if (r.status !== 200 || !r.body.products) { throw new Error('feed'); }
      return r.body;
    });
  }

  function loadMessages() {
    if (!online) { return; }
    call('GET', '/api/customer-app/messages').then(function (r) {
      if (r.status === 200 && Array.isArray(r.body)) { ui.messages = r.body; if (customer() && !ui.ticket && ui.tab === 'sale') { render(); } }
    }).catch(function () { /* keep what there is */ });
  }

  function refreshPrices(quiet) {
    return fetchFeed().then(function (feed) {
      online = true;
      data.products = liveProducts(feed);
      ui.source = 'Prices from the store system, updated ' + new Date(feed.generatedAt).toLocaleTimeString('en-PH', { hour: '2-digit', minute: '2-digit' });
      // a live session needs a valid token: if the store no longer knows it, sign out
      if (store.token) {
        call('GET', '/api/customer-app/me').then(function (r) {
          if (r.status === 401) { store.token = null; store.profile = null; save(store); render(); }
          else if (r.status === 200) { store.profile = r.body; save(store); }
        }).catch(function () { });
      }
      var typing = document.activeElement && /INPUT|TEXTAREA/.test(document.activeElement.tagName);
      if (!quiet || (customer() && !ui.ticket && !typing && (ui.tab === 'sale' || ui.tab === 'shop'))) { render(); }
    }).catch(function () { /* keep the saved prices */ });
  }

  fetch('data.json', { cache: 'no-cache' }).then(function (r) { return r.json(); })
    .then(function (d) {
      data = d; ui.source = 'Saved prices (not connected to the store)';
      render();
      refreshPrices(false).then(loadMessages);
      setInterval(function () { refreshPrices(true); loadMessages(); }, 60000);     // the sale list keeps itself current
    })
    .catch(function () { document.getElementById('app').innerHTML = '<div class="wrap"><div class="card">Could not load the store data. Check your connection and try again.</div></div>'; });

  if ('serviceWorker' in navigator) { navigator.serviceWorker.register('sw.js').catch(function () { /* optional */ }); }
})();
