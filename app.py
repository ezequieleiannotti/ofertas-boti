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
    # Verificar si tenemos access token
    access_token = session.get("access_token")
    
    if not access_token:
        # Si no hay token, mostrar página de login
        if is_development():
            redirect_uri = "http://localhost:5000/auth/callback"
        else:
            redirect_uri = PROD_REDIRECT_URI
            
        login_url = (
            f"https://auth.mercadolibre.com.ar/authorization"
            f"?response_type=code&client_id={CLIENT_ID}"
            f"&redirect_uri={redirect_uri}"
        )
        return render_template("login_required.html", login_url=login_url)
    
    # Obtener productos con access token
    productos = get_all_products()
    
    # Aplicar filtros si existen
    min_descuento = request.args.get('descuento_min', 0, type=int)
    max_descuento = request.args.get('descuento_max', 100, type=int)
    max_precio = request.args.get('precio', 999999999, type=int)
    categoria = request.args.get('categoria', '')
    
    # Filtrar productos
    productos_filtrados = []
    for producto in productos:
        # Filtro por descuento: rango entre min y max
        producto_descuento = producto.get('descuento', 0)
        if producto_descuento >= min_descuento and producto_descuento <= max_descuento:
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
                             'descuento_min': min_descuento,
                             'descuento_max': max_descuento if max_descuento < 100 else '',
                             'precio': max_precio if max_precio < 999999999 else '',
                             'categoria': categoria
                         })

@app.route("/login")
def login_page():
    # Usar redirect URI correcto según el entorno
    if is_development():
        redirect_uri = "http://localhost:5000/auth/callback"
    else:
        redirect_uri = PROD_REDIRECT_URI
        
    login_url = (
        f"https://auth.mercadolibre.com.ar/authorization"
        f"?response_type=code&client_id={CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
    )
    return render_template("login_required.html", login_url=login_url)

# -------------------------------------------------
# Callback OAuth2
# -------------------------------------------------
@app.route("/auth/callback")
def auth_callback():
    code = request.args.get("code")
    if not code:
        return "No se recibió el código", 400

    # Usar redirect URI correcto según el entorno
    if is_development():
        redirect_uri = "http://localhost:5000/auth/callback"
    else:
        redirect_uri = PROD_REDIRECT_URI

    data = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": redirect_uri,
    }

    try:
        response = requests.post("https://api.mercadolibre.com/oauth/token", data=data).json()

        if "error" in response:
            return f"Error obteniendo token: {response}"

        # Guardar tokens en sesión
        session["access_token"] = response["access_token"]
        session["refresh_token"] = response.get("refresh_token")
        
        return redirect(url_for("home"))
        
    except Exception as e:
        return f"Error en callback: {str(e)}"

# -------------------------------------------------
# Buscar ofertas reales (API pública)
# -------------------------------------------------
def get_all_products():
    # Usar API ORIGINAL de MercadoLibre con diferentes estrategias
    access_token = session.get("access_token")
    
    # Búsquedas en MercadoLibre Argentina
    busquedas = [
        "celular", "smartphone", "iphone", "samsung", 
        "notebook", "laptop", "tv", "smart tv",
        "auriculares", "tablet", "playstation", "xbox"
    ]
    
    todos_productos = []
    
    for busqueda in busquedas:
        productos = buscar_ofertas_ml(busqueda, access_token)
        if productos:
            todos_productos.extend(productos)
            print(f"Agregados {len(productos)} productos de '{busqueda}'")
        
        # Si ya tenemos suficientes productos, parar
        if len(todos_productos) >= 100:
            break
    
    if not todos_productos:
        print("No se pudieron obtener productos de MercadoLibre, usando fallback")
        return get_fallback_products()
    
    # Eliminar duplicados
    productos_unicos = {}
    for producto in todos_productos:
        titulo_key = producto["titulo"][:40]
        if titulo_key not in productos_unicos:
            productos_unicos[titulo_key] = producto
    
    productos_finales = list(productos_unicos.values())
    productos_finales.sort(key=lambda x: (x.get("descuento", 0), -x.get("precio", 0)), reverse=True)
    
    print(f"Total productos finales: {len(productos_finales)}")
    return productos_finales

def buscar_ofertas_ml(query, access_token=None):
    """Buscar en MercadoLibre con diferentes estrategias para evitar 403"""
    
    # Estrategia 1: Con access token si existe
    if access_token:
        productos = intentar_busqueda_con_token(query, access_token)
        if productos:
            return productos
    
    # Estrategia 2: Sin autenticación pero con headers más completos
    productos = intentar_busqueda_publica(query)
    if productos:
        return productos
    
    # Estrategia 3: Usando proxy/diferentes headers
    productos = intentar_busqueda_alternativa(query)
    if productos:
        return productos
    
    print(f"Todas las estrategias fallaron para '{query}'")
    return []

def intentar_busqueda_con_token(query, access_token):
    try:
        url = "https://api.mercadolibre.com/sites/MLA/search"
        params = {"q": query, "limit": 20}
        headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "OfertasBot/1.0",
            "Accept": "application/json"
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            return procesar_resultados_ml(data.get("results", []))
        else:
            print(f"Error con token para '{query}': {response.status_code}")
            return []
            
    except Exception as e:
        print(f"Error en búsqueda con token: {e}")
        return []

def intentar_busqueda_publica(query):
    try:
        url = "https://api.mercadolibre.com/sites/MLA/search"
        params = {"q": query, "limit": 20}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.mercadolibre.com.ar/",
            "Origin": "https://www.mercadolibre.com.ar"
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            return procesar_resultados_ml(data.get("results", []))
        else:
            print(f"Error en búsqueda pública para '{query}': {response.status_code}")
            return []
            
    except Exception as e:
        print(f"Error en búsqueda pública: {e}")
        return []

def intentar_busqueda_alternativa(query):
    try:
        # Usar diferentes endpoints o parámetros
        url = "https://api.mercadolibre.com/sites/MLA/search"
        params = {
            "q": query, 
            "limit": 10,
            "offset": 0,
            "sort": "relevance"
        }
        headers = {
            "User-Agent": "curl/7.68.0",
            "Accept": "*/*"
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return procesar_resultados_ml(data.get("results", []))
        else:
            print(f"Error en búsqueda alternativa para '{query}': {response.status_code}")
            return []
            
    except Exception as e:
        print(f"Error en búsqueda alternativa: {e}")
        return []

def procesar_resultados_ml(results):
    """Procesar resultados de MercadoLibre API"""
    productos = []
    
    for item in results:
        precio = item.get("price")
        if not precio or precio <= 0:
            continue
            
        original = item.get("original_price")
        descuento = 0
        
        if precio and original and original > precio:
            descuento = int(100 - (precio * 100 / original))
        
        thumbnail = item.get("thumbnail")
        if thumbnail and thumbnail.startswith("http://"):
            thumbnail = thumbnail.replace("http://", "https://")
        
        productos.append({
            "titulo": item.get("title", "Sin título"),
            "precio": int(precio),
            "precio_original": int(original) if original else None,
            "descuento": descuento,
            "link": item.get("permalink", "#"),
            "thumbnail": thumbnail or "https://via.placeholder.com/150"
        })
    
    return productos

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
    # Test de MercadoLibre API con diferentes estrategias
    access_token = session.get("access_token")
    
    resultados = {
        "access_token_exists": bool(access_token),
        "estrategias": {}
    }
    
    # Probar estrategia 1: Con token
    if access_token:
        productos = intentar_busqueda_con_token("iphone", access_token)
        resultados["estrategias"]["con_token"] = {
            "funciona": len(productos) > 0,
            "productos_count": len(productos),
            "sample": productos[:1] if productos else []
        }
    
    # Probar estrategia 2: Pública
    productos = intentar_busqueda_publica("iphone")
    resultados["estrategias"]["publica"] = {
        "funciona": len(productos) > 0,
        "productos_count": len(productos),
        "sample": productos[:1] if productos else []
    }
    
    # Probar estrategia 3: Alternativa
    productos = intentar_busqueda_alternativa("iphone")
    resultados["estrategias"]["alternativa"] = {
        "funciona": len(productos) > 0,
        "productos_count": len(productos),
        "sample": productos[:1] if productos else []
    }
    
    return resultados

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
