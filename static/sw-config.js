// Service worker configuration endpoint
self.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'FIREBASE_CONFIG') {
        // Store Firebase config for service worker
        self.firebaseConfig = event.data.config;
        
        // Reinitialize Firebase with new config
        if (self.firebase && self.firebase.apps.length > 0) {
            self.firebase.app().delete().then(() => {
                initializeFirebase();
            });
        } else {
            initializeFirebase();
        }
    }
});

function initializeFirebase() {
    if (self.firebaseConfig && self.firebase) {
        self.firebase.initializeApp(self.firebaseConfig);
        const messaging = self.firebase.messaging();
        
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
                data: payload.data || {}
            };

            return self.registration.showNotification(notificationTitle, notificationOptions);
        });
    }
}