from flask import Flask, request, redirect, render_template, session, url_for
import requests
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Necesario para session

# -------------------------------------------------
# Configuración de tu App de Mercado Libre
# -------------------------------------------------
CLIENT_ID = "1862062842480219"
CLIENT_SECRET = "wIz7tlOGXaDY9ciyTHKYfQmiI256j6wJ"
PROD_REDIRECT_URI = "https://ofertas-boti.onrender.com/auth/callback"

# -------------------------------------------------
# Detectar si es LOCAL vs PRODUCCIÓN
# -------------------------------------------------
def is_development():
    host = request.host.split(":")[0]
    return host in ["127.0.0.1", "localhost"]

# -------------------------------------------------
# Home: mostrar login si no hay token
# -------------------------------------------------
@app.route("/")
def home():
    access_token = session.get("access_token")
    if access_token:
        ofertas = get_best_offers()
        return render_template("offers.html", offers=ofertas, title="🔥 Mejores Ofertas")
    else:
        login_url = (
            f"https://auth.mercadolibre.com.ar/authorization"
            f"?response_type=code&client_id={CLIENT_ID}"
            f"&redirect_uri={PROD_REDIRECT_URI}"
        )
        return render_template("index.html", login_url=login_url)

# -------------------------------------------------
# Callback OAuth2
# -------------------------------------------------
@app.route("/auth/callback")
def auth_callback():
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

    response = requests.post("https://api.mercadolibre.com/oauth/token", data=data).json()

    if "error" in response:
        return f"Error obteniendo token: {response}"

    # Guardar tokens en sesión
    session["access_token"] = response["access_token"]
    session["refresh_token"] = response.get("refresh_token")

    return redirect(url_for("home"))

# -------------------------------------------------
# Buscar ofertas reales (API pública)
# -------------------------------------------------
def get_best_offers():
    categorias = ["celular", "notebook", "tv", "electrodomesticos", "gaming"]
    todas_ofertas = []

    for categoria in categorias:
        ofertas = buscar_ofertas(categoria)
        todas_ofertas.extend(ofertas)
        if len(todas_ofertas) >= 30:
            break

    # Ordenar por descuento si existe
    todas_ofertas.sort(key=lambda x: x.get("descuento", 0), reverse=True)
    return todas_ofertas[:30]

def buscar_ofertas(query):
    try:
        url = "https://api.mercadolibre.com/sites/MLA/search"
        params = {"q": query, "limit": 10, "sort": "price_asc"}
        headers = {"User-Agent": "Mozilla/5.0"}

        response = requests.get(url, params=params, headers=headers)
        if response.status_code != 200:
            return []

        data = response.json()
        ofertas = []
        for item in data.get("results", []):
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
    except Exception:
        return []

# -------------------------------------------------
# Demo local o test
# -------------------------------------------------
@app.route("/demo")
def demo():
    return render_template("offers.html", offers=get_best_offers(), title="Demo de Ofertas")

# -------------------------------------------------
# Logout
# -------------------------------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

# -------------------------------------------------
# Ejecutar app
# -------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, port=5000)
