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

def get_stream_url(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.content, "html.parser")
        container = soup.find("div", {"class": "player-container"})
        if container and container.get("data-id"):
            media_id = container.get("data-id")
            api_url = "https://www.kanald.com.tr/actions/media"
            params = {"id": media_id, "p": "1"}
            r_api = requests.get(api_url, params=params, headers=HEADERS)
            data = r_api.json().get("data")
            if data:
                path = data["media"]["link"]["securePath"].split("?")[0]
                if not path.startswith("/"): path = "/" + path
                return data["media"]["link"]["serviceUrl"] + path
        return ""
    except Exception as e:
        # print(e)
        return ""

def main():
    url = "https://www.kanald.com.tr/sinemalar"
    print(f"--- FİLMLER TARANIYOR: {url} ---")
    
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        print(f"Durum Kodu: {r.status_code}")
        soup = BeautifulSoup(r.content, "html.parser")
        
        items = soup.find_all("div", {"class": "item"})
        print(f"Bulunan Film Kartı: {len(items)}")
        
        movies = []
        for item in tqdm(items):
            a = item.find("a")
            t = item.find("h3")
            img_tag = item.find("img")
            if a and t:
                link = "https://www.kanald.com.tr" + a.get("href")
                name = t.get_text().strip()
                img = img_tag.get("data-src") or img_tag.get("src") if img_tag else ""
                
                stream = get_stream_url(link)
                if stream:
                    movies.append({"name": name, "img": img, "stream_url": stream, "url": link})
        
        if movies:
            data = [{"name": "Sinemalar", "episodes": movies}]
            with open(f"{OUTPUT_FOLDER}/kanald-sinemalar.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            create_single_m3u(OUTPUT_FOLDER, data, "kanald-sinemalar")
            print(f"Toplam {len(movies)} film kaydedildi.")
        else:
            print("Kaydedilecek film bulunamadı.")
            
    except Exception as e:
        print(f"Film Hatası: {e}")

if __name__=="__main__": 
    main()
