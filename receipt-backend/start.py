"""Local dev helper — exposes the backend via ngrok for mobile testing.

NOT used in production. Railway uses the Procfile / Dockerfile instead.
Requires: pip install pyngrok
"""

import uvicorn


def main() -> None:
    try:
        from pyngrok import ngrok  # noqa: WPS433

        tunnel = ngrok.connect(8000)
        print(f"\n  Backend publico em: {tunnel.public_url}")
        print("  Copia este URL para o .env do mobile!\n")
    except ImportError:
        print("\n  pyngrok nao instalado — a arrancar sem tunnel.")
        print("  pip install pyngrok  para expor via ngrok.\n")

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()