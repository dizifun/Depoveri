import requests
from bs4 import BeautifulSoup
import json
import os
import re
from tqdm import tqdm
import subprocess
from datetime import datetime
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- AYARLAR ---
BASE_URL = "https://www.startv.com.tr"
ROOT_DIR = "startv"
DIRS = {
    "series": os.path.join(ROOT_DIR, "dizi"),
    "programs": os.path.join(ROOT_DIR, "program")
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Referer": BASE_URL
}

def run_command(command):
    try:
        subprocess.run(command, shell=True, check=False, stdout=subprocess.DEVNULL)
    except: pass

def get_items_page(url):
    print(f"🌍 Sayfa Taranıyor: {url}")
    item_list = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        soup = BeautifulSoup(r.content, "html.parser")
        items = soup.find_all("div", {"class": "poster-card"})

        for item in items:
            try:
                name_div = item.find("div", {"class":"text-left"})
                if not name_div: continue
                item_name = name_div.get_text().strip()
                
                a_tag = item.find("a")
                if not a_tag: continue
                item_url = BASE_URL + a_tag.get("href")
                
                img_tag = item.find("img")
                item_img = img_tag.get("src") if img_tag else ""
                
                item_list.append({"name": item_name, "img": item_img, "url": item_url})
            except: continue
    except Exception as e: print(f"❌ Hata: {e}")
    print(f"✅ {len(item_list)} içerik bulundu.")
    return item_list

def get_api_path(url):
    """HTML içinden gizli API yolunu bulur"""
    try:
        r = requests.get(url + "/bolumler", headers=HEADERS, timeout=10, verify=False)
        # 1. Yöntem: apiUrl":"/api/..."
        match = re.search(r'apiUrl\\?":\\?"(.*?)\\?"', r.text)
        if match: return match.group(1).replace("\\", "")
    except: pass
    return None

def get_episodes(api_path, show_name):
    episode_list = []
    if not api_path: return []
    
    # URL bazen /api ile başlar bazen başlamaz, düzeltelim
    if not api_path.startswith("/api"): api_path = "/api" + api_path
    
    full_api_url = BASE_URL + api_path
    params = {"sort": "episodeNo asc", "limit": "100", "skip": 0}
    
    print(f"   🔎 {show_name} bölümleri çekiliyor...")
    
    while True:
        try:
            r = requests.get(full_api_url, params=params, headers=HEADERS, timeout=10, verify=False)
            if r.status_code != 200: break
            
            data = r.json()
            items = data.get("items", [])
            if not items: break

            for item in items:
                title = item.get("title", "")
                ep_no = item.get("episodeNo", "")
                name = f"{ep_no}. Bölüm - {title}" if ep_no else title
                
                img = ""
                if item.get("image"):
                    img = "https://media.startv.com.tr/star-tv" + item["image"]["fullPath"]
                
                # Video ID var mı?
                stream_url = ""
                if "video" in item and item["video"] and "referenceId" in item["video"]:
                    ref_id = item["video"]["referenceId"]
                    # StarTV Stream Link Yapısı
                    stream_url = f"https://dygvideo.dygdigital.com/api/redirect?PublisherId=1&ReferenceId=StarTV_{ref_id}&SecretKey=NtvApiSecret2014*&.m3u8"
                
                if stream_url:
                    episode_list.append({"name": name, "img": img, "stream_url": stream_url})

            if len(items) < 100: break
            params["skip"] += 100
        except: break
            
    print(f"   ✅ {len(episode_list)} oynatılabilir bölüm alındı.")
    return episode_list

def main():
    for d in DIRS.values(): os.makedirs(d, exist_ok=True)
    
    # Hem dizi hem program
    targets = [
        {"url": f"{BASE_URL}/dizi", "type": "series"},
        {"url": f"{BASE_URL}/program", "type": "programs"}
    ]
    
    all_data = {"series": [], "programs": []}

    for t in targets:
        items = get_items_page(t["url"])
        
        for item in tqdm(items, desc=f"{t['type']} İşleniyor"):
            api_path = get_api_path(item["url"])
            if not api_path: continue
            
            episodes = get_episodes(api_path, item["name"])
            
            if episodes:
                show_data = {"name": item["name"], "img": item["img"], "episodes": episodes}
                slug = re.sub(r'[^a-z0-9-]', '', item['name'].lower().replace(" ", "-").replace("ç","c").replace("ğ","g").replace("ı","i").replace("ö","o").replace("ş","s").replace("ü","u"))
                
                target_dir = DIRS[t["type"]]
                # JSON
                with open(os.path.join(target_dir, f"{slug}.json"), "w", encoding="utf-8") as f:
                    json.dump(show_data, f, ensure_ascii=False, indent=4)
                
                # M3U
                with open(os.path.join(target_dir, f"{slug}.m3u"), "w", encoding="utf-8") as f:
                    f.write("#EXTM3U\n")
                    for ep in episodes:
                        f.write(f'#EXTINF:-1 tvg-logo="{ep["img"]}",{ep["name"]}\n{ep["stream_url"]}\n')
                
                all_data[t["type"]].append(show_data)

    # Toplu Dosyalar
    print("\n📦 Toplu listeler oluşturuluyor...")
    for key, data in all_data.items():
        if not data: continue
        with open(os.path.join(ROOT_DIR, f"startv-{key}.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        with open(os.path.join(ROOT_DIR, f"startv-{key}.m3u"), "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for show in data:
                for ep in show["episodes"]:
                    f.write(f'#EXTINF:-1 tvg-logo="{ep["img"]}" group-title="{show["name"]}",{ep["name"]}\n{ep["stream_url"]}\n')

    # GITHUB
    print("\n🚀 GitHub'a Yükleniyor...")
    run_command("git add --all")
    run_command("git add startv/*")
    run_command(f'git commit -m "StarTV Guncelleme {datetime.now().strftime("%d-%m")}"')
    run_command("git push")
    print("✅ İşlem Tamamlandı.")

if __name__ == "__main__":
    main()

