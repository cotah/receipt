from pyngrok import ngrok
import uvicorn

tunnel = ngrok.connect(8000)
print(f"\n🚀 Backend público em: {tunnel.public_url}")
print(f"📱 Copia este URL para o .env do mobile!\n")

uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)