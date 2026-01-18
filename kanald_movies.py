
import requests
from tqdm import tqdm
from bs4 import BeautifulSoup
import json
import os

try:
    from jsontom3u import create_single_m3u
except ImportError:
    print("HATA: jsontom3u bulunamadı")
    exit(1)

OUTPUT_FOLDER = "KanalD"
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Referer": "https://www.kanald.com.tr/"
}

def clean_text(text):
    if not text: return ""
    text = text.replace("Daha Sonra İzle", "").replace("Şimdi İzle", "")
    return " ".join(text.split()).strip()

def get_stream_url(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.content, "html.parser")
        
        media_id = None
        # Yöntem 1: Data-ID
        container = soup.find("div", {"class": "player-container"})
        if container: media_id = container.get("data-id")
            
        # Yöntem 2: Embed URL
        if not media_id:
            link_embed = soup.find("link", {"itemprop": "embedURL"})
            if link_embed:
                href = link_embed.get("href")
                if href: media_id = href.split("/")[-1]

        if media_id:
            api_url = "https://www.kanald.com.tr/actions/media"
            params = {"id": media_id, "p": "1"}
            r_api = requests.get(api_url, params=params, headers=HEADERS)
            data = r_api.json().get("data")
            if data and "media" in data:
                path = data["media"]["link"]["securePath"].split("?")[0]
                if not path.startswith("/"): path = "/" + path
                return data["media"]["link"]["serviceUrl"] + path
        return ""
    except:
        return ""

def main():
    url = "https://www.kanald.com.tr/sinemalar"
    print(f"--- FİLMLER TARANIYOR: {url} ---")
    
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.content, "html.parser")
        
        items = soup.find_all("div", {"class": "item"})
        movies = []
        
        for item in tqdm(items):
            a = item.find("a")
            # Başlık temizleme
            t = item.find("h3") or item.find("div", {"class": "title"})
            img_tag = item.find("img")
            
            if a:
                link = "https://www.kanald.com.tr" + a.get("href")
                
                raw_name = ""
                if t: raw_name = t.get_text()
                else: raw_name = a.get("title") or "Bilinmeyen Film"
                
                name = clean_text(raw_name)
                img = img_tag.get("data-src") or img_tag.get("src") if img_tag else ""
                
                stream = get_stream_url(link)
                if stream:
                    movies.append({"name": name, "img": img, "stream_url": stream, "url": link})
        
        if movies:
            data = [{"name": "Sinemalar", "episodes": movies}]
            json_path = os.path.join(OUTPUT_FOLDER, "kanald-sinemalar.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            create_single_m3u(OUTPUT_FOLDER, data, "kanald-sinemalar")
            print(f"Toplam {len(movies)} film başarıyla eklendi.")
        else:
            print("Kaydedilecek film bulunamadı.")
            
    except Exception as e:
        print(f"Film Hatası: {e}")

if __name__=="__main__": 
    main()
