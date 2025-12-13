import streamlit as st
from openai import OpenAI
from PIL import Image
import json
import time
import base64
from io import BytesIO

# ==========================================
# 1. SAYFA AYARLARI
# ==========================================
st.set_page_config(page_title="AI Toplu Sınav Okuma", layout="wide")

st.markdown("""
<style>
h1 { font-size: 2.4rem !important; font-weight: 800 !important; color: #1E3A8A; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. OPENAI API
# ==========================================
if "OPENAI_API_KEY" not in st.secrets:
    st.error("❌ OPENAI_API_KEY Stream secret içine eklenmemiş")
    st.stop()

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# ==========================================
# 3. HAFIZA
# ==========================================
if "sinif_verileri" not in st.session_state:
    st.session_state.sinif_verileri = []

def hafiza_temizle():
    st.session_state.sinif_verileri = []
    st.toast("🧹 Liste temizlendi")
    st.rerun()

# ==========================================
# 4. YARDIMCI FONKSİYONLAR
# ==========================================
def image_to_base64(img):
    buf = BytesIO()
    img.convert("RGB").save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode()

def extract_json(text):
    start = text.find("{")
    end = text.rfind("}") + 1
    return text[start:end]

# ==========================================
# 5. ARAYÜZ
# ==========================================
with st.sidebar:
    st.header("⚙️ Sınıf Durumu")
    st.info(f"📂 Okunan Öğrenci: {len(st.session_state.sinif_verileri)}")
    if st.session_state.sinif_verileri:
        st.button("🚨 Listeyi Sıfırla", on_click=hafiza_temizle)

st.title("🚀 AI Toplu Sınav Okuma")
st.markdown("---")

col1, col2 = st.columns(2)

with col1:
    st.header("1. Sınav Ayarları")
    ogretmen_notu = st.text_area("Öğretmen Notu / Ek Kriterler")

    sayfa_tipi = st.radio(
        "Her Öğrenci Kaç Sayfa?",
        ["Tek Sayfa", "Çift Sayfa"],
        horizontal=True
    )

    with st.expander("📌 Cevap Anahtarı / Rubrik (Opsiyonel)"):
        rubrik_dosyasi = st.file_uploader(
            "Cevap Anahtarı Görseli Yükle",
            type=["jpg", "png", "jpeg"]
        )
        rubrik_img = Image.open(rubrik_dosyasi) if rubrik_dosyasi else None

with col2:
    st.header("2. Toplu Yükleme")
    uploaded_files = st.file_uploader(
        "Öğrenci Sınav Kağıtları",
        type=["jpg", "png", "jpeg"],
        accept_multiple_files=True
    )

# ==========================================
# 6. OKUMA & PUANLAMA
# ==========================================
st.markdown("---")

if st.button("🚀 KAĞITLARI OKU VE PUANLA", use_container_width=True):

    if not uploaded_files:
        st.warning("Dosya yüklenmedi")
        st.stop()

    adim = 2 if sayfa_tipi == "Çift Sayfa" else 1
    files = sorted(uploaded_files, key=lambda x: x.name)

    paketler = [
        files[i:i+adim]
        for i in range(0, len(files), adim)
        if len(files[i:i+adim]) == adim
    ]

    progress = st.progress(0)
    durum = st.empty()

    for i, paket in enumerate(paketler):
        durum.write(f"📄 {i+1}/{len(paketler)} okunuyor...")

        content = [
            {
                "type": "text",
                "text": f"""
Bu bir sınav değerlendirme görevdir.

Kurallar:
- Cevap anahtarı varsa mutlaka onu esas al
- Yoksa öğretmen notuna göre değerlendir
- SADECE JSON üret

JSON formatı:
{{
 "kimlik": {{ "ad_soyad": "", "numara": "" }},
 "degerlendirme": [
   {{ "no": "1", "puan": 0, "tam_puan": 10, "yorum": "" }}
 ]
}}

Öğretmen Notu:
{ogretmen_notu}
"""
            }
        ]

        if rubrik_img:
            content.append({
                "type": "text",
                "text": "CEVAP ANAHTARI:"
            })
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_to_base64(rubrik_img)}"
                }
            })

        content.append({
            "type": "text",
            "text": "ÖĞRENCİ KAĞIDI:"
        })

        for f in paket:
            img = Image.open(f)
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_to_base64(img)}"
                }
            })

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": content}],
                max_tokens=900
            )

            data = json.loads(extract_json(response.choices[0].message.content))

            kimlik = data.get("kimlik", {})
            sorular = data.get("degerlendirme", [])

            toplam = sum(float(s.get("puan", 0)) for s in sorular)

            kayit = {
                "Ad Soyad": kimlik.get("ad_soyad", f"Öğrenci {i+1}"),
                "Numara": kimlik.get("numara", "-"),
                "Toplam Puan": toplam
            }

            for s in sorular:
                kayit[f"Soru {s.get('no')}"] = s.get("puan", 0)

            st.session_state.sinif_verileri.append(kayit)

        except Exception as e:
            st.error(f"❌ {i+1}. öğrenci okunamadı: {e}")

        progress.progress((i+1)/len(paketler))
        time.sleep(0.4)

    st.success("✅ Tüm kağıtlar rubrikle birlikte okundu")
    st.balloons()
