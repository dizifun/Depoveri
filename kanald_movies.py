import requests
from tqdm import tqdm
from bs4 import BeautifulSoup
import json
import os

try:
    from jsontom3u import create_single_m3u
except ImportError:
    print("HATA: 'jsontom3u.py' dosyası bulunamadı!")
    exit(1)

OUTPUT_FOLDER = "KanalD"
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

site_base_url = "https://www.kanald.com.tr"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
}

def get_stream_url(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.content, "html.parser")
        container = soup.find("div", {"class": "player-container"})
        
        if container and container.get("data-id"):
            media_id = container.get("data-id")
            api_url = "https://www.kanald.com.tr/actions/media"
            params = {"id": media_id, "p": "1", "pc": "1", "isAMP": "false"}
            
            r_api = requests.get(api_url, params=params, headers=HEADERS)
            data = r_api.json()["data"]
            
            if data["media"]["link"]["type"] == "video/dailymotion":
                return ""
            
            path = data["media"]["link"]["securePath"].split("?")[0]
            if not path.startswith("/"):
                path = "/" + path
            return data["media"]["link"]["serviceUrl"] + path
        return ""
    except:
        return ""

def get_movies_page(url):
    all_items = []
    print(f"Sinemalar taranıyor: {url}")
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.content, "html.parser")
        
        # Sinema sayfasındaki listeyi bul
        items = soup.find_all("div", {"class": "item"})
        print(f"Bulunan film kartı sayısı: {len(items)}")

        for item in items:
            a_tag = item.find("a")
            img_tag = item.find("img")
            title_tag = item.find("h3", {"class": "title"})
            
            if a_tag and title_tag:
                i_url = site_base_url + a_tag.get("href")
                i_name = title_tag.get_text().strip()
                i_img = ""
                if img_tag:
                    i_img = img_tag.get("data-src") or img_tag.get("src") or ""
                
                # Film linki olup olmadığını basitçe kontrol et
                # (URL içinde genelde 'sinemalar' geçer ama bazen direkt film adı olabilir)
                all_items.append({"name": i_name, "img": i_img, "url": i_url})

    except Exception as e:
        print(f"Hata: {e}")
        pass
        
    unique_items = {v['url']: v for v in all_items}.values()
    return list(unique_items)

def main():
    # YENİ LİNK
    url = "https://www.kanald.com.tr/sinemalar"
    movies = []
    movie_list = get_movies_page(url)
    
    for movie in tqdm(movie_list, desc="Sinemalar"):
        stream_url = get_stream_url(movie["url"])
        if stream_url:
            movie["stream_url"] = stream_url
            movies.append(movie)

    if movies:
        data = [{"name": "Sinemalar", "episodes": movies}]
        
        json_path = os.path.join(OUTPUT_FOLDER, "kanald-sinemalar.json")
        with open(json_path, "w+", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            
        create_single_m3u(OUTPUT_FOLDER, data, "kanald-sinemalar")
        print(f"İşlem tamam! {len(movies)} film eklendi.")
    else:
        print("Çalışan film bulunamadı.")

if __name__=="__main__": 
    main()
