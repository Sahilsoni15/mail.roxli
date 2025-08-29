// Firebase messaging service worker
importScripts('https://www.gstatic.com/firebasejs/9.0.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/9.0.0/firebase-messaging-compat.js');

const firebaseConfig = {
    apiKey: "AIzaSyDummy",
    authDomain: "roxli-mail.firebaseapp.com",
    projectId: "roxli-mail",
    storageBucket: "roxli-mail.appspot.com",
    messagingSenderId: "539072741497",
    appId: "1:539072741497:web:dummy"
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