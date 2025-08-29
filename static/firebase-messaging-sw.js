// Firebase messaging service worker
importScripts('https://www.gstatic.com/firebasejs/9.0.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/9.0.0/firebase-messaging-compat.js');

// Firebase configuration
const firebaseConfig = {
    apiKey: "AIzaSyDummy",
    authDomain: "roxli-mail.firebaseapp.com",
    projectId: "roxli-mail",
    storageBucket: "roxli-mail.appspot.com",
    messagingSenderId: "539072741497",
    appId: "1:539072741497:web:dummy"
};

// Initialize Firebase
firebase.initializeApp(firebaseConfig);
const messaging = firebase.messaging();

// Handle background messages
messaging.onBackgroundMessage((payload) => {
    console.log('Background message received:', payload);
    
    const notificationTitle = payload.notification?.title || payload.data?.title || 'New Email';
    const notificationOptions = {
        body: payload.notification?.body || payload.data?.body || 'You have a new message',
        icon: '/static/images/logo.png',
        badge: '/static/images/logo.png',
        tag: 'roxli-mail-' + (payload.data?.email_id || Date.now()),
        requireInteraction: false,
        silent: false,
        vibrate: [200, 100, 200],
        data: payload.data || {},
        actions: [
            {
                action: 'view',
                title: 'View Email',
                icon: '/static/images/logo.png'
            }
        ]
    };

    return self.registration.showNotification(notificationTitle, notificationOptions);
});

// Handle notification clicks
self.addEventListener('notificationclick', (event) => {
    console.log('Notification clicked:', event);
    
    event.notification.close();
    
    if (event.action === 'view' || !event.action) {
        const emailId = event.notification.data?.email_id;
        const url = emailId ? `/read/${emailId}` : '/';
        
        event.waitUntil(
            clients.matchAll({ type: 'window', includeUncontrolled: true })
                .then((clientList) => {
                    // Check if mail.roxli.in is already open
                    for (const client of clientList) {
                        if (client.url.includes('mail.roxli.in') && 'focus' in client) {
                            client.focus();
                            client.postMessage({
                                type: 'NOTIFICATION_CLICK',
                                emailId: emailId
                            });
                            return;
                        }
                    }
                    
                    // Open new window if not already open
                    if (clients.openWindow) {
                        return clients.openWindow('https://mail.roxli.in' + url);
                    }
                })
        );
    }
});

// Handle push events (for additional reliability)
self.addEventListener('push', (event) => {
    console.log('Push event received:', event);
    
    if (event.data) {
        try {
            const payload = event.data.json();
            console.log('Push payload:', payload);
            
            const title = payload.notification?.title || payload.data?.title || 'New Email';
            const options = {
                body: payload.notification?.body || payload.data?.body || 'You have a new message',
                icon: '/static/images/logo.png',
                badge: '/static/images/logo.png',
                tag: 'roxli-mail-push',
                requireInteraction: false,
                silent: false,
                vibrate: [200, 100, 200],
                data: payload.data || {}
            };
            
            event.waitUntil(
                self.registration.showNotification(title, options)
            );
        } catch (error) {
            console.error('Error parsing push payload:', error);
        }
    }
});