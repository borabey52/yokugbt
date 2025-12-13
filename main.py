import streamlit as st
from PIL import Image
import pandas as pd
import json
import time
import base64
import io
from openai import OpenAI

# ==========================================
# 1. SAYFA AYARLARI
# ==========================================
st.set_page_config(page_title="AI Toplu Sınav Okuma", layout="wide")
st.title("🚀 AI Toplu Sınav Okuma ve Puanlama Sistemi")
st.markdown("---")

# ==========================================
# 2. API BAĞLANTISI
# ==========================================
if "OPENAI_API_KEY" not in st.secrets:
    st.error("❌ OPENAI_API_KEY bulunamadı (Streamlit secrets)")
    st.stop()

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# ==========================================
# 3. YARDIMCI FONKSİYONLAR
# ==========================================
def image_to_base64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")

def hafizayi_sil():
    st.session_state.sinif_verileri = []
    st.success("🧹 Tüm sınıf verileri silindi")
    st.rerun()

# ==========================================
# 4. SESSION STATE
# ==========================================
if "sinif_verileri" not in st.session_state:
    st.session_state.sinif_verileri = []

# ==========================================
# 5. SOL MENÜ
# ==========================================
with st.sidebar:
    st.header("⚙️ Sınıf Durumu")
    st.info(f"📂 Okunan Öğrenci Sayısı: {len(st.session_state.sinif_verileri)}")

    if st.session_state.sinif_verileri:
        if st.button("🚨 Listeyi Sıfırla"):
            hafizayi_sil()

    st.divider()
    st.caption("© Sinan Sayılır")

# ==========================================
# 6. AYARLAR
# ==========================================
col1, col2 = st.columns(2)

with col1:
    st.subheader("1️⃣ Sınav Ayarları")
    ogretmen_notu = st.text_area(
        "Öğretmen Notu / Puanlama Kriteri",
        placeholder="Her soru 10 puan. Yazım hatası -1 puan vb.",
        height=120
    )

    sayfa_tipi = st.radio(
        "Her öğrenci kaç sayfa?",
        ["Tek Sayfa", "Çift Sayfa (Ön + Arka)"],
        horizontal=True
    )

    with st.expander("📌 Cevap Anahtarı (Opsiyonel)"):
        cevap_anahtari = st.file_uploader(
            "Cevap Anahtarı Yükle",
            type=["jpg", "png", "jpeg"]
        )
        cevap_img = Image.open(cevap_anahtari) if cevap_anahtari else None

with col2:
    st.subheader("2️⃣ Öğrenci Kağıtları")
    uploaded_files = st.file_uploader(
        "Tüm sınıfın kağıtlarını seç",
        type=["jpg", "png", "jpeg"],
        accept_multiple_files=True
    )

    if uploaded_files:
        st.success(f"📄 {len(uploaded_files)} dosya yüklendi")

# ==========================================
# 7. OKUMA & PUANLAMA
# ==========================================
st.markdown("---")

if st.button("🚀 KAĞITLARI OKU VE PUANLA", use_container_width=True):

    if not uploaded_files:
        st.warning("Dosya yüklemediniz.")
        st.stop()

    adim = 2 if "Çift" in sayfa_tipi else 1
    dosyalar = sorted(uploaded_files, key=lambda x: x.name)

    gruplar = [
        dosyalar[i:i + adim]
        for i in range(0, len(dosyalar), adim)
        if len(dosyalar[i:i + adim]) == adim
    ]

    progress = st.progress(0)
    durum = st.empty()

    for i, grup in enumerate(gruplar):
        durum.write(f"⏳ {i+1}. öğrenci okunuyor...")

        images = [Image.open(f) for f in grup]

        prompt = f"""
Bu bir sınav kağıdıdır.

GÖREVLER:
1. Öğrencinin ad-soyad ve numarasını bul.
2. Tüm soruları değerlendir.
3. Her soru için puan ver.
4. Toplam puanı hesapla.

PUANLAMA KRİTERİ:
{ogretmen_notu if ogretmen_notu else "Her soruyu eşit değerlendir."}

ÇIKTIYI SADECE JSON OLARAK VER:

{{
  "kimlik": {{
    "ad_soyad": "",
    "numara": ""
  }},
  "sorular": [
    {{ "no": 1, "puan": 0, "tam_puan": 10 }},
    {{ "no": 2, "puan": 0, "tam_puan": 10 }}
  ]
}}
"""

        try:
            content = [{"type": "input_text", "text": prompt}]

            if cevap_img:
                content.append({
                    "type": "input_image",
                    "image_url": f"data:image/jpeg;base64,{image_to_base64(cevap_img)}"
                })

            for img in images:
                content.append({
                    "type": "input_image",
                    "image_url": f"data:image/jpeg;base64,{image_to_base64(img)}"
                })

            response = client.responses.create(
                model="gpt-4.1",
                input=[{
                    "role": "user",
                    "content": content
                }]
            )

            raw = response.output_text
            json_text = raw[raw.find("{"): raw.rfind("}") + 1]
            data = json.loads(json_text)

            kimlik = data["kimlik"]
            sorular = data["sorular"]

            kayit = {
                "Ad Soyad": kimlik.get("ad_soyad", f"Öğrenci {i+1}"),
                "Numara": kimlik.get("numara", "-"),
            }

            toplam = 0
            for s in sorular:
                kayit[f"Soru {s['no']}"] = s["puan"]
                toplam += s["puan"]

            kayit["Toplam Puan"] = toplam
            st.session_state.sinif_verileri.append(kayit)

        except Exception as e:
            st.error(f"{i+1}. öğrenci okunamadı: {e}")

        progress.progress((i + 1) / len(gruplar))
        time.sleep(0.5)

    durum.success("✅ Tüm kağıtlar işlendi")

# ==========================================
# 8. PUAN ÇİZELGESİ
# ==========================================
if st.session_state.sinif_verileri:
    st.markdown("## 📊 Değerlendirme Çizelgesi")

    df = pd.DataFrame(st.session_state.sinif_verileri)

    soru_cols = sorted(
        [c for c in df.columns if c.startswith("Soru")],
        key=lambda x: int(x.split()[1])
    )

    df = df[["Ad Soyad", "Numara"] + soru_cols + ["Toplam Puan"]]

    st.dataframe(df, use_container_width=True)

    st.download_button(
        "📥 Excel olarak indir",
        df.to_excel(index=False, engine="openpyxl"),
        file_name="sinav_sonuclari.xlsx"
    )
