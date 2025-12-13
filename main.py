import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
import time

# ==========================================
# 1. AYARLAR & TASARIM (CSS DÜZELTİLDİ)
# ==========================================
st.set_page_config(page_title="AI Toplu Sınav Okuma", layout="wide")

st.markdown("""
    <style>
    /* SOL MENÜ TASARIMI */
    [data-testid="stSidebarNav"] a {
        background-color: #f0f2f6; padding: 15px; border-radius: 10px;
        margin-bottom: 10px; text-decoration: none !important;
        color: #31333F !important; font-weight: 700; display: block;
        text-align: center; border: 1px solid #dcdcdc; transition: all 0.3s;
    }
    [data-testid="stSidebarNav"] a:hover {
        background-color: #e6e9ef; transform: scale(1.02);
        box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-color: #b0b0b0;
    }
    h1 { font-size: 2.5rem !important; font-weight: 800 !important; color: #1E3A8A; }
    
    /* --- KAMERA BUTONU DÜZELTMESİ (SADECE KAMERAYI ETKİLER) --- */
    /* Diğer butonları bozmasın diye 'data-testid="stCameraInput"' içine kilitledik */
    
    div[data-testid="stCameraInput"] button[kind="primary"] { 
        color: transparent !important; 
    }
    div[data-testid="stCameraInput"] button[kind="primary"]::after {
        content: "📸 FOTOĞRAFI ÇEK"; 
        color: white; 
        font-weight: bold;
        position: absolute; left: 0; right: 0; top: 0; bottom: 0;
        display: flex; align-items: center; justify-content: center;
    }
    
    div[data-testid="stCameraInput"] button[kind="secondary"] { 
        color: transparent !important; 
    }
    div[data-testid="stCameraInput"] button[kind="secondary"]::after {
        content: "🔄 Yeniden Çek"; 
        color: #31333F; 
        font-weight: bold;
        position: absolute; left: 0; right: 0; top: 0; bottom: 0;
        display: flex; align-items: center; justify-content: center;
    }
    </style>
""", unsafe_allow_html=True)

# API Anahtarı
if "GOOGLE_API_KEY" in st.secrets:
    SABIT_API_KEY = st.secrets["GOOGLE_API_KEY"]
else:
    SABIT_API_KEY = ""

# --- HAFIZA ---
if 'sinif_verileri' not in st.session_state: st.session_state.sinif_verileri = []

def tam_hafiza_temizligi():
    st.session_state.sinif_verileri = []
    st.toast("🧹 Sınıf listesi temizlendi!", icon="🗑️")
    st.rerun()

def extract_json(text):
    text = text.strip()
    try:
        if "```json" in text: text = text.split("```json")[1].split("```")[0]
        elif "```" in text: text = text.split("```")[1].split("```")[0]
        start = text.find('{')
        end = text.rfind('}') + 1
        if start != -1 and end != 0: return text[start:end]
        return text
    except:
        return text

# ==========================================
# 2. ARAYÜZ
# ==========================================
with st.sidebar:
    st.header("⚙️ Sınıf Durumu")
    st.info(f"📂 Okunan Öğrenci: **{len(st.session_state.sinif_verileri)}**")
    if len(st.session_state.sinif_verileri) > 0:
        if st.button("🚨 Listeyi Sıfırla", type="primary", use_container_width=True):
            tam_hafiza_temizligi()
    st.divider()
    st.caption("Pro Sürüm v7.0 © SİNAN SAYILIR")

st.title("🚀 AI Toplu Sınav Okuma")
st.markdown("---")

col_sol, col_sag = st.columns([1, 1], gap="large")

with col_sol:
    st.header("1. Sınav Ayarları")
    ogretmen_promptu = st.text_area("Öğretmen Notu / Puanlama Kriteri:", height=100)
    
    sayfa_tipi = st.radio("Her Öğrenci Kaç Sayfa?", ["Tek Sayfa (Sadece Ön)", "Çift Sayfa (Ön + Arka)"], horizontal=True)
    st.info("💡 Çift sayfa seçerseniz; yüklediğiniz dosyaları 2'şerli gruplar (Ön-Arka) halinde okurum.")

    with st.expander("Cevap Anahtarı (Opsiyonel)"):
        rubrik_dosyasi = st.file_uploader("Rubrik", type=["jpg", "png", "jpeg"], key="rubrik")
        rubrik_img = Image.open(rubrik_dosyasi) if rubrik_dosyasi else None

with col_sag:
    st.header("2. Toplu Yükleme")
    st.warning("⚠️ Galeriden tüm sınıfın kağıtlarını tek seferde seçebilirsiniz.")
    
    uploaded_files = st.file_uploader(
        "Tüm Sınıfın Kağıtlarını Seç", 
        type=["jpg", "png", "jpeg"], 
        accept_multiple_files=True 
    )

    if uploaded_files:
        st.success(f"📚 Toplam **{len(uploaded_files)}** dosya seçildi.")

# ==========================================
# 3. İŞLEM MOTORU
# ==========================================
st.markdown("---")

# NOT: Buton yazısı artık görünecek çünkü CSS düzeltildi.
if st.button("🚀 KAĞITLARI OKU VE PUANLA", type="primary", use_container_width=True):
    if not SABIT_API_KEY:
        st.error("API Anahtarı Eksik!")
    elif not uploaded_files:
        st.warning("Hiç dosya seçmediniz.")
    else:
        # --- MODEL SEÇİMİ ---
        # ÖNEMLİ: Eğer hala 404 alıyorsan, API Key'in faturasız projeye aittir.
        genai.configure(api_key=SABIT_API_KEY)
        model = genai.GenerativeModel("gemini-flash-latest") 

        # --- GRUPLAMA MANTIĞI ---
        is_paketleri = []
        adim = 2 if "Çift" in sayfa_tipi else 1
        sorted_files = sorted(uploaded_files, key=lambda x: x.name)

        for i in range(0, len(sorted_files), adim):
            paket = sorted_files[i : i + adim]
            if len(paket) == adim:
                img_paket = [Image.open(f) for f in paket]
                is_paketleri.append(img_paket)

        # --- İŞLEME BAŞLIYOR ---
        progress_bar = st.progress(0)
        durum_text = st.empty()
        
        toplam_paket = len(is_paketleri)
        basarili = 0

        for index, images in enumerate(is_paketleri):
            durum_text.write(f"⏳ Okunuyor: {index + 1}. Öğrenci / {toplam_paket}...")
            
            try:
                prompt = ["""
                Bu bir sınav kağıdıdır.
                1. Ön yüzdeki İsim, Soyad ve Numarayı bul.
                2. Tüm soruları puanla.
                3. Çıktıyı SADECE JSON ver.
                { "kimlik": {"ad_soyad": "...", "numara": "..."}, "degerlendirme": [{"no":"1", "soru":"...", "cevap":"...", "puan":0, "tam_puan":10, "yorum":"..."}] }
                """]
                
                if ogretmen_promptu: prompt.append(f"NOT: {ogretmen_promptu}")
                if rubrik_img: prompt.extend(["CEVAP ANAHTARI:", rubrik_img])
                prompt.append("KAĞITLAR:")
                prompt.extend(images)

                response = model.generate_content(prompt)
                json_text = extract_json(response.text)
                data = json.loads(json_text)
                
                kimlik = data.get("kimlik", {})
                sorular = data.get("degerlendirme", [])
                toplam_puan = sum([float(x.get('puan', 0)) for x in sorular])
                
                kayit = {"Ad Soyad": kimlik.get("ad_soyad", f"Öğrenci {index+1}"), 
                         "Numara": kimlik.get("numara", "-"), 
                         "Toplam Puan": toplam_puan}
                
                for s in sorular: kayit[f"Soru {s.get('no')}"] = s.get('puan', 0)
                
                st.session_state.sinif_verileri.append(kayit)
                basarili += 1

            except Exception as e:
                st.error(f"⚠️ {index+1}. Öğrenci okunamadı. Hata: {e}")
                # Eğer 404 hatası alırsan, model adını listeden bildiğimiz bir modelle değiştirmeyi deneyebilirsin.
                # Ama en doğrusu yeni API Key almaktır.
            
            progress_bar.progress((index + 1) / toplam_paket)
            time.sleep(1) # Ne olur ne olmaz biraz nefes alsın

        durum_text.success(f"✅ İşlem Tamamlandı! {basarili}/{toplam_paket} öğrenci sisteme eklendi.")
        st.balloons()
        st.info("Detaylı sonuçlar için 'Analiz Tablosu'na gidiniz.")
