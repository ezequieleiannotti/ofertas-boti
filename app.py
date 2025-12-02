from flask import Flask, request, redirect, jsonify, render_template
import requests
import os

app = Flask(__name__)

CLIENT_ID = "1862062842480219"
CLIENT_SECRET = "wIz7tlOGXaDY9ciyTHKYfQmiI256j6wJ"

import os

# URL de producción para Render.com (cambiar por tu URL real)
PROD_REDIRECT_URI = "https://tu-app.onrender.com/auth/callback"

# -----------------------------------------
# Detectar si es LOCAL vs PRODUCCIÓN
# -----------------------------------------
def is_development():
    # Render.com setea PORT como variable de entorno
    return os.getenv("PORT") is None


# -----------------------------------------
# Home
# -----------------------------------------
@app.route("/")
def home():
    if is_development():
        return render_template("index.html", login_url="/demo")

    login_url = (
        f"https://auth.mercadolibre.com.ar/authorization"
        f"?response_type=code&client_id={CLIENT_ID}"
        f"&redirect_uri={PROD_REDIRECT_URI}"
    )
    return render_template("index.html", login_url=login_url)


# -----------------------------------------
# Callback (solo prod)
# -----------------------------------------
@app.route("/auth/callback")
def auth_callback():
    if is_development():
        return "Callback no disponible en modo desarrollo"

    code = request.args.get("code")
    if not code:
        return "No se recibió el código", 400

    data = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": PROD_REDIRECT_URI,
    }

    token_response = requests.post(
        "https://api.mercadolibre.com/oauth/token", data=data
    ).json()

    # ❗ PRODUCCIÓN → usar API pública real (NO TOKEN)
    ofertas = buscar_ofertas("ofertas")

    return render_template("success.html", tokens=token_response, offers=ofertas)


# -----------------------------------------
# Buscador real sin token (API pública)
# -----------------------------------------
def buscar_ofertas(query):

    url = "https://api.mercadolibre.com/sites/MLA/search"
    params = {"q": query, "sort": "price_asc"}  # ordena mejores precios

    response = requests.get(url, params=params)
    data = response.json()

    ofertas = []
    for item in data.get("results", [])[:12]:

        precio = item.get("price")
        original = item.get("original_price")

        descuento = 0
        if precio and original and original > precio:
            descuento = int(100 - (precio * 100 / original))

        ofertas.append({
            "titulo": item.get("title"),
            "precio": precio,
            "precio_original": original,
            "descuento": descuento,
            "link": item.get("permalink"),
            "thumbnail": item.get("thumbnail")
        })

    return ofertas


# -----------------------------------------
# Demo local
# -----------------------------------------
@app.route("/demo")
def demo():
    ofertas_demo = [
        {
            "titulo": "Samsung Galaxy A54",
            "precio": 299999,
            "precio_original": 399999,
            "descuento": 25,
            "thumbnail": "https://http2.mlstatic.com/D_NQ_NP_2X_123456.webp",
            "link": "#"
        },
        {
            "titulo": "iPhone 15",
            "precio": 1299999,
            "precio_original": 1499999,
            "descuento": 13,
            "thumbnail": "https://http2.mlstatic.com/D_NQ_NP_2X_789012.webp",
            "link": "#"
        }
    ]

    return render_template("success.html", tokens={"demo": True}, offers=ofertas_demo)


# -----------------------------------------
# Test API pública
# -----------------------------------------
@app.route("/public")
def public_test():
    ofertas = buscar_ofertas("iphone")
    return render_template("success.html", tokens={"public": True}, offers=ofertas)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
