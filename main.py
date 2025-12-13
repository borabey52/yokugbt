import streamlit as st
from openai import OpenAI
from PIL import Image
import base64, io, json, time

# =========================
# SAYFA AYARLARI
# =========================
st.set_page_config(page_title="AI Sınav Okuma", layout="wide")
st.title("🧠 AI Toplu Sınav Okuma ve Puanlama")

# =========================
# API KEY
# =========================
if "OPENAI_API_KEY" in st.secrets:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
else:
    st.error("OPENAI_API_KEY bulunamadı (st.secrets)")
    st.stop()

# =========================
# YARDIMCI FONKSİYONLAR
# =========================
def image_to_base64(img: Image.Image):
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode()

def temiz_json(text):
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        return json.loads(text[start:end])
    except:
        return None

# =========================
# HAFIZA
# =========================
if "sonuclar" not in st.session_state:
    st.session_state.sonuclar = []

# =========================
# ARAYÜZ
# =========================
with st.sidebar:
    st.header("⚙️ Ayarlar")
    if st.button("🗑️ Listeyi Sıfırla"):
        st.session_state.sonuclar = []
        st.rerun()

col1, col2 = st.columns(2)

with col1:
    ogretmen_notu = st.text_area(
        "📝 Öğretmen Notu / Puanlama Açıklaması",
        placeholder="Ör: Yazım hataları -1 puan, anlam bütünlüğü önemli"
    )

    cevap_kagidi = st.file_uploader(
        "📘 Cevap Anahtarı / Rubrik (opsiyonel)",
        type=["jpg", "jpeg", "png"]
    )

with col2:
    ogrenci_kagitlari = st.file_uploader(
        "📄 Öğrenci Kağıtları (çoklu)",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True
    )

# =========================
# OKU VE DEĞERLENDİR
# =========================
if st.button("🚀 KAĞITLARI OKU VE DEĞERLENDİR", use_container_width=True):

    if not ogrenci_kagitlari:
        st.warning("Öğrenci kağıdı yüklemediniz.")
        st.stop()

    cevap_img = Image.open(cevap_kagidi) if cevap_kagidi else None

    progress = st.progress(0)
    durum = st.empty()

    for i, dosya in enumerate(ogrenci_kagitlari):
        durum.write(f"📖 Okunuyor: {dosya.name}")

        ogr_img = Image.open(dosya)

        content = [
            {
                "type": "input_text",
                "text": f"""
Bu bir sınav kağıdıdır.

GÖREVLERİN:
1. Öğrencinin cevaplarını oku ve anla
2. Eğer cevap anahtarı verilmişse onunla karşılaştır
3. Her sorunun DOĞRU cevabını belirle
4. Öğrencinin cevabını doğruya göre değerlendir
5. Soru bazlı puan ver
6. Toplam puanı hesapla

ÖĞRETMEN NOTU:
{ogretmen_notu}

SADECE JSON ÇIKTI VER:
{{
 "ogrenci": {{"ad_soyad":"", "numara":""}},
 "sorular":[
   {{
     "no":"1",
     "dogru_cevap":"...",
     "ogrenci_cevabi":"...",
     "puan":0,
     "tam_puan":10,
     "yorum":""
   }}
 ]
}}
"""
            }
        ]

        if cevap_img:
            content.append({
                "type": "input_image",
                "image_url": f"data:image/jpeg;base64,{image_to_base64(cevap_img)}"
            })

        content.append({
            "type": "input_image",
            "image_url": f"data:image/jpeg;base64,{image_to_base64(ogr_img)}"
        })

        try:
            response = client.responses.create(
                model="gpt-4.1",
                input=[{"role": "user", "content": content}],
                max_output_tokens=900
            )

            raw_text = response.output_text
            data = temiz_json(raw_text)

            if not data:
                raise ValueError("JSON okunamadı")

            ogr = data["ogrenci"]
            sorular = data["sorular"]
            toplam = sum(s["puan"] for s in sorular)

            kayit = {
                "Ad Soyad": ogr.get("ad_soyad", dosya.name),
                "Numara": ogr.get("numara", "-"),
                "Toplam Puan": toplam
            }

            for s in sorular:
                kayit[f"Soru {s['no']}"] = s["puan"]

            st.session_state.sonuclar.append(kayit)

        except Exception as e:
            st.error(f"{dosya.name} okunamadı: {e}")

        progress.progress((i + 1) / len(ogrenci_kagitlari))
        time.sleep(0.5)

    st.success("✅ Tüm kağıtlar işlendi")

# =========================
# SONUÇ TABLOSU
# =========================
if st.session_state.sonuclar:
    st.subheader("📊 Sonuç Çizelgesi")
    st.dataframe(st.session_state.sonuclar, use_container_width=True)
