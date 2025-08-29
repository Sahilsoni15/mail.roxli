// Firebase messaging service worker
importScripts('https://www.gstatic.com/firebasejs/9.0.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/9.0.0/firebase-messaging-compat.js');

// Replace with your actual Firebase config
const firebaseConfig = {
    apiKey: "YOUR_API_KEY",
    authDomain: "your-project.firebaseapp.com",
    projectId: "your-project-id",
    storageBucket: "your-project.appspot.com",
    messagingSenderId: "YOUR_SENDER_ID",
    appId: "YOUR_APP_ID"
};

firebase.initializeApp(firebaseConfig);
const messaging = firebase.messaging();

// Handle background messages
messaging.onBackgroundMessage((payload) => {
    console.log('Background message received:', payload);
    
    const { title, body } = payload.notification;
    
    self.registration.showNotification(title, {
        body,
        icon: '/static/images/logo.png',
        badge: '/static/images/logo.png',
        tag: 'roxli-mail',
        requireInteraction: true,
        data: payload.data
    });
});

// Handle notification clicks
self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    
    const data = event.notification.data;
    if (data && data.email_id) {
        event.waitUntil(
            clients.openWindow(`/read/${data.email_id}`)
        );
    } else {
        event.waitUntil(
            clients.openWindow('/')
        );
    }
});