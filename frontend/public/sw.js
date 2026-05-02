// Recovery Debt service worker.
// MVP scope: install + push notifications. Offline caching is intentionally
// not implemented (would need Workbox/Serwist + cache invalidation strategy);
// the manifest + this SW are enough for the app to be installable as a PWA.

self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("push", (event) => {
  if (!event.data) return;
  let payload;
  try {
    payload = event.data.json();
  } catch {
    payload = { title: "Recovery Debt", body: event.data.text() };
  }
  const { title, body, icon, url } = payload;
  event.waitUntil(
    self.registration.showNotification(title || "Recovery Debt", {
      body: body || "",
      icon: icon || "/icon.svg",
      badge: "/icon-mask.svg",
      data: { url: url || "/" },
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if (client.url.includes(target) && "focus" in client) return client.focus();
      }
      if (self.clients.openWindow) return self.clients.openWindow(target);
    })
  );
});
