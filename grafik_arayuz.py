import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime, timedelta
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st

st.set_page_config(page_title="AI Lock - Duygu Sistemi", layout="wide")


# ==== Firebase Bağlantısı ====
if not firebase_admin._apps:
    cred = credentials.Certificate("ai-lock-8a369-firebase-adminsdk-fbsvc-9241edcc37.json")
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://ai-lock-8a369-default-rtdb.firebaseio.com/'
    })

# ==== Hasta ID ====
hasta_id = "hasta_001"

# ==== Firebase'ten duygu verilerini al ====
def get_emotions(hasta_id):
    ref = db.reference(f"duygu_durumu/{hasta_id}")
    data = ref.get()
    if not data:
        return pd.DataFrame(columns=["datetime", "emotion"])

    parsed_data = []
    for ts_str, emotion in data.items():
        try:
            ts_int = int(ts_str)
            ts = datetime.fromtimestamp(ts_int / 1000)
            parsed_data.append({"datetime": ts, "emotion": emotion})
        except ValueError:
            # Eğer ts_str sayı değilse (örneğin yanlışlıkla string key varsa), atla
            continue

    df = pd.DataFrame(parsed_data)
    df.sort_values("datetime", inplace=True)
    return df

# ==== Duyguya özel öneri ====
def get_suggestion(dominant_emotion):
    öneriler = {
        "Mutlu": "Hasta genellikle mutlu. Bu durumu destekleyecek müzikler ve sohbetler planlayabilirsiniz.",
        "Üzgün": "Hasta üzgün görünüyor. Ona moral verecek hatıralar ve destek olunabilir.",
        "Kızgın": "Öfke belirtileri var. Ortamı sakinleştirmek iyi olabilir.",
        "Şaşırmış": "Sürpriz etkisi yaratacak olaylar olmuş olabilir. Gözlemleyin.",
        "Korkmuş": "Korku hissediyor olabilir. Daha güvenli bir ortam sunun.",
        "İğrenmiş": "Rahatsız edici bir şey olmuş olabilir. Ortamı kontrol edin.",
        "Nötr": "Duygusal değişim gözlenmiyor. Rutin devam ettirilebilir."
    }
    return öneriler.get(dominant_emotion, "Veriye göre öneri yapılamadı.")

# ==== Streamlit Arayüzü ====
st.title("🧠 Alzheimer Duygu Analizi")

option = st.selectbox("Gösterilecek zaman dilimi seçin:", ("Bugün", "Bu Hafta"))

df = get_emotions(hasta_id)

if df.empty:
    st.warning("Firebase'de duygu verisi bulunamadı.")
else:
    if option == "Bugün":
        start_time = datetime.now().replace(hour=0, minute=0, second=0)
    else:  # Bu Hafta
        start_time = datetime.now() - timedelta(days=7)

    filtered = df[df["datetime"] >= start_time]

    if filtered.empty:
        st.info(f"{option} için veri bulunamadı.")
    else:
        st.subheader(f"{option} Duygu Grafiği")
        fig, ax = plt.subplots()
        filtered["emotion"].value_counts().plot(kind="bar", color="skyblue", ax=ax)
        plt.xticks(rotation=45)
        st.pyplot(fig)

        dominant = filtered["emotion"].mode()[0]
        st.success(f"🔍 En sık gözlenen duygu: **{dominant}**")
        st.info(get_suggestion(dominant))
