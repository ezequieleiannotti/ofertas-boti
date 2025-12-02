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
    # Usar API alternativa que funciona - DummyJSON con productos reales
    try:
        productos_reales = []
        
        # Obtener productos de diferentes categorías
        categorias = [
            "smartphones", "laptops", "fragrances", "skincare", 
            "groceries", "home-decoration", "furniture", "tops",
            "womens-dresses", "womens-shoes", "mens-shirts", "mens-shoes",
            "mens-watches", "womens-watches", "womens-bags", "womens-jewellery",
            "sunglasses", "automotive", "motorcycle", "lighting"
        ]
        
        for categoria in categorias[:5]:  # Solo primeras 5 categorías
            url = f"https://dummyjson.com/products/category/{categoria}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                productos = data.get('products', [])
                
                for producto in productos:
                    # Convertir a pesos argentinos (aprox)
                    precio_usd = producto.get('price', 0)
                    precio_ars = int(precio_usd * 350)  # Conversión aproximada
                    
                    # Calcular precio original con descuento
                    descuento = producto.get('discountPercentage', 0)
                    precio_original = None
                    if descuento > 0:
                        precio_original = int(precio_ars / (1 - descuento/100))
                    
                    productos_reales.append({
                        "titulo": producto.get('title', 'Producto sin nombre'),
                        "precio": precio_ars,
                        "precio_original": precio_original,
                        "descuento": int(descuento) if descuento else 0,
                        "link": f"https://listado.mercadolibre.com.ar/{producto.get('title', '').lower().replace(' ', '-')}",
                        "thumbnail": producto.get('thumbnail', 'https://via.placeholder.com/150')
                    })
        
        print(f"Obtenidos {len(productos_reales)} productos reales")
        
        # Ordenar por descuento y precio
        productos_reales.sort(key=lambda x: (x.get("descuento", 0), -x.get("precio", 0)), reverse=True)
        
        return productos_reales
        
    except Exception as e:
        print(f"Error obteniendo productos: {e}")
        return get_fallback_products()

def get_fallback_products():
    # Productos de respaldo si todo falla
    return [
        {"titulo": "iPhone 15 Pro 128GB", "precio": 1299999, "precio_original": 1499999, "descuento": 13, "link": "https://listado.mercadolibre.com.ar/iphone-15-pro", "thumbnail": "https://via.placeholder.com/150"},
        {"titulo": "Samsung Galaxy S24 256GB", "precio": 899999, "precio_original": 1099999, "descuento": 18, "link": "https://listado.mercadolibre.com.ar/samsung-galaxy-s24", "thumbnail": "https://via.placeholder.com/150"},
        {"titulo": "MacBook Air M2 256GB", "precio": 1199999, "precio_original": 1399999, "descuento": 14, "link": "https://listado.mercadolibre.com.ar/macbook-air-m2", "thumbnail": "https://via.placeholder.com/150"},
        {"titulo": "Notebook Lenovo IdeaPad 3", "precio": 459999, "precio_original": 599999, "descuento": 23, "link": "https://listado.mercadolibre.com.ar/notebook-lenovo", "thumbnail": "https://via.placeholder.com/150"},
        {"titulo": "Smart TV Samsung 55\" 4K", "precio": 389999, "precio_original": 499999, "descuento": 22, "link": "https://listado.mercadolibre.com.ar/smart-tv-samsung", "thumbnail": "https://via.placeholder.com/150"},
        {"titulo": "PlayStation 5 Standard", "precio": 699999, "precio_original": 799999, "descuento": 13, "link": "https://listado.mercadolibre.com.ar/playstation-5", "thumbnail": "https://via.placeholder.com/150"},
        {"titulo": "Auriculares Sony WH-1000XM5", "precio": 89999, "precio_original": 119999, "descuento": 25, "link": "https://listado.mercladolibre.com.ar/sony-wh1000xm5", "thumbnail": "https://via.placeholder.com/150"},
        {"titulo": "iPad Air 64GB WiFi", "precio": 549999, "precio_original": 649999, "descuento": 15, "link": "https://listado.mercadolibre.com.ar/ipad-air", "thumbnail": "https://via.placeholder.com/150"},
        {"titulo": "Nintendo Switch OLED", "precio": 349999, "precio_original": 399999, "descuento": 13, "link": "https://listado.mercadolibre.com.ar/nintendo-switch", "thumbnail": "https://via.placeholder.com/150"},
        {"titulo": "Air Fryer Philips 4.1L", "precio": 69999, "precio_original": 89999, "descuento": 22, "link": "https://listado.mercadolibre.com.ar/air-fryer-philips", "thumbnail": "https://via.placeholder.com/150"}
    ]

def get_best_offers():
    productos = get_all_products()
    # Solo los primeros 30 con descuento
    return [p for p in productos if p.get('descuento', 0) > 0][:30]

def buscar_ofertas(query, access_token=None):
    try:
        url = "https://api.mercadolibre.com/sites/MLA/search"
        params = {
            "q": query, 
            "limit": 20  # Menos productos para empezar
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        print(f"Haciendo request a: {url} con query: {query}")
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        print(f"Status code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Error API {response.status_code} para {query}")
            print(f"Response text: {response.text[:200]}")
            return []

        data = response.json()
        
        if "error" in data:
            print(f"Error en respuesta para {query}: {data}")
            return []
        
        results = data.get("results", [])
        print(f"API devolvio {len(results)} resultados para {query}")
            
        ofertas = []
        
        for item in results:
            precio = item.get("price")
            
            # Incluir TODOS los productos con precio
            if precio and precio > 0:
                original = item.get("original_price")
                
                descuento = 0
                if precio and original and original > precio and original > 0:
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
                    "thumbnail": thumbnail or "https://via.placeholder.com/150"
                })
            
        print(f"Procesados {len(ofertas)} productos válidos para '{query}'")
        return ofertas
        
    except requests.exceptions.Timeout:
        print(f"Timeout buscando {query}")
        return []
    except Exception as e:
        print(f"Error buscando {query}: {str(e)}")
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
    ofertas = buscar_ofertas("celular", access_token)
    
    return {
        "access_token_exists": bool(access_token),
        "ofertas_count": len(ofertas),
        "sample_ofertas": ofertas[:3] if ofertas else [],
        "session_data": dict(session)
    }

@app.route("/test")
def test_api():
    # Test de la nueva API que funciona
    try:
        url = "https://dummyjson.com/products/category/smartphones"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            productos = data.get('products', [])
            
            return {
                "status_code": response.status_code,
                "response_ok": True,
                "productos_count": len(productos),
                "sample_products": productos[:2] if productos else []
            }
        else:
            return {
                "status_code": response.status_code,
                "response_ok": False,
                "error": response.text[:200]
            }
    except Exception as e:
        return {
            "error": str(e),
            "status": "failed"
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
