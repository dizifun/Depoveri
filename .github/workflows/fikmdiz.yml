import asyncio
from playwright.async_api import async_playwright

# Hedef URL
TARGET_URL = "https://vidsrc-embed.ru/embed/movie?imdb=tt18382850"

async def intercept_network():
    async with async_playwright() as p:
        # Tarayıcıyı başlat (headless=True arka planda çalışır)
        browser = await p.chromium.launch(headless=True)
        
        # Mobil görünümü taklit et (Bazen daha temiz link verir)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 10; SM-G960F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Mobile Safari/537.36"
        )
        page = await context.new_page()

        print(f"Siteye gidiliyor: {TARGET_URL}")

        # M3U8 linklerini burada toplayacağız
        found_links = set()

        # Ağ trafiğini dinleyen fonksiyon
        def handle_request(request):
            url = request.url
            if ".m3u8" in url:
                print(f"[BULUNDU] {url}")
                found_links.add(url)

        # Dinleyiciyi aktif et
        page.on("request", handle_request)

        try:
            # Siteye git
            await page.goto(TARGET_URL, timeout=60000)
            
            # Sayfanın tam yüklenmesi için bekle
            await page.wait_for_timeout(5000)

            # Oynatıcıyı tetiklemek için ekrana tıklamayı dene
            # Bu sitelerde genellikle bir "Play" overlay'i olur.
            print("Oynatıcı tetikleniyor...")
            
            # Farklı seçicilerle tıklamayı dene (Garanti olsun diye)
            clicked = False
            for selector in ["#player", ".play-button", "video", "iframe", "body"]:
                try:
                    if await page.is_visible(selector):
                        await page.click(selector, timeout=2000)
                        clicked = True
                        break
                except:
                    continue
            
            if not clicked:
                # Rastgele bir yere tıkla (bazen işe yarar)
                await page.mouse.click(100, 100)

            # Video isteğinin ağa düşmesi için bekle
            await page.wait_for_timeout(10000)

        except Exception as e:
            print(f"Hata oluştu: {e}")

        await browser.close()
        
        # Sonuçları dosyaya yaz (Artifact olarak almak için)
        with open("sonuc.txt", "w") as f:
            if found_links:
                for link in found_links:
                    f.write(link + "\n")
                print(f"\nToplam {len(found_links)} link kaydedildi.")
            else:
                f.write("Link bulunamadi.")
                print("\nMaalesef link yakalanamadı.")

if __name__ == "__main__":
    asyncio.run(intercept_network())
