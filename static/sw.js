// Angstrom's service worker: phone and desktop notifications only (14 Nov 2026).
// It caches nothing and never answers page requests, so the home-screen app always shows the live site, every new
// feature included. Its scope is /app/static/ (where Streamlit serves it); a push does not need a wider one.

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

self.addEventListener("push", (event) => {
  let note = {};
  try { note = event.data ? event.data.json() : {}; } catch (e) { note = { body: event.data ? event.data.text() : "" }; }
  const title = note.title || "Angstrom Signals";
  event.waitUntil(self.registration.showNotification(title, {
    body: note.body || "",
    icon: "/app/static/icons/icon-192.png",
    badge: "/app/static/icons/badge-96.png",
    tag: note.tag || undefined,
    renotify: !!note.tag,
    data: { url: note.url || "/" },
  }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = new URL((event.notification.data && event.notification.data.url) || "/", self.location.origin).href;
  event.waitUntil((async () => {
    const open = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    for (const client of open) {
      if (new URL(client.url).origin === self.location.origin && "focus" in client) {
        await client.focus();
        if ("navigate" in client && target !== client.url && !target.endsWith("/")) { try { await client.navigate(target); } catch (e) { /* not controlled */ } }
        return;
      }
    }
    if (self.clients.openWindow) await self.clients.openWindow(target);
  })());
});
