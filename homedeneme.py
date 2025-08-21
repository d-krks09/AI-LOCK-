import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime, timedelta, time
import pandas as pd
import matplotlib.pyplot as plt
import random
from streamlit_autorefresh import st_autorefresh

try:
    from firebase_gonder import firebase_mesaj_gonder
except ImportError:
    st.warning("firebase_gonder.py modülü bulunamadı. Firebase'e mesaj gönderme işlemi simüle edilecek.")
    def firebase_mesaj_gonder(baslik, mesaj):
        print(f"Simüle Edildi: Firebase Mesajı -> Başlık: {baslik}, Mesaj: {mesaj}")

st.set_page_config(page_title="AI Lock", layout="centered")

# Firebase
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate("ai-lock-8a369-firebase-adminsdk-fbsvc-9241edcc37.json")
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://ai-lock-8a369-default-rtdb.firebaseio.com/'
        })
    except Exception as e:
        st.error(f"Firebase başlatılırken hata oluştu: {e}")
        st.stop()

# Session state
for key, default in {
    "giris_yapildi": False,
    "ekran": "baslangic",
    "kullanici_adi": "",
    "son_bildirilen_kapi_id": None,
    "son_bildirilen_yangin_id": None,
    "son_bildirilen_ilac_ids": set(),
    "manuel_komut_basarili": False,
    "manuel_komut_mesaji": "",
    "manuel_komut_tipi": "info"
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# Firebase kayıt ve giriş
def kayit_ekle(ad_soyad, kullanici_adi, sifre, telefon):
    db.reference("/kullanicilar").child(kullanici_adi).set({
        "ad_soyad": ad_soyad,
        "sifre": sifre,
        "telefon": telefon
    })

def giris_kontrol(kullanici_adi, sifre):
    veri = db.reference(f"/kullanicilar/{kullanici_adi}").get()
    return veri and veri["sifre"] == sifre

# Bildirimler
def bildirimleri_kontrol_et():
    try:
        kilit_veriler = db.reference("/kilitDurumu").get()
        if isinstance(kilit_veriler, dict) and kilit_veriler:
            son_key = list(kilit_veriler.keys())[-1]
            if son_key != st.session_state.son_bildirilen_kapi_id:
                st.session_state.son_bildirilen_kapi_id = son_key
                detay = kilit_veriler[son_key].get("detay", "").lower().replace(" ", "")
                if "kapiyikilitle" in detay:
                    st.info("🔐 Kapı kilitlendi.")
                elif "kapiyiac" in detay:
                    st.success("🔓 Kapı açıldı.")
    except:
        pass

    try:
        yangin_veriler = db.reference("/kilitDurumu").get()
        if isinstance(yangin_veriler, dict) and yangin_veriler:
            son_key = list(yangin_veriler.keys())[-1]
            if son_key != st.session_state.son_bildirilen_yangin_id:
                st.session_state.son_bildirilen_yangin_id = son_key
                detay = yangin_veriler[son_key].get("detay", "").lower()
                if "yanginalgilandi_kapiacildi" in detay:
                    st.error("🚨 Yangın riski tespit edildi! Kapı otomatik açılıyor...")
    except:
        pass

    try:
        kullanici = st.session_state.kullanici_adi
        if kullanici:
            ilaclar = db.reference(f"/ilaclar/{kullanici}").get()
            if ilaclar:
                bugun = datetime.now().date()
                suan = datetime.now().time()
                for key, ilac in ilaclar.items():
                    if key in st.session_state.son_bildirilen_ilac_ids:
                        continue
                    try:
                        saat = datetime.strptime(ilac["saat"], "%H:%M").time()
                        kayit_tarihi = datetime.strptime(ilac["kayit_tarihi"], "%Y-%m-%d").date()
                        fark = (bugun - kayit_tarihi).days
                        if fark >= ilac["gun"] or fark < 0:
                            continue
                        if (suan.hour == saat.hour and abs(suan.minute - saat.minute) <= 1):
                            st.warning(f"⏰ İlaç zamanı: {ilac['ad']} ({ilac['doz']})")
                            st.session_state.son_bildirilen_ilac_ids.add(key)
                    except:
                        continue
    except:
        pass

# Başlangıç ekran
def show_baslangic():
    st.image("logo.jpeg", use_container_width=True)
    if st.button("Devam Et"):
        st.session_state.ekran = "kayit"

# Kayıt ekranı
def show_kayit():
    st.title("🧾 Yeni Kullanıcı Kaydı")
    ad_soyad = st.text_input("👤 Ad Soyad")
    kullanici_adi = st.text_input("📛 Kullanıcı Adı")
    sifre = st.text_input("🔐 Şifre", type="password")
    telefon = st.text_input("📞 Telefon Numarası")
    if st.button("✅ Kaydı Tamamla"):
        if ad_soyad and kullanici_adi and sifre and telefon:
            if db.reference(f"/kullanicilar/{kullanici_adi}").get():
                st.warning("Bu kullanıcı adı alınmış.")
            else:
                kayit_ekle(ad_soyad, kullanici_adi, sifre, telefon)
                st.success("✅ Kayıt başarılı!")
                st.session_state.ekran = "giris"
        else:
            st.warning("Tüm alanları doldurun.")
    if st.button("Zaten üyeyim, giriş yap"):
        st.session_state.ekran = "giris"

# Giriş ekranı
def show_giris():
    st.title("🔐 Giriş Paneli")
    kullanici_adi = st.text_input("👤 Kullanıcı Adı")
    sifre = st.text_input("🔑 Şifre", type="password")
    if st.button("Giriş Yap"):
        if giris_kontrol(kullanici_adi, sifre):
            st.success("✅ Giriş başarılı!")
            st.session_state.giris_yapildi = True
            st.session_state.kullanici_adi = kullanici_adi
            st.session_state.ekran = "panel"
            st.session_state.son_bildirilen_ilac_ids = set()
        else:
            st.error("❌ Kullanıcı adı veya şifre hatalı.")

# Ana panel
def show_panel():
    st_autorefresh(interval=30_000, limit=None, key="auto_refresh_panel")
    st.image("logo.jpeg", use_container_width=True)
    bildirimleri_kontrol_et()
    secim = st.sidebar.selectbox("📋 Sayfa Seç", [
        "Kapı Durumu", "Kapı Kontrolü", "Yangın Paneli",
        "Duygu Analizi", "İlaç Takibi", "Kayıt Defteri", "Çıkış"
    ])
    if secim == "Kapı Durumu":
        show_kapi_durumu()
    elif secim == "Kapı Kontrolü":
        show_kapi_kontrol()
    elif secim == "Yangın Paneli":
        show_yangin_paneli()
    elif secim == "Duygu Analizi":
        show_duygu_analizi()
    elif secim == "İlaç Takibi":
        show_ilac_takibi()
    elif secim == "Kayıt Defteri":
        show_kayit_defteri()
    elif secim == "Çıkış":
        st.session_state.giris_yapildi = False
        st.session_state.kullanici_adi = ""
        st.session_state.ekran = "giris"

# Diğer fonksiyonlar (kapi durumu, kapi kontrol, yangın, duygu, ilaç vs.)  
# Kodlar senin mevcut fonksiyonlarınla birebir, sadece st.toast yerine st.info/success/warning kullanıldı
# Matplotlib için: st.pyplot(fig, clear_figure=True)

if not st.session_state.giris_yapildi:
    if st.session_state.ekran=="baslangic":
        show_baslangic()
    elif st.session_state.ekran=="kayit":
        show_kayit()
    elif st.session_state.ekran=="giris":
        show_giris()
else:
    show_panel()
