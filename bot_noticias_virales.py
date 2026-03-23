#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BOT NOTICIAS VIRALES LATAM 24/7 - V5.0 COMPLETO
Distribución geográfica: 50% Sudamérica, 30% Norteamérica, 20% Centroamérica/Caribe
Hashtags automáticos por tema y ubicación
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
    'politica': (75, 0, 130),
    'economia': (0, 100, 0),
    'tecnologia': (0, 128, 128),
    'migracion': (128, 0, 128),
    'conflicto': (178, 34, 34),
    'ciencia': (70, 130, 180),
    'corrupcion': (139, 69, 19)
}

# ═══════════════════════════════════════════════════════════════
# DICCIONARIOS DE HASHTAGS Y UBICACIONES
# ═══════════════════════════════════════════════════════════════

# Mapeo de países para hashtags de ubicación
PAISES_LATAM = {
    # Sudamérica (50%)
    'argentina': '#Argentina', 'buenos aires': '#Argentina',
    'chile': '#Chile', 'santiago': '#Chile', 'valparaíso': '#Chile',
    'brasil': '#Brasil', 'sao paulo': '#Brasil', 'rio de janeiro': '#Brasil', 'brasilia': '#Brasil',
    'colombia': '#Colombia', 'bogotá': '#Colombia', 'medellín': '#Colombia', 'cali': '#Colombia',
    'perú': '#Perú', 'peru': '#Perú', 'lima': '#Perú',
    'venezuela': '#Venezuela', 'caracas': '#Venezuela',
    'ecuador': '#Ecuador', 'quito': '#Ecuador', 'guayaquil': '#Ecuador',
    'bolivia': '#Bolivia', 'la paz': '#Bolivia', 'sucre': '#Bolivia',
    'paraguay': '#Paraguay', 'asunción': '#Paraguay',
    'uruguay': '#Uruguay', 'montevideo': '#Uruguay',
    'guyana': '#Guyana', 'georgetown': '#Guyana',
    'surinam': '#Surinam', 'suriname': '#Surinam',

    # Norteamérica (30%)
    'mexico': '#México', 'méxico': '#México', 'cdmx': '#México', 'ciudad de mexico': '#México',
    'estados unidos': '#EEUU', 'eeuu': '#EEUU', 'usa': '#EEUU', 'washington': '#EEUU', 'nueva york': '#EEUU',
    'canada': '#Canadá', 'canadá': '#Canadá', 'ottawa': '#Canadá', 'toronto': '#Canadá',

    # Centroamérica y Caribe (20%)
    'guatemala': '#Guatemala', 'ciudad de guatemala': '#Guatemala',
    'el salvador': '#ElSalvador', 'san salvador': '#ElSalvador',
    'honduras': '#Honduras', 'tegucigalpa': '#Honduras',
    'nicaragua': '#Nicaragua', 'managua': '#Nicaragua',
    'costa rica': '#CostaRica', 'san josé': '#CostaRica',
    'panama': '#Panamá', 'panamá': '#Panamá', 'ciudad de panama': '#Panamá',
    'cuba': '#Cuba', 'la habana': '#Cuba',
    'república dominicana': '#RepúblicaDominicana', 'dominicana': '#RepúblicaDominicana', 'santo domingo': '#RepúblicaDominicana',
    'puerto rico': '#PuertoRico', 'san juan': '#PuertoRico',
    'haití': '#Haití', 'haiti': '#Haití', 'puerto príncipe': '#Haití',
    'jamaica': '#Jamaica', 'kingston': '#Jamaica',
    'trinidad': '#TrinidadYTobago', 'tobago': '#TrinidadYTobago',
    'bahamas': '#Bahamas', 'nassau': '#Bahamas',
    'barbados': '#Barbados',
    'belice': '#Belice', 'belize': '#Belice',
}

# Hashtags por categoría/tema
HASHTAGS_CATEGORIA = {
    'politica': ['#Política', '#PolíticaLATAM', '#Gobierno', '#Elecciones'],
    'economia': ['#Economía', '#EconomíaLATAM', '#Finanzas', '#Mercados', '#Inflación'],
    'internacional': ['#Internacional', '#Mundo', '#Global', '#Diplomacia'],
    'tecnologia': ['#Tecnología', '#Tech', '#Innovación', '#Digital', '#IA', '#Ciberseguridad'],
    'migracion': ['#Migración', '#Migrantes', '#Frontera', '#Asilo', '#Refugiados'],
    'narcotrafico': ['#Narco', '#Cárteles', '#Seguridad', '#CrimenOrganizado', '#Drogas'],
    'guerra': ['#Guerra', '#Conflicto', '#Militar', '#Defensa', '#Geopolítica'],
    'conflicto': ['#Conflicto', '#Crisis', '#Violencia', '#Protestas', '#Manifestaciones'],
    'ciencia': ['#Ciencia', '#Investigación', '#Descubrimiento', '#Salud', '#Medicina'],
    'corrupcion': ['#Corrupción', '#Impunidad', '#Transparencia', '#Justicia'],
    'escandalo': ['#Escándalo', '#Polemica', '#Controversia'],
    'deporte': ['#Deportes', '#Fútbol', '#DeporteLATAM'],
    'urgente': ['#Urgente', '#ÚltimaHora', '#Alerta', '#Breaking'],
    'default': ['#NoticiasVirales', '#LATAM', '#Actualidad']
}

# Palabras clave por categoría para detección
PALABRAS_CLAVE = {
    'politica': ['presidente', 'gobierno', 'congreso', 'senado', 'diputado', 'senador', 'ministro', 
                 'elecciones', 'voto', 'partido', 'oposición', 'oficialismo', 'impeachment', 
                 'golpe de estado', 'golpe estado', 'dictadura', 'democracia', 'gabinete', 
                 'legislatura', 'parlamento', 'cámara', 'tribunal', 'corte suprema', 
                 'milei', 'petro', 'maduro', 'lula', 'boric', 'amlo', 'trump', 'biden'],

    'economia': ['economía', 'económica', 'finanzas', 'mercado', 'bolsa', 'inflación', 
                 'devaluación', 'peso', 'dólar', 'euro', 'bitcoin', 'cripto', 'banco central',
                 'reservas', 'deuda', 'fmi', 'bm', 'comercio', 'exportación', 'importación',
                 'pib', 'recesión', 'crisis económica', 'bonos', 'inversión', 'empresas'],

    'internacional': ['onu', 'oea', 'union europea', 'otan', 'g20', 'g7', 'brics',
                      'relaciones exteriores', 'embajada', 'embajador', 'sanciones',
                      'acuerdo internacional', 'tratado', 'cumbre', 'cumbre de las américas'],

    'tecnologia': ['tecnología', 'tech', 'inteligencia artificial', 'ia', 'chatgpt', 
                   'ciberseguridad', 'hackeo', 'hacker', 'ciberataque', 'digital', 
                   'internet', 'redes sociales', 'meta', 'google', 'apple', 'microsoft',
                   'startup', 'innovación', '5g', 'telecomunicaciones', 'satélite'],

    'migracion': ['migración', 'migrantes', 'inmigración', 'frontera', 'fronteriza',
                  'deportación', 'asilo', 'refugiado', 'coyote', 'tráfico personas',
                  'caravana migrante', 'muro', 'visas', 'green card', 'remesas'],

    'narcotrafico': ['narcotráfico', 'cartel', 'cártel', 'sinaloa', 'jalisco', 'cjng',
                     'medellín', 'cali', 'pablo escobar', 'el chapo', 'fentanilo',
                     'cocaína', 'marihuana', 'droga', 'tráfico drogas', 'lavado dinero',
                     'crimen organizado', 'mafia', 'narcotraficante'],

    'guerra': ['guerra', 'conflicto armado', 'ejército', 'militar', 'defensa', 
               'armas', 'misil', 'bomba', 'ataque', 'invasión', 'ucrania', 'hamas',
               'israel', 'palestina', 'gaza', 'terrorismo', 'yihad', 'extremismo'],

    'conflicto': ['protesta', 'manifestación', 'marcha', 'huelga', 'paro', 'corte ruta',
                  'disturbios', 'enfrentamiento', 'represión', 'violencia', 'saqueo',
                  'crisis política', 'inestabilidad', 'tensión', 'conflicto social'],

    'ciencia': ['ciencia', 'investigación', 'estudio', 'descubrimiento', 'salud',
                'pandemia', 'vacuna', 'virus', 'covid', 'medicina', 'hospital',
                'médico', 'enfermedad', 'tratamiento', 'cáncer', 'espacio', 'nasa',
                'cambio climático', 'calentamiento global', 'medio ambiente'],

    'corrupcion': ['corrupción', 'soborno', 'coima', 'mordida', 'desfalco', 'fraude',
                   'evasión', 'impuestos', 'lavado activos', 'enriquecimiento ilícito',
                   'obras públicas', 'licitación', 'compra votos', 'impunidad'],

    'escandalo': ['escándalo', 'polémica', 'controversia', 'denuncia', 'acusación',
                  'investigación', 'juicio', 'juicio político', 'impeachment',
                  'filtración', 'wikileaks', 'panama papers', 'pandora papers']
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
        stop_words = {'el', 'la', 'de', 'y', 'en', 'the', 'of', 'a', 'que', 'con', 'un', 'una', 'para', 'por', 'con', 'al', 'del', 'lo', 'le', 'se', 'es', 'son', 'fue', 'era', 'será'}
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

def detectar_categoria(titulo, descripcion):
    """Detecta la categoría de la noticia basada en palabras clave"""
    texto = f"{titulo} {descripcion}".lower()

    puntajes = {}
    for categoria, palabras in PALABRAS_CLAVE.items():
        puntajes[categoria] = sum(1 for palabra in palabras if palabra in texto)

    if puntajes:
        max_categoria = max(puntajes, key=puntajes.get)
        if puntajes[max_categoria] > 0:
            return max_categoria

    return 'default'

def detectar_ubicacion(titulo, descripcion):
    """Detecta el país/ubicación de la noticia"""
    texto = f"{titulo} {descripcion}".lower()

    for pais, hashtag in PAISES_LATAM.items():
        if pais in texto:
            return hashtag

    return None

def generar_hashtags(titulo, descripcion, categoria):
    """Genera hashtags relevantes para la noticia"""
    hashtags = []

    # Hashtag de ubicación
    ubicacion = detectar_ubicacion(titulo, descripcion)
    if ubicacion:
        hashtags.append(ubicacion)

    # Hashtags de categoría
    if categoria in HASHTAGS_CATEGORIA:
        hashtags.extend(HASHTAGS_CATEGORIA[categoria][:2])  # Máximo 2 de categoría
    else:
        hashtags.extend(HASHTAGS_CATEGORIA['default'])

    # Hashtags específicos del contenido
    texto = f"{titulo} {descripcion}".lower()

    # Detectar temas específicos adicionales
    if any(p in texto for p in ['trump', 'biden', 'eeuu', 'estados unidos']):
        if '#EEUU' not in hashtags:
            hashtags.append('#EEUU')

    if any(p in texto for p in ['milei', 'argentina']):
        if '#Argentina' not in hashtags:
            hashtags.append('#Argentina')

    if any(p in texto for p in ['petro', 'colombia']):
        if '#Colombia' not in hashtags:
            hashtags.append('#Colombia')

    if any(p in texto for p in ['maduro', 'venezuela']):
        if '#Venezuela' not in hashtags:
            hashtags.append('#Venezuela')

    if any(p in texto for p in ['boric', 'chile']):
        if '#Chile' not in hashtags:
            hashtags.append('#Chile')

    if any(p in texto for p in ['lula', 'brasil']):
        if '#Brasil' not in hashtags:
            hashtags.append('#Brasil')

    if any(p in texto for p in ['amlo', 'méxico', 'mexico']):
        if '#México' not in hashtags:
            hashtags.append('#México')

    # Hashtags generales siempre presentes
    hashtags.append('#NoticiasVirales')
    hashtags.append('#LATAM')

    # Eliminar duplicados manteniendo orden
    hashtags_unicos = []
    for h in hashtags:
        if h not in hashtags_unicos:
            hashtags_unicos.append(h)

    return ' '.join(hashtags_unicos[:6])  # Máximo 6 hashtags

def calcular_puntaje_viral(titulo, desc):
    txt = f"{titulo} {desc}".lower()
    puntaje = 0

    # Palabras de alto impacto
    palabras_alta = ["golpe de estado", "corrupcion", "dictadura", "protestas", "crisis", 
                     "impeachment", "masacre", "feminicidio", "escandalo", "muerte", 
                     "viral", "trump", "milei", "amlo", "petro", "maduro", "guerra",
                     "cártel", "narco", "fentanilo", "inflación", "devaluación",
                     "hackeo", "ciberataque", "pandemia", "vacuna", "urgente"]

    for palabra in palabras_alta:
        if palabra in txt:
            puntaje += 10
            if palabra in titulo.lower():
                puntaje += 5

    # Bonus por longitud óptima de título
    if 40 <= len(titulo) <= 90:
        puntaje += 5

    # Bonus por números (datos específicos)
    if re.search(r'\d+', titulo):
        puntaje += 3

    # Bonus por ubicación detectada (relevancia local)
    if detectar_ubicacion(titulo, desc):
        puntaje += 5

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
# CREAR IMAGEN CON OVERLAY
# ═══════════════════════════════════════════════════════════════

def crear_imagen_con_overlay(imagen_original_path, titulo, categoria="noticia"):
    """Agrega overlay de texto sobre imagen original"""
    try:
        img = Image.open(imagen_original_path)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img = img.resize((1200, 630), Image.Resampling.LANCZOS)

        draw = ImageDraw.Draw(img)

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

        color_barra = COLORES_BACKUP.get(categoria, COLORES_BACKUP['neutral'])

        # Barra superior
        draw.rectangle([(0, 0), (1200, 60)], fill=color_barra)
        draw.text((20, 15), categoria.upper(), font=font_categoria, fill=(255, 255, 255))
        draw.rectangle([(0, 60), (1200, 65)], fill=(255, 255, 255))

        # Banda inferior oscura
        altura_banda = 200
        for i in range(altura_banda):
            draw.rectangle([(0, 630 - altura_banda + i), (1200, 630 - altura_banda + i + 1)],
                          fill=(0, 0, 0))

        # Título
        titulo_limpio = titulo[:130]
        lineas = textwrap.wrap(titulo_limpio, width=32)
        if len(lineas) > 3:
            lineas = lineas[:3]
            lineas[-1] = lineas[-1][:30] + "..."

        y_start = 630 - altura_banda + 30
        for i, linea in enumerate(lineas):
            y = y_start + (i * 48)
            draw.text((22, y + 2), linea, font=font_titulo, fill=(0, 0, 0))
            draw.text((20, y), linea, font=font_titulo, fill=(255, 255, 255))

        # Footer
        fecha_str = datetime.now().strftime('%d/%m/%Y %H:%M')
        draw.rectangle([(20, 605), (350, 607)], fill=(255, 255, 255))
        draw.text((20, 610), f"NOTICIAS VIRALES LATAM 24/7 | {fecha_str}",
                 font=font_footer, fill=(200, 200, 200))

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
# CREAR IMAGEN BACKUP
# ═══════════════════════════════════════════════════════════════

def crear_imagen_backup(titulo, categoria="noticia"):
    """Crea imagen de respaldo con fondo de color sólido"""
    try:
        width, height = 1200, 630
        color_fondo = COLORES_BACKUP.get(categoria, COLORES_BACKUP['neutral'])

        img = Image.new('RGB', (width, height), color_fondo)
        draw = ImageDraw.Draw(img)

        for i in range(200):
            color_gradiente = (
                max(0, color_fondo[0] - 50),
                max(0, color_fondo[1] - 50),
                max(0, color_fondo[2] - 50)
            )
            draw.rectangle([(0, height - 200 + i), (width, height - 200 + i + 1)], fill=color_gradiente)

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

        draw.rectangle([(0, 0), (width, 15)], fill=(255, 255, 255))
        draw.text((50, 35), categoria.upper(), font=font_info, fill=(220, 220, 220))

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
            draw.text((x, y), linea, font=font_titulo, fill=(255, 255, 255))

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
# PROCESAR IMAGEN
# ═══════════════════════════════════════════════════════════════

def procesar_imagen(noticia):
    """Decide qué tipo de imagen crear"""
    titulo = noticia.get('titulo', '')
    url_imagen = noticia.get('imagen')
    categoria = noticia.get('categoria', 'noticia')

    log(f"Categoría: {categoria}", 'info')

    if url_imagen:
        log(f"URL imagen encontrada: {url_imagen[:80]}...", 'imagen')
        imagen_original = descargar_imagen(url_imagen, titulo)

        if imagen_original:
            resultado = crear_imagen_con_overlay(imagen_original, titulo, categoria)
            try:
                os.remove(imagen_original)
            except:
                pass

            if resultado:
                return resultado, "original+overlay"
            else:
                log("Falló overlay, usando backup", 'advertencia')

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
# FUENTES RSS POR REGIÓN
# ═══════════════════════════════════════════════════════════════

# SUDAMÉRICA (50% de las noticias)
FEEDS_SUDAMERICA = [
    # Argentina
    'https://www.clarin.com/rss/politica/',
    'https://www.clarin.com/rss/economia/',
    'https://www.infobae.com/arc/outboundfeeds/rss/argentina/',
    'https://www.lanacion.com.ar/rss/politica.xml',
    'https://www.pagina12.com.ar/rss/secciones/el-pais/notas',
    'https://www.cronista.com/rss/feed.xml',
    'https://www.ambito.com/rss/home.xml',

    # Chile
    'https://www.emol.com/rss/economia.xml',
    'https://www.emol.com/rss/nacional.xml',
    'https://www.latercera.com/feed/',
    'https://www.lacuarta.com/feed/',
    'https://www.biobiochile.cl/feed/',
    'https://www.cooperativa.cl/noticias/rss/',

    # Colombia
    'https://www.elespectador.com/rss/',
    'https://www.semana.com/rss/',
    'https://www.eltiempo.com/rss/',
    'https://www.bluradio.com/rss/',
    'https://www.pulzo.com/rss/',

    # Brasil
    'https://g1.globo.com/rss/g1/politica/',
    'https://g1.globo.com/rss/g1/economia/',
    'https://www.folha.uol.com.br/emcimadahora/rss091.xml',
    'https://www.estadao.com.br/rss/',
    'https://oglobo.globo.com/rss.xml',

    # Perú
    'https://elcomercio.pe/feed/',
    'https://larepublica.pe/rss/',
    'https://gestion.pe/feed/',
    'https://www.infobae.com/arc/outboundfeeds/rss/peru/',

    # Venezuela
    'https://www.infobae.com/arc/outboundfeeds/rss/america/venezuela/',
    'https://www.lapatilla.com/feed/',
    'https://www.elnacional.com/feed/',

    # Ecuador
    'https://www.elcomercio.com/rss/',
    'https://www.eluniverso.com/rss/',
    'https://www.infobae.com/arc/outboundfeeds/rss/america/ecuador/',

    # Bolivia
    'https://www.lostiempos.com/rss/ultimas-noticias.xml',
    'https://www.eldeber.com.bo/rss/',
    'https://www.opinion.com.bo/rss/',

    # Uruguay
    'https://www.elpais.com.uy/rss/',
    'https://www.montevideo.com.uy/rss/',

    # Paraguay
    'https://www.ultimahora.com/rss/',
    'https://www.abc.com.py/rss/',
]

# NORTEAMÉRICA (30% de las noticias)
FEEDS_NORTEAMERICA = [
    # México
    'https://www.reforma.com/rss/politica.xml',
    'https://www.jornada.com.mx/rss/politica.xml',
    'https://www.excelsior.com.mx/rss/politica.xml',
    'https://www.eluniversal.com.mx/rss/politica.xml',
    'https://www.milenio.com/rss/politica',
    'https://www.infobae.com/arc/outboundfeeds/rss/mexico/',
    'https://aristeguinoticias.com/feed/',
    'https://www.animalpolitico.com/feed/',
    'https://www.sinembargo.mx/feed/',

    # EEUU - Latino
    'https://www.univision.com/rss/news',
    'https://www.telemundo.com/rss',
    'https://www.lanacion.com.ar/rss/mundo.xml',
    'https://www.infobae.com/arc/outboundfeeds/rss/america/estados-unidos/',

    # Canadá
    'https://www.theglobeandmail.com/feeds/rss/',
    'https://www.cbc.ca/cmlink/rss-topstories',
]

# CENTROAMÉRICA Y CARIBE (20% de las noticias)
FEEDS_CENTROAMERICA_CARIBE = [
    # Centroamérica
    'https://www.prensalibre.com/rss/',
    'https://www.elsalvador.com/rss/',
    'https://www.laprensa.hn/rss/',
    'https://www.elnuevodiario.com.ni/rss/',
    'https://www.nacion.com/rss/',
    'https://www.prensa.com/rss/',

    # Caribe
    'https://www.elnuevoherald.com/rss/',
    'https://www.diariolibre.com/rss/',
    'https://listindiario.com/rss/',
    'https://www.elcaribe.com.do/rss/',
    'https://www.jamaicaobserver.com/rss/',
    'https://www.cubanet.org/feed/',
    'https://www.14ymedio.com/rss/',
    'https://www.elnacional.com.do/rss/',
]

# Todos los feeds combinados
TODOS_LOS_FEEDS = FEEDS_SUDAMERICA + FEEDS_NORTEAMERICA + FEEDS_CENTROAMERICA_CARIBE

# ═══════════════════════════════════════════════════════════════
# FUENTES DE NOTICIAS
# ═══════════════════════════════════════════════════════════════

def obtener_newsapi():
    """Obtiene noticias de NewsAPI con queries ampliadas"""
    if not NEWS_API_KEY:
        return []

    noticias = []

    # Queries ampliadas por categoría
    queries = [
        # Política
        'Trump', 'Biden', 'AMLO', 'Milei', 'Petro', 'Maduro', 'Lula', 'Boric',
        'golpe de estado', 'impeachment', 'elecciones', 'gobierno',

        # Economía
        'economía Latinoamérica', 'inflación', 'devaluación', 'FMI', 'crisis económica',

        # Migración
        'migración', 'migrantes', 'frontera', 'deportación', 'asilo',

        # Narcotráfico
        'cártel', 'narcotráfico', 'fentanilo', 'crimen organizado',

        # Conflicto/Guerra
        'guerra', 'conflicto', 'protestas', 'manifestaciones', 'disturbios',

        # Tecnología
        'inteligencia artificial', 'ciberseguridad', 'hackeo', 'ciberataque',

        # Ciencia/Salud
        'pandemia', 'vacuna', 'cambio climático', 'crisis climática',

        # Corrupción
        'corrupción', 'escándalo político', 'soborno', 'impunidad'
    ]

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
                        desc = limpiar_texto(art.get('description', ''))
                        categoria = detectar_categoria(titulo, desc)

                        noticias.append({
                            'titulo': limpiar_texto(titulo),
                            'descripcion': desc,
                            'url': art.get('url', ''),
                            'imagen': art.get('urlToImage'),
                            'fuente': f"NewsAPI:{art.get('source', {}).get('name', 'Unknown')}",
                            'fecha': art.get('publishedAt'),
                            'categoria': categoria,
                            'puntaje': calcular_puntaje_viral(titulo, desc),
                            'region': detectar_region(titulo, desc)
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
    topics = ['world', 'nation', 'business', 'technology']

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
                    desc = limpiar_texto(art.get('description', ''))
                    categoria = detectar_categoria(titulo, desc)

                    noticias.append({
                        'titulo': limpiar_texto(titulo),
                        'descripcion': desc,
                        'url': art.get('url', ''),
                        'imagen': art.get('image'),
                        'fuente': f"GNews:{art.get('source', {}).get('name', 'Unknown')}",
                        'fecha': art.get('publishedAt'),
                        'categoria': categoria,
                        'puntaje': calcular_puntaje_viral(titulo, desc),
                        'region': detectar_region(titulo, desc)
                    })
        except Exception as e:
            log(f"Error GNews: {e}", 'error')
            continue

    log(f"GNews: {len(noticias)} noticias", 'info')
    return noticias

def detectar_region(titulo, descripcion):
    """Detecta la región de la noticia para balancear distribución"""
    texto = f"{titulo} {descripcion}".lower()

    # Sudamérica
    sudamerica = ['argentina', 'chile', 'brasil', 'colombia', 'perú', 'peru', 
                  'venezuela', 'ecuador', 'bolivia', 'paraguay', 'uruguay', 
                  'guyana', 'surinam', 'suriname']

    # Norteamérica
    norteamerica = ['mexico', 'méxico', 'estados unidos', 'eeuu', 'usa', 'canada', 'canadá']

    # Centroamérica y Caribe
    centroamerica = ['guatemala', 'el salvador', 'honduras', 'nicaragua', 
                     'costa rica', 'panama', 'panamá', 'cuba', 'república dominicana',
                     'dominicana', 'puerto rico', 'haití', 'haiti', 'jamaica',
                     'trinidad', 'tobago', 'bahamas', 'barbados', 'belice', 'belize']

    for pais in sudamerica:
        if pais in texto:
            return 'sudamerica'

    for pais in norteamerica:
        if pais in texto:
            return 'norteamerica'

    for pais in centroamerica:
        if pais in texto:
            return 'centroamerica'

    return 'desconocida'

def obtener_rss_por_region(region_feeds, max_noticias=15):
    """Obtiene noticias de feeds RSS de una región específica"""
    noticias = []

    for feed_url in region_feeds:
        try:
            r = requests.get(feed_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=8)
            if r.status_code != 200:
                continue

            feed = feedparser.parse(r.content)
            if not feed or not feed.entries:
                continue

            fuente = feed.feed.get('title', 'RSS')[:20]

            for entry in feed.entries[:3]:  # Máximo 3 por feed
                titulo = entry.get('title', '')
                if not titulo:
                    continue

                link = entry.get('link', '')
                if not link:
                    continue

                desc = entry.get('summary', '') or entry.get('description', '')
                desc = re.sub(r'<[^>]+>', '', desc)

                # Buscar imagen
                imagen = None
                if 'media_content' in entry:
                    imagen = entry.media_content[0].get('url')
                elif 'links' in entry:
                    for link_data in entry.links:
                        if link_data.get('type', '').startswith('image/'):
                            imagen = link_data.get('href')
                            break

                categoria = detectar_categoria(titulo, desc)

                noticias.append({
                    'titulo': limpiar_texto(titulo),
                    'descripcion': limpiar_texto(desc),
                    'url': link,
                    'imagen': imagen,
                    'fuente': f"RSS:{fuente}",
                    'fecha': entry.get('published'),
                    'categoria': categoria,
                    'puntaje': calcular_puntaje_viral(titulo, desc),
                    'region': detectar_region(titulo, desc)
                })

                if len(noticias) >= max_noticias:
                    break

        except Exception as e:
            log(f"Error RSS {feed_url[:50]}: {e}", 'error')
            continue

    return noticias

def obtener_rss():
    """Obtiene noticias de feeds RSS con distribución geográfica balanceada"""
    noticias = []

    # 50% Sudamérica
    log("Obteniendo RSS Sudamérica...", 'info')
    noticias_sudamerica = obtener_rss_por_region(FEEDS_SUDAMERICA, max_noticias=25)
    noticias.extend(noticias_sudamerica)
    log(f"RSS Sudamérica: {len(noticias_sudamerica)} noticias", 'info')

    # 30% Norteamérica
    log("Obteniendo RSS Norteamérica...", 'info')
    noticias_norteamerica = obtener_rss_por_region(FEEDS_NORTEAMERICA, max_noticias=15)
    noticias.extend(noticias_norteamerica)
    log(f"RSS Norteamérica: {len(noticias_norteamerica)} noticias", 'info')

    # 20% Centroamérica y Caribe
    log("Obteniendo RSS Centroamérica/Caribe...", 'info')
    noticias_centroamerica = obtener_rss_por_region(FEEDS_CENTROAMERICA_CARIBE, max_noticias=10)
    noticias.extend(noticias_centroamerica)
    log(f"RSS Centroamérica/Caribe: {len(noticias_centroamerica)} noticias", 'info')

    log(f"RSS Total: {len(noticias)} noticias", 'info')
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
    print("BOT NOTICIAS VIRALES LATAM 24/7 - V5.0")
    print("Distribución: 50% Sudamérica | 30% Norteamérica | 20% Centroamérica/Caribe")
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("ERROR: Faltan credenciales Facebook", 'error')
        log("Configura las variables de entorno:", 'error')
        log("  export FB_PAGE_ID='tu_page_id'", 'error')
        log("  export FB_ACCESS_TOKEN='tu_token'", 'error')
        return False

    if not verificar_tiempo():
        return True

    historial = cargar_historial()
    log(f"Historial: {len(historial.get('urls', []))} URLs", 'info')

    # Obtener noticias de todas las fuentes
    noticias = []

    if NEWS_API_KEY:
        noticias.extend(obtener_newsapi())
    if GNEWS_API_KEY:
        noticias.extend(obtener_gnews())

    # Siempre obtener RSS (nuestra principal fuente ahora)
    noticias_rss = obtener_rss()
    noticias.extend(noticias_rss)

    if not noticias:
        log("No se encontraron noticias", 'error')
        return False

    log(f"Total noticias: {len(noticias)}", 'info')

    # Filtrar duplicados
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

    # Balancear por región si es posible
    por_region = {'sudamerica': [], 'norteamerica': [], 'centroamerica': [], 'desconocida': []}
    for n in noticias_unicas:
        region = n.get('region', 'desconocida')
        por_region[region].append(n)

    log(f"Distribución: Sudamérica={len(por_region['sudamerica'])}, "
        f"Norteamérica={len(por_region['norteamerica'])}, "
        f"Centroamérica={len(por_region['centroamerica'])}", 'info')

    # Ordenar por puntaje viral
    noticias_unicas.sort(key=lambda x: x.get('puntaje', 0), reverse=True)

    # Seleccionar mejor noticia
    seleccionada = noticias_unicas[0]
    categoria = seleccionada.get('categoria', 'default')
    region = seleccionada.get('region', 'desconocida')

    log(f"Seleccionada: {seleccionada['titulo'][:60]}...", 'info')
    log(f"Categoría: {categoria} | Región: {region} | Puntaje: {seleccionada.get('puntaje', 0)}", 'info')

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

    # Generar hashtags automáticos
    hashtags = generar_hashtags(seleccionada['titulo'], seleccionada.get('descripcion', ''), categoria)
    log(f"Hashtags: {hashtags}", 'info')

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
        guardar_historial(historial, seleccionada['url'], seleccionada['titulo'],
                         seleccionada.get('descripcion', ''))

        estado = {
            'ultima_publicacion': datetime.now().isoformat(),
            'ultima_noticia': seleccionada['titulo'][:50],
            'ultima_categoria': categoria,
            'ultima_region': region
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
