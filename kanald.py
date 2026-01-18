import requests
from bs4 import BeautifulSoup
import json
import os
import re
from tqdm import tqdm
import urllib3
import subprocess
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- AYARLAR ---
BASE_URL = "https://www.kanald.com.tr"
ROOT_DIR = "kanald"
DIRS = {
    "series": os.path.join(ROOT_DIR, "dizi"),
    "programs": os.path.join(ROOT_DIR, "program")
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": BASE_URL
}

def run_command(command):
    try:
        subprocess.run(command, shell=True, check=False, stdout=subprocess.DEVNULL)
    except: pass

def get_stream_url(page_url):
    """Video sayfasından m3u8 linkini (Zorlayarak) çeker"""
    try:
        r = requests.get(page_url, headers=HEADERS, verify=False, timeout=10)
        html = r.text
        
        # YÖNTEM 1: Standart "Path":"...m3u8" yapısı (JSON içinde)
        # Regex: "Path":"(https:.*?\.m3u8.*?)"
        match = re.search(r'"Path":"(https:[^"]*?\.m3u8[^"]*?)"', html)
        if match: return match.group(1).replace("\\/", "/")

        # YÖNTEM 2: data-media-sources attribute'u
        match2 = re.search(r"data-media-sources='(.*?)'", html)
        if match2:
            try:
                data = json.loads(match2.group(1))
                if "Hls" in data and "Path" in data["Hls"]:
                    return data["Hls"]["Path"]
            except: pass
            
        # YÖNTEM 3: Secure HLS Path
        match3 = re.search(r'"SecurePath":"(https:[^"]*?\.m3u8[^"]*?)"', html)
        if match3: return match3.group(1).replace("\\/", "/")

        # YÖNTEM 4: Basit düz metin arama (Son çare)
        match4 = re.search(r'(https:\/\/kanald[^"\']*?\.m3u8[^"\']*?)', html)
        if match4: return match4.group(1).replace("\\/", "/")

    except: pass
    return None

def get_episodes(show_url, show_name):
    episodes = []
    page = 1
    bolumler_url = show_url + "/bolumler"
    print(f"   🔎 {show_name} bölümleri taranıyor...")
    
    # Max 50 sayfa (Sonsuz döngüyü önlemek için)
    while page < 50:
        try:
            target_url = f"{bolumler_url}?page={page}"
            r = requests.get(target_url, headers=HEADERS, verify=False, timeout=10)
            soup = BeautifulSoup(r.content, "html.parser")
            
            cards = soup.select(".listing-holder .item")
            if not cards: break
            
            # Bu sayfada yeni bölüm bulduk mu?
            found_in_page = 0
            
            for card in cards:
                try:
                    a_tag = card.find("a")
                    if not a_tag: continue
                    link = BASE_URL + a_tag.get("href")
                    
                    title_tag = card.find("h3") or card.find("img")
                    title = title_tag.get_text(strip=True) if title_tag else "Bolum"
                    if not title and title_tag.name == "img": title = title_tag.get("alt")
                    
                    img_tag = card.find("img")
                    img = img_tag.get("data-src") or img_tag.get("src") if img_tag else ""
                    
                    # Video Linkini Çek
                    stream = get_stream_url(link)
                    
                    if stream:
                        episodes.append({"name": title, "img": img, "stream_url": stream})
                        found_in_page += 1
                except: continue
            
            if found_in_page == 0: 
                # Eğer sayfa 1 boşsa, belki direkt ana sayfada videolar vardır
                if page == 1: break 
                else: break
            
            page += 1
            
        except: break

    print(f"   ✅ Toplam {len(episodes)} oynatılabilir bölüm bulundu.")
    return episodes

def collect_shows(category_url):
    print(f"🌍 Kategori Taranıyor: {category_url}")
    shows = []
    try:
        r = requests.get(category_url, headers=HEADERS, verify=False, timeout=15)
        soup = BeautifulSoup(r.content, "html.parser")
        cards = soup.select(".listing-holder .item, .program-list .item")
        
        for card in cards:
            a = card.find("a")
            if not a: continue
            url = BASE_URL + a.get("href")
            
            t_tag = card.find("h3") or card.find("img")
            name = t_tag.get_text(strip=True) if t_tag else "Bilinmeyen"
            if not name and t_tag.name == "img": name = t_tag.get("alt")
            
            img_tag = card.find("img")
            img = img_tag.get("data-src") or img_tag.get("src") if img_tag else ""
            
            shows.append({"name": name, "url": url, "img": img})
    except: pass
    print(f"✅ {len(shows)} dizi/program bulundu.")
    return shows

def main():
    for d in DIRS.values(): os.makedirs(d, exist_ok=True)
    
    targets = [
        {"url": f"{BASE_URL}/diziler", "type": "series"},
        {"url": f"{BASE_URL}/programlar", "type": "programs"}
    ]
    
    all_data = {"series": [], "programs": []}
    
    for t in targets:
        shows = collect_shows(t["url"])
        
        for show in tqdm(shows, desc=f"{t['type']} İşleniyor"):
            episodes = get_episodes(show["url"], show["name"])
            if episodes:
                show_data = {"name": show["name"], "img": show["img"], "episodes": episodes}
                slug = re.sub(r'[^a-z0-9-]', '', show['name'].lower().replace(" ", "-").replace("ç","c").replace("ğ","g").replace("ı","i").replace("ö","o").replace("ş","s").replace("ü","u"))
                
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
        with open(os.path.join(ROOT_DIR, f"kanald-{key}.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        with open(os.path.join(ROOT_DIR, f"kanald-{key}.m3u"), "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for show in data:
                for ep in show["episodes"]:
                    f.write(f'#EXTINF:-1 tvg-logo="{ep["img"]}" group-title="{show["name"]}",{ep["name"]}\n{ep["stream_url"]}\n')

    # GITHUB
    print("\n🚀 GitHub'a Yükleniyor...")
    run_command("git add --all")
    run_command("git add kanald/*")
    run_command(f'git commit -m "KanalD Guncelleme {datetime.now().strftime("%d-%m")}"')
    run_command("git push")
    print("✅ İşlem Tamamlandı.")

if __name__ == "__main__":
    main()

