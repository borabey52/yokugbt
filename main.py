import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
import time

# =====================================================
# 1. SAYFA AYARLARI & TASARIM
# =====================================================
st.set_page_config(page_title="AI Toplu Sınav Okuma", layout="wide")

st.markdown("""
<style>
h1 {font-size:2.4rem !important; font-weight:800; color:#1E3A8A;}
</style>
""", unsafe_allow_html=True)

# =====================================================
# 2. API KEY
# =====================================================
if "GOOGLE_API_KEY" in st.secrets:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
else:
    API_KEY = ""

# =====================================================
# 3. HAFIZA
# =====================================================
if "sinif_verileri" not in st.session_state:
    st.session_state.sinif_verileri = []

def hafiza_temizle():
    st.session_state.sinif_verileri = []
    st.success("Sınıf listesi temizlendi")
    st.rerun()

# =====================================================
# 4. YARDIMCI FONKSİYON
# =====================================================
def temiz_json(text):
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    return text.strip()

# =====================================================
# 5. ARAYÜZ
# =====================================================
with st.sidebar:
    st.header("📊 Sınıf Durumu")
    st.info(f"Okunan öğrenci: {len(st.session_state.sinif_verileri)}")
    if st.session_state.sinif_verileri:
        if st.button("🗑️ Listeyi Sıfırla"):
            hafiza_temizle()
    st.caption("© Sinan Sayılır")

st.title("🚀 AI Toplu Sınav Okuma ve Değerlendirme")
st.divider()

col1, col2 = st.columns(2)

with col1:
    st.subheader("1️⃣ Değerlendirme Ayarları")
    ogretmen_notu = st.text_area(
        "Öğretmen Notu / Puanlama Kriteri",
        placeholder="Her soru 10 puan. Kavram doğruysa yarım puan verilebilir.",
        height=120
    )

    sayfa_tipi = st.radio(
        "Öğrenci Kaç Sayfa?",
        ["Tek Sayfa", "Çift Sayfa (Ön + Arka)"],
        horizontal=True
    )

    with st.expander("📌 Cevap Anahtarı / Rubrik (Opsiyonel)"):
        rubrik_dosya = st.file_uploader(
            "Cevap anahtarı yükle",
            type=["jpg", "png", "jpeg"]
        )
        rubrik_img = Image.open(rubrik_dosya) if rubrik_dosya else None

with col2:
    st.subheader("2️⃣ Sınav Kağıtları")
    uploaded_files = st.file_uploader(
        "Tüm sınıfın kağıtlarını seç",
        type=["jpg", "png", "jpeg"],
        accept_multiple_files=True
    )
    if uploaded_files:
        st.success(f"{len(uploaded_files)} dosya yüklendi")

# =====================================================
# 6. İŞLEM
# =====================================================
st.divider()

if st.button("🚀 KAĞITLARI OKU VE PUANLA", use_container_width=True):
    if not API_KEY:
        st.error("API Key eksik")
        st.stop()

    if not uploaded_files:
        st.warning("Kağıt yüklenmedi")
        st.stop()

    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")

    adim = 2 if "Çift" in sayfa_tipi else 1
    dosyalar = sorted(uploaded_files, key=lambda x: x.name)

    paketler = []
    for i in range(0, len(dosyalar), adim):
        if len(dosyalar[i:i+adim]) == adim:
            paketler.append([Image.open(f) for f in dosyalar[i:i+adim]])

    progress = st.progress(0)
    durum = st.empty()

    for i, img_paket in enumerate(paketler):
        durum.write(f"📄 {i+1}. öğrenci okunuyor...")

        try:
            prompt = f"""
Bu bir öğrencinin sınav kağıdıdır.

DEĞERLENDİRME ZORUNLU ADIMLARI:
1. Soruyu oku ve anla.
2. O soru için DOĞRU CEVABI SEN ÜRET.
3. Öğrencinin cevabını oku.
4. Doğru cevap ile karşılaştır.
5. Akademik doğruluğa göre puan ver.

PUANLAMA KRİTERİ:
{ogretmen_notu if ogretmen_notu else "Her soru tam puan üzerinden değerlendirilecektir."}

ÇIKTIYI SADECE JSON OLARAK VER:

{{
  "kimlik": {{
    "ad_soyad": "",
    "numara": ""
  }},
  "sorular": [
    {{
      "no": 1,
      "soru": "",
      "ogrenci_cevabi": "",
      "dogru_cevap": "",
      "puan": 0,
      "tam_puan": 10,
      "gerekce": ""
    }}
  ]
}}
"""

            content = [prompt]

            if rubrik_img:
                content.append("CEVAP ANAHTARI:")
                content.append(rubrik_img)

            content.append("SINAV KAĞIDI:")
            content.extend(img_paket)

            response = model.generate_content(content)
            json_text = temiz_json(response.text)
            veri = json.loads(json_text)

            kimlik = veri.get("kimlik", {})
            sorular = veri.get("sorular", [])

            toplam = sum(float(s["puan"]) for s in sorular)

            kayit = {
                "Ad Soyad": kimlik.get("ad_soyad", f"Öğrenci {i+1}"),
                "Numara": kimlik.get("numara", "-"),
                "Toplam Puan": toplam
            }

            for s in sorular:
                kayit[f"Soru {s['no']}"] = s["puan"]

            st.session_state.sinif_verileri.append(kayit)

        except Exception as e:
            st.error(f"{i+1}. öğrenci okunamadı → {e}")

        progress.progress((i+1) / len(paketler))
        time.sleep(0.5)

    st.success("✅ Tüm kağıtlar işlendi")
    st.balloons()

# =====================================================
# 7. SONUÇ TABLOSU
# =====================================================
if st.session_state.sinif_verileri:
    st.divider()
    st.subheader("📊 Sınıf Puan Çizelgesi")
    st.dataframe(st.session_state.sinif_verileri, use_container_width=True)
