from flask import Flask, render_template_string
import firebase_admin
from firebase_admin import credentials, db

app = Flask(__name__)

# Firebase bağlantısı (aynı Streamlit’te yaptığın gibi)
cred = credentials.Certificate("ai-lock-8a369-firebase-adminsdk-fbsvc-9241edcc37.json")  # JSON dosyanın yolu
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://ai-lock-8a369-default-rtdb.firebaseio.com/'
})

@app.route('/')
def home():
    try:
        durum_ref = db.reference("/kilitDurumu")
        durum = durum_ref.get()
    except Exception as e:
        durum = f"Bağlantı hatası: {e}"

    html = f"""
    <h1>AI Lock - Kapı Durumu</h1>
    <p>Kapı durumu: <strong>{durum}</strong></p>
    """

    return render_template_string(html)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
