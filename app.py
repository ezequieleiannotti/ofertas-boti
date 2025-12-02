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
    # Obtener TODOS los productos disponibles
    productos = get_all_products()
    
    # Aplicar filtros si existen
    min_descuento = request.args.get('descuento', 0, type=int)
    max_precio = request.args.get('precio', 999999999, type=int)
    categoria = request.args.get('categoria', '')
    
    # Filtrar productos
    productos_filtrados = []
    for producto in productos:
        # Filtro por descuento
        if producto.get('descuento', 0) >= min_descuento:
            # Filtro por precio
            if producto.get('precio', 0) <= max_precio:
                # Filtro por categoría
                if not categoria or categoria.lower() in producto.get('titulo', '').lower():
                    productos_filtrados.append(producto)
    
    return render_template("products.html", 
                         products=productos_filtrados, 
                         total_products=len(productos),
                         filtered_count=len(productos_filtrados),
                         current_filters={
                             'descuento': min_descuento,
                             'precio': max_precio if max_precio < 999999999 else '',
                             'categoria': categoria
                         })

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
def get_all_products():
    access_token = session.get("access_token")
    
    # Búsquedas amplias para obtener MUCHOS productos
    busquedas = [
        "celular", "smartphone", "iphone", "samsung", "xiaomi",
        "notebook", "laptop", "computadora", "pc",
        "tv", "smart tv", "televisor", "monitor",
        "auriculares", "parlante", "audio",
        "tablet", "ipad", 
        "playstation", "xbox", "nintendo", "gaming",
        "electrodomesticos", "heladera", "lavarropas", "microondas",
        "air fryer", "cafetera", "aspiradora",
        "reloj", "smartwatch", "fitness",
        "camara", "fotografia", "gopro"
    ]
    
    todos_productos = []
    
    for busqueda in busquedas:
        productos = buscar_ofertas(busqueda, access_token)
        todos_productos.extend(productos)
        
        # Obtener más productos (hasta 200 por búsqueda)
        if len(todos_productos) >= 500:
            break
    
    # Eliminar duplicados por título
    productos_unicos = {}
    for producto in todos_productos:
        titulo_key = producto["titulo"][:40]
        if titulo_key not in productos_unicos:
            productos_unicos[titulo_key] = producto
    
    productos_finales = list(productos_unicos.values())
    
    # Ordenar por relevancia (precio, descuento)
    productos_finales.sort(key=lambda x: (x.get("descuento", 0), -x.get("precio", 999999)), reverse=True)
    
    return productos_finales

def get_best_offers():
    productos = get_all_products()
    # Solo los primeros 30 con descuento
    return [p for p in productos if p.get('descuento', 0) > 0][:30]

def buscar_ofertas(query, access_token=None):
    try:
        url = "https://api.mercadolibre.com/sites/MLA/search"
        params = {
            "q": query, 
            "limit": 50,
            "sort": "price_asc"  # Por precio ascendente
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        # Si tenemos token, usarlo
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        response = requests.get(url, params=params, headers=headers)
        
        if response.status_code != 200:
            print(f"Error API {response.status_code} para {query}")
            return []

        data = response.json()
        
        if "error" in data:
            print(f"Error en respuesta para {query}: {data}")
            return []
            
        ofertas = []
        
        for item in data.get("results", []):
            precio = item.get("price")
            
            # Incluir TODOS los productos con precio
            if precio and precio > 0:
                original = item.get("original_price")
                
                descuento = 0
                if precio and original and original > precio:
                    descuento = int(100 - (precio * 100 / original))
                
                thumbnail = item.get("thumbnail")
                if thumbnail and thumbnail.startswith("http://"):
                    thumbnail = thumbnail.replace("http://", "https://")
                
                ofertas.append({
                    "titulo": item.get("title", "Sin título"),
                    "precio": precio,
                    "precio_original": original,
                    "descuento": descuento,
                    "link": item.get("permalink", "#"),
                    "thumbnail": thumbnail
                })
            
        print(f"Encontrados {len(ofertas)} productos para '{query}'")
        return ofertas
        
    except Exception as e:
        print(f"Error buscando {query}: {e}")
        return []

# -------------------------------------------------
# Demo local o test
# -------------------------------------------------
@app.route("/demo")
def demo():
    return render_template("offers.html", offers=get_best_offers(), title="Demo de Ofertas")

@app.route("/debug")
def debug():
    access_token = session.get("access_token")
    
    # Probar una búsqueda simple
    ofertas = buscar_ofertas("iphone", access_token)
    
    return {
        "access_token_exists": bool(access_token),
        "ofertas_count": len(ofertas),
        "sample_ofertas": ofertas[:3] if ofertas else [],
        "session_data": dict(session)
    }

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
