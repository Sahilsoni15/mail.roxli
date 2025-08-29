# Firebase Cloud Messaging Setup Guide

## 1. Create Firebase Project

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Click "Create a project" or "Add project"
3. Enter project name (e.g., "roxli-mail")
4. Enable Google Analytics (optional)
5. Click "Create project"

## 2. Enable Cloud Messaging

1. In your Firebase project, go to "Project Settings" (gear icon)
2. Click on "Cloud Messaging" tab
3. Note down your "Server key" and "Sender ID"

## 3. Generate Service Account Key

1. Go to "Project Settings" > "Service accounts"
2. Click "Generate new private key"
3. Download the JSON file
4. Rename it to `roxli-mail-firebase-adminsdk.json`
5. Place it in your project root directory

## 4. Get Web App Config

1. In Firebase Console, click "Add app" > Web app icon
2. Register your app with nickname "Roxli Mail Web"
3. Copy the Firebase config object
4. Update the config in both:
   - `templates/inbox.html` (firebaseConfig object)
   - `static/firebase-messaging-sw.js` (firebaseConfig object)

## 5. Generate VAPID Key

1. Go to "Project Settings" > "Cloud Messaging"
2. In "Web configuration" section, click "Generate key pair"
3. Copy the VAPID key
4. Update `YOUR_VAPID_KEY` in `templates/inbox.html`

## 6. Update Configuration Files

### Update `templates/inbox.html`:
```javascript
const firebaseConfig = {
    apiKey: "your-api-key",
    authDomain: "your-project.firebaseapp.com",
    projectId: "your-project-id",
    storageBucket: "your-project.appspot.com",
    messagingSenderId: "your-sender-id",
    appId: "your-app-id"
};
```

### Update `static/firebase-messaging-sw.js`:
```javascript
const firebaseConfig = {
    // Same config as above
};
```

### Update VAPID key in `templates/inbox.html`:
```javascript
messaging.getToken({ vapidKey: 'YOUR_ACTUAL_VAPID_KEY' })
```

## 7. Environment Variables (Production)

Set these environment variables:
- `FIREBASE_CONFIG`: JSON string of service account key
- `FIREBASE_DATABASE_URL`: Your Firebase Realtime Database URL

## 8. Test Notifications

1. Open the mail app in browser
2. Allow notification permissions when prompted
3. Send a test email to yourself
4. You should receive a push notification

## How Auto Notifications Work

### When User Receives Email:

1. **Email Sent**: When someone sends an email via `/api/send-email`
2. **Recipient Found**: System finds recipient in auth database
3. **Email Stored**: Email saved to recipient's inbox in Firebase
4. **Notification Triggered**: `send_notification_to_user()` called
5. **FCM Token Retrieved**: System gets user's FCM token from database
6. **Push Sent**: FCM notification sent to user's device
7. **Background/Foreground**: 
   - **Background**: Service worker shows notification
   - **Foreground**: In-app notification displayed

### Notification Flow:

```
New Email → Store in DB → Get FCM Token → Send Push → User Receives
```

### Service Worker Handles:
- Background message reception
- Notification display when app is closed
- Notification click actions (opens email)

### Frontend Handles:
- FCM token generation and registration
- Foreground message reception
- In-app notification display
- Permission requests

## Troubleshooting

### No Notifications Received:
1. Check browser console for errors
2. Verify Firebase config is correct
3. Ensure VAPID key is set
4. Check if notifications are blocked in browser
5. Verify service worker is registered

### Permission Denied:
1. Clear browser data for the site
2. Reload and allow permissions again
3. Check browser notification settings

### Service Worker Issues:
1. Check `/static/firebase-messaging-sw.js` is accessible
2. Verify Firebase SDK versions match
3. Check browser developer tools > Application > Service Workers

## Security Notes

- Never expose service account keys in client-side code
- Use environment variables for sensitive config
- Validate all notification data on server-side
- Implement rate limiting for notifications