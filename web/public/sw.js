// MarketNavi (new app) service worker: phone and desktop notifications only. It caches nothing and never answers
// page requests, so the home-screen app always shows the live site. Scope: the folder it is served from (/ on app.marketnavi.ai). The worker's pushes carry the
// classic app's link (/?note=…); here a tap opens the new app's Alerts page instead.

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

const HOME = new URL("./", self.registration.scope).href;          // https://app.marketnavi.ai/

self.addEventListener("push", (event) => {
  let note = {};
  try { note = event.data ? event.data.json() : {}; } catch (e) { note = { body: event.data ? event.data.text() : "" }; }
  event.waitUntil(self.registration.showNotification(note.title || "MarketNavi", {
    body: note.body || "",
    icon: HOME + "icons/icon-192.png",
    badge: HOME + "icons/badge-96.png",
    tag: note.tag || undefined,
    renotify: !!note.tag,
    data: { url: HOME + "#alerts" },
  }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || HOME;
  event.waitUntil((async () => {
    const open = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    for (const client of open) {
      if (client.url.startsWith(HOME) && "focus" in client) {
        await client.focus();
        if ("navigate" in client) { try { await client.navigate(target); } catch (e) { /* not controlled */ } }
        return;
      }
    }
    if (self.clients.openWindow) await self.clients.openWindow(target);
  })());
});
