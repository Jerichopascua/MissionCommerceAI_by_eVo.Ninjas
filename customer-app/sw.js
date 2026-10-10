// Keeps the app shell available offline; data.json is fetched fresh when online so prices stay current.
var CACHE = 'mm-shell-v2';
var SHELL = ['./', 'index.html', 'style.css', 'app.js', 'vendor/qrcode.js', 'manifest.webmanifest',
  'icons/icon-192.png', 'icons/icon-512.png', 'icons/icon-diamond.png', 'icons/hub-banner-clearance.png', 'data.json'];

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(SHELL); }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener('fetch', function (e) {
  if (e.request.method !== 'GET') { return; }
  if (new URL(e.request.url).origin !== self.location.origin) { return; }   // the store's price feed is never cached here
  var isData = e.request.url.indexOf('data.json') >= 0;
  e.respondWith(isData
    ? fetch(e.request).then(function (r) { var c = r.clone(); caches.open(CACHE).then(function (ch) { ch.put(e.request, c); }); return r; })
        .catch(function () { return caches.match(e.request); })
    : caches.match(e.request).then(function (hit) { return hit || fetch(e.request); }));
});
