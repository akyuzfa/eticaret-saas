import pandas as pd
import numpy as np
import streamlit as st
import requests

# =================================================================
# 🔑 META ADS API KİMLİK BİLGİLERİ
# Token ve Hesap ID bilgilerinizi aşağıdaki tırnak işaretlerinin içine yazın.
# =================================================================
META_ACCESS_TOKEN = "EAAN6R3WgZApYBRolMblUZAzCN6ePzTPx9iPjddwNjlIpKa50oHRPNIKtIp41ehe4F8UCuVhVZBrlxthb3TY19ZAGG95fF4hEYOpw00YJ6bhUZAD0FkxbZBnVumcZAodCmcuTZBZAKCysHNjeBDGCTaN5ZAJkG8R1FWUjZCVghaZB8I7Iaa2mioAANMxjP1ddtPN3Qg1kadUyFT9EX44pFQZDZD"
AD_ACCOUNT_ID = "act_1604034446875292"
# =================================================================

def veriyi_yukle_ve_temizle():
    """
    ikas-siparisler-26201806.csv dosyasını belirtilen 
    tam kolon isimlerine göre yükler ve işler.
    """
    dosya_adi = "ikas-siparisler-26201806.csv"
    
    try:
        df = pd.read_csv(dosya_adi, encoding="utf-8-sig")
    except FileNotFoundError:
        st.error(f"'{dosya_adi}' dosyası bulunamadı! Lütfen proje ana dizinine yüklediğinizden emin olun.")
        return pd.DataFrame()

    # --- KULLANICI TARAFINDAN BELİRTİLEN TAM KOLON HARİTASI ---
    kolon_haritasi = {
        'Sipariş Numarası': 'siparis_id',
        'Sipariş Tarihi': 'tarih',
        'Toplam': 'toplam_ciro',
        'Ürün Sayısı': 'satis_adedi',
        'Ürün İndirim Fiyatı': 'birim_satis_fiyati',
        'Ürün Alış Fiyatı': 'birim_maliyet',
        'Kargo Adresi Şehir': 'kargo_sehir',
        'Ürün Adı': 'urun_adi',
        'Varyant Değeri 1': 'varyant'
    }
    
    df = df.rename(columns=kolon_haritasi)
    
    if 'varyant' not in df.columns:
        possible_variant_cols = [c for c in df.columns if 'Varyant' in c or 'Seçenek' in c]
        if possible_variant_cols:
            df = df.rename(columns={possible_variant_cols[0]: 'varyant'})
        else:
            df['varyant'] = "Standart"

    # --- VERİ TİPİ DÖNÜŞTÜRMELERİ ---
    if 'tarih' in df.columns:
        df["tarih"] = pd.to_datetime(df["tarih"], errors='coerce')
    else:
        df["tarih"] = pd.to_datetime("2026-01-01")

    num_cols = ['toplam_ciro', 'satis_adedi', 'birim_satis_fiyati', 'birim_maliyet']
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        else:
            df[col] = 0

    # Gerçek Mal Maliyeti (COGS) Hesabı
    df['mal_maliyeti'] = df['birim_maliyet'] * df['satis_adedi']

    # --- ÖZEL KATEGORİ KONSOLİDASYONU ---
    if 'urun_adi' in df.columns:
        df['urun_adi'] = df['urun_adi'].replace({
            'Dana Sucuk-Doğal Fermente': 'Dana Sucuk',
            'Dana Sucuk - Doğal Fermente': 'Dana Sucuk'
        })

    return df

def get_meta_ads_data(start_date, end_date):
    """
    Meta Graph API üzerinden tarih aralığına duyarlı olarak 
    gerçek kampanya harcamalarını ve dönüşüm (ROAS) değerlerini çeker.
    """
    # Eğer henüz gerçek token girilmediyse panelin çökmemesi için uyarı verip simülasyona düşer
    if "BURAYA" in META_ACCESS_TOKEN or "BURAYA" in AD_ACCOUNT_ID:
        st.sidebar.warning("⚠️ Meta API Kimlik Bilgileri Eksik! (Şu an simülasyon verileri gösteriliyor)")
        
        # Güvenli Fallback Simülasyon Verisi
        np.random.seed(42)
        kampanyalar = ["Dönüşüm - Kampanyası - Dana Sucuk", "Dönüşüm - Kampanyası - Peynir", "TOFU - Bilinirlik", "Retargeting - Sepet"]
        veri_listesi = []
        for kampanya in kampanyalar:
            harcama = np.random.uniform(4000, 15000)
            sim_roas = np.random.uniform(2.5, 6.0)
            veri_listesi.append({
                "Kampanya Adı": kampanya,
                "Harcama (TL)": round(harcama, 2),
                "E-Ticaret Geliri (TL)": round(harcama * sim_roas, 2)
            })
        return pd.DataFrame(veri_listesi)

    # Canlı Meta Insights API Çağrısı
    url = f"https://graph.facebook.com/v19.0/{AD_ACCOUNT_ID}/insights"
    
    params = {
        'access_token': META_ACCESS_TOKEN,
        'level': 'campaign',
        'fields': 'campaign_name,spend,action_values',
        'time_range': f"{{\"since\":\"{start_date}\",\"until\":\"{end_date}\"}}",
        'limit': 150
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if 'error' in data:
            st.error(f"Meta API Hatası: {data['error']['message']}")
            return pd.DataFrame()
            
        api_verisi = []
        for item in data.get('data', []):
            kampanya_adi = item.get('campaign_name', 'Bilinmeyen Kampanya')
            harcama = float(item.get('spend', 0))
            
            # Purchase event değerini parse etme
            gelir = 0.0
            action_values = item.get('action_values', [])
            for action in action_values:
                action_type = action.get('action_type', '')
                if action_type in ['offsite_conversion.fb_pixel_purchase', 'purchase']:
                    gelir = float(action.get('value', 0))
                    break
            
            api_verisi.append({
                "Kampanya Adı": kampanya_adi,
                "Harcama (TL)": harcama,
                "E-Ticaret Geliri (TL)": gelir
            })
            
        return pd.DataFrame(api_verisi)
        
    except Exception as e:
        st.error(f"Meta API bağlantı hatası oluştu: {e}")
        return pd.DataFrame()

def bcg_stratejisi_hesapla(df):
    if df.empty:
        return pd.DataFrame()
        
    bcg_data = df.groupby(["urun_adi", "varyant"]).agg(
        urun_sayisi=("satis_adedi", "sum"),
        toplam_ciro=("toplam_ciro", "sum"),
        toplam_maliyet=("mal_maliyeti", "sum")
    ).reset_index()
    
    ciro_esik = bcg_data["toplam_ciro"].median() if not bcg_data.empty else 0
    adet_esik = bcg_data["urun_sayisi"].median() if not bcg_data.empty else 0
    
    def segment_atama(row):
        if row["toplam_ciro"] >= ciro_esik and row["urun_sayisi"] >= adet_esik:
            return "Yıldızlar"
        elif row["toplam_ciro"] < ciro_esik and row["urun_sayisi"] >= adet_esik:
            return "Sürümden Kazananlar"
        elif row["toplam_ciro"] >= ciro_esik and row["urun_sayisi"] < adet_esik:
            return "Gizli Cevherler"
        else:
            return "Ölü Kilo"
            
    bcg_data["Strateji"] = bcg_data.apply(segment_atama, axis=1)
    return bcg_data