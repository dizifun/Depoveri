import requests
from tqdm import tqdm
from bs4 import BeautifulSoup
import json
import os

# jsontom3u dosyasını import et
try:
    from jsontom3u import create_single_m3u, create_m3us
except ImportError:
    print("HATA: 'jsontom3u.py' dosyası bulunamadı!")
    exit(1)

# Çıktıların gideceği klasör
OUTPUT_FOLDER = "KanalD"

if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

site_base_url = "https://www.kanald.com.tr"

def get_stream_url(media_id):
    url = "https://www.kanald.com.tr/actions/media"
    params = {"id": media_id, "p": "1", "pc": "1", "isAMP": "false"}
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()["data"]
        if data["media"]["link"]["type"] == "video/dailymotion":
            return ""
        else:
            path = data["media"]["link"]["securePath"].split("?")[0]
            if path[0] != "/":
                path = "/" + path
            full_url = data["media"]["link"]["serviceUrl"] + path
            return full_url
    except:
        return ""

def parse_bolum_page(url):
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.content, "html.parser")
        link_tag = soup.find("link", {"itemprop": "embedURL"})
        if link_tag:
            return link_tag.get("href").split("/")[-1]
        return ""
    except:
        return ""

def parse_bolumler_page(url):
    item_list = []
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.content, "html.parser")
        listing = soup.find("section", {"class": "listing-holder"})
        if not listing: return []
        
        items = listing.find_all("div", {"class": "item"})
        for item in items:
            a_tag = item.find("a")
            img_tag = item.find("img")
            title_tag = item.find("h3", {"class": "title"})
            
            if a_tag and img_tag and title_tag:
                item_url = site_base_url + a_tag.get("href")
                item_img = img_tag.get("data-src") or img_tag.get("src")
                item_name = title_tag.get_text().strip()
                item_list.append({"name": item_name, "img": item_img, "url": item_url})
    except:
        pass
    return item_list

def get_bolumler_page(url):
    all_items = []
    url = url + "/bolumler"
    try:
        r = requests.get(url, allow_redirects=False, timeout=10)
        if r.status_code == 200:
            soup = BeautifulSoup(r.content, "html.parser")
            pagination = soup.find("ul", {"class": "pagination"})
            if pagination:
                pages = pagination.find_all("li")
                for page in pages:
                    a_tag = page.find("a")
                    if not a_tag: continue
                    page_url = r.url + a_tag.get("href")
                    all_items += parse_bolumler_page(page_url)
            else:
                all_items = parse_bolumler_page(url)
    except:
        pass
    return all_items

def get_arsiv_page(url):
    all_items = []
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.content, "html.parser")
        
        def parse_arsiv(page_url):
            lst = []
            try:
                r_sub = requests.get(page_url, timeout=10)
                s_sub = BeautifulSoup(r_sub.content, "html.parser")
                listing = s_sub.find("section", {"class": "listing-holder"})
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
            except:
                pass
            return lst

        pagination = soup.find("ul", {"class": "pagination"})
        if pagination:
            for page in pagination.find_all("li"):
                a_tag = page.find("a")
                if a_tag:
                    full_link = r.url.split("?")[0] + a_tag.get("href") if "?" in r.url else r.url + a_tag.get("href")
                    # Basit fix: pagination linkleri bazen tam bazen relative gelebilir, burada basit tutuyoruz
                    # Genelde "?p=2" şeklindedir
                    all_items += parse_arsiv(site_base_url + a_tag.get("href") if a_tag.get("href").startswith("/") else r.url + a_tag.get("href"))
        else:
            all_items = parse_arsiv(url)
    except:
        pass
    return all_items

def main(url, name):
    data = []
    series_list = get_arsiv_page(url)
    print(f"Toplam {len(series_list)} içerik bulundu: {name}")
    
    for serie in tqdm(series_list, desc=name):
        episodes = get_bolumler_page(serie["url"])
        if episodes:
            temp_serie = serie.copy()
            temp_serie["episodes"] = []
            
            # Son 5 bölümü alarak test edebilirsin, tümünü almak için [:5] kısmını sil.
            # Hız kazanmak için şu an tümünü alıyoruz:
            for episode in episodes:
                media_url = parse_bolum_page(episode["url"])
                stream_url = get_stream_url(media_url)
                if stream_url and stream_url != " ":
                    episode["stream_url"] = stream_url
                    temp_serie["episodes"].append(episode)
            
            if temp_serie["episodes"]:
                data.append(temp_serie)

    # Dosyaları KanalD klasörüne kaydet
    create_single_m3u(OUTPUT_FOLDER, data, name)
    
    json_path = os.path.join(OUTPUT_FOLDER, f"{name}.json")
    with open(json_path, "w+", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        
    # Alt klasörleme (KanalD/arsiv-diziler/DiziAdi/playlist.m3u)
    sub_folder = os.path.join(OUTPUT_FOLDER, name)
    create_m3us(sub_folder, data)

if __name__ == "__main__":
    print("--- DİZİLER BAŞLIYOR ---")
    main("https://www.kanald.com.tr/diziler/arsiv", "arsiv-diziler")
    
    print("--- PROGRAMLAR BAŞLIYOR ---")
    main("https://www.kanald.com.tr/programlar/arsiv", "arsiv-programlar")
