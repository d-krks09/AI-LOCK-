import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime, timedelta, time
import pandas as pd
import matplotlib.pyplot as plt
import random

# Firebase mesaj gönderme modülü
try:
    from firebase_gonder import firebase_mesaj_gonder
except ImportError:
    st.warning("firebase_gonder.py modülü bulunamadı. Firebase'e mesaj gönderme işlemi simüle edilecek.")
    def firebase_mesaj_gonder(baslik, mesaj):
        print(f"Simüle Edildi: Firebase Mesajı -> Başlık: {baslik}, Mesaj: {mesaj}")

st.set_page_config(page_title="AI Lock", layout="centered")

# Firebase bağlantısı
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
if "giris_yapildi" not in st.session_state: st.session_state.giris_yapildi = False
if "ekran" not in st.session_state: st.session_state.ekran = "baslangic"
if "kullanici_adi" not in st.session_state: st.session_state.kullanici_adi = ""
if "son_bildirilen_kapi_id" not in st.session_state: st.session_state.son_bildirilen_kapi_id = None
if "son_bildirilen_yangin_id" not in st.session_state: st.session_state.son_bildirilen_yangin_id = None
if "son_bildirilen_ilac_ids" not in st.session_state: st.session_state.son_bildirilen_ilac_ids = set()
if "manuel_komut_mesaji" not in st.session_state: st.session_state.manuel_komut_mesaji = ""
if "manuel_komut_tipi" not in st.session_state: st.session_state.manuel_komut_tipi = "info"

# Firebase işlemleri
def kayit_ekle(ad_soyad, kullanici_adi, sifre, telefon):
    ref = db.reference("/kullanicilar")
    ref.child(kullanici_adi).set({"ad_soyad": ad_soyad, "sifre": sifre, "telefon": telefon})

def giris_kontrol(kullanici_adi, sifre):
    ref = db.reference(f"/kullanicilar/{kullanici_adi}")
    veri = ref.get()
    return veri and veri["sifre"] == sifre

# Bildirim kontrolü
def bildirimleri_kontrol_et():
    # Kapı
    try:
        kilit_ref = db.reference("/kilitDurumu")
        kilit_veriler = kilit_ref.get() or {}
        son_key = list(kilit_veriler.keys())[-1] if kilit_veriler else None
        if son_key and son_key != st.session_state.son_bildirilen_kapi_id:
            st.session_state.son_bildirilen_kapi_id = son_key
            detay = kilit_veriler[son_key].get("detay", "").lower().replace(" ", "")
            if "kapiyikilitle" in detay:
                st.success("🔐 Kapı kilitlendi.")
            elif "kapiyiac" in detay:
                st.success("🔓 Kapı açıldı.")
    except Exception as e:
        st.error(f"Kapı bildirimi kontrol hatası: {e}")

    # Yangın
    try:
        yangin_ref = db.reference("/kilitDurumu")
        yangin_veriler = yangin_ref.get() or {}
        son_key = list(yangin_veriler.keys())[-1] if yangin_veriler else None
        if son_key and son_key != st.session_state.son_bildirilen_yangin_id:
            st.session_state.son_bildirilen_yangin_id = son_key
            detay = yangin_veriler[son_key].get("detay", "").lower()
            if "yanginalgilandi_kapiacildi" in detay:
                st.error("🚨 Yangın riski tespit edildi! Kapı otomatik açılıyor...")
    except Exception as e:
        st.error(f"Yangın bildirimi kontrol hatası: {e}")

    # İlaç
    try:
        kullanici = st.session_state.kullanici_adi
        if kullanici:
            ilac_ref = db.reference(f"/ilaclar/{kullanici}")
            ilaclar = ilac_ref.get() or {}
            bugun = datetime.now().date()
            suan = datetime.now().time()
            for key, ilac in ilaclar.items():
                if key in st.session_state.son_bildirilen_ilac_ids: continue
                try:
                    saat = datetime.strptime(ilac.get("saat","00:00"), "%H:%M").time()
                    kayit_tarihi = datetime.strptime(ilac.get("kayit_tarihi","2000-01-01"), "%Y-%m-%d").date()
                except:
                    continue
                fark = (bugun - kayit_tarihi).days
                if fark >= ilac["gun"] or fark < 0: continue
                if (suan.hour == saat.hour and abs(suan.minute - saat.minute) <= 1):
                    st.info(f"⏰ İlaç zamanı: {ilac['ad']} ({ilac['doz']})")
                    st.session_state.son_bildirilen_ilac_ids.add(key)
    except Exception as e:
        st.error(f"İlaç bildirimi kontrol hatası: {e}")

# Başlangıç ekranı
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
                st.warning("Bu kullanıcı adı zaten alınmış.")
            else:
                kayit_ekle(ad_soyad, kullanici_adi, sifre, telefon)
                st.success("✅ Kayıt başarılı!")
                st.session_state.ekran = "giris"
        else:
            st.warning("Tüm alanları doldurun.")
    st.markdown("---")
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
            st.session_state.son_bildirilen_ilac_ids = set()
        else:
            st.error("❌ Kullanıcı adı veya şifre hatalı.")

# Kapı durumu
def show_kapi_durumu():
    st.subheader("🔒 Kapı Durumu")
    try:
        ref = db.reference("/kilitDurumu")
        veriler = ref.get() or {}
        if veriler:
            son_key = list(veriler.keys())[-1]
            son = veriler[son_key]
            detay = son.get("detay","").lower().replace(" ","").replace(":","")
            zaman = son.get("zaman","Bilinmiyor")
            st.info(f"🕒 Son Güncelleme: {zaman}")
            if any(kelime in detay for kelime in ["kapiyikilitle","kilitlendi","kapikilitle"]):
                st.error("Kapı şu anda: KİLİTLİ")
            elif any(kelime in detay for kelime in ["kapiyiac","acildi"]):
                st.success("Kapı şu anda: AÇIK")
            else:
                st.warning("Kapı durumu bilinmiyor.")
        else:
            st.warning("Henüz kapı verisi yok.")
    except Exception as e:
        st.error(f"Kapı durumu alınamadı: {e}")

# Kapı kontrol
def show_kapi_kontrol():
    st.subheader("🖱️ Kapı Kontrolü")
    if st.button("🔓 Kapıyı Aç"):
        firebase_mesaj_gonder("Kapı Aç", "Manuel komut: kapıyı aç")
        st.success("Komut gönderildi: Kapı Aç")
    if st.button("🔐 Kapıyı Kilitle"):
        firebase_mesaj_gonder("Kapı Kilitle", "Manuel komut: kapıyı kilitle")
        st.success("Komut gönderildi: Kapı Kilitle")

# Yangın paneli
def show_yangin_paneli():
    st.subheader("🔥 Yangın Paneli")
    try:
        ref = db.reference("/kilitDurumu")
        veriler = ref.get() or {}
        son_key = list(veriler.keys())[-1] if veriler else None
        if son_key:
            son = veriler[son_key]
            detay = son.get("detay","")
            if "yangin" in detay.lower():
                st.error(f"🚨 Yangın tespit edildi: {detay}")
            else:
                st.success("Şu anda yangın riski yok.")
        else:
            st.warning("Yangın verisi yok.")
    except Exception as e:
        st.error(f"Yangın paneli alınamadı: {e}")

# Duygu analizi
def show_duygu_analizi():
    st.subheader("😊 Duygu Analizi")
    try:
        ref = db.reference(f"/duygu_durumu/{st.session_state.kullanici_adi}")
        veriler = ref.get() or {}
        if veriler:
            df = pd.DataFrame.from_dict(veriler, orient="index")
            df.index = pd.to_datetime(df.index)
            # Günlük
            gunluk = df.resample("D").mean()
            fig, ax = plt.subplots()
            gunluk.plot(ax=ax, y='duygu', legend=False, color='purple')
            ax.set_title("Günlük Duygu Ortalaması")
            ax.set_ylabel("Duygu Skoru")
            st.pyplot(fig)
            # Haftalık
            haftalik = df.resample("W").mean()
            fig2, ax2 = plt.subplots()
            haftalik.plot(ax=ax2, y='duygu', legend=False, color='green')
            ax2.set_title("Haftalık Duygu Ortalaması")
            ax2.set_ylabel("Duygu Skoru")
            st.pyplot(fig2)
        else:
            st.warning("Henüz duygu verisi yok.")
    except Exception as e:
        st.error(f"Duygu analizi alınamadı: {e}")

# İlaç takibi
def show_ilac_takibi():
    st.subheader("💊 İlaç Takibi")
    try:
        ref = db.reference(f"/ilaclar/{st.session_state.kullanici_adi}")
        veriler = ref.get() or {}
        if veriler:
            df = pd.DataFrame.from_dict(veriler, orient="index")
            st.table(df)
        else:
            st.warning("Henüz ilaç eklenmemiş.")
    except Exception as e:
        st.error(f"İlaç takibi alınamadı: {e}")

# Kayıt defteri
def show_kayit_defteri():
    st.subheader("📖 Kayıt Defteri")
    try:
        ref = db.reference("/kullanicilar")
        veriler = ref.get() or {}
        if veriler:
            df = pd.DataFrame.from_dict(veriler, orient="index")
            st.table(df)
        else:
            st.warning("Kayıtlı kullanıcı yok.")
    except Exception as e:
        st.error(f"Kayıt defteri alınamadı: {e}")

# Panel
def show_panel():
    st.image("logo.jpeg", use_container_width=True)
    bildirimleri_kontrol_et()
    secim = st.sidebar.selectbox("📋 Sayfa Seç", [
        "Kapı Durumu", "Kapı Kontrolü", "Yangın Paneli",
        "Duygu Analizi", "İlaç Takibi", "Kayıt Defteri", "Çıkış"
    ])
    if secim == "Kapı Durumu": show_kapi_durumu()
    elif secim == "Kapı Kontrolü": show_kapi_kontrol()
    elif secim == "Yangın Paneli": show_yangin_paneli()
    elif secim == "Duygu Analizi": show_duygu_analizi()
    elif secim == "İlaç Takibi": show_ilac_takibi()
    elif secim == "Kayıt Defteri": show_kayit_defteri()
    elif secim == "Çıkış":
        st.session_state.giris_yapildi = False
        st.session_state.kullanici_adi = ""
        st.session_state.ekran = "giris"

# Main
if not st.session_state.giris_yapildi:
    if st.session_state.ekran=="baslangic": show_baslangic()
    elif st.session_state.ekran=="kayit": show_kayit()
    elif st.session_state.ekran=="giris": show_giris()
else:
    show_panel()
