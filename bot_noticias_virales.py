#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BOT NOTICIAS VIRALES LATAM 24/7 - V4.2 COMPLETO
Usa imagen original de la noticia + texto overlay
Si no hay imagen original, usa backup con fondo de color
"""

import requests
import feedparser
import re
import hashlib
import json
import os
import random
import textwrap
from datetime import datetime
from difflib import SequenceMatcher
from urllib.parse import urlparse
from PIL import Image, ImageDraw, ImageFont

# ═══════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════

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

COLORES_BACKUP = {
    'urgente': (220, 20, 60),
    'negativa': (139, 0, 0),
    'positiva': (34, 139, 34),
    'neutral': (25, 25, 112),
    'deporte': (255, 140, 0),
    'politica': (75, 0, 130)
}

# ═══════════════════════════════════════════════════════════════
# FUNCIONES UTILITARIAS
# ═══════════════════════════════════════════════════════════════

def log(mensaje, tipo='info'):
    iconos = {'info': '[i]', 'exito': '[OK]', 'error': '[ERR]', 'advertencia': '[!]', 'imagen': '[IMG]'}
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
    palabras_alta = ["golpe de estado", "corrupcion", "dictadura", "protestas", "crisis", "impeachment",
                     "masacre", "feminicidio", "escandalo", "muerte", "viral", "trump", "milei", "amlo"]
    for palabra in palabras_alta:
        if palabra in txt:
            puntaje += 10
            if palabra in titulo.lower():
                puntaje += 5
    if 40 <= len(titulo) <= 90:
        puntaje += 5
    if re.search(r'\d+', titulo):
        puntaje += 3
    return puntaje

# ═══════════════════════════════════════════════════════════════
# DESCARGAR IMAGEN ORIGINAL
# ═══════════════════════════════════════════════════════════════

def descargar_imagen(url_imagen, titulo):
    """Descarga imagen original de la noticia"""
    if not url_imagen:
        return None

    try:
        log(f"Descargando imagen original...", 'imagen')

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(url_imagen, headers=headers, timeout=15)

        if response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            if 'image' not in content_type:
                log(f"URL no es imagen: {content_type}", 'advertencia')
                return None

            img_path = f'/tmp/original_{generar_hash(titulo)}.jpg'
            with open(img_path, 'wb') as f:
                f.write(response.content)

            if os.path.getsize(img_path) > 10000:
                log(f"Imagen descargada: {img_path} ({os.path.getsize(img_path)} bytes)", 'exito')
                return img_path
            else:
                os.remove(img_path)
                log("Imagen muy pequeña, descartada", 'advertencia')
                return None
        else:
            log(f"Error descargando imagen: HTTP {response.status_code}", 'error')
            return None

    except Exception as e:
        log(f"Error descargando: {e}", 'error')
        return None

# ═══════════════════════════════════════════════════════════════
# CREAR IMAGEN CON OVERLAY (Título sobre imagen original)
# ═══════════════════════════════════════════════════════════════

def crear_imagen_con_overlay(imagen_original_path, titulo, categoria="noticia"):
    """Agrega overlay de texto sobre imagen original"""
    try:
        # Abrir y redimensionar imagen
        img = Image.open(imagen_original_path)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img = img.resize((1200, 630), Image.Resampling.LANCZOS)

        draw = ImageDraw.Draw(img)

        # Fuentes
        try:
            font_titulo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 42)
            font_categoria = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
            font_footer = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        except:
            try:
                font_titulo = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 42)
                font_categoria = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 28)
                font_footer = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 20)
            except:
                font_titulo = ImageFont.load_default()
                font_categoria = font_footer = font_titulo

        # Color según categoría
        color_barra = {
            'urgente': (220, 20, 60),
            'politica': (75, 0, 130),
            'deporte': (255, 140, 0),
            'noticia': (25, 25, 112)
        }.get(categoria, (25, 25, 112))

        # 1. BARRA SUPERIOR
        draw.rectangle([(0, 0), (1200, 60)], fill=color_barra)
        draw.text((20, 15), categoria.upper(), font=font_categoria, fill=(255, 255, 255))
        draw.rectangle([(0, 60), (1200, 65)], fill=(255, 255, 255))

        # 2. BANDA INFERIOR OSCURA (gradiente)
        altura_banda = 200
        for i in range(altura_banda):
            draw.rectangle([(0, 630 - altura_banda + i), (1200, 630 - altura_banda + i + 1)],
                          fill=(0, 0, 0))

        # 3. TÍTULO
        titulo_limpio = titulo[:130]
        lineas = textwrap.wrap(titulo_limpio, width=32)
        if len(lineas) > 3:
            lineas = lineas[:3]
            lineas[-1] = lineas[-1][:30] + "..."

        y_start = 630 - altura_banda + 30
        for i, linea in enumerate(lineas):
            y = y_start + (i * 48)
            # Sombra
            draw.text((22, y + 2), linea, font=font_titulo, fill=(0, 0, 0))
            # Texto
            draw.text((20, y), linea, font=font_titulo, fill=(255, 255, 255))

        # 4. FOOTER
        fecha_str = datetime.now().strftime('%d/%m/%Y %H:%M')
        draw.rectangle([(20, 605), (350, 607)], fill=(255, 255, 255))
        draw.text((20, 610), f"NOTICIAS VIRALES LATAM 24/7 | {fecha_str}",
                 font=font_footer, fill=(200, 200, 200))

        # Guardar
        img_path = f'/tmp/viral_overlay_{generar_hash(titulo[:50])}.jpg'
        img.save(img_path, 'JPEG', quality=95)

        log(f"Overlay creado: {img_path}", 'exito')
        return img_path

    except Exception as e:
        log(f"Error overlay: {e}", 'error')
        import traceback
        traceback.print_exc()
        return None

# ═══════════════════════════════════════════════════════════════
# CREAR IMAGEN BACKUP (sin imagen original)
# ═══════════════════════════════════════════════════════════════

def crear_imagen_backup(titulo, categoria="noticia"):
    """Crea imagen de respaldo con fondo de color sólido"""
    try:
        width, height = 1200, 630

        # Color según categoría
        color_fondo = COLORES_BACKUP.get(categoria, COLORES_BACKUP['neutral'])

        img = Image.new('RGB', (width, height), color_fondo)
        draw = ImageDraw.Draw(img)

        # Gradient sutil
        for i in range(200):
            color_gradiente = (
                max(0, color_fondo[0] - 50),
                max(0, color_fondo[1] - 50),
                max(0, color_fondo[2] - 50)
            )
            draw.rectangle([(0, height - 200 + i), (width, height - 200 + i + 1)], fill=color_gradiente)

        # Fuentes
        try:
            font_titulo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
            font_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
            font_info = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        except:
            try:
                font_titulo = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 48)
                font_sub = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 24)
                font_info = font_sub
            except:
                font_titulo = ImageFont.load_default()
                font_sub = font_info = font_titulo

        # Barra superior
        draw.rectangle([(0, 0), (width, 15)], fill=(255, 255, 255))

        # Categoría
        draw.text((50, 35), categoria.upper(), font=font_info, fill=(220, 220, 220))

        # Título wrap
        titulo_limpio = titulo[:140]
        lineas = textwrap.wrap(titulo_limpio, width=28)
        if len(lineas) > 4:
            lineas = lineas[:4]
            lineas[-1] = lineas[-1][:25] + "..."

        altura_texto = len(lineas) * 55
        y_start = ((height - altura_texto) // 2) - 20

        for i, linea in enumerate(lineas):
            y = y_start + (i * 55)
            x = 60
            for offset in [(3, 3), (2, 2), (1, 1)]:
                draw.text((x + offset[0], y + offset[1]), linea, font=font_titulo, fill=(0, 0, 0))
            draw.text((x - 1, y - 1), linea, font=font_titulo, fill=(255, 255, 255))
            draw.text((x, y), linea, font=font_titulo, fill=(255, 255, 255))

        # Footer
        draw.rectangle([(50, height - 80), (width - 50, height - 78)], fill=(255, 255, 255))
        draw.text((50, height - 70), "NOTICIAS VIRALES LATAM 24/7", font=font_sub, fill=(255, 255, 255))
        fecha_str = datetime.now().strftime('%d/%m/%Y %H:%M')
        draw.text((50, height - 40), f"{fecha_str} | Información que importa",
                 font=font_info, fill=(200, 200, 200))

        img_path = f'/tmp/viral_backup_{generar_hash(titulo[:50])}.jpg'
        img.save(img_path, 'JPEG', quality=95)

        log(f"Imagen backup creada: {img_path}", 'exito')
        return img_path

    except Exception as e:
        log(f"Error creando backup: {e}", 'error')
        return None

# ═══════════════════════════════════════════════════════════════
# PROCESAR IMAGEN (decidir: original+overlay vs backup)
# ═══════════════════════════════════════════════════════════════

def procesar_imagen(noticia):
    """Decide qué tipo de imagen crear"""
    titulo = noticia.get('titulo', '')
    url_imagen = noticia.get('imagen')

    # Detectar categoría
    categoria = "noticia"
    titulo_lower = titulo.lower()
    if any(p in titulo_lower for p in ['trump', 'biden', 'presidente', 'gobierno', 'política', 'elecciones']):
        categoria = "politica"
    elif any(p in titulo_lower for p in ['fútbol', 'mundial', 'deporte', 'gol', 'partido', 'cop']):
        categoria = "deporte"
    elif any(p in titulo_lower for p in ['urgente', 'crisis', 'muerte', 'ataque', 'guerra', 'protesta']):
        categoria = "urgente"

    log(f"Categoría: {categoria}", 'info')

    # Intentar usar imagen original
    if url_imagen:
        log(f"URL imagen encontrada: {url_imagen[:80]}...", 'imagen')
        imagen_original = descargar_imagen(url_imagen, titulo)

        if imagen_original:
            resultado = crear_imagen_con_overlay(imagen_original, titulo, categoria)

            # Limpiar temporal
            try:
                os.remove(imagen_original)
            except:
                pass

            if resultado:
                return resultado, "original+overlay"
            else:
                log("Falló overlay, usando backup", 'advertencia')

    # Fallback: crear backup
    log("Creando imagen backup...", 'imagen')
    return crear_imagen_backup(titulo, categoria), "backup"

# ═══════════════════════════════════════════════════════════════
# HISTORIAL
# ═══════════════════════════════════════════════════════════════

def cargar_historial():
    default = {
        'urls': [], 'urls_normalizadas': [], 'hashes': [], 'timestamps': [],
        'titulos': [], 'descripciones': [],
        'estadisticas': {'total_publicadas': 0, 'ultimas_24h': 0}
    }
    h = cargar_json(HISTORIAL_PATH, default)
    for k in default:
        if k not in h:
            h[k] = default[k]
    return h

def noticia_ya_publicada(historial, url, titulo, desc=""):
    if not historial:
        return False, "sin_historial"

    url_norm = normalizar_url(url)
    hash_titulo = generar_hash(titulo)

    if es_titulo_generico(titulo):
        return True, "titulo_generico"

    if url_norm in historial.get('urls_normalizadas', []):
        return True, "url_duplicada"

    if hash_titulo in historial.get('hashes', []):
        return True, "hash_duplicado"

    for titulo_hist in historial.get('titulos', []):
        sim = calcular_similitud(titulo, titulo_hist)
        if sim >= UMBRAL_SIMILITUD_TITULO:
            return True, f"similitud_titulo_{sim:.2f}"

    return False, "nuevo"

def guardar_historial(historial, url, titulo, desc=""):
    url_norm = normalizar_url(url)
    hash_t = generar_hash(titulo)

    historial['urls'].append(url)
    historial['urls_normalizadas'].append(url_norm)
    historial['hashes'].append(hash_t)
    historial['timestamps'].append(datetime.now().isoformat())
    historial['titulos'].append(titulo)
    historial['descripciones'].append(desc[:400] if desc else "")

    stats = historial.get('estadisticas', {'total_publicadas': 0})
    stats['total_publicadas'] = stats.get('total_publicadas', 0) + 1
    historial['estadisticas'] = stats

    for key in ['urls', 'urls_normalizadas', 'hashes', 'timestamps', 'titulos', 'descripciones']:
        if len(historial[key]) > MAX_TITULOS_HISTORIA:
            historial[key] = historial[key][-MAX_TITULOS_HISTORIA:]

    guardar_json(HISTORIAL_PATH, historial)
    return historial

# ═══════════════════════════════════════════════════════════════
# FUENTES DE NOTICIAS
# ═══════════════════════════════════════════════════════════════

def obtener_newsapi():
    """Obtiene noticias de NewsAPI"""
    if not NEWS_API_KEY:
        return []

    noticias = []
    queries = ['Trump', 'Biden', 'Mexico AMLO', 'Argentina Milei', 'Colombia Petro']

    for query in queries:
        try:
            r = requests.get('https://newsapi.org/v2/everything',
                           params={
                               'apiKey': NEWS_API_KEY,
                               'q': query,
                               'language': 'es',
                               'sortBy': 'publishedAt',
                               'pageSize': 3
                           },
                           timeout=10).json()

            if r.get('status') == 'ok':
                for art in r.get('articles', []):
                    titulo = art.get('title', '')
                    if titulo and '[Removed]' not in titulo:
                        noticias.append({
                            'titulo': limpiar_texto(titulo),
                            'descripcion': limpiar_texto(art.get('description', '')),
                            'url': art.get('url', ''),
                            'imagen': art.get('urlToImage'),
                            'fuente': f"NewsAPI:{art.get('source', {}).get('name', 'Unknown')}",
                            'fecha': art.get('publishedAt'),
                            'puntaje': calcular_puntaje_viral(titulo, art.get('description', ''))
                        })
        except Exception as e:
            log(f"Error NewsAPI: {e}", 'error')
            continue

    log(f"NewsAPI: {len(noticias)} noticias", 'info')
    return noticias

def obtener_gnews():
    """Obtiene noticias de GNews"""
    if not GNEWS_API_KEY:
        return []

    noticias = []
    topics = ['world', 'nation', 'business']

    for topic in topics:
        try:
            r = requests.get('https://gnews.io/api/v4/top-headlines',
                           params={
                               'apikey': GNEWS_API_KEY,
                               'lang': 'es',
                               'max': 5,
                               'topic': topic
                           },
                           timeout=10).json()

            for art in r.get('articles', []):
                titulo = art.get('title', '')
                if titulo:
                    noticias.append({
                        'titulo': limpiar_texto(titulo),
                        'descripcion': limpiar_texto(art.get('description', '')),
                        'url': art.get('url', ''),
                        'imagen': art.get('image'),
                        'fuente': f"GNews:{art.get('source', {}).get('name', 'Unknown')}",
                        'fecha': art.get('publishedAt'),
                        'puntaje': calcular_puntaje_viral(titulo, art.get('description', ''))
                    })
        except Exception as e:
            log(f"Error GNews: {e}", 'error')
            continue

    log(f"GNews: {len(noticias)} noticias", 'info')
    return noticias

def obtener_rss():
    """Obtiene noticias de feeds RSS"""
    feeds = [
        'https://www.infobae.com/arc/outboundfeeds/rss/mundo/',
        'http://feeds.bbci.co.uk/mundo/rss.xml',
        'https://www.clarin.com/rss/mundo/'
    ]

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
            for entry in feed.entries[:5]:
                titulo = entry.get('title', '')
                if not titulo:
                    continue

                link = entry.get('link', '')
                if not link:
                    continue

                desc = entry.get('summary', '') or entry.get('description', '')
                desc = re.sub(r'<[^>]+>', '', desc)

                # Buscar imagen en el feed
                imagen = None
                if 'media_content' in entry:
                    imagen = entry.media_content[0].get('url')
                elif 'links' in entry:
                    for link_data in entry.links:
                        if link_data.get('type', '').startswith('image/'):
                            imagen = link_data.get('href')
                            break

                noticias.append({
                    'titulo': limpiar_texto(titulo),
                    'descripcion': limpiar_texto(desc),
                    'url': link,
                    'imagen': imagen,
                    'fuente': f"RSS:{fuente}",
                    'fecha': entry.get('published'),
                    'puntaje': calcular_puntaje_viral(titulo, desc)
                })
        except Exception as e:
            log(f"Error RSS: {e}", 'error')
            continue

    log(f"RSS: {len(noticias)} noticias", 'info')
    return noticias

# ═══════════════════════════════════════════════════════════════
# PUBLICACIÓN FACEBOOK
# ═══════════════════════════════════════════════════════════════

def publicar_facebook(titulo, texto, imagen_path, hashtags):
    """Publica en Facebook"""
    log(f"Iniciando publicación Facebook...", 'info')
    log(f"Page ID: {FB_PAGE_ID}", 'debug')
    log(f"Token configurado: {'Sí' if FB_ACCESS_TOKEN else 'No'}", 'debug')
    log(f"Imagen: {imagen_path}", 'debug')

    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("ERROR: Faltan credenciales Facebook", 'error')
        return False

    if not imagen_path or not os.path.exists(imagen_path):
        log("ERROR: No hay imagen para publicar", 'error')
        return False

    mensaje = f"{texto}\n\n{hashtags}\n\nNoticias Virales LATAM 24/7"

    if len(mensaje) > 2200:
        mensaje = mensaje[:2100] + "..."

    try:
        url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/photos"

        with open(imagen_path, 'rb') as f:
            files = {'file': ('imagen.jpg', f, 'image/jpeg')}
            data = {
                'message': mensaje,
                'access_token': FB_ACCESS_TOKEN,
                'published': 'true'
            }

            log("Enviando POST a Facebook...", 'info')
            response = requests.post(url, files=files, data=data, timeout=60)

            log(f"Respuesta HTTP: {response.status_code}", 'info')
            log(f"Respuesta: {response.text[:300]}", 'debug')

            resultado = response.json()

            if 'id' in resultado:
                log(f"✓ Publicado ID: {resultado['id']}", 'exito')
                return True
            else:
                error = resultado.get('error', {})
                log(f"✗ Error: {error.get('message', 'Desconocido')}", 'error')
                log(f"  Código: {error.get('code', 'N/A')}", 'error')
                return False

    except Exception as e:
        log(f"✗ Excepción: {e}", 'error')
        import traceback
        traceback.print_exc()
        return False

# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def verificar_tiempo():
    """Verifica tiempo entre publicaciones"""
    estado = cargar_json(ESTADO_PATH, {'ultima_publicacion': None})
    ultima = estado.get('ultima_publicacion')

    # Si es GitHub Actions, siempre permitir
    if os.getenv('GITHUB_RUN_NUMBER'):
        return True

    if not ultima:
        return True

    try:
        ultima_dt = datetime.fromisoformat(ultima)
        minutos = (datetime.now() - ultima_dt).total_seconds() / 60
        if minutos < TIEMPO_ENTRE_PUBLICACIONES:
            log(f"Esperando... Última hace {minutos:.0f} min", 'info')
            return False
    except:
        pass

    return True

def main():
    print("\n" + "=" * 60)
    print("BOT NOTICIAS VIRALES LATAM 24/7 - V4.2")
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Verificar credenciales
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("ERROR: Faltan credenciales Facebook", 'error')
        log("Configura las variables de entorno:", 'error')
        log("  export FB_PAGE_ID='tu_page_id'", 'error')
        log("  export FB_ACCESS_TOKEN='tu_token'", 'error')
        return False

    # Verificar tiempo
    if not verificar_tiempo():
        return True

    # Cargar historial
    historial = cargar_historial()
    log(f"Historial: {len(historial.get('urls', []))} URLs", 'info')

    # Obtener noticias
    noticias = []

    if NEWS_API_KEY:
        noticias.extend(obtener_newsapi())
    if GNEWS_API_KEY:
        noticias.extend(obtener_gnews())
    if len(noticias) < 5:
        noticias.extend(obtener_rss())

    if not noticias:
        log("No se encontraron noticias", 'error')
        return False

    log(f"Total noticias: {len(noticias)}", 'info')

    # Filtrar duplicados y ordenar
    noticias_unicas = []
    urls_vistas = set()

    for n in noticias:
        url_norm = normalizar_url(n.get('url', ''))
        if url_norm in urls_vistas:
            continue

        duplicada, razon = noticia_ya_publicada(historial, n['url'], n['titulo'])
        if duplicada:
            log(f"Duplicada ({razon}): {n['titulo'][:40]}...", 'debug')
            continue

        urls_vistas.add(url_norm)
        noticias_unicas.append(n)

    if not noticias_unicas:
        log("Todas las noticias ya fueron publicadas", 'advertencia')
        return False

    # Ordenar por puntaje
    noticias_unicas.sort(key=lambda x: x.get('puntaje', 0), reverse=True)

    # Seleccionar mejor noticia
    seleccionada = noticias_unicas[0]
    log(f"Seleccionada: {seleccionada['titulo'][:60]}...", 'info')
    log(f"Puntaje: {seleccionada.get('puntaje', 0)}", 'info')

    # PROCESAR IMAGEN
    imagen_path, tipo_imagen = procesar_imagen(seleccionada)
    log(f"Tipo imagen: {tipo_imagen}", 'imagen')

    if not imagen_path:
        log("No se pudo crear imagen", 'error')
        return False

    # Preparar texto
    contenido = seleccionada.get('descripcion', '')
    if len(contenido) > 300:
        contenido = contenido[:297] + "..."

    publicacion = f"{seleccionada['titulo']}\n\n{contenido}\n\nFuente: {seleccionada['fuente']}"
    hashtags = "#NoticiasVirales #LATAM #UltimaHora #Viral"

    # Publicar
    exito = publicar_facebook(seleccionada['titulo'], publicacion, imagen_path, hashtags)

    # Limpiar
    try:
        if os.path.exists(imagen_path):
            os.remove(imagen_path)
            log("Imagen temporal eliminada", 'debug')
    except:
        pass

    if exito:
        # Guardar en historial
        guardar_historial(historial, seleccionada['url'], seleccionada['titulo'],
                         seleccionada.get('descripcion', ''))

        # Guardar estado
        estado = {
            'ultima_publicacion': datetime.now().isoformat(),
            'ultima_noticia': seleccionada['titulo'][:50]
        }
        guardar_json(ESTADO_PATH, estado)

        total = historial.get('estadisticas', {}).get('total_publicadas', 0)
        log(f"✓ ÉXITO - Total publicadas: {total}", 'exito')
        return True
    else:
        log("✗ PUBLICACIÓN FALLIDA", 'error')
        return False

if __name__ == "__main__":
    try:
        success = main()
        exit(0 if success else 1)
    except Exception as e:
        log(f"Error crítico: {e}", 'error')
        import traceback
        traceback.print_exc()
        exit(1)
