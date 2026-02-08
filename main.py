import asyncio
import random
from playwright.async_api import async_playwright
# Stealth modülü tarayıcının bot olduğunu gizler
from playwright_stealth import stealth_async

# Hedef URL
TARGET_URL = "https://vidsrc-embed.ru/embed/movie?imdb=tt18382850"

async def intercept_network():
    async with async_playwright() as p:
        # Tarayıcıyı başlatırken ekstra argümanlar ekleyerek bot izlerini siliyoruz
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-infobars',
                '--window-position=0,0',
                '--ignore-certifcate-errors',
                '--ignore-certifcate-errors-spki-list',
                '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
            ]
        )
        
        # Tarayıcı bağlamı oluştur
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        )
        
        page = await context.new_page()
        
        # SİHİRLİ DOKUNUŞ: Stealth modülünü yükle
        await stealth_async(page)

        print(f"Siteye gidiliyor: {TARGET_URL}")

        found_links = set()

        def handle_request(request):
            # M3U8 veya MP4 linklerini yakala
            if ".m3u8" in request.url or ".mp4" in request.url:
                print(f"[YAKALANDI] {request.url}")
                found_links.add(request.url)

        page.on("request", handle_request)

        try:
            # Siteye git
            await page.goto(TARGET_URL, timeout=90000, wait_until="domcontentloaded")
            
            # Biraz bekle (Cloudflare kontrolü geçsin diye)
            await page.wait_for_timeout(5000)

            # Ekranda ne olduğunu görmek için ekran görüntüsü al (Debug için çok önemli)
            await page.screenshot(path="ekran_goruntusu.png", full_page=True)

            # Oynat butonuna basmaya çalış
            print("Video başlatılmaya çalışılıyor...")
            
            # Sayfadaki olası play butonlarına tıkla
            # Bu sitelerde play butonu genelde bir 'overlay' div'idir.
            clicked = False
            selectors = ["#player", ".play-button", "div[class*='play']", "video", "iframe"]
            
            for sel in selectors:
                if await page.locator(sel).count() > 0:
                    try:
                        await page.click(sel, timeout=2000)
                        print(f"Tıklandı: {sel}")
                        clicked = True
                        await page.wait_for_timeout(2000) # Tepki bekle
                    except:
                        pass
            
            # Eğer tıklanmadıysa ortaya tıkla
            if not clicked:
                await page.mouse.click(960, 540)
            
            # Ağ trafiğinin oluşması için bekle
            await page.wait_for_timeout(10000)

        except Exception as e:
            print(f"Hata oluştu: {e}")
            # Hata anında da görüntü al
            await page.screenshot(path="hata_goruntusu.png")

        await browser.close()
        
        # Sonuçları kaydet
        with open("sonuc.txt", "w") as f:
            if found_links:
                for link in found_links:
                    f.write(link + "\n")
                print(f"\nBaşarılı! {len(found_links)} link bulundu.")
            else:
                f.write("Link bulunamadi. Lütfen ekran görüntüsünü (artifact) kontrol et.")
                print("\nLink bulunamadı.")

if __name__ == "__main__":
    asyncio.run(intercept_network())
