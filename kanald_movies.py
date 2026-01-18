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

def get_stream_url(url):
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.content, "html.parser")
        container = soup.find("div", {"class": "player-container"})
        
        if container and container.get("data-id"):
            media_id = container.get("data-id")
            api_url = "https://www.kanald.com.tr/actions/media"
            params = {"id": media_id, "p": "1", "pc": "1", "isAMP": "false"}
            
            r_api = requests.get(api_url, params=params)
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

def get_arsiv_page(url):
    all_items = []
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.content, "html.parser")
        
        def parse_items(page_soup):
            lst = []
            listing = page_soup.find("section", {"class": "listing-holder"})
            if listing:
                for item in listing.find_all("div", {"class": "item"}):
                    a_tag = item.find("a")
                    img_tag = item.find("img")
                    title_tag = item.find("h3", {"class": "title"})
                    
                    if a_tag and img_tag and title_tag:
                        i_url = site_base_url + a_tag.get("href")
                        i_img = img_tag.get("data-src") or img_tag.get("src")
                        i_name = title_tag.get_text().strip()
                        lst.append({"name": i_name, "img": i_img, "url": i_url})
            return lst

        pagination = soup.find("ul", {"class": "pagination"})
        if pagination:
            for page in pagination.find_all("li"):
                a = page.find("a")
                if a:
                    sub_r = requests.get(r.url + a.get("href"), timeout=10)
                    all_items += parse_items(BeautifulSoup(sub_r.content, "html.parser"))
        else:
            all_items = parse_items(soup)
    except:
        pass
    return all_items

def main():
    url = "https://www.kanald.com.tr/evde-sinema"
    movies = []
    movie_list = get_arsiv_page(url)
    
    print(f"Toplam {len(movie_list)} film bulundu.")
    
    for movie in tqdm(movie_list, desc="Evde Sinema"):
        stream_url = get_stream_url(movie["url"])
        if stream_url:
            movie["stream_url"] = stream_url
            movies.append(movie)

    data = [{"name": "Evde Sinema", "episodes": movies}]
    
    # JSON Kaydet
    json_path = os.path.join(OUTPUT_FOLDER, "evde-sinema.json")
    with open(json_path, "w+", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        
    # M3U Kaydet
    create_single_m3u(OUTPUT_FOLDER, data, "evde-sinema")

if __name__=="__main__": 
    main()
