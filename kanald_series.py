import requests
from tqdm import tqdm
from bs4 import BeautifulSoup
import json
import os
import re

# Yardımcı kütüphane kontrolü
try:
    from jsontom3u import create_single_m3u, create_m3us
except ImportError:
    # Eğer dosya yoksa basit bir placeholder fonksiyon
    def create_single_m3u(*args): pass
    def create_m3us(*args): pass

OUTPUT_FOLDER = "KanalD"
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

site_base_url = "https://www.kanald.com.tr"

# Decompile kodlarındaki headerlar ile güncellendi
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36 OPR/89.0.0.0",
    "Referer": site_base_url + "/",
    "X-Requested-With": "XMLHttpRequest"
}

def clean_title(text):
    if not text: return ""
    text = text.replace("Daha Sonra İzle", "").replace("Şimdi İzle", "")
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def get_stream_url(media_id):
    """
    Decompile edilen 'Dosyalar' ve 'Yanit' sınıflarının kullandığı 
    yeni API endpoint yapısı.
    """
    api_url = f"{site_base_url}/actions/media"
    params = {
        "id": media_id,
        "p": "1",
        "pc": "1",
        "isAMP": "false"
    }
    try:
        r = requests.get(api_url, params=params, headers=HEADERS, timeout=10)
        res_json = r.json()
        
        # Decompile kodundaki data -> items -> files hiyerarşisi
        data = res_json.get("data", {})
        media_link = data.get("media", {}).get("link", {})
        
        if media_link.get("type") == "video/dailymotion":
            return ""
            
        service_url = media_link.get("serviceUrl", "")
        secure_path = media_link.get("securePath", "").split("?")[0]
        
        if not secure_path.startswith("/"):
            secure_path = "/" + secure_path
            
        return f"{service_url}{secure_path}"
    except:
        return ""

def get_episodes_from_api(content_url):
    """
    Kanal D'nin yeni sezona göre bölümleri getiren yapısı.
    """
    episodes = []
    try:
        r = requests.get(content_url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.content, "html.parser")
        
        # Sitede 'data-id' içeren tüm bölüm kartlarını bulur
        items = soup.find_all("div", {"class": "item"})
        for item in items:
            a_tag = item.find("a")
            if not a_tag: continue
            
            href = a_tag.get("href", "")
            if "/bolumler/" not in href and "/klipler/" not in href:
                continue
                
            full_url = site_base_url + href if href.startswith("/") else href
            title_tag = item.find("h3") or item.find("div", {"class": "title"})
            title = clean_title(title_tag.get_text()) if title_tag else "Bölüm"
            
            img_tag = item.find("img")
            img = img_tag.get("data-src") or img_tag.get("src") if img_tag else ""
            
            episodes.append({
                "name": title,
                "url": full_url,
                "img": img
            })
    except Exception as e:
        print(f"Hata: {content_url} bölümleri alınamadı: {e}")
    
    return episodes

def get_archive_items(category_url):
    """
    Ana sayfadaki (Programlar/Diziler) tüm içeriği yakalar.
    """
    results = []
    try:
        r = requests.get(category_url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.content, "html.parser")
        
        # Ana listedeki kartlar
        cards = soup.select(".item, .card-item")
        for card in cards:
            a_tag = card.find("a")
            if not a_tag: continue
            
            link = a_tag.get("href", "")
            if link.startswith("/"):
                link = site_base_url + link
            
            img_tag = card.find("img")
            img = img_tag.get("src") or img_tag.get("data-src") if img_tag else ""
            title = img_tag.get("alt") if img_tag else "İçerik"
            
            results.append({
                "name": clean_title(title),
                "url": link,
                "img": img
            })
    except:
        pass
    return results

def main():
    # Decompile kodundaki MainPageData listesi ile eşleşen hedefler
    targets = [
        ("https://www.kanald.com.tr/programlar", "guncel-programlar"),
        ("https://www.kanald.com.tr/diziler", "guncel-diziler"),
        ("https://www.kanald.com.tr/diziler/arsiv", "arsiv-diziler")
    ]
    
    for url, name in targets:
        print(f"--- {name.upper()} Taranıyor ---")
        content_list = get_archive_items(url)
        final_data = []

        for content in tqdm(content_list, desc=name):
            episodes = get_episodes_from_api(content["url"])
            if not episodes: continue
            
            valid_episodes = []
            for ep in episodes:
                # Bölüm sayfasından media_id çekme (Decompile load$bolumler$3 mantığı)
                try:
                    ep_req = requests.get(ep["url"], headers=HEADERS, timeout=10)
                    ep_soup = BeautifulSoup(ep_req.content, "html.parser")
                    
                    # Player container'daki data-id en güvenilir yoldur
                    player_div = ep_soup.find("div", {"class": "player-container"})
                    media_id = player_div.get("data-id") if player_div else None
                    
                    if not media_id:
                        # Fallback: embed linkinden çekme
                        embed_link = ep_soup.find("link", {"itemprop": "embedURL"})
                        if embed_link:
                            media_id = embed_link.get("href", "").split("/")[-1]
                    
                    if media_id:
                        stream_url = get_stream_url(media_id)
                        if stream_url:
                            ep["stream_url"] = stream_url
                            valid_episodes.append(ep)
                except:
                    continue
            
            if valid_episodes:
                content["episodes"] = valid_episodes
                final_data.append(content)

        # Kayıt işlemleri
        if final_data:
            json_path = os.path.join(OUTPUT_FOLDER, f"{name}.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(final_data, f, ensure_ascii=False, indent=4)
            create_single_m3u(OUTPUT_FOLDER, final_data, name)
            print(f"Başarılı: {name} kaydedildi.")

if __name__ == "__main__":
    main()
