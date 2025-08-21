import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import serial
import time
from firebase_gonder import firebase_mesaj_gonder

# ==== Firebase Ayarları ====
if not firebase_admin._apps:
    cred = credentials.Certificate("ai-lock-8a369-firebase-adminsdk-fbsvc-9241edcc37.json")
    firebase_admin.initialize_app(cred, {
        "databaseURL": "https://ai-lock-8a369-default-rtdb.firebaseio.com/"
    })

# ==== Arduino Bağlantısı ====
try:
    arduino = serial.Serial('COM5', 9600, timeout=1)
    time.sleep(2)
    arduino_baglandi = True
except:
    class FakeArduino:
        def write(self, data): print(f"(Simülasyon) Arduino komutu: {data.decode().strip()}")
        def readline(self): return b""
    arduino = FakeArduino()
    arduino_baglandi = False

# ==== Komut Gönderme Fonksiyonu ====
def send_command(cmd):
    try:
        arduino.write((cmd + "\n").encode())
        firebase_mesaj_gonder("Komut Gönderildi", f"Komut: {cmd}")
        st.success(f"Komut gönderildi: {cmd}")
    except Exception as e:
        st.error(f"Hata: {e}")

# ==== Streamlit Arayüz ====
st.set_page_config(page_title="AI Lock – Manuel Kilit Kontrol", layout="centered")
st.title("🔐 Manuel Kilit Kontrol Ekranı")

st.write("Arduino bağlantısı durumu:")
if arduino_baglandi:
    st.success("Arduino bağlı.")
else:
    st.warning("Arduino bağlı değil, simülasyon modunda çalışıyor.")

# ==== Butonlar ====
col1, col2 = st.columns(2)

with col1:
    if st.button("🔓 Kilit Aç"):
        send_command("KapiyiAc")
        db.reference("/kapidurum").update({
            "durum": "acik",
            "detay": "manuelolarakaçıldı(webarayüzü)"
        })
        firebase_mesaj_gonder("Kilit Komutu", "Manuel olarak kilit açıldı")

with col2:
    if st.button("🔒 Kilitle"):
        send_command("KapiyiKilitle")
        db.reference("/kapidurum").update({
            "durum": "kilitli",
            "detay": "manuelolarakkilitlendi(webarayüzü)"
        })
        firebase_mesaj_gonder("Kilit Komutu", "Manuel olarak kilitlendi")
