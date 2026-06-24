import streamlit as st
import plotly.express as px
import numpy as np
import pandas as pd
import datetime
from analiz import veriyi_yukle_ve_temizle, bcg_stratejisi_hesapla, get_meta_ads_data

st.set_page_config(layout="wide", page_title="Kaşarcızade Performans & Strateji Paneli")

st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 20px; border-radius: 8px; box-shadow: 1px 1px 5px rgba(0,0,0,0.05); border-left: 5px solid #00D1B2; }
    </style>
    """, unsafe_allow_html=True)

# ikas CSV verilerini yükle
df = veriyi_yukle_ve_temizle()

if df.empty:
    st.warning("⚠️ 'ikas-siparisler-26201806.csv' dosyası yüklenemedi veya belirtilen sütunlar uyuşmuyor.")
else:
    # --- YAN PANEL NAVİGASYON ---
    st.sidebar.title("🚀 Kaşarcızade Kontrol Paneli")
    sayfa = st.sidebar.radio(
        "Analiz Bölümleri:",
        ["1- Genel Performans & KPI", "2- Şehir Dağılımı", "3- Reklam Performansı & ROAS", "4- BCG Ürün Stratejisi", "5- Fiyat Simülasyonu"]
    )
    
    st.sidebar.divider()
    st.sidebar.subheader("📅 Dönem Filtresi")
    
    min_date = df["tarih"].min().date()
    max_date = df["tarih"].max().date()
    
    tarihler = st.sidebar.date_input("Rapor Tarih Aralığı", [min_date, max_date])
    
    # Tarih aralığının doğru seçildiğinden ve Meta API'ye doğru formatta gittiğinden emin oluyoruz
    if isinstance(tarihler, (list, tuple)) and len(tarihler) == 2:
        start_str = tarihler[0].strftime("%Y-%m-%d")
        end_str = tarihler[1].strftime("%Y-%m-%d")
        
        mask = (df["tarih"].dt.date >= tarihler[0]) & (df["tarih"].dt.date <= tarihler[1])
        df_filt = df[mask]
        meta_df = get_meta_ads_data(start_str, end_str)
    else:
        start_str = min_date.strftime("%Y-%m-%d")
        end_str = max_date.strftime("%Y-%m-%d")
        df_filt = df
        meta_df = get_meta_ads_data(start_str, end_str)

    # --- MENÜ SAYFALARI ---
    
    if sayfa == "1- Genel Performans & KPI":
        st.header("📈 Şirket Genel Performans Göstergeleri")
        
        toplam_ciro = df_filt["toplam_ciro"].sum()
        toplam_maliyet = df_filt["mal_maliyeti"].sum()
        
        # Meta canlı API verilerinin metrik toplamları
        toplam_reklam_harcamasi = meta_df["Harcama (TL)"].sum() if not meta_df.empty else 0
        toplam_reklam_geliri = meta_df["E-Ticaret Geliri (TL)"].sum() if not meta_df.empty else 0
        
        net_kar_urun = toplam_ciro - toplam_maliyet
        gercek_net_kar = net_kar_urun - toplam_reklam_harcamasi
        genel_kar_marji = (gercek_net_kar / toplam_ciro) * 100 if toplam_ciro > 0 else 0
        birlesik_roas = (toplam_reklam_geliri / toplam_reklam_harcamasi) if toplam_reklam_harcamasi > 0 else 0
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Toplam Ciro", f"{toplam_ciro:,.2f} TL")
        c2.metric("Mal Maliyeti (COGS)", f"{toplam_maliyet:,.2f} TL")
        c3.metric("Net Kâr (Ürün Bazlı)", f"{net_kar_urun:,.2f} TL")
        c4.metric("Toplam Reklam Harcaması", f"{toplam_reklam_harcamasi:,.2f} TL")
        
        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Gerçek Net Kâr (Reklam Dahil)", f"{gercek_net_kar:,.2f} TL")
        c6.metric("Toplam Sipariş (Adrese Göre)", f"{df_filt['siparis_id'].nunique():,} Adet")
        c7.metric("Satılan Toplam Ürün Satış Adedi", f"{df_filt['satis_adedi'].sum():,} Adet")
        c8.metric("Genel Kâr Marjı / Birleşik ROAS", f"%{genel_kar_marji:.2f}", f"ROAS: {birlesik_roas:.2f}")
        
        st.write("### Ürün ve Varyant Bazlı Satış, Maliyet ve Marj Tablosu")
        urun_ozet = df_filt.groupby(["urun_adi", "varyant"]).agg(
            satis_adedi=("satis_adedi", "sum"),
            toplam_ciro=("toplam_ciro", "sum"),
            mal_maliyeti=("mal_maliyeti", "sum")
        ).reset_index()
        urun_ozet["net_kar"] = urun_ozet["toplam_ciro"] - urun_ozet["mal_maliyeti"]
        urun_ozet["kar_marji"] = (urun_ozet["net_kar"] / urun_ozet["toplam_ciro"]) * 100
        
        st.dataframe(urun_ozet.style.format({
            "toplam_ciro": "{:,.2f} TL", 
            "mal_maliyeti": "{:,.2f} TL", 
            "net_kar": "{:,.2f} TL",
            "kar_marji": "%{:.2f}"
        }), use_container_width=True)

    elif sayfa == "2- Şehir Dağılımı":
        st.header("📍 Şehir Dağılımı Çubuk Grafiği")
        sehir_df = df_filt[df_filt["kargo_sehir"].notna() & (df_filt["kargo_sehir"] != "") & (df_filt["kargo_sehir"] != "Belirtilmemiş")]
        
        if not sehir_df.empty:
            city_data = sehir_df.groupby("kargo_sehir")["siparis_id"].count().reset_index().sort_values("siparis_id", ascending=False)
            fig = px.bar(city_data, x="kargo_sehir", y="siparis_id", color="siparis_id", text_auto=True, 
                         labels={"siparis_id": "Sipariş Sayısı", "kargo_sehir": "Kargo Şehir Adresi"})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Seçilen filtrelerde kargo şehir adresi verisi bulunamadı.")

    elif sayfa == "3- Reklam Performansı & ROAS":
        st.header("📣 Reklamların ROAS Değerleri ve Reklam Maliyetleri")
        
        if not meta_df.empty:
            # Sınırsız ROAS hatası (sıfıra bölünme) koruması
            meta_df["ROAS"] = np.where(meta_df["Harcama (TL)"] > 0, meta_df["E-Ticaret Geliri (TL)"] / meta_df["Harcama (TL)"], 0)
            
            r_col1, r_col2, r_col3 = st.columns(3)
            r_col1.metric("Toplam Reklam Maliyeti", f"{meta_df['Harcama (TL)'].sum():,.2f} TL")
            r_col2.metric("Reklam Gelirleri", f"{meta_df['E-Ticaret Geliri (TL)'].sum():,.2f} TL")
            
            hesap_harcama = meta_df['Harcama (TL)'].sum()
            birlesik_roas_val = (meta_df['E-Ticaret Geliri (TL)'].sum() / hesap_harcama) if hesap_harcama > 0 else 0
            r_col3.metric("Birleşik ROAS Değeri", f"{birlesik_roas_val:.2f}")
            
            st.dataframe(meta_df.style.format({"Harcama (TL)": "{:,.2f} TL", "E-Ticaret Geliri (TL)": "{:,.2f} TL", "ROAS": "{:.2f}x"}), use_container_width=True)
            fig_roas = px.bar(meta_df, x="Kampanya Adı", y="ROAS", color="ROAS", text_auto=".2f", color_continuous_scale="RdYlGn")
            st.plotly_chart(fig_roas, use_container_width=True)
        else:
            st.info("Seçilen tarih aralığında Meta reklam verisi bulunamadı veya API verisi boş.")

    elif sayfa == "4- BCG Ürün Stratejisi":
        st.header("🎯 BCG Matrisi Ürün Stratejisi")
        bcg_sonuc = bcg_stratejisi_hesapla(df_filt)
        
        if not bcg_sonuc.empty:
            secilen_strateji = st.selectbox("İncelemek İstediğiniz Strateji Grubu:", ["Yıldızlar", "Sürümden Kazananlar", "Gizli Cevherler", "Ölü Kilo"])
            detay_tablo = bcg_sonuc[bcg_sonuc["Strateji"] == secilen_strateji]
            
            st.subheader(f"💎 {secilen_strateji} Segmentindeki Ürünler")
            st.dataframe(detay_tablo[["urun_adi", "varyant", "urun_sayisi", "toplam_ciro", "toplam_maliyet"]].style.format({
                "toplam_ciro": "{:,.2f} TL",
                "toplam_maliyet": "{:,.2f} TL",
                "urun_sayisi": "{:,}"
            }), use_container_width=True)
            
            fig_bcg = px.scatter(bcg_sonuc, x="urun_sayisi", y="toplam_ciro", color="Strateji", size="toplam_ciro", hover_data=["urun_adi", "varyant"], text="urun_adi")
            st.plotly_chart(fig_bcg, use_container_width=True)

    elif sayfa == "5- Fiyat Simülasyonu":
        st.header("🧪 Ürünlerin Varyant Bazlı Fiyat Simülasyonu")
        
        if 'urun_adi' in df_filt.columns and not df_filt.empty:
            col_s1, col_s2 = st.columns([1, 2])
            with col_s1:
                secilen_urun = st.selectbox("Ürün Seçin", df_filt["urun_adi"].unique())
                secilen_varyant = st.selectbox("Varyant Seçin", df_filt[df_filt["urun_adi"] == secilen_urun]["varyant"].unique())
                
                target_df = df_filt[(df_filt["urun_adi"] == secilen_urun) & (df_filt["varyant"] == secilen_varyant)]
                mevcut_adet = target_df["satis_adedi"].sum()
                mevcut_ciro = target_df["toplam_ciro"].sum()
                mevcut_maliyet = target_df["mal_maliyeti"].sum()
                
                mevcut_fiyat = target_df["birim_satis_fiyati"].mean() if mevcut_adet > 0 else 0
                
                yeni_fiyat = st.slider("Dinamik Birim Fiyat Simülasyonu (TL)", float(mevcut_fiyat*0.5), float(mevcut_fiyat*2.0), float(mevcut_fiyat), step=5.0)
                
            with col_s2:
                yeni_ciro = mevcut_adet * yeni_fiyat
                yeni_kar = yeni_ciro - mevcut_maliyet
                eski_kar = mevcut_ciro - mevcut_maliyet
                
                st.subheader("Karlılık Nasıl Değişiyor?")
                res_c1, res_c2 = st.columns(2)
                res_c1.metric("Yeni Tahmini Toplam Ciro", f"{yeni_ciro:,.2f} TL", f"{yeni_ciro - mevcut_ciro:,.2f} TL")
                res_c2.metric("Yeni Tahmini Net Kâr", f"{yeni_kar:,.2f} TL", f"{yeni_kar - eski_kar:,.2f} TL")