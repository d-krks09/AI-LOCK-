import face_recognition
import cv2
import os
import serial
import time
import threading
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import requests
import firebase_admin
from firebase_admin import credentials, db
from firebase_gonder import firebase_mesaj_gonder, firebase_duygu_gonder 
from deepface import DeepFace
from datetime import datetime

#Ayarlama 
KNOWN_FACES_DIR = "face_images"
TOLERANCE = 0.5
FRAME_THICKNESS = 3
FONT_THICKNESS = 2
MODEL = "hog" 

BOT_TOKEN = ' '    
CHAT_ID = ' '          

fire_alert_sent = False 

# duygu
son_duygu = None
son_duygu_gonderimi = 0
duygu_bekleme = 30     
duygu_cevir = {
    "happy": "Mutlu",
    "sad": "Üzgün",
    "angry": "Kızgın",
    "surprise": "Şaşırmış",
    "fear": "Korkmuş",
    "disgust": "İğrenmiş",
    "neutral": "Nötr"
}

recognized_person_present = False 

# Kapı durumu yeni
current_door_state = "UNKNOWN" 
last_door_command_sent = ""    

last_door_action_time = time.time() 
door_command_cooldown = 3 

# Override
last_manual_open_time = 0 
manual_open_override_duration = 5 

# Firebase
cred = credentials.Certificate("ai-lock-8a369-firebase-adminsdk-fbsvc-9241edcc37.json")
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred, {
        "databaseURL": "https://ai-lock-8a369-default-rtdb.firebaseio.com/"
    })

kilit_ref = db.reference('kilitDurumu') 

# Tkinter arayüz
window = tk.Tk()
window.title("Akıllı Kilit Sistemi")
window.geometry("720x600")
window.configure(bg="#222")

video_label = tk.Label(window, bg="#000")
video_label.pack(pady=10)

status_label = tk.Label(window, text="Başlatılıyor...", fg="white", bg="#222", font=("Arial", 12))
status_label.pack(pady=5)

# Telegram
def send_telegram_message(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": msg}
        requests.post(url, data=payload)
        status_label.config(text="Telegram mesajı gönderildi.")
    except Exception as e:
        status_label.config(text=f"Telegram bağlantı hatası: {e}")

# arduino
try:
    arduino = serial.Serial('COM5', 9600, timeout=1) 
    time.sleep(2) 
    arduino_connected = True
    print("Arduino bağlantısı başarılı.")
except Exception as e:
    class FakeArduino:
        def write(self, data): 
            print(f"(Simülasyon) Arduino komutu: {data.decode().strip()}")
        def readline(self): 
            return b"" 
    arduino = FakeArduino()
    arduino_connected = False
    print(f"Arduino bağlantısı kurulamadı: {e}. Simülasyon modunda çalışılıyor.")

def send_command(cmd_key):
    """Arduino'ya komut gönderir ve Firebase'e loglar.
    cmd_key: 'KapiyiAc', 'KapiyiKilitle', 'YanginAlgilandi_KapiAcildi' vb.
    """
    global last_door_action_time, current_door_state, last_door_command_sent, last_manual_open_time # Yeni global değişkeni ekle
    current_time = time.time()

    is_manual_command = cmd_key in ("KapiyiAc", "KapiyiKilitle") 

    if (current_time - last_door_action_time) < door_command_cooldown:
         return

    arduino_cmd = ""
    olay_detay = ""
    olay_baslik = ""
    new_state = ""

    if cmd_key == "KapiyiAc":
        arduino_cmd = "KapiyiAc"
        olay_detay = "ManuelAcildi" 
        olay_baslik = "Kapı Açma"
        new_state = "acik"
        if is_manual_command: 
            last_manual_open_time = current_time 
    elif cmd_key == "KapiyiKilitle":
        arduino_cmd = "KapiyiKilitle"
        olay_detay = "ManuelKilitlendi" 
        olay_baslik = "Kapı Kilitleme"
        new_state = "kilitli"
    elif cmd_key == "YanginAlgilandi_KapiAcildi": 
        arduino_cmd = "KapiyiAc" 
        olay_detay = "YanginAlgilandi_KapiAcildi"
        olay_baslik = "Yangın Alarmı"
        new_state = "acik"
    elif cmd_key == "YuzTanindi_KapiKilitle": 
        arduino_cmd = "KapiyiKilitle" 
        olay_detay = "YuzTanindi_KapiKilitlendi" 
        olay_baslik = "Kapı Kilitleme"
        new_state = "kilitli"
    elif cmd_key == "SistemBaslangici_KapiAc":
        arduino_cmd = "KapiyiAc"
        olay_detay = "SistemBaslangici_KapiAcildi"
        olay_baslik = "Sistem Başlangıcı"
        new_state = "acik"
    elif cmd_key == "YanginBitti_KapiKilitle": 
        arduino_cmd = "KapiyiKilitle"
        olay_detay = "YanginBitti_KapiKilitlendi"
        olay_baslik = "Yangın Durumu Sonlandı"
        new_state = "kilitli"
    else:
        print(f"[ERROR] send_command fonksiyonuna geçersiz cmd_key geldi: {cmd_key}")
        return
    
    if is_manual_command or (new_state != current_door_state or arduino_cmd != last_door_command_sent):
        arduino.write((arduino_cmd + "\n").encode())
        last_door_action_time = current_time
        current_door_state = new_state
        last_door_command_sent = arduino_cmd

        if olay_detay: 
            try:
                kilit_ref.push({
                    'zaman': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'detay': olay_detay,
                    'olay': olay_baslik,
                    'mevcut_kapi_durumu': current_door_state
                })
                print(f"[DEBUG main.py] Firebase kilit durumu güncellendi: Detay='{olay_detay}', Mevcut Durum='{current_door_state}'")
                firebase_mesaj_gonder(olay_baslik, f"Kapı durumu: {olay_detay.replace('_', ' ').replace('Acildi', 'açıldı').replace('Kilitlendi', 'kilitlendi')}")
            except Exception as e:
                print(f"Firebase kilit durumu güncelleme hatası: {e}")
                status_label.config(text=f"Firebase kilit durumu hatası: {e}")

        status_label.config(text=f"Komut gönderildi: {arduino_cmd}")
        print(f"[DEBUG main.py] Arduino komutu: {arduino_cmd} (Firebase detayı: {olay_detay}) - Yeni Durum: {new_state}")
    else:
        print(f"[DEBUG main.py] Komut gönderilmedi (durum aynı veya zaten gönderilmiş): {cmd_key}. Hedef durum ({new_state}) mevcut durumla ({current_door_state}) aynı veya aynı komut zaten gönderildi. (Otomatik komut için)")


#Başlangıç
send_command("SistemBaslangici_KapiAc") 

# yüz ekle
def load_known_faces():
    encodings = []
    names = []
    if not os.path.exists(KNOWN_FACES_DIR):
        os.makedirs(KNOWN_FACES_DIR) 
    for file in os.listdir(KNOWN_FACES_DIR):
        if file.endswith(('.jpg', '.png')):
            img_path = os.path.join(KNOWN_FACES_DIR, file)
            try:
                img = face_recognition.load_image_file(img_path)
                enc = face_recognition.face_encodings(img)
                if enc:
                    encodings.append(enc[0])
                    names.append("Hasta") 
                    print(f"Yüklenen yüz: {file} -> Hasta")
                else:
                    print(f"Uyarı: {file} dosyasında yüz bulunamadı.")
            except Exception as e:
                print(f"Hata: {file} yüklenirken sorun oluştu: {e}")
    print(f"Toplam {len(encodings)} yüz başarıyla yüklendi.")
    return encodings, names

known_faces, known_names = load_known_faces()

# Manuel
cmd_frame = tk.Frame(window, bg="#222")
cmd_frame.pack(pady=5)

command_entry = tk.Entry(cmd_frame, font=("Arial", 12), width=15)
command_entry.grid(row=0, column=0, padx=5)

def handle_manual_command(event=None):
    cmd_text = command_entry.get().strip().lower()
    if cmd_text in ("aç", "ac", "open"):
        send_command("KapiyiAc")
    elif cmd_text in ("kapat", "close"):
        send_command("KapiyiKilitle")
    else:
        messagebox.showwarning("Geçersiz Komut", "Lütfen 'aç' veya 'kapat' yazın.")
    command_entry.delete(0, tk.END)

command_entry.bind("<Return>", handle_manual_command)

tk.Button(cmd_frame, text="🔒 Kilitle", bg="#f44336", fg="white", font=("Arial", 12),
          command=lambda: send_command("KapiyiKilitle")).grid(row=0, column=1, padx=5)

tk.Button(cmd_frame, text="🔓 Aç", bg="#4CAF50", fg="white", font=("Arial", 12),
          command=lambda: send_command("KapiyiAc")).grid(row=0, column=2, padx=5)

# Yüz kayıt
def save_face():
    """Kameradan alınan yüzü kaydeder."""
    ret, frame = video.read()
    if not ret:
        status_label.config(text="Kamera görüntüsü alınamadı.")
        return
    
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(100, 100)) 

    if len(faces) == 0:
        messagebox.showwarning("Uyarı", "Kamerada yüz algılanamadı. Lütfen yüzünüzü net bir şekilde gösterin.")
        return
    
    x, y, w, h = faces[0] 
    padding = 20 
    y_start = max(0, y - padding)
    y_end = min(frame.shape[0], y + h + padding)
    x_start = max(0, x - padding)
    x_end = min(frame.shape[1], x + w + padding)

    roi = frame[y_start:y_end, x_start:x_end]

    if roi.size == 0: 
        messagebox.showwarning("Hata", "Yüz görüntüsü kesilirken sorun oluştu.")
        return

    path = os.path.join(KNOWN_FACES_DIR, f"face_{int(time.time())}.jpg")
    cv2.imwrite(path, roi)
    
    new_img = face_recognition.load_image_file(path)
    new_enc = face_recognition.face_encodings(new_img)
    if new_enc:
        known_faces.append(new_enc[0])
        known_names.append("Hasta") 
        status_label.config(text=f"Yüz başarıyla kaydedildi: {path}")
        print(f"Yeni yüz kaydedildi: {path}")
    else:
        messagebox.showwarning("Hata", "Kaydedilen resimde yüz kodu oluşturulamadı.")
        os.remove(path) 
    
tk.Button(window, text="👤 Yüz Kaydet", command=save_face, bg="#2196F3", fg="white", font=("Arial", 14)).pack(pady=10)

#kamera
video = cv2.VideoCapture(0) 
if not video.isOpened():
    status_label.config(text="Kamera açılamadı. Lütfen bağlı olduğundan emin olun.")
    print("Kamera açılamadı.")

# Görüntü güncelle
def update_frame():
    global recognized_person_present, son_duygu, son_duygu_gonderimi, fire_alert_sent, current_door_state, last_manual_open_time
    
    ret, frame = video.read()
    if not ret:
        status_label.config(text="Kamera hatası veya bağlantı kesildi.")
        window.after(1000, update_frame) 
        return

    small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
    rgb_small = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

    locations = face_recognition.face_locations(rgb_small, model=MODEL)
    encodings = face_recognition.face_encodings(rgb_small, locations)

    current_person_recognized_in_frame = False 
    
    current_time = time.time() 

    if locations: 
        for enc, loc in zip(encodings, locations):
            matches = face_recognition.compare_faces(known_faces, enc, TOLERANCE)
            name = "YABANCI"
            
            if True in matches:
                name = "TANINDI"
                current_person_recognized_in_frame = True
                
                
                if (current_time - last_manual_open_time) > manual_open_override_duration: 
                    if not recognized_person_present: 
                        recognized_person_present = True 
                        send_telegram_message("Tanınan bir kişi kapı önünde algılandı. Kapı kilitleniyor.")
                        send_command("YuzTanindi_KapiKilitle") 
                        print("[DEBUG main.py] Tanınan yüz algılandı ve kapı kilitlenme komutu gönderildi.")
                else:
                    print(f"[DEBUG main.py] Manuel açma override süresi içinde. Otomatik kilitleme engellendi. Kalan süre: {round(manual_open_override_duration - (current_time - last_manual_open_time), 1)}s")

                # Duygu
                if current_time - son_duygu_gonderimi > duygu_bekleme:
                    try:
                        top, right, bottom, left = [v * 4 for v in loc]
                        face_roi = frame[top:bottom, left:right]
                        if face_roi.size > 0: 
                            result = DeepFace.analyze(face_roi, actions=['emotion'], enforce_detection=False)[0]
                            emotion = result.get("dominant_emotion", None)
                            
                            if emotion:
                                emotion_tr = duygu_cevir.get(emotion, emotion)
                                confidence = result.get("emotion", {}).get(emotion, 0) 
                                timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                                if confidence >= 70 and emotion_tr != son_duygu:
                                    firebase_duygu_gonder("hasta_001", emotion_tr, timestamp_str)
                                    son_duygu = emotion_tr
                                    son_duygu_gonderimi = current_time
                                    print(f"Duygu gönderildi: {emotion_tr} - Güven: %{round(confidence)}")
                                else:
                                    pass 
                            else:
                                pass 
                        else:
                            pass 
                    except Exception as e:
                        print("Duygu analizi hatası:", e)

            top, right, bottom, left = [v * 4 for v in loc] 
            color = (0, 255, 0) if name == "TANINDI" else (0, 0, 255)
            cv2.rectangle(frame, (left, top), (right, bottom), color, FRAME_THICKNESS)
            cv2.putText(frame, name, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, FONT_THICKNESS)
        
    else:
        if recognized_person_present: 
            recognized_person_present = False 
            
    img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    imgtk = ImageTk.PhotoImage(Image.fromarray(img))
    video_label.imgtk = imgtk
    video_label.configure(image=imgtk)
    
    window.after(30, update_frame)

# Firebase komut dinle
def firebase_komut_dinle():
    """Firebase'den gelen manuel kilit komutlarını dinler."""
    ref = db.reference("/komutlar/manuelKomut")
    son_firebase_manuel_komut = "" 

    def listener(event):
        nonlocal son_firebase_manuel_komut
        komut = event.data
        if komut and komut != son_firebase_manuel_komut: 
            print(f"Firebase'den manuel komut alındı: {komut}")
            if komut == "ac":
                send_command("KapiyiAc")
            elif komut == "kapat":
                send_command("KapiyiKilitle")
            son_firebase_manuel_komut = komut 
            ref.set(None) 
    
    threading.Thread(target=lambda: ref.listen(listener), daemon=True).start()

# arduino okuma
def serial_read_loop():
    global fire_alert_sent
    while True:
        if arduino_connected and arduino.in_waiting > 0:
            line = arduino.readline().decode(errors='ignore').strip()
            if line:
                print(f"Arduino: '{line}'")
                if "ALEV ALGILANDI" in line:
                    if not fire_alert_sent:
                        send_telegram_message("Yangın algılandı! Kapı otomatik açıldı!")
                        send_command("YanginAlgilandi_KapiAcildi") 
                        fire_alert_sent = True
                        status_label.config(text="Yangın algılandı, kilit açıldı.")
                elif "ALEV BİTTİ" in line or "SONLANDI" in line:
                    if fire_alert_sent: 
                        send_telegram_message("Yangın durumu sonlandı, kilit kapatıldı.")
                        send_command("YanginBitti_KapiKilitle") 
                        fire_alert_sent = False
                        status_label.config(text="Yangın durumu bitti, kilit kapatıldı.")
        time.sleep(0.1)

# başla
window.bind("<k>", lambda e: save_face())
firebase_komut_dinle() 

if arduino_connected:
    threading.Thread(target=serial_read_loop, daemon=True).start() 

update_frame()
window.mainloop()

if video.isOpened():
    video.release()
if arduino_connected:
    arduino.close()
cv2.destroyAllWindows()