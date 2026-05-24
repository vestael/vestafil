import asyncio
from fastapi import FastAPI, BackgroundTasks
from playwright.async_api import async_playwright
import requests
from pydantic import BaseModel

app = FastAPI()

class ProductRequest(BaseModel):
    product_url: str
    webhook_url: str
    id_produit: str  # 1. On ajoute le champ pour recevoir l'ID envoyé par Make

async def extraire_et_envoyer(product_url: str, webhook_url: str, id_produit: str): # 2. On passe l'ID en paramètre ici
    async with async_playwright() as p:
        # Lancement d'un Chrome invisible configuré comme un vrai PC
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        page = await context.new_page()
        video_url = None

        # On écoute les requêtes réseau en tâche de fond pour intercepter le MP4
        def intercepter(response):
            nonlocal video_url
            if ".mp4" in response.url or "videoUrl" in response.url:
                video_url = response.url

        page.on("response", intercepter)

        try:
            # Navigation vers le produit
            await page.goto(product_url, wait_until="networkidle", timeout=60000)
            # Petit scroll pour forcer le chargement de la vidéo (Lazy Loading)
            await page.evaluate("window.scrollBy(0, 400)")
            await asyncio.sleep(4)
        except Exception as e:
            print(f"Erreur d'extraction: {e}")
        finally:
            await browser.close()

        # 3. On ajoute l'id_produit dans le dictionnaire envoyé au Scénario 2 de Make
        payload = {
            "id_produit": id_produit,
            "product_url": product_url, 
            "video_url": video_url
        }
        
        try:
            requests.post(webhook_url, json=payload, timeout=10)
        except Exception as e:
            print(f"Erreur d'envoi au Webhook: {e}")

@app.post("/extract")
def extract_video(request: ProductRequest, background_tasks: BackgroundTasks):
    # On exécute le scraping en arrière-plan en lui transmettant le nouvel ID
    background_tasks.add_task(
        extraire_et_envoyer, 
        request.product_url, 
        request.webhook_url, 
        request.id_produit  # Transmis ici
    )
    return {"status": "Scraping en cours"}
