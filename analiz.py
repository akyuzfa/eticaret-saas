import pandas as pd
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount

# ==============================================================================
# 1. KISIM: FİNANSAL VE STRATEJİK ANALİZ MOTORU
# ==============================================================================
def veriyi_ozetle(dosya_yolu, baslangic_tarihi, bitis_tarihi):
    chunks = []
    try:
        gerekli_sutunlar = [
            'Sipariş Tarihi', 'Sipariş Numarası', 'Sipariş No', 'Sipariş ID',
            'Ürün Adı', 'Varyant Değeri 1', 'Ürün Sayısı', 
            'Ürün İndirim Fiyatı', 'Ürün Alış Fiyatı', 'Kargo Adresi Şehir', 
            'Toplam', 'Sipariş Ödeme Durumu'
        ]
        
        first_chunk = next(pd.read_csv(dosya_yolu, chunksize=1, low_memory=False))
        first_chunk.columns = first_chunk.columns.str.strip()
        mevcut_sutunlar = [col for col in gerekli_sutunlar if col in first_chunk.columns]
        
        for chunk in pd.read_csv(dosya_yolu, chunksize=20000, usecols=mevcut_sutunlar, low_memory=False):
            chunk.columns = chunk.columns.str.strip()
            chunks.append(chunk)
    except Exception:
        return {}, {}, pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        
    if not chunks:
        return {}, {}, pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        
    df = pd.concat(chunks, axis=0)
    
    # Ödeme Durumu Filtresi
    if 'Sipariş Ödeme Durumu' in df.columns:
        df['Sipariş Ödeme Durumu'] = df['Sipariş Ödeme Durumu'].astype(str).str.strip()
        gecerli_odemeler = ['Ödendi', 'Parçalı Ödendi', 'Bekliyor']
        df = df[df['Sipariş Ödeme Durumu'].isin(gecerli_odemeler)]
    
    if df.empty:
        return {}, {}, pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    siparis_no_kolonu = 'Sipariş Numarası' if 'Sipariş Numarası' in df.columns else ('Sipariş No' if 'Sipariş No' in df.columns else 'Sipariş ID')
    if siparis_no_kolonu in df.columns:
        df['Sipariş Numarası'] = df[siparis_no_kolonu].astype(str).str.strip()
    else:
        return {}, {}, pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    if 'Varyant Değeri 1' in df.columns:
        df['Varyant Değeri 1'] = df['Varyant Değeri 1'].fillna('Standart').astype(str).str.strip()
    else:
        df['Varyant Değeri 1'] = 'Standart'
        
    if 'Ürün Adı' in df.columns:
        df['Ürün Adı'] = df['Ürün Adı'].astype(str).str.strip().replace({'Dana Sucuk - Doğal Fermente': 'Dana Sucuk'})
    
    if 'Sipariş Tarihi' in df.columns:
        df['Sipariş Tarihi'] = pd.to_datetime(df['Sipariş Tarihi'], errors='coerce', format='mixed')
        df = df.dropna(subset=['Sipariş Tarihi'])
    else:
        return {}, {}, pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # Tarih Filtresi
    baslangic_dt = pd.to_datetime(baslangic_tarihi)
    bitis_dt = pd.to_datetime(bitis_tarihi)
    df = df[(df['Sipariş Tarihi'] >= baslangic_dt) & (df['Sipariş Tarihi'] <= bitis_dt)]
    
    if df.empty:
        return {}, {}, pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    df['Sipariş Ayı'] = df['Sipariş Tarihi'].dt.to_period('M').astype(str)
    
    # 🌟 İSTEDİĞİNİZ DEĞİŞİKLİK: Ürün performansı ve marjlar için eski güvenli formül devrede
    df['toplam_ciro'] = df['Ürün Sayısı'] * df['Ürün İndirim Fiyatı']
    df['toplam_maliyet'] = df['Ürün Sayısı'] * df['Ürün Alış Fiyatı']
    df['net_kar'] = df['toplam_ciro'] - df['toplam_maliyet']
    
    # Güvenli kâr marjı hesaplaması
    df['kar_marji_orani'] = 0.0
    gecerli_ciro = df['toplam_ciro'] > 0
    df.loc[gecerli_ciro, 'kar_marji_orani'] = ((df.loc[gecerli_ciro, 'toplam_ciro'] - df.loc[gecerli_ciro, 'toplam_maliyet']) / df.loc[gecerli_ciro, 'toplam_ciro']) * 100
    
    # Şehir Dağılım Verisi
    if 'Kargo Adresi Şehir' in df.columns:
        df['Kargo Adresi Şehir'] = df['Kargo Adresi Şehir'].fillna('BELİRTİLMEMİŞ').astype(str).str.upper().str.strip()
        aylik_sehir_analizi = df.groupby(['Sipariş Ayı', 'Kargo Adresi Şehir']).agg({
            'Sipariş Numarası': 'nunique', 'toplam_ciro': 'sum', 'net_kar': 'sum'
        }).reset_index().rename(columns={'Sipariş Numarası': 'Sipariş Adedi'})
        
        sehir_ay_pivot = aylik_sehir_analizi.pivot(index='Kargo Adresi Şehir', columns='Sipariş Ayı', values='Sipariş Adedi').fillna(0).astype(int).reset_index()
    else:
        aylik_sehir_analizi = pd.DataFrame()
        sehir_ay_pivot = pd.DataFrame()

    # Ürün Performans Analizi
    urun_analiz = df.groupby(['Ürün Adı', 'Varyant Değeri 1']).agg({
        'Ürün Sayısı': 'sum',
        'toplam_ciro': 'sum',
        'toplam_maliyet': 'sum',
        'net_kar': 'sum',
        'kar_marji_orani': 'mean'
    }).reset_index()
    
    if not urun_analiz.empty:
        urun_analiz['Tam Ürün Tanımı'] = urun_analiz['Ürün Adı'] + " (" + urun_analiz['Varyant Değeri 1'] + ")"
        orta_adet = urun_analiz['Ürün Sayısı'].median()
        orta_marj = urun_analiz['kar_marji_orani'].median()
    else:
        orta_adet, orta_marj = 0, 0
    
    # BCG Matrisi
    segmentler = {
        "Yıldızlar (Yüksek Satış - Yüksek Marj)": urun_analiz[(urun_analiz['Ürün Sayısı'] >= orta_adet) & (urun_analiz['kar_marji_orani'] >= orta_marj)] if not urun_analiz.empty else pd.DataFrame(),
        "Sürümden Kazananlar (Yüksek Satış - Düşük Marj)": urun_analiz[(urun_analiz['Ürün Sayısı'] >= orta_adet) & (urun_analiz['kar_marji_orani'] < orta_marj)] if not urun_analiz.empty else pd.DataFrame(),
        "Gizli Cevherler (Düşük Satış - Yüksek Marj)": urun_analiz[(urun_analiz['Ürün Sayısı'] < orta_adet) & (urun_analiz['kar_marji_orani'] >= orta_marj)] if not urun_analiz.empty else pd.DataFrame(),
        "Ölü Kilo (Düşük Satış - Düşük Marj)": urun_analiz[(urun_analiz['Ürün Sayısı'] < orta_adet) & (urun_analiz['kar_marji_orani'] < orta_marj)] if not urun_analiz.empty else pd.DataFrame()
    }

    # 🌟 GENEL FİNANS İÇİN KORUNAN ÖZEL KOŞUL: 
    # Genel konsolide ciro hesaplanırken dosyadaki indirimler düşülmüş 'Toplam' kolonu baz alınır.
    if 'Toplam' in df.columns:
        kasadaki_toplam_ciro = pd.to_numeric(df['Toplam'], errors='coerce').fillna(0).sum()
    else:
        kasadaki_toplam_ciro = df['toplam_ciro'].sum()

    toplam_maliyet = df['toplam_maliyet'].sum()
    genel_ozet = {
        "toplam_ciro": kasadaki_toplam_ciro, 
        "toplam_maliyet": toplam_maliyet, 
        "toplam_net_kar": (kasadaki_toplam_ciro - toplam_maliyet),
        "toplam_adet": df['Ürün Sayısı'].sum(), 
        "genel_kar_marji": ((kasadaki_toplam_ciro - toplam_maliyet) / kasadaki_toplam_ciro * 100) if kasadaki_toplam_ciro > 0 else 0.0
    }
    
    return segmentler, genel_ozet, urun_analiz, aylik_sehir_analizi, sehir_ay_pivot

# ==============================================================================
# 2. KISIM: MÜŞTERI COHORT VE PERSONA ANALİZİ
# ==============================================================================
def musteri_analizi_yap(dosya_yolu):
    chunks = []
    gerekli_sutunlar = ['Sipariş Tarihi', 'E-posta', 'Sipariş Numarası', 'Sipariş No', 'Sipariş ID', 'Ürün Sayısı', 'Ürün İndirim Fiyatı', 'Toplam', 'Sipariş Ödeme Durumu']
    
    try:
        first_chunk = next(pd.read_csv(dosya_yolu, chunksize=1, low_memory=False))
        first_chunk.columns = first_chunk.columns.str.strip()
        mevcut_sutunlar = [col for col in gerekli_sutunlar if col in first_chunk.columns]
        
        for chunk in pd.read_csv(dosya_yolu, chunksize=20000, usecols=mevcut_sutunlar, low_memory=False):
            chunk.columns = chunk.columns.str.strip()
            chunks.append(chunk)
    except Exception:
        return pd.DataFrame(), pd.DataFrame()
        
    if not chunks:
        return pd.DataFrame(), pd.DataFrame()
        
    df = pd.concat(chunks, axis=0)
    
    if 'Sipariş Ödeme Durumu' in df.columns:
        df['Sipariş Ödeme Durumu'] = df['Sipariş Ödeme Durumu'].astype(str).str.strip()
        gecerli_odemeler = ['Ödendi', 'Parçalı Ödendi', 'Bekliyor']
        df = df[df['Sipariş Ödeme Durumu'].isin(gecerli_odemeler)]
        
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()
        
    df['Sipariş Tarihi'] = pd.to_datetime(df['Sipariş Tarihi'], errors='coerce', format='mixed')
    df = df.dropna(subset=['Sipariş Tarihi'])
    
    musteri_kolonu = 'E-posta' if 'E-posta' in df.columns else df.columns[0]
    siparis_no_kolonu = 'Sipariş Numarası' if 'Sipariş Numarası' in df.columns else ('Sipariş No' if 'Sipariş No' in df.columns else 'Sipariş ID')

    df['Sipariş Ayı'] = df['Sipariş Tarihi'].dt.to_period('M')
    df['İlk Sipariş Ayı'] = df.groupby(musteri_kolonu)['Sipariş Tarihi'].transform('min').dt.to_period('M')
    
    if 'Toplam' in df.columns:
        df['satir_cirosu'] = pd.to_numeric(df['Toplam'], errors='coerce').fillna(0)
    else:
        df['satir_cirosu'] = df['Ürün Sayısı'] * df['Ürün İndirim Fiyatı']
    
    cohort_data = df.groupby(['İlk Sipariş Ayı', 'Sipariş Ayı']).agg({musteri_kolonu: 'nunique'}).reset_index()
    cohort_data['Dönem Mesafesi'] = (cohort_data['Sipariş Ayı'] - cohort_data['İlk Sipariş Ayı']).apply(lambda x: x.n if hasattr(x, 'n') else 0)
    
    cohort_pivot = cohort_data.pivot(index='İlk Sipariş Ayı', columns='Dönem Mesafesi', values=musteri_kolonu).fillna(0)
    cohort_sizes = cohort_pivot.iloc[:, 0]
    retention_matrix = cohort_pivot.divide(cohort_sizes, axis=0) * 100
    
    siparis_bazli_ozet = df.groupby([musteri_kolonu, siparis_no_kolonu]).agg({
        'Sipariş Tarihi': 'max', 'satir_cirosu': 'sum'
    }).reset_index()
    
    bugun = pd.to_datetime('2026-06-10') 
    rfm = siparis_bazli_ozet.groupby(musteri_kolonu).agg({
        'Sipariş Tarihi': lambda x: (bugun - x.max()).days,
        siparis_no_kolonu: 'count',
        'satir_cirosu': 'sum'
    }).reset_index()
    
    rfm.columns = [musteri_kolonu, 'Recency', 'Frequency', 'Monetary']
    return retention_matrix, rfm

# ==============================================================================
# 3. KISIM: CANLI META ADS PERFORMANS ANALİZİ
# ==============================================================================
def meta_performans_cek(access_token, account_id, baslangic_tarihi, bitis_tarihi):
    if not access_token or not account_id:
        return pd.DataFrame()
    try:
        if not str(account_id).startswith('act_'):
            account_id = f"act_{account_id}"
        FacebookAdsApi.init(access_token=access_token)
        account = AdAccount(account_id)
        fields = ['adset_id', 'adset_name', 'spend', 'actions', 'action_values']
        params = {'time_range': {'since': baslangic_tarihi, 'until': bitis_tarihi}, 'level': 'adset'}
        insights = account.get_insights(fields=fields, params=params)
        data = []
        for insight in insights:
            purchases = 0
            purchase_value = 0.0
            if 'actions' in insight:
                for action in insight['actions']:
                    if action['action_type'] == 'purchase': purchases = int(action['value'])
            if 'action_values' in insight:
                for val in insight['action_values']:
                    if val['action_type'] == 'purchase': purchase_value = float(val['value'])
            harcanan = float(insight['spend'])
            data.append({
                'Reklam Seti Adı': insight['adset_name'], 'Harcanan Tutar (TL)': harcanan,
                'Satış Adedi': purchases, 'Toplam Ciro (TL)': purchase_value
            })
        return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame()