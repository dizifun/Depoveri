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
    def create_single_m3u(*args): pass
    def create_m3us(*args): pass

OUTPUT_FOLDER = "KanalD"
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

site_base_url = "https://www.kanald.com.tr"

# Decompile kodlarındaki profesyonel headerlar
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36 OPR/89.0.0.0",
    "Referer": site_base_url + "/",
    "X-Requested-With": "XMLHttpRequest"
}

def clean_title(text):
    """'Daha Sonra İzle' gibi gereksiz metinleri temizler."""
    if not text: return "Bilinmeyen Başlık"
    text = text.replace("Daha Sonra İzle", "").replace("Şimdi İzle", "")
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def get_stream_url(media_id):
    """KanalD API'sinden gerçek stream linkini çözer."""
    api_url = f"{site_base_url}/actions/media"
    params = {"id": media_id, "p": "1", "pc": "1", "isAMP": "false"}
    try:
        r = requests.get(api_url, params=params, headers=HEADERS, timeout=10)
        data = r.json().get("data", {}).get("media", {}).get("link", {})
        if data.get("type") == "video/dailymotion": return ""
        
        service_url = data.get("serviceUrl", "")
        path = data.get("securePath", "").split("?")[0]
        if not path.startswith("/"): path = "/" + path
        return f"{service_url}{path}"
    except:
        return ""

def get_episodes_from_page(url):
    """Bölüm sayfasındaki tüm bölümleri ve linkleri toplar."""
    episodes = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.content, "html.parser")
        items = soup.find_all("div", {"class": "item"})
        for item in items:
            a_tag = item.find("a")
            if not a_tag: continue
            
            href = a_tag.get("href", "")
            if "/bolumler/" not in href and "/klipler/" not in href: continue
            
            full_url = site_base_url + href if href.startswith("/") else href
            title_tag = item.find("h3") or item.find("div", {"class": "title"})
            img_tag = item.find("img")
            
            episodes.append({
                "name": clean_title(title_tag.get_text()) if title_tag else "Bölüm",
                "url": full_url,
                "img": img_tag.get("data-src") or img_tag.get("src") if img_tag else ""
            })
    except: pass
    return episodes

def get_main_list(url):
    """Dizi veya program listesini ve sayfalama linklerini tarar."""
    results = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.content, "html.parser")
        
        # Sayfalama linklerini düzeltme (Invalid URL hatası çözümü)
        page_links = [url]
        pagination = soup.find("ul", {"class": "pagination"})
        if pagination:
            for a in pagination.find_all("a"):
                href = a.get("href", "")
                if href:
                    # Link eksikse (örn: ?page=2) tam URL'ye çevir
                    full_p = site_base_url + href if href.startswith("/") else url.split("?")[0] + href
                    if full_p not in page_links: page_links.append(full_p)

        for p_url in page_links:
            r_p = requests.get(p_url, headers=HEADERS, timeout=10)
            soup_p = BeautifulSoup(r_p.content, "html.parser")
            for item in soup_p.find_all("div", {"class": "item"}):
                a = item.find("a")
                if a and a.get("href"):
                    href = a.get("href")
                    results.append({
                        "name": clean_title(item.get_text()),
                        "url": site_base_url + href if href.startswith("/") else href,
                        "img": item.find("img").get("src") if item.find("img") else ""
                    })
    except: pass
    return results

def main():
    categories = [
        ("https://www.kanald.com.tr/diziler/arsiv", "arsiv-diziler"),
        ("https://www.kanald.com.tr/programlar/arsiv", "arsiv-programlar")
    ]
    
    for url, name in categories:
        print(f"--- {name} taranıyor ---")
        items = get_main_list(url)
        final_data = []
        for item in tqdm(items[:20], desc=name): # Örnek için ilk 20, isterseniz sınırı kaldırın
            eps = get_episodes_from_page(item["url"])
            valid_eps = []
            for ep in eps:
                try:
                    r_ep = requests.get(ep["url"], headers=HEADERS, timeout=5)
                    soup_ep = BeautifulSoup(r_ep.content, "html.parser")
                    # Decompile kodundaki data-id yakalama mantığı
                    player = soup_ep.find("div", {"class": "player-container"})
                    m_id = player.get("data-id") if player else None
                    if m_id:
                        stream = get_stream_url(m_id)
                        if stream:
                            ep["stream_url"] = stream
                            valid_eps.append(ep)
                except: continue
            if valid_eps:
                item["episodes"] = valid_eps
                final_data.append(item)
        
        with open(f"{OUTPUT_FOLDER}/{name}.json", "w", encoding="utf-8") as f:
            json.dump(final_data, f, ensure_ascii=False, indent=4)
        create_single_m3u(OUTPUT_FOLDER, final_data, name)

if __name__ == "__main__":
    main()
