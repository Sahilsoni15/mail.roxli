// Firebase Cloud Messaging for push notifications
import { initializeApp } from 'firebase/app';
import { getMessaging, getToken, onMessage } from 'firebase/messaging';

const firebaseConfig = {
    apiKey: "your-api-key",
    authDomain: "roxli-mail.firebaseapp.com",
    projectId: "roxli-mail",
    storageBucket: "roxli-mail.appspot.com",
    messagingSenderId: "your-sender-id",
    appId: "your-app-id"
};

const app = initializeApp(firebaseConfig);
const messaging = getMessaging(app);

// Request notification permission and get FCM token
export async function initializeNotifications() {
    try {
        const permission = await Notification.requestPermission();
        
        if (permission === 'granted') {
            const token = await getToken(messaging, {
                vapidKey: 'your-vapid-key'
            });
            
            if (token) {
                // Send token to server
                await fetch('/api/subscribe-notifications', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ token })
                });
                
                console.log('FCM token registered:', token);
                return true;
            }
        }
        
        return false;
    } catch (error) {
        console.error('Error initializing notifications:', error);
        return false;
    }
}

// Handle foreground messages
onMessage(messaging, (payload) => {
    console.log('Message received:', payload);
    
    const { title, body } = payload.notification;
    
    // Show browser notification
    if ('Notification' in window && Notification.permission === 'granted') {
        new Notification(title, {
            body,
            icon: '/static/images/logo.png',
            badge: '/static/images/logo.png',
            tag: 'roxli-mail',
            requireInteraction: true,
            data: payload.data
        });
    }
    
    // Show in-app notification
    showInAppNotification(title, body);
});

function showInAppNotification(title, body) {
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #1a73e8;
        color: white;
        padding: 16px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        z-index: 10000;
        max-width: 300px;
        animation: slideIn 0.3s ease-out;
    `;
    
    notification.innerHTML = `
        <div style="font-weight: 600; margin-bottom: 4px;">${title}</div>
        <div style="font-size: 14px; opacity: 0.9;">${body}</div>
        <button onclick="this.parentElement.remove()" style="
            position: absolute;
            top: 8px;
            right: 8px;
            background: none;
            border: none;
            color: white;
            font-size: 18px;
            cursor: pointer;
        ">&times;</button>
    `;
    
    document.body.appendChild(notification);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 5000);
}

// Add CSS animation
if (!document.querySelector('#notification-styles')) {
    const style = document.createElement('style');
    style.id = 'notification-styles';
    style.textContent = `
        @keyframes slideIn {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
    `;
    document.head.appendChild(style);
}