import firebase_admin
from firebase_admin import credentials, db

try:
    cred = credentials.Certificate("ai-lock-8a369-firebase-adminsdk-fbsvc-9241edcc37.json")
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://ai-lock-8a369-default-rtdb.firebaseio.com/'
    })
    ref = db.reference("/kilitDurumu")
    data = ref.get()
    print("Firebase bağlantısı başarılı. Veri:", data)
except Exception as e:
    print("Hata:", e)
