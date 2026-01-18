import requests
from tqdm import tqdm
from bs4 import BeautifulSoup
import json
import os

# jsontom3u kontrolü
try:
    from jsontom3u import create_single_m3u, create_m3us
except ImportError:
    print("HATA: 'jsontom3u.py' dosyası bulunamadı!")
    exit(1)

OUTPUT_FOLDER = "KanalD"
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

site_base_url = "https://www.kanald.com.tr"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Referer": "https://www.kanald.com.tr/"
}

def clean_text(text):
    """Metin içindeki gereksiz 'Daha Sonra İzle', boşluk ve newlineları temizler."""
    if not text: return ""
    # İstenmeyen kelimeleri sil
    text = text.replace("Daha Sonra İzle", "").replace("Şimdi İzle", "")
    # Satır sonlarını boşluğa çevir
    text = text.replace("\n", " ").replace("\r", "").replace("\t", "")
    # Fazla boşlukları tek boşluğa düşür ve kenarları kırp
    return " ".join(text.split()).strip()

def get_stream_url(media_id):
    url = "https://www.kanald.com.tr/actions/media"
    params = {"id": media_id, "p": "1", "pc": "1", "isAMP": "false"}
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=10)
        data = r.json().get("data")
        
        if not data or "media" not in data or "link" not in data["media"]:
            return ""

        if data["media"]["link"]["type"] == "video/dailymotion":
            return ""
        
        path = data["media"]["link"]["securePath"].split("?")[0]
        if path[0] != "/":
            path = "/" + path
        full_url = data["media"]["link"]["serviceUrl"] + path
        return full_url
    except:
        return ""

def parse_bolum_page(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.content, "html.parser")
        link_tag = soup.find("link", {"itemprop": "embedURL"})
        if link_tag:
            return link_tag.get("href").split("/")[-1]
        return ""
    except:
        return ""

def get_bolumler_page(url):
    all_items = []
    # Hem ana sayfa hem bölümler sayfasını dene
    urls_to_check = [url, url + "/bolumler"]
    seen_urls = set()

    for check_url in urls_to_check:
        if check_url in seen_urls: continue
        seen_urls.add(check_url)
        
        try:
            r = requests.get(check_url, headers=HEADERS, timeout=10)
            if r.status_code != 200: continue
            
            soup = BeautifulSoup(r.content, "html.parser")
            
            # Kartları bul
            items = soup.find_all("div", {"class": "item"})
            
            for item in items:
                a_tag = item.find("a")
                
                # Başlığı bulmak için farklı yerlere bak
                title_tag = item.find("h3") or item.find("div", {"class": "title"}) or item.find("span", {"class": "title"})
                img_tag = item.find("img")

                if a_tag:
                    href = a_tag.get("href")
                    if href and ("/bolumler/" in href or "/klipler/" in href):
                        full_link = site_base_url + href if href.startswith("/") else href
                        
                        # İsim temizleme işlemi
                        raw_name = ""
                        if title_tag:
                            raw_name = title_tag.get_text()
                        elif a_tag.get("title"):
                            raw_name = a_tag.get("title")
                        
                        clean_name = clean_text(raw_name)
                        
                        # Eğer isim boşsa ve linkte varsa linkten üret (Son çare)
                        if not clean_name:
                            clean_name = href.split("/")[-1].replace("-", " ").title()

                        img = ""
                        if img_tag:
                            img = img_tag.get("data-src") or img_tag.get("src")
                        
                        all_items.append({"name": clean_name, "img": img or "", "url": full_link})
        except:
            pass
            
    unique_items = {v['url']: v for v in all_items}.values()
    return list(unique_items)

def get_archive_list(start_url):
    all_series = []
    print(f"--- ARŞİV TARANIYOR: {start_url} ---")
    
    try:
        r = requests.get(start_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.content, "html.parser")
        
        # Sayfalama: Tüm sayfa numaralarını bul
        page_links = [start_url]
        pagination = soup.find("ul", {"class": "pagination"})
        
        if pagination:
            # Pagination içindeki tüm linkleri topla
            for li in pagination.find_all("li"):
                a = li.find("a")
                if a and a.get("href"):
                    href = a.get("href")
                    # href "?p=2" gibi gelebilir
                    if href.startswith("?"):
                        base = start_url.split("?")[0]
                        full_link = base + href
                    elif href.startswith("/"):
                        full_link = site_base_url + href
                    else:
                        full_link = href
                    
                    if full_link not in page_links:
                        page_links.append(full_link)
        
        # Tekrarları önle ve sırala
        page_links = sorted(list(set(page_links)))
        print(f"Toplam {len(page_links)} arşiv sayfası gezilecek.")
        
        # Sayfaları gez
        for page_url in page_links:
            try:
                r_page = requests.get(page_url, headers=HEADERS, timeout=10)
                s_page = BeautifulSoup(r_page.content, "html.parser")
                
                items = s_page.find_all("div", {"class": "item"})
                
                for item in items:
                    a_tag = item.find("a")
                    t_tag = item.find("h3") or item.find("div", {"
