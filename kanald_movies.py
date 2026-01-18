import requests
from tqdm import tqdm
from bs4 import BeautifulSoup
import json
import os

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36 OPR/89.0.0.0",
    "Referer": "https://www.kanald.com.tr/"
}

def get_stream(url):
    """Film sayfasından stream linkini decompile edilen metodla çözer."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.content, "html.parser")
        # Android plugin'in kullandığı data-id yakalama yöntemi
        player = soup.find("div", {"class": "player-container"})
        media_id = player.get("data-id") if player else None
        
        if media_id:
            api = "https://www.kanald.com.tr/actions/media"
            res = requests.get(api, params={"id": media_id, "p": "1"}, headers=HEADERS).json()
            link_data = res.get("data", {}).get("media", {}).get("link", {})
            return f"{link_data.get('serviceUrl')}{link_data.get('securePath').split('?')[0]}"
    except: return None
    return None

def main():
    url = "https://www.kanald.com.tr/sinemalar"
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.content, "html.parser")
    items = soup.find_all("div", {"class": "item"})
    
    movies = []
    for item in tqdm(items, desc="Filmler"):
        a = item.find("a")
        if a:
            link = "https://www.kanald.com.tr" + a.get("href")
            stream = get_stream(link)
            if stream:
                movies.append({
                    "name": item.get_text().strip(),
                    "stream_url": stream,
                    "img": item.find("img").get("src") if item.find("img") else ""
                })
    
    if movies:
        data = [{"name": "Sinemalar", "episodes": movies}]
        with open("KanalD/sinemalar.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Başarılı: {len(movies)} film eklendi.")
    else:
        print("Film bulunamadı.")

if __name__ == "__main__":
    main()
