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

# Kullanıcı bilgisi
if "giris_yapildi" not in st.session_state:
    st.session_state.giris_yapildi = False
if "ekran" not in st.session_state:
    st.session_state.ekran = "baslangic"
if "kullanici_adi" not in st.session_state:
    st.session_state.kullanici_adi = ""
if "son_bildirilen_kapi_id" not in st.session_state:
    st.session_state.son_bildirilen_kapi_id = None
if "son_bildirilen_yangin_id" not in st.session_state:
    st.session_state.son_bildirilen_yangin_id = None
if "son_bildirilen_ilac_ids" not in st.session_state:
    st.session_state.son_bildirilen_ilac_ids = set()
if "manuel_komut_basarili" not in st.session_state:
    st.session_state.manuel_komut_basarili = False
if "manuel_komut_mesaji" not in st.session_state:
    st.session_state.manuel_komut_mesaji = ""
if "manuel_komut_tipi" not in st.session_state:
    st.session_state.manuel_komut_tipi = "info" 

# firebase komut ekleme
def kayit_ekle(ad_soyad, kullanici_adi, sifre, telefon):
    ref = db.reference("/kullanicilar")
    ref.child(kullanici_adi).set({
        "ad_soyad": ad_soyad,
        "sifre": sifre,
        "telefon": telefon
    })

def giris_kontrol(kullanici_adi, sifre):
    ref = db.reference(f"/kullanicilar/{kullanici_adi}")
    veri = ref.get()
    return veri and veri["sifre"] == sifre

# Bildirimler
def bildirimleri_kontrol_et():
    # Kapı
    try:
        kilit_ref = db.reference("/kilitDurumu")
        kilit_veriler = kilit_ref.get()
        if isinstance(kilit_veriler, dict) and kilit_veriler:
            son_key = list(kilit_veriler.keys())[-1]
            if son_key != st.session_state.son_bildirilen_kapi_id:
                st.session_state.son_bildirilen_kapi_id = son_key
                detay = kilit_veriler[son_key].get("detay", "").lower().replace(" ", "")
                if "kapiyikilitle" in detay:
                    st.toast("🔐 Kapı kilitlendi.")
                elif "kapiyiac" in detay:
                    st.toast("🔓 Kapı açıldı.")
    except Exception as e:
        st.error(f"Kapı bildirimi kontrol hatası: {e}")

    # Yangın
    try:
        yangin_ref = db.reference("/kilitDurumu") 
        yangin_veriler = yangin_ref.get()
        if isinstance(yangin_veriler, dict) and yangin_veriler:
            son_key = list(yangin_veriler.keys())[-1]
            if son_key != st.session_state.son_bildirilen_yangin_id:
                st.session_state.son_bildirilen_yangin_id = son_key
                detay = yangin_veriler[son_key].get("detay", "").lower()
                if "yanginalgilandi_kapiacildi" in detay:
                    st.toast("🚨 Yangın riski tespit edildi! Kapı otomatik açılıyor...")
    except Exception as e:
        st.error(f"Yangın bildirimi kontrol hatası: {e}")

    # İlaç
    try:
        kullanici = st.session_state.kullanici_adi
        if kullanici:
            ilac_ref = db.reference(f"/ilaclar/{kullanici}")
            ilaclar = ilac_ref.get()
            if ilaclar:
                suan = datetime.now().time()
                bugun = datetime.now().date()
                for key, ilac in ilaclar.items():
                    if key in st.session_state.son_bildirilen_ilac_ids:
                        continue 
                    
                    saat_str = ilac.get("saat")
                    kayit_tarihi_str = ilac.get("kayit_tarihi")

                    if not saat_str or not kayit_tarihi_str:
                        continue

                    try:
                        saat = datetime.strptime(saat_str, "%H:%M").time()
                        kayit_tarihi = datetime.strptime(kayit_tarihi_str, "%Y-%m-%d").date()
                    except ValueError as ve:
                        continue

                    fark = (bugun - kayit_tarihi).days
                    
                    if fark >= ilac["gun"] or fark < 0:
                        continue 
                    
                    if (suan.hour == saat.hour and abs(suan.minute - saat.minute) <= 1):
                        st.toast(f"⏰ İlaç zamanı: {ilac['ad']} ({ilac['doz']})")
                        st.session_state.son_bildirilen_ilac_ids.add(key) 

    except Exception as e:
        st.error(f"İlaç bildirimi kontrol hatası: {e}")

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
                st.warning("Bu kullanıcı adı zaten alınmış. Lütfen başka bir kullanıcı adı seçin.")
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
            st.session_state.ekran = "panel"
            st.session_state.son_bildirilen_ilac_ids = set() 
            
        else:
            st.error("❌ Kullanıcı adı veya şifre hatalı.")

# Ana panel
def show_panel():
    st_autorefresh(interval=10_000, limit=None, key="auto_refresh_panel") 

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
        

# Kapı durumu
def show_kapi_durumu():
    st.subheader("🔒 Kapı Durumu")
    try:
        ref = db.reference("/kilitDurumu")
        veriler = ref.get()

        if isinstance(veriler, dict) and len(veriler) > 0:
            son_key = list(veriler.keys())[-1]
            son = veriler[son_key]

            detay = son.get("detay", "").lower().replace(" ", "").replace(":", "")
            zaman = son.get("zaman", "Bilinmiyor")
            st.info(f"🕒 Son Güncelleme: {zaman}")

            if any(kelime in detay for kelime in ["kapiyikilitle", "kilitlendi", "kapikilitle"]):
                st.error("Kapı şu anda: KİLİTLİ")
            elif any(kelime in detay for kelime in ["kapiyiac", "acildi", "kapiaç", "yanginalgilandikapiacildi"]):
                st.success("Kapı şu anda: AÇIK")
            else:
                st.warning(f"Kapı durumu bilinmiyor. (detay: {detay})")
        else:
            st.warning("Kapı durumu verisi alınamadı.")
    except Exception as e:
        st.error(f"Firebase bağlantı hatası: {e}")

#Kapı kontrol
def show_kapi_kontrol():
    st.subheader("🚪 Kapı Kontrol Paneli")

    message_placeholder = st.empty()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔒 Kapıyı Kilitle", key="manuel_kilit_kilitle"):
            try:
                db.reference("/komutlar/manuelKomut").set("kapat") 
                st.session_state.manuel_komut_mesaji = "Kapıyı Kilitleme komutu gönderildi. Kapı durumu birkaç saniye içinde güncellenecektir."
                st.session_state.manuel_komut_tipi = "success"
                firebase_mesaj_gonder("Kilit Komutu", "Manuel olarak kilitlendi (Web Arayüzü)")
            except Exception as e:
                st.session_state.manuel_komut_mesaji = f"Komut gönderilirken hata oluştu: {e}"
                st.session_state.manuel_komut_tipi = "error"
            
    with col2:
        if st.button("🔓 Kapıyı Aç", key="manuel_kilit_ac"):
            try:
                db.reference("/komutlar/manuelKomut").set("ac")
                st.session_state.manuel_komut_mesaji = "Kapıyı Açma komutu gönderildi. Kapı durumu birkaç saniye içinde güncellenecektir."
                st.session_state.manuel_komut_tipi = "success"
                firebase_mesaj_gonder("Kilit Komutu", "Manuel olarak kilit açıldı (Web Arayüzü)")
            except Exception as e:
                st.session_state.manuel_komut_mesaji = f"Komut gönderilirken hata oluştu: {e}"
                st.session_state.manuel_komut_tipi = "error"
            

    
    if st.session_state.manuel_komut_mesaji:
        if st.session_state.manuel_komut_tipi == "success":
            message_placeholder.success(st.session_state.manuel_komut_mesaji)
        elif st.session_state.manuel_komut_tipi == "error":
            message_placeholder.error(st.session_state.manuel_komut_mesaji)
        elif st.session_state.manuel_komut_tipi == "warning":
            message_placeholder.warning(st.session_state.manuel_komut_mesaji)
        else: 
            message_placeholder.info(st.session_state.manuel_komut_mesaji)
        
       
        st.session_state.manuel_komut_mesaji = ""
        st.session_state.manuel_komut_tipi = "info" 


#Yangın ekranı
def show_yangin_paneli():
    st.subheader("🔥 Yangın Durumu Paneli")
    sicaklik = random.randint(20, 60) 
    st.metric("🌡 Sıcaklık (°C)", f"{sicaklik}°C")
    
    YANGIN_ESIGI = 40 

    if sicaklik >= YANGIN_ESIGI:
        st.error("🚨 Yangın riski var! Kapı otomatik açılıyor...")
        db.reference("/komutlar/manuelKomut").set("ac") 
        db.reference("/kilitDurumu").push({
            "detay": "YanginAlgilandi_KapiAcildi", 
            "olay": "Yangın Alarmı",             
            "zaman": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
    else:
        st.success("Normal sıcaklık düzeyi. Yangın riski yok.")

#Duygu analizi ekranı
def show_duygu_analizi():
    st.subheader("🧠 Duygu Analizi")
    hasta_id = "hasta_001" 
    data = db.reference(f"/duygu_durumu/{hasta_id}").get()

    if not data:
        st.info("Bu hastaya ait duygu analizi verisi bulunamadı.")
        return
    
    parsed = []
    for ts_str, emo in data.items():
        try:
            parsed.append({"datetime": datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S"), "emotion": emo})
            
        except ValueError:
            try:
                parsed.append({"datetime": datetime.fromtimestamp(int(ts_str)/1000), "emotion": emo})
            except Exception as e:
                continue

    if not parsed:
        st.info("İşlenebilir duygu analizi verisi bulunamadı.")
        return

    df = pd.DataFrame(parsed).sort_values("datetime")

    st.markdown("---")
    st.markdown("### 📊 Duygu Dağılımı")

    zaman_araligi = st.selectbox("Zaman Aralığına Göre Filtrele", ["Tümü", "Bugün", "Son 7 Gün", "Son 30 Gün"])
    
    filtered_df = df.copy()

    if zaman_araligi == "Bugün":
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        filtered_df = df[df["datetime"] >= today_start]
    elif zaman_araligi == "Son 7 Gün":
        seven_days_ago = datetime.now() - timedelta(days=7)
        filtered_df = df[df["datetime"] >= seven_days_ago]
    elif zaman_araligi == "Son 30 Gün":
        thirty_days_ago = datetime.now() - timedelta(days=30)
        filtered_df = df[df["datetime"] >= thirty_days_ago]
    
    if filtered_df.empty:
        st.info("Seçilen zaman aralığında duygu verisi bulunamadı.")
        return

    fig, ax = plt.subplots(figsize=(10, 6))
    emotion_counts = filtered_df["emotion"].value_counts(normalize=True) * 100 
    emotion_counts.plot(kind="bar", ax=ax, color='skyblue')
    ax.set_title(f"{zaman_araligi} İçin Duygu Dağılımı")
    ax.set_xlabel("Duygu")
    ax.set_ylabel("Yüzde (%)")
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    st.pyplot(fig)

    dominant_emotion = filtered_df["emotion"].mode()[0]
    st.success(f"🔍 Seçilen zaman aralığında en sık görülen duygu: **{dominant_emotion}**")

    st.markdown("---")
    st.markdown("### 📈 Duygu Trendi (Zaman Çizgisi)")

    if not filtered_df.empty:
        fig2, ax2 = plt.subplots(figsize=(12, 6))
        
        ax2.plot(filtered_df['datetime'], filtered_df['emotion'], marker='o', linestyle='-', markersize=5)
        
        ax2.set_title(f"{zaman_araligi} İçin Duygu Trendi")
        ax2.set_xlabel("Zaman")
        ax2.set_ylabel("Duygu")
        plt.xticks(rotation=45, ha='right')
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.tight_layout()
        st.pyplot(fig2)

    st.markdown("---")
    st.markdown("### 📋 Ham Duygu Verileri")
    st.dataframe(filtered_df.rename(columns={"datetime": "Tarih/Saat", "emotion": "Duygu"}))


# İlaç ekranı
def show_ilac_takibi():
    st.subheader("💊 İlaç Takip ve Hatırlatma Sistemi")
    kullanici = st.session_state.kullanici_adi
    ilac_ref = db.reference(f"/ilaclar/{kullanici}")

    with st.expander("➕ Yeni İlaç Ekle"):
        ilac_adi = st.text_input("İlaç Adı", placeholder="Örn: Aricept", key="new_ilac_adi")
        ilac_dozu = st.text_input("Dozaj", placeholder="Örn: 10 mg", key="new_ilac_dozu")
        ilac_saati = st.time_input("İlaç Alma Saati", value=time(21, 0), key="new_ilac_saati")
        kac_gun = st.number_input("Kaç gün boyunca alınacak?", min_value=1, max_value=365, value=30, key="new_kac_gun")

        if st.button("💾 Hatırlatıcıyı Kaydet", key="save_new_ilac"):
            if ilac_adi and ilac_dozu:
                kayit = {
                    "ad": ilac_adi,
                    "doz": ilac_dozu,
                    "saat": ilac_saati.strftime("%H:%M"),
                    "gun": kac_gun,
                    "kayit_tarihi": datetime.now().strftime("%Y-%m-%d")
                }
                ilac_ref.push(kayit)
                st.success(f"'{ilac_adi}' hatırlatıcısı başarıyla kaydedildi.")
                
            else:
                st.warning("İlaç adı ve dozaj alanları boş bırakılamaz.")

    st.markdown("### 🔔 Aktif Hatırlatmalar")
    data = ilac_ref.get()

    if not data:
        st.info("Kayıtlı hatırlatıcı yok.")
        return

    bugun = datetime.now().date()
    suan = datetime.now().time()

    sorted_ilaclar = sorted(data.items(), key=lambda item: datetime.strptime(item[1]['saat'], "%H:%M").time())

    for key, ilac in sorted_ilaclar:
        try:
            saat_obj = datetime.strptime(ilac["saat"], "%H:%M").time()
            kayit_tarihi_obj = datetime.strptime(ilac["kayit_tarihi"], "%Y-%m-%d").date()
            
            kalan_gun_sayisi = ilac["gun"] - (bugun - kayit_tarihi_obj).days
            
            if kalan_gun_sayisi <= 0:
                st.warning(f"🕒 {ilac['ad']} - Süresi doldu ({ilac['gun']} gün tamamlandı).")
                if st.button(f"Süresi Dolanı Sil: {ilac['ad']}", key=f"delete_expired_{key}"):
                    ilac_ref.child(key).delete()
                    st.success(f"'{ilac['ad']}' (süresi dolan) silindi.")
                    
                continue 

            with st.expander(f"💊 {ilac['ad']} ({ilac['doz']}) - {ilac['saat']}"):
                if suan.hour == saat_obj.hour and abs(suan.minute - saat_obj.minute) < 5: 
                    st.error("⏰ İlacı alma zamanı geldi / yaklaşıyor!")
                elif suan > saat_obj:
                    st.info(f"Hatırlatma saati geçti: {saat_obj.strftime('%H:%M')}")
                else:
                    st.info(f"Hatırlatma saati: {saat_obj.strftime('%H:%M')}")

                st.caption(f"Kalan gün: {kalan_gun_sayisi} / {ilac['gun']}")

                col1, col2 = st.columns(2)

                with col1:
                    if st.button("✏️ Düzenle", key=f"duzenle_{key}"):
                        with st.form(f"form_{key}"):
                            yeni_ad = st.text_input("İlaç Adı", value=ilac["ad"], key=f"yeni_ad_{key}")
                            yeni_doz = st.text_input("Dozaj", value=ilac["doz"], key=f"yeni_doz_{key}")
                            yeni_saat = st.time_input("Alım Saati", value=saat_obj, key=f"yeni_saat_{key}")
                            yeni_gun = st.number_input("Kaç gün?", min_value=1, max_value=365, value=ilac["gun"], key=f"yeni_gun_{key}")
                            kaydet = st.form_submit_button("💾 Kaydet", key=f"kaydet_form_{key}")

                            if kaydet:
                                ilac_ref.child(key).update({
                                    "ad": yeni_ad,
                                    "doz": yeni_doz,
                                    "saat": yeni_saat.strftime("%H:%M"),
                                    "gun": yeni_gun
                                })
                                st.success("İlaç bilgisi güncellendi.")
                                

                with col2:
                    if st.button("🗑️ Sil", key=f"sil_{key}"):
                        ilac_ref.child(key).delete()
                        st.warning(f"'{ilac['ad']}' silindi.")
                        

        except Exception as e:
            st.error(f"İlaç bilgisi okunurken veya işlenirken hata oluştu (ID: {key}): {e}")

# Kayıt defteri ekranı
def show_kayit_defteri():
    st.subheader("📑 Sistem Kayıt Defteri")
    
    st.markdown("#### 🔒 Kapı ve Sistem Olay Kayıtları")
    kilit_log_ref = db.reference("/kilitDurumu")
    kilit_logs = kilit_log_ref.get()

    if kilit_logs:
        df_kilit = pd.DataFrame(kilit_logs.values())
        df_kilit["zaman"] = pd.to_datetime(df_kilit["zaman"])
        df_kilit = df_kilit.sort_values(by="zaman", ascending=False)
        st.dataframe(df_kilit, use_container_width=True)
    else:
        st.info("Kapı veya sistem olay kaydı bulunamadı.")

    st.markdown("---")
    st.markdown("#### 🧠 Duygu Analizi Kayıtları")
    duygu_log_ref = db.reference("/duygu_durumu/hasta_001")
    duygu_logs = duygu_log_ref.get()

    if duygu_logs:
        parsed_duygu_logs = []
        for ts_str, duygu_val in duygu_logs.items():
            try:
                parsed_duygu_logs.append({"Zaman": datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S"), "Duygu": duygu_val})
            except ValueError:
                try:
                    parsed_duygu_logs.append({"Zaman": datetime.fromtimestamp(int(ts_str)/1000), "Duygu": duygu_val})
                except Exception as e:
                    continue

        if parsed_duygu_logs:
            df_duygu = pd.DataFrame(parsed_duygu_logs)
            df_duygu = df_duygu.sort_values(by="Zaman", ascending=False)
            st.dataframe(df_duygu, use_container_width=True)
        else:
            st.info("İşlenebilir duygu kaydı bulunamadı.")
    else:
        st.info("Duygu kaydı bulunamadı.")


if not st.session_state.giris_yapildi:
    if st.session_state.ekran=="baslangic":
        show_baslangic()
    elif st.session_state.ekran=="kayit":
        show_kayit()
    elif st.session_state.ekran=="giris":
        show_giris()
else:
    show_panel()