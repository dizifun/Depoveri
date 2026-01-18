import requests
from tqdm import tqdm
from bs4 import BeautifulSoup
import json
import os
import re

# formatting toolkit for saving lists
try:
    from jsontom3u import create_single_m3u, create_m3us
except ImportError:
    def create_single_m3u(*args): pass
    def create_m3us(*args): pass

OUTPUT_FOLDER = "KanalD"
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

site_base_url = "https://www.kanald.com.tr"

# Synchronized with decompiled headers for mobile emulation
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36 OPR/89.0.0.0",
    "Referer": site_base_url + "/",
    "X-Requested-With": "XMLHttpRequest"
}

def clean_title(text):
    if not text: return "Bilinmeyen Başlık"
    # Remove metadata text that appears in parsed titles
    text = text.replace("Daha Sonra İzle", "").replace("Şimdi İzle", "")
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def get_stream_url(media_id):
    """Resolves stream using the dedicated actions/media API identified in Kotlin files."""
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
    """Parses individual episodes from a series page."""
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
    """Traverses main archives and handles pagination fix for partial URLs."""
    results = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.content, "html.parser")
        
        # Pagination handling to prevent 'Invalid URL' errors
        page_links = [url]
        pagination = soup.find("ul", {"class": "pagination"})
        if pagination:
            for a in pagination.find_all("a"):
                href = a.get("href", "")
                if href:
                    # Fix: Ensure partial links like '?page=2' are prefixed with site_base_url
                    full_p = site_base_url + href if href.startswith("/") else url.split("?")[0] + href
                    if full_p not in page_links: page_links.append(full_p)

        for p_url in page_links:
            r_p = requests.get(p_url, headers=HEADERS, timeout=10)
            soup_p = BeautifulSoup(r_p.content, "html.parser")
            for item in soup_p.find_all("div", {"class": "item"}):
                a = item.find("a")
                if a and a.get("href"):
                    href = a.get("href")
                    img_tag = item.find("img")
                    title_tag = item.find("h3", {"class": "title"})
                    results.append({
                        "name": clean_title(title_tag.get_text()) if title_tag else clean_title(item.get_text()),
                        "url": site_base_url + href if href.startswith("/") else href,
                        "img": img_tag.get("src") if img_tag else ""
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
        for item in tqdm(items, desc=name): 
            eps = get_episodes_from_page(item["url"])
            valid_eps = []
            for ep in eps:
                try:
                    r_ep = requests.get(ep["url"], headers=HEADERS, timeout=5)
                    soup_ep = BeautifulSoup(r_ep.content, "html.parser")
                    # Utilize the data-id parsing logic found in the decompiled code
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
        
        # Save results to output folder
        with open(f"{OUTPUT_FOLDER}/{name}.json", "w", encoding="utf-8") as f:
            json.dump(final_data, f, ensure_ascii=False, indent=4)
        create_single_m3u(OUTPUT_FOLDER, final_data, name)

if __name__ == "__main__":
    main()
