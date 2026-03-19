#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BOT NOTICIAS VIRALES LATAM 24/7 - GitHub Actions Edition
"""

import requests
import feedparser
import re
import hashlib
import json
import os
import random
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from difflib import SequenceMatcher
from urllib.parse import urlparse, quote

# CONFIGURACION
NEWS_API_KEY = os.getenv('NEWS_API_KEY')
NEWSDATA_API_KEY = os.getenv('NEWSDATA_API_KEY')
GNEWS_API_KEY = os.getenv('GNEWS_API_KEY')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')

HISTORIAL_PATH = os.getenv('HISTORIAL_PATH', 'data/historial_viral.json')
ESTADO_PATH = os.getenv('ESTADO_PATH', 'data/estado_bot_viral.json')

TIEMPO_ENTRE_PUBLICACIONES = 55
MAX_TITULOS_HISTORIA = 300
UMBRAL_SIMILITUD_TITULO = 0.85
UMBRAL_SIMILITUD_CONTENIDO = 0.75

PALABRAS_VIRALES_ALTA = [
    "golpe de estado", "corrupcion", "dictadura", "protestas masivas", "crisis politica",
    "impeachment", "renuncia", "detencion", "extradicion", "narco", "cartel",
    "crisis economica", "inflacion record", "devaluacion", "dolar", "pobreza extrema",
    "masacre", "feminicidio", "secuestro", "violencia", "crimen organizado",
    "famoso", "celebridad", "escandalo", "divorcio", "muerte",
    "viral", "tiktok", "tendencia",
    "mundial", "final", "campeon", "gol"
]

PALABRAS_VIRALES_MEDIA = [
    "revelan", "exclusiva", "filtran", "inesperado", "sorprendente", "impactante",
    "urgente", "alerta", "emergencia"
]

CTAS_VIRALES = [
    "QUE OPINAS? Dejalo en los comentarios!",
    "COMPARTE si crees que esto debe saberse",
    "Siguenos para mas noticias virales de LATAM",
    "ULTIMO MINUTO - Informacion en constante actualizacion"
]

def log(mensaje, tipo='info'):
    iconos = {'info': '[i]', 'exito': '[OK]', 'error': '[ERR]', 'advertencia': '[!]'}
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {iconos.get(tipo, '[i]')} {mensaje}")

def cargar_json(ruta, default=None):
    if default is None: 
        default = {}
    if os.path.exists(ruta):
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                return json.loads(content) if content else default.copy()
        except Exception as e:
            log(f"Error cargando JSON {ruta}: {e}", 'error')
    return default.copy()

def guardar_json(ruta, datos):
    try:
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        temp_path = f"{ruta}.tmp"
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, ruta)
        return True
    except Exception as e:
        log(f"Error guardando JSON: {e}", 'error')
        return False

def generar_hash(texto):
    if not texto: 
        return ""
    t = re.sub(r'[^\w\s]', '', texto.lower().strip())
    t = re.sub(r'\s+', ' ', t)
    return hashlib.md5(t.encode()).hexdigest()

def normalizar_url(url):
    if not url: 
        return ""
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        path = parsed.path.lower()
        netloc = re.sub(r'^(www\.|m\.|mobile\.|amp\.)', '', netloc)
        path = re.sub(r'/index\.(html|php|htm|asp)$', '/', path)
        path = path.rstrip('/')
        path = re.sub(r'\.html?$', '', path)
        return f"{netloc}{path}"
    except:
        return url.lower().strip()

def calcular_similitud(t1, t2):
    if not t1 or not t2: 
        return 0.0
    def normalizar(t):
        t = re.sub(r'[^\w\s]', '', t.lower().strip())
        t = re.sub(r'\s+', ' ', t)
        stop_words = {'el', 'la', 'de', 'y', 'en', 'the', 'of', 'a', 'que', 'con'}
        palabras = [p for p in t.split() if p not in stop_words and len(p) > 3]
        return ' '.join(palabras)
    return SequenceMatcher(None, normalizar(t1), normalizar(t2)).ratio()

def es_titulo_generico(titulo):
    if not titulo: 
        return True
    tl = titulo.lower().strip()
    palabras = re.findall(r'\b\w+\b', tl)
    palabras_significativas = [p for p in palabras if len(p) > 4]
    return len(set(palabras_significativas)) < 3

def limpiar_texto(texto):
    if not texto: 
        return ""
    import html
    t = html.unescape(texto)
    t = re.sub(r'<[^>]+>', ' ', t)
    t = re.sub(r'\s+', ' ', t)
    t = re.sub(r'https?://\S*', '', t)
    return t.strip()

def calcular_puntaje_viral(titulo, desc):
    txt = f"{titulo} {desc}".lower()
    puntaje = 0
    for palabra in PALABRAS_VIRALES_ALTA:
        if palabra in txt:
            puntaje += 10
            if palabra in titulo.lower():
                puntaje += 5
    for palabra in PALABRAS_VIRALES_MEDIA:
        if palabra in txt:
            puntaje += 3
    if 40 <= len(titulo) <= 90:
        puntaje += 5
    if re.search(r'\d+', titulo):
        puntaje += 3
    return puntaje

def extraer_contenido(url):
    if not url: 
        return None, None
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        r = requests.get(url, headers=headers, timeout=12)
        soup = BeautifulSoup(r.content, 'html.parser')
        for elem in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            elem.decompose()
        article = soup.find('article')
        if article:
            parrafos = article.find_all('p')
            if len(parrafos) >= 2:
                texto = ' '.join([limpiar_texto(p.get_text()) for p in parrafos if len(p.get_text()) > 30])
                if len(texto) > 200:
                    return texto[:1500], None
        for clase in ['article-content', 'entry-content', 'post-content', 'content']:
            elem = soup.find(class_=lambda x: x and clase in x.lower())
            if elem:
                parrafos = elem.find_all('p')
                if len(parrafos) >= 2:
                    texto = ' '.join([limpiar_texto(p.get_text()) for p in parrafos if len(p.get_text()) > 30])
                    if len(texto) > 200:
                        return texto[:1500], None
        return None, None
    except:
        return None, None

def generar_prompt_imagen(titulo, contenido):
    txt = f"{titulo} {contenido[:150]}".lower()
    if any(p in txt for p in ['politica', 'gobierno', 'presidente']):
        categoria = "political breaking news photography"
        estilo = "photojournalism style, dramatic lighting"
    elif any(p in txt for p in ['crimen', 'policia', 'accidente']):
        categoria = "breaking news emergency scene"
        estilo = "cinematic high contrast, urgent lighting"
    elif any(p in txt for p in ['economia', 'dinero', 'crisis']):
        categoria = "financial news illustration"
        estilo = "modern professional style"
    elif any(p in txt for p in ['famoso', 'celebridad']):
        categoria = "celebrity news event"
        estilo = "paparazzi style, flash photography"
    elif any(p in txt for p in ['deporte', 'futbol']):
        categoria = "sports breaking news"
        estilo = "dynamic sports photography"
    else:
        categoria = "breaking news photography"
        estilo = "professional photojournalism"
    titulo_limpio = re.sub(r'[^\w\s]', '', titulo)[:80]
    return f"{categoria}, {titulo_limpio}, {estilo}, high quality, 4k"

def generar_imagen_ia(titulo, contenido):
    try:
        prompt = generar_prompt_imagen(titulo, contenido)
        log("Generando imagen...", 'imagen')
        prompt_encoded = quote(prompt)
        seed = random.randint(1000, 9999)
        url = f"https://image.pollinations.ai/prompt/{prompt_encoded}?width=1200&height=630&nologo=true&seed={seed}"
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=45)
        if response.status_code == 200:
            img_path = f'/tmp/viral_img_{generar_hash(titulo)}_{seed}.jpg'
            with open(img_path, 'wb') as f:
                f.write(response.content)
            if os.path.getsize(img_path) > 15000:
                log(f"Imagen generada: {img_path}", 'exito')
                return img_path
            os.remove(img_path)
        return None
    except Exception as e:
        log(f"Error imagen IA: {e}", 'error')
        return None

def crear_imagen_backup(titulo):
    try:
        from PIL import Image, ImageDraw, ImageFont
        colores = ['#FF006E', '#FB5607', '#FFBE0B', '#8338EC', '#3A86FF']
        color_fondo = random.choice(colores)
        img = Image.new('RGB', (1200, 630), color=color_fondo)
        draw = ImageDraw.Draw(img)
        try:
            font_titulo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 44)
            font_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 26)
        except:
            font_titulo = ImageFont.load_default()
            font_sub = font_titulo
        draw.rectangle([(0, 0), (1200, 10)], fill='white')
        draw.rectangle([(0, 620), (1200, 630)], fill='white')
        import textwrap
        titulo_wrapped = textwrap.fill(titulo[:130], width=30)
        lineas = titulo_wrapped.split('\n')
        y_start = (630 - len(lineas) * 55) // 2 - 30
        for i, linea in enumerate(lineas):
            y = y_start + i * 55
            draw.text((52, y+2), linea, font=font_titulo, fill='black')
            draw.text((50, y), linea, font=font_titulo, fill='white')
        draw.text((50, 540), "NOTICIAS VIRALES LATAM", font=font_sub, fill='white')
        draw.text((50, 575), "24/7 - " + datetime.now().strftime('%H:%M'), font=font_sub, fill='white')
        img_path = f'/tmp/viral_backup_{generar_hash(titulo)}.jpg'
        img.save(img_path, 'JPEG', quality=92)
        return img_path
    except Exception as e:
        log(f"Error backup imagen: {e}", 'error')
        return None

def dividir_parrafos_viral(texto):
    if not texto:
        return []
    oraciones = [o.strip() for o in re.split(r'(?<=[.!?])\s+', texto) if len(o.strip()) > 15]
    if len(oraciones) < 2:
        return [texto[:250] + "..."] if len(texto) > 80 else []
    parrafos = []
    actual = []
    palabras = 0
    for i, oracion in enumerate(oraciones[:10]):
        actual.append(oracion)
        palabras += len(oracion.split())
        if palabras >= 20 or i == len(oraciones) - 1 or len(actual) >= 2:
            if len(' '.join(actual).split()) >= 8:
                parrafos.append(' '.join(actual))
            actual = []
            palabras = 0
    return parrafos[:4]

def construir_publicacion_viral(titulo, contenido, fuente):
    titulo_limpio = limpiar_texto(titulo)
    parrafos = dividir_parrafos_viral(contenido)
    if len(parrafos) < 2:
        oraciones = [o.strip() for o in re.split(r'(?<=[.!?])\s+', contenido) if len(o.strip()) > 15]
        parrafos = [' '.join(oraciones[i:i+2]) for i in range(0, min(5, len(oraciones)), 2)]
    lineas = [titulo_limpio, "", "-" * 20, ""]
    for i, parrafo in enumerate(parrafos):
        lineas.append(parrafo)
        if i < len(parrafos) - 1:
            lineas.append("")
    lineas.extend(["", "-" * 20, "", random.choice(CTAS_VIRALES), "", f"Fuente: {fuente}", "Noticias Virales LATAM 24/7"])
    return '\n'.join(lineas)

def generar_hashtags_virales(titulo, contenido):
    txt = f"{titulo} {contenido}".lower()
    hashtags = ['#NoticiasVirales', '#LATAM', '#UltimaHora']
    temas = {
        r'mexico': '#Mexico', r'argentina': '#Argentina', r'colombia': '#Colombia',
        r'chile': '#Chile', r'peru': '#Peru', r'venezuela': '#Venezuela', r'brasil': '#Brasil',
        r'politica': '#Politica', r'economia': '#Economia', r'deporte': '#Deportes'
    }
    for patron, hashtag in temas.items():
        if re.search(patron, txt) and hashtag not in hashtags:
            hashtags.append(hashtag)
    hashtags.extend(['#Viral', '#Tendencia'])
    return ' '.join(hashtags[:7])

def cargar_historial():
    default = {
        'urls': [], 'urls_normalizadas': [], 'hashes': [], 'timestamps': [],
        'titulos': [], 'descripciones': [],
        'estadisticas': {'total_publicadas': 0, 'ultimas_24h': 0, 'github_run_id': None}
    }
    h = cargar_json(HISTORIAL_PATH, default)
    for k in default:
        if k not in h:
            h[k] = default[k]
    limpiar_historial_antiguo(h)
    run_id = os.getenv('GITHUB_RUN_ID')
    if run_id and h.get('estadisticas', {}).get('github_run_id') != run_id:
        h['estadisticas']['github_run_id'] = run_id
        log(f"GitHub Run ID: {run_id}", 'info')
    return h

def limpiar_historial_antiguo(h):
    try:
        ahora = datetime.now()
        indices_validos = []
        for i, ts in enumerate(h.get('timestamps', [])):
            try:
                fecha = datetime.fromisoformat(ts)
                if (ahora - fecha).days < 7:
                    indices_validos.append(i)
            except:
                continue
        for key in ['urls', 'urls_normalizadas', 'hashes', 'timestamps', 'titulos', 'descripciones']:
            if key in h and isinstance(h[key], list):
                h[key] = [h[key][i] for i in indices_validos if i < len(h[key])]
        count_24h = sum(1 for ts in h.get('timestamps', []) if (ahora - datetime.fromisoformat(ts)).total_seconds() < 86400)
        h['estadisticas']['ultimas_24h'] = count_24h
    except Exception as e:
        log(f"Error limpiando historial: {e}", 'error')

def noticia_ya_publicada(h, url, titulo, desc=""):
    if not h:
        return False, "sin_historial"
    url_norm = normalizar_url(url)
    hash_titulo = generar_hash(titulo)
    if es_titulo_generico(titulo):
        return True, "titulo_generico"
    if url_norm in h.get('urls_normalizadas', []):
        return True, "url_duplicada"
    if hash_titulo in h.get('hashes', []):
        return True, "hash_duplicado"
    for titulo_hist in h.get('titulos', []):
        sim = calcular_similitud(titulo, titulo_hist)
        if sim >= UMBRAL_SIMILITUD_TITULO:
            return True, f"similitud_titulo_{sim:.2f}"
    if desc:
        for desc_hist in h.get('descripciones', []):
            sim = calcular_similitud(desc[:150], desc_hist[:150])
            if sim >= UMBRAL_SIMILITUD_CONTENIDO:
                return True, f"similitud_contenido_{sim:.2f}"
    return False, "nuevo"

def guardar_historial(h, url, titulo, desc=""):
    url_norm = normalizar_url(url)
    hash_t = generar_hash(titulo)
    h['urls'].append(url)
    h['urls_normalizadas'].append(url_norm)
    h['hashes'].append(hash_t)
    h['timestamps'].append(datetime.now().isoformat())
    h['titulos'].append(titulo)
    h['descripciones'].append(desc[:400] if desc else "")
    h['estadisticas']['total_publicadas'] += 1
    for key in ['urls', 'urls_normalizadas', 'hashes', 'timestamps', 'titulos', 'descripciones']:
        if len(h[key]) > MAX_TITULOS_HISTORIA:
            h[key] = h[key][-MAX_TITULOS_HISTORIA:]
    guardar_json(HISTORIAL_PATH, h)
    return h

def obtener_newsapi():
    if not NEWS_API_KEY:
        return []
    noticias = []
    queries = ['Mexico AMLO crisis', 'Argentina Milei economy', 'Colombia Petro', 'Chile Boric', 'Peru Dina', 'Venezuela Maduro', 'Brazil Lula', 'Latin America crisis']
    for query in queries:
        try:
            r = requests.get('https://newsapi.org/v2/everything', params={'apiKey': NEWS_API_KEY, 'q': query, 'language': 'es', 'sortBy': 'publishedAt', 'pageSize': 3}, timeout=10).json()
            if r.get('status') == 'ok':
                for art in r.get('articles', []):
                    titulo = art.get('title', '')
                    if titulo and '[Removed]' not in titulo:
                        desc = art.get('description', '')
                        noticias.append({'titulo': limpiar_texto(titulo), 'descripcion': limpiar_texto(desc), 'url': art.get('url', ''), 'imagen': art.get('urlToImage'), 'fuente': f"NewsAPI:{art.get('source', {}).get('name', 'Unknown')}", 'fecha': art.get('publishedAt'), 'puntaje': calcular_puntaje_viral(titulo, desc)})
        except:
            continue
    log(f"NewsAPI: {len(noticias)} noticias", 'info')
    return noticias

def obtener_newsdata():
    if not NEWSDATA_API_KEY:
        return []
    noticias = []
    for cat in ['world', 'politics', 'business', 'entertainment', 'sports']:
        try:
            r = requests.get('https://newsdata.io/api/1/news', params={'apikey': NEWSDATA_API_KEY, 'language': 'es', 'category': cat, 'size': 8}, timeout=10).json()
            if r.get('status') == 'success':
                for art in r.get('results', []):
                    titulo = art.get('title', '')
                    if titulo:
                        desc = art.get('description', '')
                        noticias.append({'titulo': limpiar_texto(titulo), 'descripcion': limpiar_texto(desc), 'url': art.get('link', ''), 'imagen': art.get('image_url'), 'fuente': f"NewsData:{art.get('source_id', 'Unknown')}", 'fecha': art.get('pubDate'), 'puntaje': calcular_puntaje_viral(titulo, desc)})
        except:
            continue
    log(f"NewsData: {len(noticias)} noticias", 'info')
    return noticias

def obtener_gnews():
    if not GNEWS_API_KEY:
        return []
    noticias = []
    for topic in ['world', 'nation', 'business', 'technology', 'entertainment', 'sports']:
        try:
            r = requests.get('https://gnews.io/api/v4/top-headlines', params={'apikey': GNEWS_API_KEY, 'lang': 'es', 'max': 8, 'topic': topic}, timeout=10).json()
            for art in r.get('articles', []):
                titulo = art.get('title', '')
                if titulo:
                    desc = art.get('description', '')
                    noticias.append({'titulo': limpiar_texto(titulo), 'descripcion': limpiar_texto(desc), 'url': art.get('url', ''), 'imagen': art.get('image'), 'fuente': f"GNews:{art.get('source', {}).get('name', 'Unknown')}", 'fecha': art.get('publishedAt'), 'puntaje': calcular_puntaje_viral(titulo, desc)})
        except:
            continue
    log(f"GNews: {len(noticias)} noticias", 'info')
    return noticias

def obtener_rss_latam():
    feeds = ['https://www.infobae.com/arc/outboundfeeds/rss/mundo/', 'https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/internacional/portada', 'http://feeds.bbci.co.uk/mundo/rss.xml', 'https://feeds.france24.com/es/', 'https://www.clarin.com/rss/mundo/', 'https://www.lanacion.com.ar/feed/']
    noticias = []
    for feed_url in feeds:
        try:
            r = requests.get(feed_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=8)
            if r.status_code != 200:
                continue
            feed = feedparser.parse(r.content)
            if not feed or not feed.entries:
                continue
            fuente = feed.feed.get('title', 'RSS')[:20]
            for entry in feed.entries[:6]:
                titulo = entry.get('title', '')
                if not titulo:
                    continue
                titulo = re.sub(r'\s*-\s*[^-]*$', '', titulo)
                link = entry.get('link', '')
                if not link:
                    continue
                desc = entry.get('summary', '') or entry.get('description', '')
                desc = re.sub(r'<[^>]+>', '', desc)
                imagen = None
                if 'media_content' in entry:
                    imagen = entry.media_content[0].get('url')
                elif 'links' in entry:
                    for link_data in entry.links:
                        if link_data.get('type', '').startswith('image/'):
                            imagen = link_data.get('href')
                            break
                noticias.append({'titulo': limpiar_texto(titulo), 'descripcion': limpiar_texto(desc), 'url': link, 'imagen': imagen, 'fuente': f"RSS:{fuente}", 'fecha': entry.get('published'), 'puntaje': calcular_puntaje_viral(titulo, desc)})
        except:
            continue
    log(f"RSS LATAM: {len(noticias)} noticias", 'info')
    return noticias

def publicar_facebook(titulo, texto, imagen_path, hashtags):
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("ERROR: Faltan credenciales Facebook", 'error')
        return False
    mensaje = f"{texto}\n\n{hashtags}\n\nNoticias Virales LATAM 24/7\nSiguenos para mas contenido viral"
    if len(mensaje) > 2200:
        lineas = texto.split('\n')
        texto_corto = ""
        for linea in lineas:
            if len(texto_corto + linea + "\n") < 1800:
                texto_corto += linea + "\n"
            else:
                break
        mensaje = f"{texto_corto.rstrip()}\n\n[...]\n\n{hashtags}\n\nNoticias Virales LATAM 24/7"
    try:
        url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/photos"
        with open(imagen_path, 'rb') as f:
            files = {'file': ('imagen.jpg', f, 'image/jpeg')}
            data = {'message': mensaje, 'access_token': FB_ACCESS_TOKEN}
            r = requests.post(url, files=files, data=data, timeout=50)
            resultado = r.json()
            if 'id' in resultado:
                log(f"Publicado ID: {resultado['id']}", 'exito')
                return True
            else:
                log(f"Error Facebook: {resultado.get('error', {}).get('message', 'Unknown')}", 'error')
                return False
    except Exception as e:
        log(f"Excepcion publicando: {e}", 'error')
        return False

def verificar_tiempo():
    estado = cargar_json(ESTADO_PATH, {'ultima_publicacion': None, 'github_run_number': None})
    ultima = estado.get('ultima_publicacion')
    run_number = os.getenv('GITHUB_RUN_NUMBER')
    if run_number and estado.get('github_run_number') != run_number:
        log(f"Nuevo run detectado: #{run_number}", 'info')
        return True
    if not ultima:
        return True
    try:
        minutos = (datetime.now() - datetime.fromisoformat(ultima)).total_seconds() / 60
        if minutos < TIEMPO_ENTRE_PUBLICACIONES:
            log(f"Esperando... Ultima hace {minutos:.0f} min (min: {TIEMPO_ENTRE_PUBLICACIONES})", 'info')
            return False
    except:
        pass
    return True

def main():
    print("\n" + "="*60)
    print("BOT NOTICIAS VIRALES LATAM 24/7")
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Run: {os.getenv('GITHUB_RUN_ID', 'local')}")
    print("="*60)
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("ERROR: Faltan credenciales Facebook", 'error')
        return False
    if not verificar_tiempo():
        log("Demasiado pronto para publicar. Saliendo.", 'advertencia')
        return True
    historial = cargar_historial()
    stats = historial.get('estadisticas', {})
    log(f"Historial: {len(historial.get('urls', []))} URLs | 24h: {stats.get('ultimas_24h', 0)} posts | Total: {stats.get('total_publicadas', 0)}", 'info')
    todas_noticias = []
    if NEWS_API_KEY:
        todas_noticias.extend(obtener_newsapi())
    if NEWSDATA_API_KEY and len(todas_noticias) < 25:
        todas_noticias.extend(obtener_newsdata())
    if GNEWS_API_KEY and len(todas_noticias) < 35:
        todas_noticias.extend(obtener_gnews())
    if len(todas_noticias) < 25:
        rss_noticias = obtener_rss_latam()
        if rss_noticias:
            todas_noticias.extend(rss_noticias)
    urls_vistas = set()
    titulos_vistos = {}
    noticias_unicas = []
    for noticia in todas_noticias:
        url_norm = normalizar_url(noticia.get('url', ''))
        titulo = noticia.get('titulo', '')
        if url_norm in urls_vistas:
            continue
        duplicado = False
        for t_existente in titulos_vistos.keys():
            if calcular_similitud(titulo, t_existente) > 0.88:
                duplicado = True
                break
        if duplicado:
            continue
        urls_vistas.add(url_norm)
        titulos_vistos[titulo] = url_norm
        noticias_unicas.append(noticia)
    log(f"Total unicas: {len(noticias_unicas)} noticias", 'info')
    if not noticias_unicas:
        log("ERROR: No se encontraron noticias", 'error')
        return False
    noticias_unicas.sort(key=lambda x: (x.get('puntaje', 0), x.get('fecha', '')), reverse=True)
    seleccionada = None
    contenido_final = None
    max_intentos = min(40, len(noticias_unicas))
    for i, noticia in enumerate(noticias_unicas[:max_intentos]):
        url = noticia.get('url', '')
        titulo = noticia.get('titulo', '')
        desc = noticia.get('descripcion', '')
        if not url or not titulo:
            continue
        duplicada, razon = noticia_ya_publicada(historial, url, titulo, desc)
        if duplicada:
            log(f"   [{i+1}] Duplicada: {razon[:30]}", 'debug')
            continue
        if noticia.get('puntaje', 0) < 8:
            log(f"   [{i+1}] Puntaje bajo ({noticia.get('puntaje', 0)})", 'debug')
            continue
        log(f"\nNOTICIA: {titulo[:55]}...")
        log(f"   Fuente: {noticia['fuente']} | Viralidad: {noticia.get('puntaje', 0)}/100")
        contenido, _ = extraer_contenido(url)
        if contenido and len(contenido) >= 120:
            log(f"   Contenido: {len(contenido)} chars", 'exito')
            seleccionada = noticia
            contenido_final = contenido
            break
        else:
            if len(desc) >= 80:
                log(f"   Usando descripcion: {len(desc)} chars", 'exito')
                seleccionada = noticia
                contenido_final = desc
                break
    if not seleccionada:
        log("ERROR: No hay noticias validas", 'error')
        return False
    publicacion = construir_publicacion_viral(seleccionada['titulo'], contenido_final, seleccionada['fuente'])
    hashtags = generar_hashtags_virales(seleccionada['titulo'], contenido_final)
    log("Generando imagen viral...", 'imagen')
    imagen_path = generar_imagen_ia(seleccionada['titulo'], contenido_final)
    if not imagen_path:
        imagen_path = crear_imagen_backup(seleccionada['titulo'])
    if not imagen_path:
        log("ERROR: No se pudo generar imagen", 'error')
        return False
    exito = publicar_facebook(seleccionada['titulo'], publicacion, imagen_path, hashtags)
    try:
        if os.path.exists(imagen_path):
            os.remove(imagen_path)
    except:
        pass
    if exito:
        historial = guardar_historial(historial, seleccionada['url'], seleccionada['titulo'], seleccionada.get('descripcion', ''))
        estado = {'ultima_publicacion': datetime.now().isoformat(), 'github_run_number': os.getenv('GITHUB_RUN_NUMBER'), 'github_run_id': os.getenv('GITHUB_RUN_ID'), 'ultima_noticia': seleccionada['titulo'][:50]}
        guardar_json(ESTADO_PATH, estado)
        total = historial.get('estadisticas', {}).get('total_publicadas', 0)
        log(f"EXITO - Total: {total} noticias virales", 'exito')
        return True
    else:
        log("Publicacion fallida", 'error')
        return False

if __name__ == "__main__":
    try:
        success = main()
        exit(0 if success else 1)
    except Exception as e:
        log(f"Error critico: {e}", 'error')
        import traceback
        traceback.print_exc()
        exit(1)
