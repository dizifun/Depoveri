import requests
from bs4 import BeautifulSoup
import json
import os
import re
from tqdm import tqdm
import subprocess
from datetime import datetime

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
        subprocess.run(command, shell=True, check=False)
    except: pass

def get_items_page(url):
    """Diziler/Programlar sayfasındaki kutuları tarar"""
    print(f"🌍 Sayfa Taranıyor: {url}")
    item_list = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.content, "html.parser")
        items = soup.find_all("div", {"class": "poster-card"})

        for item in items:
            try:
                name_div = item.find("div", {"class":"text-left"})
                if not name_div: continue
                
                item_name = name_div.get_text().strip()
                img_tag = item.find("img")
                item_img = img_tag.get("src") if img_tag else ""
                
                a_tag = item.find("a")
                if not a_tag: continue
                item_url = BASE_URL + a_tag.get("href")
                
                item_list.append({
                    "name": item_name, 
                    "img": item_img,
                    "url": item_url
                })
            except: continue
    except Exception as e:
        print(f"❌ Hata: {e}")

    print(f"✅ {len(item_list)} içerik bulundu.")
    return item_list

def get_api_path(url):
    """Dizi sayfasından gizli API linkini bulur"""
    try:
        r = requests.get(url + "/bolumler", headers=HEADERS, timeout=10)
        # Regex ile apiUrl:"/api/..." kısmını yakala
        match = re.search(r'apiUrl\\":\\"(.*?)\\"', r.text)
        if match:
            return match.group(1).replace("\\", "")
    except: pass
    return None

def get_episodes_from_api(api_path):
    """API'den bölümleri çeker (Şeffaf Mod)"""
    episode_list = []
    if not api_path: return []

    full_api_url = BASE_URL + api_path
    params = {"sort": "episodeNo asc", "limit": "100", "skip": 0}
    
    print(f"   📡 API Bağlanıyor: {api_path}")
    
    while True:
        try:
            r = requests.get(full_api_url, params=params, headers=HEADERS, timeout=10)
            data = r.json()
            items = data.get("items", [])
            
            if not items: break

            for item in items:
                title = item.get("title", "")
                ep_no = item.get("episodeNo", "")
                name = f"{ep_no}. Bölüm - {title}" if ep_no else title
                
                # Resim
                img = ""
                if item.get("image"):
                    img = "https://media.startv.com.tr/star-tv" + item["image"]["fullPath"]
                
                # Stream URL (M3U8)
                stream_url = ""
                if "video" in item and "referenceId" in item["video"]:
                    ref_id = item["video"]["referenceId"]
                    stream_url = f"https://dygvideo.dygdigital.com/api/redirect?PublisherId=1&ReferenceId=StarTV_{ref_id}&SecretKey=NtvApiSecret2014*&.m3u8"
                
                if stream_url:
                    episode_list.append({
                        "name": name,
                        "img": img,
                        "stream_url": stream_url
                    })

            # Sayfalama
            if len(items) < 100: break
            params["skip"] += 100

        except Exception as e:
            print(f"   ⚠️ API Hatası: {e}")
            break
            
    print(f"   ✅ {len(episode_list)} bölüm alındı.")
    return episode_list

def save_data(data, category):
    target_dir = DIRS[category]
    all_list = []

    for show in tqdm(data, desc=f"{category} Kaydediliyor"):
        slug = re.sub(r'[^a-z0-9-]', '', show['name'].lower().replace(" ", "-").replace("ç","c").replace("ğ","g").replace("ı","i").replace("ö","o").replace("ş","s").replace("ü","u"))
        
        # Tekil JSON
        with open(os.path.join(target_dir, f"{slug}.json"), "w", encoding="utf-8") as f:
            json.dump(show, f, ensure_ascii=False, indent=4)
        
        # Tekil M3U
        try:
            with open(os.path.join(target_dir, f"{slug}.m3u"), "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                for ep in show["episodes"]:
                    f.write(f'#EXTINF:-1 tvg-logo="{ep["img"]}",{ep["name"]}\n{ep["stream_url"]}\n')
        except: pass
        
        all_list.append(show)

    # Toplu Dosyalar
    with open(os.path.join(ROOT_DIR, f"startv-{category}.json"), "w", encoding="utf-8") as f:
        json.dump(all_list, f, ensure_ascii=False, indent=4)
    
    with open(os.path.join(ROOT_DIR, f"startv-{category}.m3u"), "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for show in all_list:
            for ep in show["episodes"]:
                f.write(f'#EXTINF:-1 tvg-logo="{ep["img"]}" group-title="{show["name"]}",{ep["name"]}\n{ep["stream_url"]}\n')

def main():
    for d in DIRS.values(): os.makedirs(d, exist_ok=True)

    targets = [
        {"url": f"{BASE_URL}/dizi", "type": "series"},
        {"url": f"{BASE_URL}/program", "type": "programs"}
    ]

    for t in targets:
        items = get_items_page(t["url"])
        processed_data = []

        for item in items:
            print(f"\n📺 İşleniyor: {item['name']}")
            api_path = get_api_path(item["url"])
            episodes = get_episodes_from_api(api_path)
            
            if episodes:
                item["episodes"] = episodes
                processed_data.append(item)
        
        save_data(processed_data, t["type"])

    # GITHUB GÖNDERİMİ
    print("\n🚀 GitHub'a Yükleniyor...")
    run_command("git add --all")
    run_command(f'git commit -m "StarTV Guncelleme {datetime.now().strftime("%Y-%m-%d")}"')
    run_command("git push")
    print("✅ İşlem Tamamlandı.")

if __name__ == "__main__":
    main()

