import requests
from bs4 import BeautifulSoup
import json
import re
import os
from tqdm import tqdm

# --- AYARLAR ---
OUTPUT_FOLDER = "KanalD_Arsiv"
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

# Header (Tarayıcı Taklidi)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.kanald.com.tr/",
    "Origin": "https://www.kanald.com.tr"
}

def clean_text(text):
    if not text: return "Isimsiz_Icerik"
    # Gereksiz boşlukları ve newlineları temizle
    text = text.replace("\n", " ").replace("\r", "")
    # Dosya adını bozan karakterleri temizle
    text = re.sub(r'[<>:"/\\|?*]', '', text)
    return " ".join(text.split())

def create_m3u(category_name, series_name, episodes):
    """Her dizi/program için ayrı bir klasör ve M3U dosyası oluşturur."""
    # Klasör yapısı: KanalD_Arsiv / Kategorisi / Dizi Adi
    folder_path = os.path.join(OUTPUT_FOLDER, category_name, series_name)
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    
    file_path = os.path.join(folder_path, "playlist.m3u")
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for ep in episodes:
            f.write(f'#EXTINF:-1 tvg-logo="{ep["img"]}",{ep["name"]}\n')
            f.write(f'{ep["stream_url"]}\n')

def extract_stream_from_html(html_content):
    """
    HTML içindeki 'mediaSourcesList.push' satırlarını bulur.
    En yüksek kalitedeki m3u8 linkini döndürür.
    """
    try:
        # Regex ile gömülü JSON verisini yakala
        matches = re.findall(r'mediaSourcesList\.push\(({.*?})\);', html_content)
        
        for match in matches:
            try:
                data = json.loads(match)
                
                # 1. Tercih: HLS (m3u8)
                if data.get("Hls") and data["Hls"].get("Path"):
                    return data["Hls"]["Path"]
                
                # 2. Tercih: MP4
                if data.get("Mp4") and data["Mp4"].get("Path"):
                    return data["Mp4"]["Path"]
                    
            except:
                continue
    except:
        pass
    return None

def get_episodes(content_url):
    """Dizi veya Programın detay sayfasına girip bölümleri toplar."""
    episodes = []
    try:
        # Sayfalama varsa tümünü almak gerekir ama şimdilik ana sayfadaki listeyi alıyoruz
        # (Detaylı sayfalama için "?page=X" döngüsü eklenebilir)
        r = requests.get(content_url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.content, "html.parser")
        
        # Bölüm kartlarını bul (.item class'ı genelde ortaktır)
        items = soup.select(".listing-holder .item, .section-story .swiper-slide")
        
        for item in items:
            a_tag = item.find("a")
            if not a_tag: continue
            
            link = a_tag.get("href")
            if not link: continue
            
            # Link filtreleme (sadece video sayfaları)
            if "/bolumler/" in link or "/klipler/" in link or "/ozel-klipler/" in link:
                full_link = "https://www.kanald.com.tr" + link if link.startswith("/") else link
                
                img_tag = item.find("img")
                img_url = ""
                if img_tag:
                    img_url = img_tag.get("data-src") or img_tag.get("src") or ""
                
                title_tag = item.find("h3", class_="title") or item.find("p", class_="title")
                title = clean_text(title_tag.get_text()) if title_tag else "Bolum"
                
                episodes.append({
                    "name": title,
                    "url": full_link,
                    "img": img_url
                })
                
    except Exception as e:
        print(f"Bölüm tarama hatası: {e}")
        
    return episodes

def process_main_category(url, category_label):
    """Ana kategori sayfasını (Örn: Programlar/Arşiv) tarar."""
    print(f"\n>>> {category_label} TARANIYOR...")
    
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.content, "html.parser")
        
        # Sayfadaki tüm dizi/program kapaklarını bul
        # Kanal D yapısında genelde '.listing-holder .item' içindedir
        cards = soup.select(".listing-holder .item")
        
        print(f"Toplam {len(cards)} içerik bulundu.")
        
        for card in tqdm(cards, desc=category_label):
            a_tag = card.find("a")
            if not a_tag: continue
            
            main_link = a_tag.get("href")
            if not main_link: continue
            
            full_main_link = "https://www.kanald.com.tr" + main_link if main_link.startswith("/") else main_link
            
            # Başlık bulma
            title_el = card.find("h3", class_="title") or card.find("img")
            if not title_el: continue
            
            content_name = clean_text(title_el.get_text() if title_el.name != "img" else title_el.get("alt"))
            
            # Bu içeriğin bölümlerine git
            episode_list = get_episodes(full_main_link)
            
            valid_streams = []
            for ep in episode_list:
                # Video sayfasına gir ve mediaSourcesList'i sök
                try:
                    v_req = requests.get(ep["url"], headers=HEADERS, timeout=8)
                    stream_url = extract_stream_from_html(v_req.text)
                    
                    if stream_url:
                        ep["stream_url"] = stream_url
                        valid_streams.append(ep)
                except:
                    continue
            
            # Eğer çalışan linkler bulduysak kaydet
            if valid_streams:
                create_m3u(category_label, content_name, valid_streams)

    except Exception as e:
        print(f"Kategori hatası ({category_label}): {e}")

if __name__ == "__main__":
    # 1. GÜNCEL DİZİLER
    process_main_category("https://www.kanald.com.tr/diziler", "Diziler_Guncel")
    
    # 2. ARŞİV DİZİLER
    process_main_category("https://www.kanald.com.tr/diziler/arsiv", "Diziler_Arsiv")
    
    # 3. GÜNCEL PROGRAMLAR (Senin istediğin kısım)
    process_main_category("https://www.kanald.com.tr/programlar", "Programlar_Guncel")
    
    # 4. ARŞİV PROGRAMLAR
    process_main_category("https://www.kanald.com.tr/programlar/arsiv", "Programlar_Arsiv")
