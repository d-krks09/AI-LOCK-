import firebase_admin
from firebase_admin import credentials, db
import time
from datetime import datetime 

# Firebase 
if not firebase_admin._apps:
    cred = credentials.Certificate("ai-lock-8a369-firebase-adminsdk-fbsvc-9241edcc37.json")
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://ai-lock-8a369-default-rtdb.firebaseio.com/'
    })

def firebase_mesaj_gonder(olay, detay):
    try:
        ref = db.reference("/kilitDurumu")
        ref.push({
            "olay": olay,
            "detay": detay,
            "zaman": time.strftime("%Y-%m-%d %H:%M:%S")
        })
        print(f"Firebase'e gönderildi: {olay} - {detay}")
    except Exception as e:
        print("Firebase gönderim hatası:", e)

def firebase_duygu_gonder(hasta_id, emotion, timestamp_str): 
    try:
        
        dt_object = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")

     
        millis = int(dt_object.timestamp() * 1000)

        ref = db.reference(f"duygu_durumu/{hasta_id}")
        ref.child(str(millis)).set(emotion) 

        print(f"Firebase: Hasta '{hasta_id}' için duygu '{emotion}' ve milisaniye '{millis}' gönderildi.")
    except Exception as e:
        print(f"Firebase duygu gönderim hatası: {e}")