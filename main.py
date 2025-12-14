import streamlit as st
from openai import OpenAI
from PIL import Image
import json
import time
import pandas as pd
import io
import base64

# ==========================================
# 1. AYARLAR & TASARIM
# ==========================================
st.set_page_config(page_title="OkutAİ - Akıllı Sınav Okuma", layout="wide", page_icon="📑")

st.markdown("""
    <style>
    /* --- GÖRSEL EŞİTLEME & TASARIM --- */
    .stTextArea label, .stRadio label, .stFileUploader label p {
        font-size: 16px !important;
        font-weight: 600 !important;
        color: #31333F !important;
    }
    .stTabs button {
        font-size: 16px !important;
        font-weight: 600 !important;
        color: #31333F !important;
    }
    [data-testid="stFileUploaderDropzone"] button {
        font-size: 16px !important;
        font-weight: 600 !important;
        color: #31333F !important;
    }
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
    }
    header[data-testid="stHeader"] {
        background-color: transparent;
    }
    [data-testid="stSidebarUserContent"] {
        padding-top: 2rem !important;
    }
    [data-testid="stSidebarNav"] a {
        background-color: #f0f2f6; padding: 15px; border-radius: 10px;
        margin-bottom: 10px; text-decoration: none !important;
        color: #002D62 !important; font-weight: 700; display: block;
        text-align: center; border: 1px solid #dcdcdc; transition: all 0.3s;
    }
    [data-testid="stSidebarNav"] a:hover {
        background-color: #e6e9ef; transform: scale(1.02);
        box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-color: #b0b0b0;
    }
    div[data-testid="stCameraInput"] button { color: transparent !important; }
    div[data-testid="stCameraInput"] button::after {
        content: "📸 TARAT"; color: #333; font-weight: bold; position: absolute; left:0; right:0; top:0; bottom:0; display: flex; align-items: center; justify-content: center;
    }
    .streamlit-expanderHeader {
        font-weight: bold; background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; margin-bottom: 5px;
    }
    </style>
""", unsafe_allow_html=True)

# API Anahtarı Kontrolü
if "OPENAI_API_KEY" in st.secrets:
    api_key = st.secrets["OPENAI_API_KEY"]
else:
    api_key = ""

# --- HAFIZA ---
if 'sinif_verileri' not in st.session_state: st.session_state.sinif_verileri = []
if 'kamera_acik' not in st.session_state: st.session_state.kamera_acik = False

def tam_hafiza_temizligi():
    st.session_state.sinif_verileri = []
    st.toast("🧹 Liste temizlendi!", icon="🗑️")
    st.rerun()

def kamera_durumunu_degistir():
    st.session_state.kamera_acik = not st.session_state.kamera_acik

# --- GÖRSEL İŞLEME (HATA DÜZELTİLDİ) ---
def pil_to_base64_url(img):
    # RGBA (Saydamlık) varsa RGB'ye çevir ki JPEG hatası vermesin
    if img.mode == 'RGBA':
        img = img.convert('RGB')
        
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/jpeg;base64,{img_str}"

def get_img_as_base64(file):
    try:
        with open(file, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except:
        return ""

# ==========================================
# 2. ARAYÜZ (HEADER)
# ==========================================

with st.sidebar:
    st.header("⚙️ Durum")
    st.info(f"📂 Okunan: **{len(st.session_state.sinif_verileri)}**")
    if len(st.session_state.sinif_verileri) > 0:
        if st.button("🚨 Listeyi Sıfırla", type="primary", use_container_width=True):
            tam_hafiza_temizligi()
    st.divider()
    st.caption("OkutAİ v1.1 (OpenAI Edition)")

# --- ANA SAYFA LOGO ---
try:
    img_base64 = get_img_as_base64("okutai_logo.png") 
    if img_base64:
        st.markdown(
            f"""
            <div style="display: flex; flex-direction: column; align-items: center; justify-content: center;">
                <img src="data:image/png;base64,{img_base64}" width="400" style="margin-bottom: 5px;">
                <h3 style='color: #002D62; margin: 0; font-size: 1.5rem; font-weight: 800;'>Sınav okumanın Akıllı Yolu</h3>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        raise Exception("Logo yok")
except:
    st.markdown("""
        <h1 style='text-align: center; color: #002D62;'>Okut<span style='color: #00aaff;'>Aİ</span></h1>
        <h3 style='text-align: center;'>Sen Okut, O Puanlasın.</h3>
        """, unsafe_allow_html=True)

st.markdown("---")

# ==========================================
# 3. İŞLEM ALANI
# ==========================================
col_sol, col_sag = st.columns([1, 1], gap="large")

with col_sol:
    st.header("1. Sınav Ayarları")
    ogretmen_promptu = st.text_area("Öğretmen Notu / Puanlama Kriteri:", height=100, placeholder="Ör: Yazım hataları -1 puan, anlam bütünlüğü önemli...")
    sayfa_tipi = st.radio("Her Öğrenci Kaç Sayfa?", ["Tek Sayfa (Sadece Ön)", "Çift Sayfa (Ön + Arka)"], horizontal=True)
    
    with st.expander("Cevap Anahtarı (Opsiyonel)"):
        rubrik_dosyasi = st.file_uploader("Cevap Anahtarı Yükle", type=["jpg", "png", "jpeg"], key="rubrik")
        rubrik_img = Image.open(rubrik_dosyasi) if rubrik_dosyasi else None

with col_sag:
    st.header("2. Kağıt Yükleme")
    
    tab_dosya, tab_kamera = st.tabs(["📂 Dosya Yükle", "📸 Kamera"])
    
    uploaded_files = []
    camera_file = None
    
    with tab_dosya:
        st.info("Galeriden çoklu seçim yapabilirsiniz.")
        uploaded_files_list = st.file_uploader("Okutulacak Kağıtları Seç", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
        if uploaded_files_list: uploaded_files = uploaded_files_list
            
    with tab_kamera:
        if st.session_state.kamera_acik:
            if st.button("❌ Kamerayı Kapat", type="secondary", use_container_width=True):
                kamera_durumunu_degistir()
                st.rerun()
            camera_input = st.camera_input("Fotoğrafı Çek")
            if camera_input: camera_file = camera_input
        else:
            if st.button("📸 Kamerayı Başlat", type="primary", use_container_width=True):
                kamera_durumunu_degistir()
                st.rerun()

# ==========================================
# 4. İŞLEM BUTONU VE MOTORU
# ==========================================
st.markdown("---")

if st.button("🚀 KAĞITLARI OKUT VE PUANLA", type="primary", use_container_width=True):
    
    tum_gorseller = []
    if uploaded_files: tum_gorseller.extend(uploaded_files)
    if camera_file: tum_gorseller.append(camera_file)
    
    if not api_key:
        st.error("Lütfen secrets.toml dosyasına 'OPENAI_API_KEY' ekleyin!")
    elif not tum_gorseller:
        st.warning("Lütfen dosya yükleyin veya fotoğraf çekin.")
    else:
        # OpenAI İstemcisi
        client = OpenAI(api_key=api_key)

        is_paketleri = []
        adim = 2 if "Çift" in sayfa_tipi and len(tum_gorseller) > 1 else 1
        sorted_files = sorted(tum_gorseller, key=lambda x: x.name if hasattr(x, 'name') else "camera")

        for i in range(0, len(sorted_files), adim):
            paket = sorted_files[i : i + adim]
            if len(paket) > 0:
                img_paket = [Image.open(f) for f in paket]
                is_paketleri.append(img_paket)

        progress_bar = st.progress(0)
        durum_text = st.empty()
        toplam_paket = len(is_paketleri)
        basarili = 0

        for index, images in enumerate(is_paketleri):
            durum_text.write(f"⏳ Taranıyor (GPT-4o): {index + 1}. Öğrenci / {toplam_paket}...")
            
            try:
                # --- GÜÇLENDİRİLMİŞ PROMPT (DAHA DETAYLI SONUÇ İÇİN) ---
                system_instruction = """
                Sen dünyanın en titiz, en detaycı ve adil öğretmenisin. 
                Görevin öğrenci kağıtlarını incelemek ve ASLA "özet" geçmeden, her detayı analiz ederek notlandırmak.
                Çıktıyı SADECE geçerli bir JSON formatında ver. Başka hiçbir metin yazma.
                """

                user_prompt_text = f"""
                GÖREV: Bu bir sınav kağıdıdır. Öğrenciyi değerlendir.
                
                DİKKAT EDİLECEK KURALLAR (KESİN UYGULA):
                1. İNCELEME: Öğrencinin yazdığı her kelimeyi dikkatle oku. El yazısı kötüyse bile bağlamdan çıkarmaya çalış.
                2. YORUMLAMA: "Doğru", "Yanlış" deyip geçme. Neden puan kırdığını veya neden tam puan verdiğini 'yorum' kısmında detaylıca açıkla. Öğrenciye geri bildirim veriyormuş gibi yaz.
                3. OBJEKTİFLİK: Cevap anahtarı varsa ona sadık kal, yoksa akademik doğruluğa göre puanla.
                
                PUANLAMA ALGORİTMASI:
                1. Kağıt üzerinde soru puanı yazıyorsa onu kullan.
                2. Cevap anahtarı görseli varsa oradaki puanı kullan.
                3. Hiçbiri yoksa puanları soru sayısına eşit bölüştür.
                
                EKSTRA ÖĞRETMEN NOTU: {ogretmen_promptu if ogretmen_promptu else 'Yok'}
                
                İSTENEN JSON FORMATI:
                {{ "kimlik": {{"ad_soyad": "...", "numara": "..."}}, "degerlendirme": [{{"no":"1", "soru":"...", "cevap":"...", "puan":0, "tam_puan":20, "yorum":"..."}}] }}
                """

                content_list = [{"type": "text", "text": user_prompt_text}]

                # Rubrik Ekleme
                if rubrik_img:
                    content_list.append({"type": "text", "text": "REFERANS ALINACAK CEVAP ANAHTARI (RUBRİK):"})
                    content_list.append({
                        "type": "image_url",
                        "image_url": {"url": pil_to_base64_url(rubrik_img)}
                    })

                # Öğrenci Kağıdı Ekleme
                content_list.append({"type": "text", "text": "DEĞERLENDİRİLECEK ÖĞRENCİ KAĞIDI:"})
                for img in images:
                    content_list.append({
                        "type": "image_url",
                        "image_url": {"url": pil_to_base64_url(img)}
                    })

                # --- GPT ÇAĞRISI ---
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": content_list}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.3, # Daha tutarlı ve az "halüsinasyonlu" olması için düşürdük
                    max_tokens=4000
                )

                json_text = response.choices[0].message.content
                data = json.loads(json_text)
                
                kimlik = data.get("kimlik", {})
                sorular = data.get("degerlendirme", [])
                toplam_puan = sum([float(x.get('puan', 0)) for x in sorular])
                
                kayit = {
                    "Ad Soyad": kimlik.get("ad_soyad", f"Öğrenci {index+1}"), 
                    "Numara": kimlik.get("numara", "-"), 
                    "Toplam Puan": toplam_puan,
                    "Detaylar": sorular
                }
                
                for s in sorular: 
                    kayit[f"Soru {s.get('no')}"] = s.get('puan', 0)

                st.session_state.sinif_verileri.append(kayit)
                basarili += 1

            except Exception as e:
                st.error(f"⚠️ Hata oluştu (Öğrenci {index+1}): {e}")
            
            progress_bar.progress((index + 1) / toplam_paket)
            time.sleep(0.5)

        durum_text.success(f"✅ Tamamlandı! {basarili} kağıt başarıyla okundu.")
        st.balloons()
        time.sleep(1)
        st.rerun()

# ==========================================
# 5. SONUÇ LİSTESİ
# ==========================================
if len(st.session_state.sinif_verileri) > 0:
    st.markdown("### 📝 Sınıf Sonuçları")
    
    for i, ogrenci in enumerate(st.session_state.sinif_verileri):
        baslik = f"📄 {ogrenci['Ad Soyad']} (No: {ogrenci['Numara']}) | Puan: {int(ogrenci['Toplam Puan'])}"
        
        with st.expander(baslik, expanded=False):
            if "Detaylar" in ogrenci:
                for soru in ogrenci["Detaylar"]:
                    puan = soru.get('puan', 0)
                    tam_puan = soru.get('tam_puan', 0)
                    
                    if puan == tam_puan:
                        renk = "green"; ikon = "✅"
                    elif puan == 0:
                        renk = "red"; ikon = "❌"
                    else:
                        renk = "orange"; ikon = "⚠️"
                    
                    st.markdown(f"**Soru {soru.get('no')}** - {ikon} :{renk}[**{puan}** / {tam_puan}]")
                    st.info(f"**Öğrenci Cevabı:** {soru.get('cevap')}")
                    
                    st.markdown(f"""
                    <div style="background-color: #f0f8ff; padding: 10px; border-radius: 5px; border-left: 5px solid #002D62; margin-bottom: 5px;">
                        <span style="font-weight:bold; color:#002D62;">🤖 OkutAİ Yorumu:</span><br>
                        <span style="font-size: 16px; color: #222;">{soru.get('yorum')}</span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.divider() 

    # Excel İndirme
    st.markdown("---")
    df_excel = pd.DataFrame(st.session_state.sinif_verileri)
    if "Detaylar" in df_excel.columns: df_excel = df_excel.drop(columns=["Detaylar"])
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_excel.to_excel(writer, index=False, sheet_name='Sonuclar')
        
    st.download_button("📥 Excel Olarak İndir", data=output.getvalue(), file_name='OkutAI_Sonuclari.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', type="primary", use_container_width=True)

# Footer
st.markdown("---")
st.markdown("""
    <div style='text-align: center; margin-top: 50px; margin-bottom: 20px; color: #666;'>
        <p style='font-size: 18px; font-weight: 600;'>
            © 2024 OkutAİ - Sinan Sayılır tarafından geliştirilmiştir.
        </p>
        <p style='font-size: 14px;'>Sınav okumanın Akıllı Yolu</p>
    </div>
""", unsafe_allow_html=True)
