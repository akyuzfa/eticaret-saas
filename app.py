import streamlit as st
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import os
import sys

# Çalışma dizinini sys.path'e zorunlu olarak ekliyoruz (Circular Import önleyici)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from analiz import veriyi_ozetle, musteri_analizi_yap, meta_performans_cek
except ImportError:
    import analiz
    veriyi_ozetle = analiz.veriyi_ozetle
    musteri_analizi_yap = analiz.musteri_analizi_yap
    meta_performans_cek = analiz.meta_performans_cek

# Sayfa Genişlik Ayarı
st.set_page_config(layout="wide", page_title="Konsolide E-Ticaret Paneli")

# ==============================================================================
# 🗃️ KODA GÖMÜLEN SABİT VERİLER
# ==============================================================================
SABIT_DOSYA_YOLU = "ikas-siparisler-26201806.csv"
META_ACCESS_TOKEN = "EAAN6R3WgZApYBRolMblUZAzCN6ePzTPx9iPjddwNjlIpKa50oHRPNIKtIp41ehe4F8UCuVhVZBrlxthb3TY19ZAGG95fF4hEYOpw00YJ6bhUZAD0FkxbZBnVumcZAodCmcuTZBZAKCysHNjeBDGCTaN5ZAJkG8R1FWUjZCVghaZB8I7Iaa2mioAANMxjP1ddtPN3Qg1kadUyFT9EX44pFQZDZD"  # <-- Token'ınızı buraya ekleyin
META_REKLAM_HESABI_ID = "1604034446875292"   # <-- Sadece rakamlardan oluşan ID girin

def main():
    st.title("📊 E-Ticaret & Meta Ads Konsolide Yönetim Paneli")
    
    st.sidebar.header("📅 Tarih Filtresi")
    baslangic = st.sidebar.date_input("Başlangıç Tarihi", value=pd.to_datetime("2026-01-01"))
    bitis = st.sidebar.date_input("Bitiş Tarihi", value=pd.to_datetime("2026-06-30"))

    # Dosya Mevcudiyet Kontrolü
    if os.path.exists(SABIT_DOSYA_YOLU):
        with st.spinner("Tüm finansal veriler ve ürün metrikleri hesaplanıyor..."):
            segmentler, ecom_ozet, urun_analiz, aylik_sehir_analizi, sehir_ay_pivot = veriyi_ozetle(SABIT_DOSYA_YOLU, str(baslangic), str(bitis))
            retention_matrix, rfm_df = musteri_analizi_yap(SABIT_DOSYA_YOLU)
            df_meta = meta_performans_cek(META_ACCESS_TOKEN, META_REKLAM_HESABI_ID, str(baslangic), str(bitis))
        
        if not ecom_ozet:
            st.warning("Seçilen tarih aralığında herhangi bir sipariş verisi bulunamadı.")
            return

        # Finansal Özet Hesaplamaları
        toplam_reklam = df_meta['Harcanan Tutar (TL)'].sum() if not df_meta.empty else 0.0
        ciro = ecom_ozet["toplam_ciro"]
        maliyet = ecom_ozet["toplam_maliyet"]
        urun_kar = ecom_ozet["toplam_net_kar"]
        gercek_kar = urun_kar - toplam_reklam
        roas = (ciro / toplam_reklam) if toplam_reklam > 0 else 0.0
        
        # Adrese Göre Sipariş Sayısı Hesaplama (Belirtilmemiş Hariç)
        toplam_siparis_sayisi = 0
        if not aylik_sehir_analizi.empty:
            filtreli_sehirler = aylik_sehir_analizi[aylik_sehir_analizi['Kargo Adresi Şehir'] != 'BELİRTİLMEMİŞ']
            toplam_siparis_sayisi = filtreli_sehirler['Sipariş Adedi'].sum()
        else:
            toplam_siparis_sayisi = rfm_df['Frequency'].sum() if not rfm_df.empty else 0

        # Tablo Alanı: İstenen Tüm Finansal Metriklerin Sunumu
        st.subheader("📋 Genel Finansal Performans Özeti")
        
        finansal_veri = {
            "Metrik Bilgisi": [
                "Toplam Ciro", 
                "Mal Maliyeti (COGS)", 
                "Net Kâr (Ürün Bazlı)", 
                "Toplam Reklam Harcaması", 
                "Gerçek Net Kâr (Reklam Dahil)",
                "Toplam Sipariş Sayısı (Adrese Göre)", 
                "Satılan Toplam Ürün Satış Adedi", 
                "Genel Kâr Marjı", 
                "Birleşik ROAS"
            ],
            "Değer / Oran": [
                f"{ciro:,.2f} TL",
                f"{maliyet:,.2f} TL",
                f"{urun_kar:,.2f} TL",
                f"{toplam_reklam:,.2f} TL",
                f"{gercek_kar:,.2f} TL",
                f"{toplam_siparis_sayisi:,} Adet",
                f"{ecom_ozet['toplam_adet']:,} Adet",
                f"%{ecom_ozet['genel_kar_marji']:.2f}",
                f"{roas:.2f}"
            ]
        }
        df_finans_tablo = pd.DataFrame(finansal_veri)
        st.table(df_finans_tablo)
        
        st.write("---")

        # Yeni Sekme Yapısı ve Sıralaması (Ürün Satış Detayları ilk sıraya alındı)
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📦 Ürün Satış Detayları",
            "📊 Şehir Dağılımı (Çubuk Grafik)", 
            "📐 BCG Matrisi (Ürün Stratejisi)", 
            "👥 Müşteri Retention (Süreklilik)", 
            "🎯 RFM Persona Analizi"
        ])

        # TAB 1: Ürün Satış Detayları (İlk Sırada)
        with tab1:
            st.subheader("Ürün Bazlı Satış, Maliyet ve Marj Tablosu (Tarih Filtreli)")
            if not urun_analiz.empty:
                gosterilecek_urunler = urun_analiz.rename(columns={
                    'Ürün Adı': 'Ürün Adı',
                    'Varyant Değeri 1': 'Varyant',
                    'Ürün Sayısı': 'Satış Adedi',
                    'toplam_ciro': 'Toplam Ciro (TL)',
                    'toplam_maliyet': 'Mal Maliyeti (TL)',
                    'net_kar': 'Net Kâr (TL)',
                    'kar_marji_orani': 'Kâr Marjı (%)'
                }).sort_values(by='Satış Adedi', ascending=False)
                
                st.dataframe(
                    gosterilecek_urunler[[
                        'Ürün Adı', 'Varyant', 'Satış Adedi', 
                        'Toplam Ciro (TL)', 'Mal Maliyeti (TL)', 'Net Kâr (TL)', 'Kâr Marjı (%)'
                    ]].style.format({
                        'Toplam Ciro (TL)': '{:,.2f}',
                        'Mal Maliyeti (TL)': '{:,.2f}',
                        'Net Kâr (TL)': '{:,.2f}',
                        'Kâr Marjı (%)': '%{:.2f}'
                    }), 
                    use_container_width=True
                )
            else:
                st.info("Ürün satışı detay verisi bulunamadı.")

        # TAB 2: Şehir Dağılımı (İkinci Sırada)
        with tab2:
            st.subheader("En Çok Sipariş Verilen Top 20 Şehir Dağılımı")
            if not sehir_ay_pivot.empty:
                temiz_sehir_pivot = sehir_ay_pivot[sehir_ay_pivot['Kargo Adresi Şehir'] != 'BELİRTİLMEMİŞ']
                gorsel_matris = temiz_sehir_pivot.set_index('Kargo Adresi Şehir')
                sehir_toplamlari = gorsel_matris.sum(axis=1).sort_values(ascending=False).head(20)
                
                if not sehir_toplamlari.empty:
                    fig, ax = plt.subplots(figsize=(12, 6))
                    sehir_toplamlari.plot(kind='bar', color='skyblue', edgecolor='black', ax=ax)
                    
                    plt.title("Şehirlere Göre Toplam Sipariş Adetleri (Top 20)", fontsize=13, pad=15)
                    plt.xlabel("Şehir Adı", fontsize=11)
                    plt.ylabel("Sipariş Sayısı", fontsize=11)
                    plt.xticks(rotation=45, ha='right')
                    plt.grid(axis='y', linestyle='--', alpha=0.7)
                    
                    for i, v in enumerate(sehir_toplamlari):
                        ax.text(i, v + (v * 0.01), str(int(v)), ha='center', va='bottom', fontsize=9)
                    
                    st.pyplot(fig)
                    plt.close(fig)
                else:
                    st.info("Filtrelenecek geçerli bir şehir verisi bulunamadı.")
            else:
                st.info("Grafik üretimi için kargo şehir verisi bulunamadı.")

        # TAB 3: BCG Matrisi Segmentleri
        with tab3:
            st.subheader("BCG Matrisine Göre Ürün Performans Segmentasyonu")
            sb1, sb2 = st.columns(2)
            columns_list = ['Ürün Adı', 'Varyant Değeri 1', 'Ürün Sayısı', 'toplam_ciro', 'toplam_maliyet', 'kar_marji_orani']
            with sb1:
                st.success("⭐ Yıldızlar (Yüksek Satış - Yüksek Marj)")
                st.dataframe(segmentler["Yıldızlar (Yüksek Satış - Yüksek Marj)"][columns_list] if not segmentler["Yıldızlar (Yüksek Satış - Yüksek Marj)"].empty else pd.DataFrame(), use_container_width=True)
                st.info("💎 Gizli Cevherler (Düşük Satış - Yüksek Marj)")
                st.dataframe(segmentler["Gizli Cevherler (Düşük Satış - Yüksek Marj)"][columns_list] if not segmentler["Gizli Cevherler (Düşük Satış - Yüksek Marj)"].empty else pd.DataFrame(), use_container_width=True)
            with sb2:
                st.warning("🚜 Sürümden Kazananlar (Yüksek Satış - Düşük Marj)")
                st.dataframe(segmentler["Sürümden Kazananlar (Yüksek Satış - Düşük Marj)"][columns_list] if not segmentler["Sürümden Kazananlar (Yüksek Satış - Düşük Marj)"].empty else pd.DataFrame(), use_container_width=True)
                st.error("📉 Ölü Kilo (Düşük Satış - Düşük Marj)")
                st.dataframe(segmentler["Ölü Kilo (Düşük Satış - Düşük Marj)"][columns_list] if not segmentler["Ölü Kilo (Düşük Satış - Düşük Marj)"].empty else pd.DataFrame(), use_container_width=True)

        # TAB 4: Cohort Retention
        with tab4:
            st.subheader("Müşteri Geri Kazanım Oranları (Cohort Retention %)")
            if not retention_matrix.empty:
                fig, ax = plt.subplots(figsize=(14, 6))
                sns.heatmap(retention_matrix, annot=True, fmt=".1f", cmap="RdYlGn", vmin=0, vmax=25, ax=ax)
                st.pyplot(fig)
                plt.close(fig)

        # TAB 5: RFM
        with tab5:
            st.subheader("Müşteri Bazlı RFM Skor Tablosu")
            if not rfm_df.empty:
                st.dataframe(rfm_df.sort_values(by='Monetary', ascending=False), use_container_width=True)
    else:
        st.error(f"❌ '{SABIT_DOSYA_YOLU}' dosyası bulunamadı. Lütfen bu dosyayı app.py ile yan yana koyun.")

if __name__ == "__main__":
    main()