#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VERDAD HOY — NOTICIAS CHILE 24/7 - V7.0
Foco 100% Chile: noticias nacionales + internacionales relacionadas con Chile
Prioriza noticias con imagen | CTA poderoso | Publica cada 30 minutos
MEJORAS V7.0:
  - Video automático con diseño split + efecto Ken Burns
  - Voz natural edge-tts (4 presentadores rotativos, español latino)
  - CTA temático doble: en el post y en el video (panel rojo de cierre)
  - Horarios pico Chile + límite 6 posts/día
  - Modo FORZAR_PUBLICACION para pruebas desde GitHub Actions
  - NewsData API implementada (estaba declarada pero sin usar)
  - Publicación dual: Facebook video/foto + WordPress (opcional)
  - Queries NewsAPI actualizadas (gobierno Kast 2026)
  - Reintento inteligente en publicación Facebook (3 intentos)
  - API Graph actualizada a v21.0
"""

import requests
import feedparser
import re
import hashlib
import json
import os
import random
import textwrap
import asyncio
import subprocess
import time as time_module
from datetime import datetime, time
from difflib import SequenceMatcher
from urllib.parse import urlparse
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

# ═══════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════

NEWS_API_KEY      = os.getenv('NEWS_API_KEY')
NEWSDATA_API_KEY  = os.getenv('NEWSDATA_API_KEY')
GNEWS_API_KEY     = os.getenv('GNEWS_API_KEY')
FB_PAGE_ID        = os.getenv('FB_PAGE_ID')
FB_ACCESS_TOKEN   = os.getenv('FB_ACCESS_TOKEN')

# WordPress (opcional — si no están configuradas, se omite publicación WP)
WP_URL            = os.getenv('WP_URL', '')          # ej: https://verdadhoy.cl
WP_USER           = os.getenv('WP_USER', '')         # usuario editor WordPress
WP_APP_PASSWORD   = os.getenv('WP_APP_PASSWORD', '') # Application Password de WP

HISTORIAL_PATH = os.getenv('HISTORIAL_PATH', 'data/historial_chile.json')
ESTADO_PATH    = os.getenv('ESTADO_PATH',    'data/estado_bot_chile.json')

FB_API_VERSION = 'v21.0'   # actualizado desde v18.0
FB_MAX_REINTENTOS = 3      # intentos antes de declarar fallo en publicación FB

# ── Horarios pico y límite diario ────────────────────────────
MAX_POSTS_POR_DIA  = 8
FORZAR_PUBLICACION = os.getenv('FORZAR_PUBLICACION', 'false').lower() == 'true'

# Horarios pico en UTC para audiencia hispanohablante (Chile = UTC-3 o UTC-4)
# 10:00-14:00 UTC = 06:00-10:00 Chile (mañana)
# 15:00-19:00 UTC = 11:00-15:00 Chile (mediodía)
# 22:00-02:00 UTC = 18:00-22:00 Chile (noche)
HORARIOS_PICO_UTC = [
    (time(10, 0), time(14, 0)),
    (time(15, 0), time(19, 0)),
    (time(22, 0), time(23, 59)),
    (time(0,  0), time(2,  0)),
]

# ── Voces edge-tts — Chile primero, luego variantes latino ──
VOCES_TTS = [
    'es-CL-CatalinaNeural',  # presentadora chilena nativa ← principal
    'es-CL-LorenzoNeural',   # conductor chileno nativo
    'es-MX-DaliaNeural',     # presentadora mexicana (backup)
    'es-CO-SalomeNeural',    # presentadora colombiana (backup)
]

# Siglas chilenas comunes → pronunciación fonética para TTS
SIGLAS_PRONUNCIACION = {
    'SHOA':    'Shoa',          # Servicio Hidrográfico
    'ONEMI':   'Onemi',
    'SENAPRED':'Senapred',
    'CONAF':   'Conaf',
    'MINSAL':  'Minsal',
    'SEREMI':  'Seremi',
    'PDI':     'Pe De I',
    'SII':     'S I I',
    'AFP':     'A F P',
    'CAE':     'C A E',
    'PAES':    'Paes',
    'SIMCE':   'Simce',
    'ENAP':    'Enap',
    'LATAM':   'Látam',
    'PIB':     'P I B',
    'IPC':     'I P C',
    'TVN':     'T V N',
    'CNN':     'C N N',
    'CHV':     'C H V',
    'CONAF':   'Conaf',
    'FONASA':  'Fonasa',
    'ISAPRE':  'Isapre',
    'ONU':     'O N U',
    'EEUU':    'Estados Unidos',
    'EE.UU.':  'Estados Unidos',
    'VIF':     'V I F',
    'RSH':     'R S H',
}

TIEMPO_ENTRE_PUBLICACIONES = 28          # minutos (un poco menos de 30 para margen)
MAX_TITULOS_HISTORIA       = 500
UMBRAL_SIMILITUD_TITULO    = 0.82
BONUS_IMAGEN               = 30          # puntaje extra por tener imagen
BONUS_CHILE_DIRECTO        = 25          # puntaje extra noticia 100% Chile
BONUS_FUENTE_CL            = 15          # puntaje extra fuente .cl

# ═══════════════════════════════════════════════════════════════
# KEYWORDS CHILE — filtro geográfico
# ═══════════════════════════════════════════════════════════════

# Palabras que identifican una noticia como de Chile o relacionada
KEYWORDS_CHILE_PRIMARIAS = [
    'chile', 'chileno', 'chilena', 'chilenos', 'chilenas',
    'santiago', 'valparaíso', 'concepción', 'antofagasta', 'viña del mar',
    'temuco', 'rancagua', 'iquique', 'arica', 'coquimbo', 'la serena',
    'talca', 'chillán', 'puerto montt', 'osorno', 'copiapó', 'punta arenas',
    'calama', 'tocopilla', 'ovalle', 'quillota', 'san antonio', 'curicó',
    'los ángeles', 'valdivia', 'puerto natales', 'puerto varas',
]

KEYWORDS_CHILE_SECUNDARIAS = [
    'boric', 'gobierno chileno', 'gobierno de chile', 'congreso nacional',
    'carabineros', 'pdi', 'fiscalía', 'minsal', 'seremi', 'municipalidad',
    'peso chileno', 'banco central de chile', 'economía chilena',
    'constitución chilena', 'senado chile', 'diputados chile', 'senadores chilenos',
    'tribunal constitucional', 'corte suprema chile', 'ministerio',
    'atacama', 'araucanía', 'magallanes', 'aysén', 'tarapacá', 'biobío',
    'maule', 'ñuble', "o'higgins", 'los ríos', 'los lagos', 'patagonia chilena',
    'atacameño', 'mapuche', 'rapanui', 'aymara chileno',
    'litio chile', 'cobre chile', 'minería chilena', 'pesca chilena',
    'vino chileno', 'salmón chileno', 'fruta chilena',
    'isapre', 'fonasa', 'afp chilena', 'sii chile', 'serviu',
    'falabella chile', 'cencosud', 'latam airlines', 'codelco', 'enap',
]

# Palabras que indican que una noticia internacional afecta a Chile
KEYWORDS_CHILE_INTERNACIONAL = [
    'chile en', 'chile ante', 'chile y', 'para chile', 'hacia chile',
    'afecta a chile', 'impacto en chile', 'consecuencias en chile',
    'acuerdo con chile', 'tratado con chile', 'relaciones con chile',
    'cancillería', 'embajada de chile', 'embajador chileno',
    'delegación chilena', 'selección chilena', 'la roja',
    'copa chile', 'chileno en el exterior', 'chilenos en',
]

def es_noticia_chile(titulo, descripcion, fuente=''):
    """
    Retorna (True, nivel) si la noticia es de Chile o relacionada.
    nivel: 'directo' = 100% Chile | 'relacionado' = Chile mencionado
    """
    texto = f"{titulo} {descripcion} {fuente}".lower()

    # Nivel 1: Chile mencionado directamente (nombres clave)
    for kw in KEYWORDS_CHILE_PRIMARIAS:
        if kw in texto:
            return True, 'directo'

    # Nivel 2: Instituciones, personajes o términos chilenos
    for kw in KEYWORDS_CHILE_SECUNDARIAS:
        if kw in texto:
            return True, 'directo'

    # Nivel 3: Noticia internacional que afecta/menciona Chile
    for kw in KEYWORDS_CHILE_INTERNACIONAL:
        if kw in texto:
            return True, 'relacionado'

    return False, None


# ═══════════════════════════════════════════════════════════════
# REGIONES Y HASHTAGS CHILE
# ═══════════════════════════════════════════════════════════════

REGIONES_CHILE = {
    'santiago': '#Santiago', 'región metropolitana': '#Santiago', 'rm ': '#Santiago',
    'valparaíso': '#Valparaíso', 'viña del mar': '#Valparaíso', 'quillota': '#Valparaíso',
    'concepción': '#Biobío', 'biobío': '#Biobío', 'biobio': '#Biobío', 'los ángeles': '#Biobío',
    'antofagasta': '#Antofagasta', 'calama': '#Antofagasta', 'tocopilla': '#Antofagasta',
    'iquique': '#Tarapacá', 'alto hospicio': '#Tarapacá',
    'arica': '#AricaParinacota',
    'la serena': '#Coquimbo', 'coquimbo': '#Coquimbo', 'ovalle': '#Coquimbo',
    'copiapó': '#Atacama',
    'rancagua': '#OHiggins',
    'talca': '#Maule', 'curicó': '#Maule',
    'chillán': '#Ñuble',
    'temuco': '#Araucanía', 'araucanía': '#Araucanía',
    'valdivia': '#LosRíos',
    'puerto montt': '#LosLagos', 'osorno': '#LosLagos', 'puerto varas': '#LosLagos',
    'coyhaique': '#Aysén',
    'punta arenas': '#Magallanes', 'puerto natales': '#Magallanes',
}

HASHTAGS_CATEGORIA = {
    'politica':      ['#PolíticaChile', '#GobiernoChile'],
    'economia':      ['#EconomíaChile', '#FinanzasChile'],
    'seguridad':     ['#SeguridadChile', '#DelincuenciaChile'],
    'policial':      ['#PolicialChile', '#CriminalidadChile'],
    'social':        ['#ChileSocial', '#ViviendaChile'],
    'educacion':     ['#EducaciónChile', '#UniversidadesChile'],
    'internacional': ['#ChileEnElMundo', '#Internacional'],
    'tecnologia':    ['#TecnologíaChile', '#InnovaciónChile'],
    'deporte':       ['#DeporteChile', '#FútbolChile'],
    'ciencia':       ['#CienciaChile', '#SaludChile'],
    'medioambiente': ['#MedioambienteChile', '#CambioClimático'],
    'cultura':       ['#CulturaChile', '#EntretenimientoChile'],
    'conflicto':     ['#ConflictoChile', '#ProtestasChile'],
    'corrupcion':    ['#CorrupciónChile', '#TransparenciaChile'],
    'escandalo':     ['#EscándaloChile', '#PolémicaChile'],
    'default':       ['#NoticiasChile', '#Chile'],
}

COLORES_BACKUP = {
    'urgente':       (180, 0,   30),
    'negativa':      (120, 0,   0),
    'positiva':      (0,   100, 60),
    'neutral':       (20,  40,  90),
    'deporte':       (200, 100, 0),
    'politica':      (60,  0,   100),
    'economia':      (0,   80,  40),
    'tecnologia':    (0,   100, 110),
    'policial':      (40,  40,  40),
    'seguridad':     (120, 20,  20),   # rojo oscuro — urgencia ciudadana
    'social':        (0,   80,  120),  # azul — bienestar
    'educacion':     (20,  80,  160),  # azul medio — institucional
    'conflicto':     (150, 20,  20),
    'ciencia':       (40,  100, 160),
    'corrupcion':    (100, 50,  10),
    'medioambiente': (0,   120, 60),
    'cultura':       (100, 0,   80),
}

# ═══════════════════════════════════════════════════════════════
# PALABRAS CLAVE POR CATEGORÍA
# ═══════════════════════════════════════════════════════════════

PALABRAS_CLAVE = {
    # ── Política ─────────────────────────────────────────────
    'politica': [
        # Figuras actuales Chile 2026
        'josé antonio kast', 'kast', 'presidente de chile', 'presidente kast',
        'partido republicano', 'republicanos', 'gobierno de kast',
        'johannes kaiser', 'kaiser',
        'gabriel boric', 'boric', 'expresidente boric',
        'jeannette jara', 'jara',
        'evelyn matthei', 'matthei',
        'vlado mirosevic', 'mirosevic',
        # Instituciones
        'gobierno', 'congreso nacional', 'senado', 'cámara de diputados',
        'diputado', 'diputada', 'senador', 'senadora',
        'ministro', 'ministra', 'ministerio',
        'gabinete', 'moneda', 'la moneda',
        'parlamento', 'constitución', 'plebiscito', 'referéndum',
        'alcalde', 'alcaldesa', 'municipalidad', 'municipio',
        'partido', 'coalición', 'apruebo dignidad', 'chile vamos',
        'oposición', 'oficialismo', 'elecciones municipales',
        'elecciones presidenciales', 'primarias', 'segunda vuelta',
        'servel', 'tribunal constitucional', 'contraloria',
    ],

    # ── Economía ──────────────────────────────────────────────
    'economia': [
        'economía', 'finanzas', 'mercado', 'bolsa', 'inflación', 'ipc',
        'peso chileno', 'dólar', 'tipo de cambio', 'banco central',
        'deuda', 'desempleo', 'cesantía', 'empleo', 'trabajo',
        'pib', 'recesión', 'inversión', 'exportación', 'importación',
        'isapre', 'afp', 'pensión', 'jubilación', 'reforma previsional',
        'codelco', 'litio', 'cobre', 'minería', 'precio del cobre',
        'enap', 'bencina', 'combustible', 'tarifas', 'luz', 'agua',
        'sueldo mínimo', 'salario mínimo', 'reajuste',
        'impuesto', 'tributario', 'sii', 'hacienda',
        'retail', 'falabella', 'cencosud', 'ripley', 'quiebra',
        'startup chilena', 'emprendimiento',
    ],

    # ── Seguridad ciudadana (NUEVA) ────────────────────────────
    'seguridad': [
        'seguridad ciudadana', 'delincuencia', 'inseguridad',
        'portonazo', 'carjacking', 'robo con violencia', 'asalto a mano armada',
        'banda delictual', 'banda criminal', 'crimen organizado',
        'tren de aragua', 'pandilla', 'extorsión', 'cobro de piso',
        'sicariato', 'sicario', 'ajuste de cuentas',
        'zona roja', 'punto de droga', 'narcomenudeo',
        'plan de seguridad', 'estado de excepción',
        'carabineros baleado', 'carabinero muerto', 'carabinero herido',
        'pdi operativo', 'fiscalía investigación', 'detenidos operativo',
        'femicidio', 'violencia intrafamiliar', 'vif',
        'desaparecido', 'desaparecida', 'persona desaparecida',
        'cámara de seguridad', 'imputado formalizado',
    ],

    # ── Policial / Judicial ────────────────────────────────────
    'policial': [
        'detenido', 'detenida', 'arrestado', 'arrestada',
        'carabineros', 'pdi', 'fiscalía', 'fiscal',
        'homicidio', 'asesinato', 'crimen', 'robo',
        'narcotráfico', 'droga', 'cocaína', 'pasta base', 'marihuana',
        'imputado', 'imputada', 'formalizado', 'formalizada',
        'condena', 'sentencia', 'tribunal oral', 'juzgado',
        'prisión preventiva', 'sobreseimiento', 'querella',
        'investigado', 'investigación penal', 'delito',
        'accidente de tránsito', 'accidente fatal',
    ],

    # ── Social / Vivienda (NUEVA) ──────────────────────────────
    'social': [
        'vivienda', 'vivienda social', 'conjunto habitacional',
        'serviu', 'subsidio habitacional', 'lista de espera vivienda',
        'campamento', 'toma de terreno', 'allegados',
        'pobreza', 'vulnerabilidad', 'exclusión social',
        'pensión básica solidaria', 'aporte previsional solidario',
        'registro social de hogares', 'rsh',
        'bono', 'transferencia social', 'ayuda gobierno',
        'adulto mayor', 'tercera edad', 'discapacidad',
        'migrantes', 'inmigración', 'refugiados en chile',
        'pueblos originarios', 'mapuche derechos',
        'desigualdad', 'brecha social', 'movilidad social',
        'fila de atención', 'lista de espera salud',
        'fonasa', 'cesfam', 'consultorio',
    ],

    # ── Educación (NUEVA) ──────────────────────────────────────
    'educacion': [
        'educación', 'colegio', 'escuela', 'liceo',
        'universidad', 'universidades', 'cruch',
        'mineduc', 'ministerio de educación',
        'paes', 'psu', 'prueba de admisión',
        'gratuidad universitaria', 'beca', 'crédito universitario', 'cae',
        'huelga estudiantil', 'toma de colegio', 'paro docente',
        'profesores', 'docentes', 'asistentes de educación',
        'mejoramiento salarial docente',
        'sala cuna', 'jardín infantil', 'junji', 'integra',
        'convivencia escolar', 'bullying', 'acoso escolar',
        'deserción escolar', 'matrícula', 'sostenedor',
        'prueba pisa', 'simce', 'rendimiento académico',
        'educación superior', 'postgrado', 'magíster',
    ],

    # ── Internacional ──────────────────────────────────────────
    'internacional': [
        'onu', 'eeuu', 'argentina', 'perú', 'bolivia', 'brasil',
        'relaciones exteriores', 'embajada', 'canciller', 'acuerdo',
        'tratado', 'cumbre', 'guerra', 'conflicto', 'crisis global',
        'cancillería chilena', 'política exterior', 'diálogo bilateral',
    ],

    # ── Tecnología ────────────────────────────────────────────
    'tecnologia': [
        'tecnología', 'inteligencia artificial', 'ia', 'startup', 'digital',
        'ciberseguridad', 'hackeo', 'internet', 'app', 'innovación',
        'transformación digital', 'fintech', 'e-commerce',
    ],

    # ── Deporte ───────────────────────────────────────────────
    'deporte': [
        'fútbol', 'selección chilena', 'la roja', 'copa', 'mundial', 'gol',
        'partido', 'torneo', 'campeonato', 'tenis', 'atletismo', 'ciclismo',
        'universidad de chile', 'colo colo', 'universidad católica',
        'conmebol', 'clasificatorias', 'eliminatorias',
        'alexis sánchez', 'arturo vidal', 'claudio bravo',
        'ben brereton', 'gary medel',
        'padel', 'basquetbol chile', 'volleyball chile',
    ],

    # ── Ciencia / Salud ───────────────────────────────────────
    'ciencia': [
        'salud', 'hospital', 'medicina', 'vacuna', 'enfermedad', 'minsal',
        'investigación científica', 'descubrimiento', 'científico', 'pandemia',
        'dengue', 'hantavirus', 'influenza', 'virus', 'brote',
        'oncología', 'cáncer', 'trasplante', 'cirugía',
        'lista de espera hospital', 'urgencias', 'cesfam saturado',
    ],

    # ── Medioambiente ─────────────────────────────────────────
    'medioambiente': [
        'medioambiente', 'incendio forestal', 'terremoto', 'tsunami', 'maremoto',
        'sequía', 'contaminación', 'cambio climático', 'glaciar', 'patagonia',
        'lluvia', 'inundación', 'alerta temprana', 'erupción volcánica', 'volcán',
        'ola de calor', 'ola de frío', 'nevazón', 'aluvión',
        'zona de catástrofe', 'alerta roja', 'alerta amarilla',
        'onemi', 'senapred', 'conaf',
    ],

    # ── Cultura / Entretenimiento ─────────────────────────────
    'cultura': [
        'cultura', 'arte', 'música', 'cine', 'teatro', 'festival',
        'patrimonio', 'tradición', 'gastronomía', 'turismo',
        'viña del mar festival', 'festival de viña', 'lollapalooza chile',
        'fiestas patrias', 'dieciocho', '18 de septiembre',
        'libro', 'literatura chilena', 'premio', 'reconocimiento',
        'farandula', 'farándula', 'televisión chilena', 'tvn', 'canal 13',
    ],

    # ── Conflicto social ──────────────────────────────────────
    'conflicto': [
        'protesta', 'manifestación', 'huelga', 'paro', 'disturbio',
        'represión', 'violencia', 'enfrentamiento', 'mapuche', 'araucanía',
        'wallmapu', 'lof', 'weichafe', 'quema de camiones',
        'corte de ruta', 'barricada', 'desmanes',
    ],

    # ── Corrupción ────────────────────────────────────────────
    'corrupcion': [
        'corrupción', 'soborno', 'desfalco', 'fraude', 'lavado de activos',
        'enriquecimiento ilícito', 'licitación irregular', 'caso judicial',
        'peculado', 'malversación', 'colusión', 'caso facturas',
        'audit', 'contraloría investiga', 'funcionario imputado',
    ],

    # ── Escándalo ─────────────────────────────────────────────
    'escandalo': [
        'escándalo', 'polémica', 'controversia', 'denuncia', 'acusación',
        'filtración', 'revelación', 'juicio', 'renuncia exigida',
        'audio filtrado', 'chats filtrados', 'grabación secreta',
        'conflicto de interés', 'nepotismo', 'tráfico de influencias',
    ],
}

# ═══════════════════════════════════════════════════════════════
# CTA — LLAMADAS A LA ACCIÓN PODEROSAS
# ═══════════════════════════════════════════════════════════════

CTAS_POR_CATEGORIA = {
    'politica': [
        "🔴 ¿Estás de acuerdo con esta decisión del gobierno? COMENTA tu opinión 👇",
        "⚡ Esta noticia está dando que hablar. ¿Qué opinas tú? DÉJALO en los comentarios",
        "🗳️ La política chilena no para. ¿Apoya o rechaza esta medida? Cuéntanos 👇",
        "💬 Miles de chilenos debaten esto ahora mismo. ¿Y tú qué piensas? COMENTA",
    ],
    'economia': [
        "💸 ¿Cómo te afecta esto en tu bolsillo? CUÉNTANOS abajo 👇",
        "📊 La economía chilena en movimiento. ¿Sientes el impacto? COMENTA",
        "🚨 Esto afecta a todos los chilenos. COMPARTE para que más personas lo sepan 🔁",
        "💰 ¿Tu familia resiente este cambio económico? Dinos en los comentarios 👇",
    ],
    'seguridad': [
        "🚨 La seguridad de Chile nos preocupa a TODOS. ¿Cuál es tu solución? COMENTA 👇",
        "😤 ¿Cansado/a de la delincuencia en tu barrio? COMENTA y COMPARTE 🔁",
        "🔴 ALERTA CIUDADANA — COMPARTE para que tu comunidad esté informada 🔁",
        "⚠️ ¿Te sientes seguro/a en Chile hoy? SÍ o NO en los comentarios 👇",
        "🛡️ Chile merece vivir sin miedo. ¿Estás de acuerdo? COMENTA y COMPARTE 🔁",
    ],
    'policial': [
        "🚨 URGENTE. COMPARTE para que tu comunidad esté informada 🔁",
        "⚖️ ¿La justicia actuó bien en este caso? COMENTA tu opinión 👇",
        "🔴 Noticia de alto impacto. COMPARTE con tu familia y amigos 🔁",
        "😤 ¿Crees que la pena fue justa? COMENTA abajo 👇",
    ],
    'social': [
        "🏠 El derecho a una vivienda digna es de todos. ¿Estás de acuerdo? COMENTA 👇",
        "💙 ¿Conoces a alguien que necesite este apoyo? COMPARTE para que llegue a más personas 🔁",
        "🇨🇱 Chile merece más igualdad. ¿Qué cambiarías tú? COMENTA 👇",
        "👨‍👩‍👧 ¿Esta política social te parece suficiente? SÍ o NO en los comentarios 👇",
        "📢 Información que muchas familias chilenas necesitan saber. COMPARTE 🔁",
    ],
    'educacion': [
        "📚 La educación de Chile está en juego. ¿Qué opinas? COMENTA 👇",
        "🎓 ¿Crees que la educación chilena va por buen camino? DINOS abajo 👇",
        "✏️ El futuro de Chile está en las aulas. COMPARTE si te importa la educación 🔁",
        "👨‍🏫 ¿Apoyarías esta medida para mejorar la educación? COMENTA 👇",
        "📢 Información clave para estudiantes y apoderados. COMPARTE 🔁",
    ],
    'internacional': [
        "🌎 El mundo habla de Chile. ¿Estás orgulloso/a de ser chileno/a? COMENTA 🇨🇱",
        "🌐 Esto impacta directamente a Chile. COMPARTE para que todos lo sepan 🔁",
        "🗺️ Noticia que cruza fronteras. ¿Cómo crees que afecta a nuestro país? 👇",
    ],
    'deporte': [
        "⚽ ¡CHILE! ¿Crees que podemos lograrlo? COMENTA con tu pronóstico 🇨🇱",
        "🏆 El deporte chileno en acción. ¿Los apoyas? DALE LIKE y COMPARTE 🔁",
        "🔥 ¡La Roja necesita tu apoyo! COMENTA y COMPARTE para alentarlos 💪",
    ],
    'medioambiente': [
        "🌱 Nuestra tierra chilena en peligro. COMPARTE para crear conciencia 🔁",
        "🔥 Emergencia en Chile. COMPARTE para que todos estén informados 🚨",
        "🌊 El medioambiente chileno nos necesita. ¿Qué hacemos? COMENTA 👇",
    ],
    'ciencia': [
        "🧬 La ciencia chilena avanza. COMPARTE esta noticia importante 🔁",
        "💊 Información de salud que todos debemos conocer. COMPARTE 🔁",
        "🏥 Tu salud importa. GUARDA esta publicación y COMPÁRTELA 👇",
    ],
    'cultura': [
        "🎭 Orgullo chileno. ¿Sabías esto de nuestra cultura? COMENTA 🇨🇱",
        "🎵 Chile tiene mucho que mostrar al mundo. COMPARTE si te enorgullece 🔁",
    ],
    'conflicto': [
        "⚡ La situación se tensiona. ¿Cómo lo ves tú? COMENTA abajo 👇",
        "🔴 Esto está pasando en Chile AHORA. COMPARTE para informar 🔁",
        "💬 Tu voz importa. ¿Qué solución propones? COMENTA 👇",
    ],
    'corrupcion': [
        "😡 ¿Indignado/a? COMPARTE para que nadie se olvide de esto 🔁",
        "⚖️ La justicia debe actuar. ¿Estás de acuerdo? COMENTA 👇",
        "🔎 Chile merece transparencia. COMPARTE para exigirla juntos 🔁",
    ],
    'escandalo': [
        "😮 ¿Lo podías creer? COMENTA tu reacción 👇",
        "🔥 La polémica que sacude Chile. ¿Qué opinas? DÉJALO en comentarios",
        "💬 Todo Chile habla de esto. ¿Y tú? COMENTA y COMPARTE 🔁",
    ],
    'default': [
        "📢 Noticia importante para Chile. COMPARTE para que todos la vean 🔁",
        "🇨🇱 Información que todo chileno debe saber. COMPARTE 🔁",
        "💬 ¿Qué opinas de esto? COMENTA abajo y COMPARTE con tu familia 👇",
        "🔔 Mantente informado/a. COMPARTE esta noticia con quienes más quieres 🔁",
    ],
}

def obtener_cta(categoria, titulo=''):
    """Retorna un CTA aleatorio según categoría, con urgencia adicional si aplica"""
    palabras_urgencia = ['urgente', 'alerta', 'emergencia', 'terremoto', 'tsunami',
                         'incendio', 'ataque', 'explosión', 'fallecido', 'muerto']
    titulo_lower = titulo.lower()

    if any(p in titulo_lower for p in palabras_urgencia):
        return "🚨 URGENTE — COMPARTE AHORA para que todos en Chile estén informados 🔁🇨🇱"

    ctas = CTAS_POR_CATEGORIA.get(categoria, CTAS_POR_CATEGORIA['default'])
    return random.choice(ctas)


# ─────────────────────────────────────────────────────────────
# CTA PARA VIDEO (panel rojo de cierre + voz)
# ─────────────────────────────────────────────────────────────

CTAS_VIDEO = {
    'politica':      "¿Estás de acuerdo? SÍ o NO en comentarios 👇",
    'economia':      "¿Sientes esto en tu bolsillo? Comenta 👇",
    'seguridad':     "¿Te sientes seguro/a en Chile hoy? Comenta 👇",
    'policial':      "¿La justicia actuó bien? Opina abajo 👇",
    'social':        "¿Chile merece más igualdad? Comenta 👇",
    'educacion':     "¿Va bien la educación en Chile? Opina 👇",
    'internacional': "¿Cómo afecta esto a Chile? Comenta 👇",
    'tecnologia':    "¿La IA nos ayuda o nos amenaza? Comenta 👇",
    'deporte':       "¿Crees que lo logramos? Comenta 🇨🇱",
    'ciencia':       "¿Sabías esto? Comenta y comparte 👇",
    'medioambiente': "¿Preocupado/a por Chile? Comenta 👇",
    'cultura':       "¿Orgullo chileno? ¡Comenta! 🇨🇱",
    'conflicto':     "¿Cuál es tu solución? Comenta 👇",
    'corrupcion':    "¿Indignado/a? Comenta y comparte 👇",
    'escandalo':     "¿Lo podías creer? Comenta tu reacción 👇",
    'default':       "¿Qué opinas? Comenta abajo 👇",
}

def obtener_cta_video(categoria, titulo=''):
    """CTA corto para el panel rojo del video"""
    palabras_urgencia = ['urgente', 'alerta', 'terremoto', 'tsunami', 'incendio']
    if any(p in titulo.lower() for p in palabras_urgencia):
        return "🚨 URGENTE — Comenta y comparte ahora 🔁"
    return CTAS_VIDEO.get(categoria, CTAS_VIDEO['default'])


# ─────────────────────────────────────────────────────────────
# HORARIOS PICO + LÍMITE DIARIO
# ─────────────────────────────────────────────────────────────

def esta_en_horario_pico():
    """Retorna True si la hora UTC actual está en una ventana pico"""
    if FORZAR_PUBLICACION:
        return True
    ahora = datetime.utcnow().time()
    for inicio, fin in HORARIOS_PICO_UTC:
        if inicio <= fin:
            if inicio <= ahora <= fin:
                return True
        else:  # cruza medianoche
            if ahora >= inicio or ahora <= fin:
                return True
    return False

def limite_diario_alcanzado(historial):
    """Retorna True si ya se publicaron MAX_POSTS_POR_DIA hoy"""
    if FORZAR_PUBLICACION:
        return False
    hoy = datetime.now().strftime('%Y-%m-%d')
    timestamps = historial.get('timestamps', [])
    posts_hoy = sum(1 for ts in timestamps if ts.startswith(hoy))
    log(f"Posts hoy: {posts_hoy}/{MAX_POSTS_POR_DIA}", 'info')
    return posts_hoy >= MAX_POSTS_POR_DIA


# ═══════════════════════════════════════════════════════════════
# FUNCIONES UTILITARIAS
# ═══════════════════════════════════════════════════════════════

def log(mensaje, tipo='info'):
    iconos = {
        'info': '[i]', 'exito': '[OK]', 'error': '[ERR]',
        'advertencia': '[!]', 'imagen': '[IMG]', 'debug': '[D]'
    }
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
        temp = f"{ruta}.tmp"
        with open(temp, 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        os.replace(temp, ruta)
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
        netloc = re.sub(r'^(www\.|m\.|mobile\.|amp\.)', '', parsed.netloc.lower())
        path   = re.sub(r'/index\.(html|php|htm)$', '/', parsed.path.lower())
        path   = re.sub(r'\.html?$', '', path.rstrip('/'))
        return f"{netloc}{path}"
    except:
        return url.lower().strip()

def calcular_similitud(t1, t2):
    if not t1 or not t2:
        return 0.0
    stop = {'el','la','de','y','en','the','of','a','que','con','un','una',
            'para','por','al','del','lo','le','se','es','son','fue','era','será'}
    def norm(t):
        t = re.sub(r'[^\w\s]', '', t.lower().strip())
        return ' '.join(p for p in re.sub(r'\s+', ' ', t).split()
                        if p not in stop and len(p) > 3)
    return SequenceMatcher(None, norm(t1), norm(t2)).ratio()

def es_titulo_generico(titulo):
    if not titulo:
        return True
    palabras = [p for p in re.findall(r'\b\w+\b', titulo.lower()) if len(p) > 4]
    return len(set(palabras)) < 3

def limpiar_texto(texto):
    if not texto:
        return ""
    import html
    t = html.unescape(texto)
    t = re.sub(r'<[^>]+>', ' ', t)
    t = re.sub(r'\s+', ' ', t)
    t = re.sub(r'https?://\S*', '', t)
    return t.strip()

# ═══════════════════════════════════════════════════════════════
# SCRAPING DE ARTÍCULO COMPLETO
# ═══════════════════════════════════════════════════════════════

# Selectores CSS de contenido principal por dominio
SELECTORES_ARTICULO = {
    'emol.com':          ['div.col-xs-12.texto', 'div#cuDetalle', 'section.body-noticia'],
    'latercera.com':     ['div.article-content', 'div.content-text', 'section.article__body'],
    'biobiochile.cl':    ['div.entry-content', 'article.post-content', 'div.article-body'],
    'cooperativa.cl':    ['div.noticia-texto', 'div.story-body', 'article'],
    'cnnchile.com':      ['div.article__body', 'div.content-article', 'section.body'],
    't13.cl':            ['div.article-body', 'div.nota-cuerpo', 'section.content'],
    '24horas.cl':        ['div.article-body', 'div.content-nota', 'article'],
    'meganoticias.cl':   ['div.article-content', 'div.body-nota', 'article'],
    'df.cl':             ['div.article-body', 'div.nota-body', 'section.content'],
    'elmostrador.cl':    ['div.entry-content', 'article.post', 'div.content'],
    'eldinamo.cl':       ['div.entry-content', 'article', 'div.post-content'],
    'eldesconcierto.cl': ['div.entry-content', 'div.article-body', 'article'],
    'publimetro.cl':     ['div.article__body', 'div.content-body', 'article'],
    'lacuarta.com':      ['div.entry-content', 'div.article-body', 'article'],
    'lun.com':           ['div.article-body', 'div.nota-texto', 'article'],
    'soychile.cl':       ['div.article-body', 'div.content', 'article'],
    'adnradio.cl':       ['div.article-content', 'div.entry-content', 'article'],
}

# Selectores genéricos (fallback para medios no mapeados)
SELECTORES_GENERICOS = [
    'article',
    'div[class*="article-body"]',
    'div[class*="article-content"]',
    'div[class*="entry-content"]',
    'div[class*="nota-cuerpo"]',
    'div[class*="story-body"]',
    'div[class*="post-content"]',
    'div[class*="content-text"]',
    'div[class*="body-nota"]',
    'main',
]

# Elementos a eliminar del DOM antes de extraer texto
TAGS_BASURA = [
    'script', 'style', 'nav', 'header', 'footer', 'aside',
    'figure', 'figcaption', 'iframe', 'form', 'button',
    'noscript', 'advertisement', 'div[class*="publicidad"]',
    'div[class*="ads"]', 'div[class*="related"]',
    'div[class*="recomendado"]', 'div[class*="social"]',
    'div[class*="comentario"]', 'div[class*="tag"]',
]

def extraer_texto_articulo(url, desc_fallback='', timeout=8):
    """
    Intenta extraer el texto completo del artículo desde la URL.
    Retorna el texto limpio o desc_fallback si falla.
    Estrategia: BeautifulSoup con selectores específicos por medio,
    luego selectores genéricos, luego heurística de densidad de texto.
    """
    if not url:
        return desc_fallback

    try:
        from urllib.parse import urlparse as _up
        dominio = _up(url).netloc.lower()
        dominio = re.sub(r'^(www\.|m\.)', '', dominio)

        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ),
            'Accept-Language': 'es-CL,es;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }

        r = requests.get(url, headers=headers, timeout=timeout)
        if r.status_code != 200:
            log(f"Scraping HTTP {r.status_code}: {url[:60]}", 'advertencia')
            return desc_fallback

        # Necesitamos BeautifulSoup
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            log("BeautifulSoup no disponible — usando fallback", 'advertencia')
            return desc_fallback

        soup = BeautifulSoup(r.content, 'html.parser')

        # Eliminar basura
        for tag in soup(['script', 'style', 'nav', 'header', 'footer',
                         'aside', 'figure', 'figcaption', 'iframe',
                         'form', 'button', 'noscript']):
            tag.decompose()
        for clase in ['publicidad', 'ads', 'related', 'recomendado',
                      'social-share', 'comentario', 'tags', 'newsletter']:
            for el in soup.find_all(class_=re.compile(clase, re.I)):
                el.decompose()

        # ── Intentar selectores específicos del medio ─────────
        texto = ''
        selectores = SELECTORES_ARTICULO.get(dominio, []) + SELECTORES_GENERICOS

        for selector in selectores:
            try:
                el = soup.select_one(selector)
                if el:
                    # Extraer párrafos del elemento encontrado
                    parrafos_el = el.find_all('p')
                    if parrafos_el:
                        bloques = [p.get_text(strip=True) for p in parrafos_el
                                   if len(p.get_text(strip=True)) > 40]
                        if bloques:
                            candidato = '\n\n'.join(bloques)
                            if len(candidato) > len(texto) and len(candidato) > 200:
                                texto = candidato
                                break
                    # Si no tiene párrafos internos, texto plano
                    candidato = el.get_text(separator=' ', strip=True)
                    candidato = re.sub(r'\s+', ' ', candidato).strip()
                    if len(candidato) > len(texto) and len(candidato) > 200:
                        texto = candidato
                        break
            except Exception:
                continue

        # ── Heurística de densidad si ningún selector funcionó ─
        if len(texto) < 200:
            parrafos = soup.find_all('p')
            bloques = []
            for p in parrafos:
                t = p.get_text(strip=True)
                if len(t) > 60:
                    bloques.append(t)
            if bloques:
                texto = '\n\n'.join(bloques)   # ← párrafos separados, no espacio

        # Limpiar espacios extra pero preservar saltos de párrafo
        texto = re.sub(r'[ \t]+', ' ', texto)          # espacios múltiples → uno
        texto = re.sub(r'\n{3,}', '\n\n', texto)       # más de 2 saltos → 2
        texto = texto.strip()

        if len(texto) > 300:
            log(f"Scraping OK: {len(texto)} chars desde {dominio}", 'exito')
            return texto
        else:
            log(f"Scraping insuficiente ({len(texto)} chars), usando fallback", 'advertencia')
            return desc_fallback if desc_fallback else texto

    except Exception as e:
        log(f"Error scraping {url[:60]}: {e}", 'error')
        return desc_fallback


def formatear_parrafos(texto, max_chars=1400):
    """
    Formatea el texto para Facebook:
    - Separa oraciones largas en párrafos visuales
    - Preserva saltos de línea existentes
    - Trunca respetando el final de una oración completa
    """
    if not texto:
        return ''

    # Si ya tiene párrafos (del scraping), limpiar y respetar
    if '\n\n' in texto:
        parrafos = [p.strip() for p in texto.split('\n\n') if p.strip()][:40]
    else:
        # Texto plano: dividir en oraciones y agrupar de 2 en 2
        oraciones = re.split(r'(?<=[.!?])\s+', texto.strip())
        oraciones = [o.strip() for o in oraciones if len(o.strip()) > 20]
        # Agrupar de 2 oraciones por párrafo
        parrafos = []
        for i in range(0, len(oraciones), 2):
            bloque = ' '.join(oraciones[i:i+2])
            if bloque:
                parrafos.append(bloque)

    # Unir con doble salto de línea
    resultado = '\n\n'.join(parrafos)

    # Truncar respetando párrafos completos
    if len(resultado) <= max_chars:
        return resultado

    # Cortar en el último \n\n antes del límite
    truncado = resultado[:max_chars]
    ultimo_parrafo = truncado.rfind('\n\n')
    ultimo_punto   = max(truncado.rfind('. '), truncado.rfind('.\n'))

    if ultimo_parrafo > max_chars * 0.5:
        return truncado[:ultimo_parrafo].rstrip()
    elif ultimo_punto > max_chars * 0.5:
        return truncado[:ultimo_punto + 1].rstrip()
    return truncado.rstrip() + '…'


def obtener_descripcion_completa(noticia, max_chars=1400):
    """
    Orquesta la obtención del texto completo:
    1. Intenta scraping del artículo original
    2. Si falla o es muy corto, usa la descripción del RSS
    3. Formatea en párrafos visuales para Facebook
    """
    url  = noticia.get('url', '')
    desc = noticia.get('descripcion', '')

    if len(desc) > 600:
        texto = desc
        log(f"Descripción RSS suficiente: {len(desc)} chars", 'info')
    else:
        log(f"Intentando scraping completo de: {url[:70]}", 'info')
        texto = extraer_texto_articulo(url, desc_fallback=desc)

    return formatear_parrafos(texto, max_chars=max_chars)


def detectar_categoria(titulo, descripcion):
    texto = f"{titulo} {descripcion}".lower()
    puntajes = {cat: sum(1 for kw in kws if kw in texto)
                for cat, kws in PALABRAS_CLAVE.items()}
    max_cat = max(puntajes, key=puntajes.get)
    return max_cat if puntajes[max_cat] > 0 else 'default'

def detectar_region_chile(titulo, descripcion):
    texto = f"{titulo} {descripcion}".lower()
    for lugar, hashtag in REGIONES_CHILE.items():
        if lugar in texto:
            return hashtag
    return None

def generar_hashtags(titulo, descripcion, categoria):
    hashtags = ['#Chile', '#ChileNoticias']

    region = detectar_region_chile(titulo, descripcion)
    if region and region not in hashtags:
        hashtags.append(region)

    cat_tags = HASHTAGS_CATEGORIA.get(categoria, HASHTAGS_CATEGORIA['default'])
    for tag in cat_tags[:2]:
        if tag not in hashtags:
            hashtags.append(tag)

    # Tag de urgencia si aplica
    texto = f"{titulo} {descripcion}".lower()
    if any(p in texto for p in ['urgente', 'última hora', 'alerta', 'terremoto', 'tsunami']):
        if '#Urgente' not in hashtags:
            hashtags.append('#Urgente')

    # Deduplicar
    vistos = []
    for h in hashtags:
        if h not in vistos:
            vistos.append(h)

    return ' '.join(vistos[:7])


# ═══════════════════════════════════════════════════════════════
# PUNTAJE VIRAL — PRIORIZA CHILE + IMAGEN
# ═══════════════════════════════════════════════════════════════

def calcular_puntaje_viral(titulo, desc, tiene_imagen=False, fuente='', nivel_chile=''):
    txt = f"{titulo} {desc}".lower()
    puntaje = 0

    # ── Bonus imagen (máxima prioridad) ──────────────────────
    if tiene_imagen:
        puntaje += BONUS_IMAGEN

    # ── Bonus Chile ──────────────────────────────────────────
    if nivel_chile == 'directo':
        puntaje += BONUS_CHILE_DIRECTO
    elif nivel_chile == 'relacionado':
        puntaje += 10

    # Fuente chilena (.cl)
    if '.cl' in fuente.lower() or 'chile' in fuente.lower():
        puntaje += BONUS_FUENTE_CL

    # ── Impacto del contenido ────────────────────────────────
    palabras_impacto = [
        'urgente', 'alerta', 'terremoto', 'tsunami', 'incendio', 'emergencia',
        'fallecido', 'muerto', 'herido', 'desaparecido', 'rescate',
        'escándalo', 'denuncia', 'corrupción', 'detenido', 'crimen',
        'protesta', 'huelga', 'paro nacional', 'conflicto',
        'récord', 'histórico', 'primera vez', 'inédito',
        'boric', 'gobierno', 'congreso', 'senado',
        'economía', 'inflación', 'dólar', 'pensiones',
    ]
    for p in palabras_impacto:
        if p in txt:
            puntaje += 8
            if p in titulo.lower():
                puntaje += 4

    # Longitud óptima de título
    if 40 <= len(titulo) <= 100:
        puntaje += 5

    # Números en el título (datos concretos)
    if re.search(r'\d+', titulo):
        puntaje += 3

    return puntaje


# ═══════════════════════════════════════════════════════════════
# AUDIO — edge-tts con fallback a espeak
# ═══════════════════════════════════════════════════════════════

def _limpiar_para_voz(texto):
    """
    Prepara el texto para TTS:
    - Reemplaza siglas chilenas por su pronunciación fonética
    - Elimina emojis, hashtags y caracteres no pronunciables
    """
    if not texto:
        return ''
    # Reemplazar siglas por pronunciación (word boundary para no tocar palabras dentro)
    for sigla, fonetica in SIGLAS_PRONUNCIACION.items():
        texto = re.sub(rf'\b{re.escape(sigla)}\b', fonetica, texto)
    # Limpiar emojis y símbolos
    texto = re.sub(r'[\U00010000-\U0010ffff]', '', texto)
    texto = re.sub(r'[🇦-🇿]{2}', '', texto)
    texto = re.sub(r'[#@]', '', texto)
    texto = re.sub(r'[─═]', '', texto)           # separadores
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto

def crear_audio_noticia(titulo, descripcion, cta_video, max_desc_chars=300):
    """
    Genera audio MP3 con la voz leyendo:
    'Última hora. [TÍTULO]. [RESUMEN]. [CTA]. Comenta, reacciona y comparte.
    Más detalles en la descripción de esta publicación.'
    Retorna ruta del MP3 o None si falla.
    """
    titulo_voz = _limpiar_para_voz(titulo)
    desc_corta = _limpiar_para_voz(descripcion[:max_desc_chars])
    if desc_corta and not desc_corta.endswith('.'):
        desc_corta = desc_corta.rstrip('…').strip() + '.'
    cta_voz = _limpiar_para_voz(cta_video.split('👇')[0].strip())

    guion = (
        f"Última hora. {titulo_voz}. "
        f"{desc_corta} "
        f"{cta_voz}. "
        "Comenta, reacciona y comparte. "
        "Más detalles en la descripción de esta publicación."
    )

    voz    = random.choice(VOCES_TTS)
    out_mp3 = f'/tmp/audio_{hashlib.md5(titulo.encode()).hexdigest()[:8]}.mp3'

    # ── Intentar edge-tts ────────────────────────────────────
    try:
        import edge_tts
        async def _generar():
            comm = edge_tts.Communicate(guion, voz, rate='+8%')
            await comm.save(out_mp3)
        asyncio.run(_generar())
        if os.path.exists(out_mp3) and os.path.getsize(out_mp3) > 5000:
            log(f"🔊 Audio TTS generado con {voz} ({os.path.getsize(out_mp3)//1024} KB)", 'exito')
            return out_mp3
    except Exception as e:
        log(f"edge-tts falló ({e}), intentando espeak...", 'advertencia')

    # ── Fallback: espeak ─────────────────────────────────────
    try:
        wav_path = out_mp3.replace('.mp3', '.wav')
        subprocess.run(
            ['espeak', '-v', 'es-la', '-s', '145', '-w', wav_path, guion],
            check=True, capture_output=True, timeout=30
        )
        # convertir WAV → MP3 con ffmpeg
        subprocess.run(
            ['ffmpeg', '-y', '-i', wav_path, '-codec:a', 'libmp3lame', '-q:a', '4', out_mp3],
            check=True, capture_output=True, timeout=30
        )
        try:
            os.remove(wav_path)
        except:
            pass
        if os.path.exists(out_mp3) and os.path.getsize(out_mp3) > 1000:
            log(f"🔊 Audio espeak generado ({os.path.getsize(out_mp3)//1024} KB)", 'info')
            return out_mp3
    except Exception as e:
        log(f"espeak también falló: {e}", 'error')

    return None


# ═══════════════════════════════════════════════════════════════
# VIDEO — Generación con Ken Burns + diseño split
# ═══════════════════════════════════════════════════════════════

def _cargar_fuente_video(bold=True, size=36):
    rutas = [
        f'/usr/share/fonts/truetype/dejavu/DejaVuSans-{"Bold" if bold else ""}.ttf',
        f'/usr/share/fonts/truetype/liberation/LiberationSans-{"Bold" if bold else "Regular"}.ttf',
    ]
    for r in rutas:
        try:
            return ImageFont.truetype(r, size)
        except:
            pass
    return ImageFont.load_default()

def crear_frame_video(imagen_noticia, titulo, resumen, categoria,
                      progreso=0.0, mostrar_cta=False, cta_texto=''):
    """
    Genera un frame PIL 720×1280 (9:16 vertical — optimizado para Reels).
    Layout:
    - Superior: imagen nítida con efecto Ken Burns (~55% del alto)
    - Inferior: panel oscuro con marca + título + resumen
    - Últimos frames: panel rojo de cierre con CTA
    """
    W, H = 720, 1280
    frame = Image.new('RGB', (W, H), (10, 10, 20))

    # ── Zona imagen superior (55% del alto) ─────────────────
    IMG_H = int(H * 0.55)   # ~704px
    if imagen_noticia:
        try:
            # Ken Burns: zoom 130% → 100%
            escala = 1.30 - (0.30 * progreso)
            img    = imagen_noticia.copy()
            iw, ih = img.size
            # escalar para cubrir el área superior completa
            ratio  = max(W / iw, IMG_H / ih) * escala
            nw, nh = int(iw * ratio), int(ih * ratio)
            img    = img.resize((nw, nh), Image.Resampling.LANCZOS)
            # centrar
            x = max(0, (nw - W) // 2)
            y = max(0, (nh - IMG_H) // 2)
            img = img.crop((x, y, x + W, y + IMG_H))
            # nitidez
            img = ImageEnhance.Sharpness(img).enhance(1.4)
            img = ImageEnhance.Contrast(img).enhance(1.1)
            # gradiente suave en el borde inferior (fusión con panel)
            grad_h = 120
            grad   = Image.new('L', (W, IMG_H), 255)
            for gy in range(grad_h):
                alpha = int(255 * (1 - gy / grad_h))
                for gx in range(W):
                    grad.putpixel((gx, IMG_H - grad_h + gy), alpha)
            frame.paste(img, (0, 0), grad)
        except Exception as e:
            log(f"Error frame imagen: {e}", 'advertencia')

    draw = ImageDraw.Draw(frame)

    # ── Barra de marca superior (sobre la imagen) ────────────
    color_cat = COLORES_BACKUP.get(categoria, COLORES_BACKUP['neutral'])
    draw.rectangle([(0, 0), (W, 56)], fill=color_cat)
    # acento rojo lateral
    draw.rectangle([(0, 0), (6, 56)], fill=(210, 16, 52))
    font_marca = _cargar_fuente_video(True, 20)
    draw.text((14, 16), 'VERDAD HOY — NOTICIAS CHILE', font=font_marca, fill=(255, 255, 255))

    # ── ÚLTIMA HORA badge (sobre imagen) ────────────────────
    if progreso > 0.05:
        draw.rectangle([(14, 66), (190, 92)], fill=(210, 16, 52))
        font_badge = _cargar_fuente_video(True, 17)
        draw.text((20, 70), 'ÚLTIMA HORA', font=font_badge, fill=(255, 255, 255))

    # ── Panel texto inferior ─────────────────────────────────
    PANEL_Y = IMG_H
    draw.rectangle([(0, PANEL_Y), (W, H)], fill=(12, 12, 25))
    # acento rojo superior del panel
    draw.rectangle([(0, PANEL_Y), (W, PANEL_Y + 4)], fill=(210, 16, 52))

    # ── Título ───────────────────────────────────────────────
    font_tit   = _cargar_fuente_video(True, 34)
    lineas_tit = textwrap.wrap(titulo[:130], width=20)[:4]
    y = PANEL_Y + 20
    for linea in lineas_tit:
        draw.text((18, y + 2), linea, font=font_tit, fill=(0, 0, 0))   # sombra
        draw.text((16, y),     linea, font=font_tit, fill=(255, 255, 255))
        y += 46

    # Separador
    draw.rectangle([(16, y + 6), (260, y + 8)], fill=(210, 16, 52))
    y += 20

    # ── Resumen ──────────────────────────────────────────────
    if progreso > 0.12:
        font_res   = _cargar_fuente_video(False, 22)
        lineas_res = textwrap.wrap(resumen[:300], width=28)[:5]
        for linea in lineas_res:
            if y + 30 > H - 60:
                break
            draw.text((16, y), linea, font=font_res, fill=(190, 190, 205))
            y += 30

    # ── Footer ───────────────────────────────────────────────
    font_foot = _cargar_fuente_video(False, 17)
    fecha_str = datetime.now().strftime('%d/%m/%Y %H:%M')
    draw.text((16, H - 34), f'verdadhoy.cl  |  {fecha_str}', font=font_foot, fill=(110, 110, 130))

    # ── Panel rojo de cierre (últimos frames) ────────────────
    if mostrar_cta and cta_texto:
        draw.rectangle([(0, H - 160), (W, H)], fill=(180, 10, 30))
        draw.rectangle([(0, H - 164), (W, H - 160)], fill=(255, 255, 255))
        font_cta1 = _cargar_fuente_video(True, 27)
        font_cta2 = _cargar_fuente_video(False, 18)
        cta_limpio = re.sub(r'[🇦-🇿𐀀-􏿿]', '', cta_texto).strip()
        # centrar el CTA
        lineas_cta = textwrap.wrap(cta_limpio, width=28)[:2]
        cy = H - 148
        for lc in lineas_cta:
            draw.text((18, cy), lc, font=font_cta1, fill=(255, 255, 255))
            cy += 36
        draw.text((18, H - 42),
                  'Comenta · Reacciona · Comparte · Ver descripcion',
                  font=font_cta2, fill=(255, 200, 200))

    return frame


def crear_video_noticia(imagen_path, titulo, descripcion, categoria, cta_video):
    """
    Genera un video MP4 de ~28 segundos con:
    - Ken Burns sobre la imagen + panel informativo animado
    - Audio de voz (edge-tts / espeak)
    - Panel rojo de cierre con CTA
    Retorna ruta del MP4 o None si falla.
    """
    try:
        from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
    except ImportError:
        log("moviepy no disponible — usando imagen", 'advertencia')
        return None

    try:
        FPS        = 24
        DURACION   = 28       # segundos totales
        CTA_DESDE  = 23       # segundo en que aparece panel rojo
        total_frames = FPS * DURACION

        # Cargar y preparar imagen base
        img_base = None
        if imagen_path and os.path.exists(imagen_path):
            try:
                img_raw  = Image.open(imagen_path).convert('RGB')
                # escalar a mínimo 1280px de ancho manteniendo ratio
                w, h = img_raw.size
                if w < 1280:
                    img_raw = img_raw.resize((1280, int(h * 1280 / w)), Image.Resampling.LANCZOS)
                img_base = img_raw
            except Exception as e:
                log(f"Error cargando imagen para video: {e}", 'advertencia')

        resumen_corto = descripcion[:280] if descripcion else ''

        # Generar frames
        log("🎬 Generando frames del video...", 'info')
        frames_paths = []
        for i in range(total_frames):
            progreso   = i / total_frames
            mostrar_cta = i >= (CTA_DESDE * FPS)
            frame = crear_frame_video(
                img_base, titulo, resumen_corto, categoria,
                progreso=progreso,
                mostrar_cta=mostrar_cta,
                cta_texto=re.sub(r'[🇦-🇿\U00010000-\U0010ffff👇👍🔁💬]', '', cta_video)
            )
            fpath = f'/tmp/frame_{i:05d}.png'
            frame.save(fpath)
            frames_paths.append(fpath)

        # Ensamblar con ffmpeg (más estable que moviepy para frames)
        video_sin_audio = f'/tmp/video_sa_{hashlib.md5(titulo.encode()).hexdigest()[:8]}.mp4'
        subprocess.run([
            'ffmpeg', '-y',
            '-framerate', str(FPS),
            '-i', '/tmp/frame_%05d.png',
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
            '-preset', 'fast', '-crf', '23',
            '-vf', 'scale=720:1280',          # forzar 9:16 vertical
            '-metadata:s:v', 'rotate=0',       # sin rotación (ya es vertical)
            video_sin_audio
        ], check=True, capture_output=True, timeout=120)

        # Limpiar frames
        for fp in frames_paths:
            try:
                os.remove(fp)
            except:
                pass

        # Generar audio
        audio_path = crear_audio_noticia(titulo, resumen_corto,
                                          re.sub(r'[🇦-🇿\U00010000-\U0010ffff👇]', '', cta_video))

        video_final = f'/tmp/verdadhoy_video_{hashlib.md5(titulo.encode()).hexdigest()[:8]}.mp4'

        if audio_path and os.path.exists(audio_path):
            # Mezclar audio + video
            subprocess.run([
                'ffmpeg', '-y',
                '-i', video_sin_audio,
                '-i', audio_path,
                '-c:v', 'copy',
                '-c:a', 'aac', '-b:a', '128k',
                '-shortest',
                video_final
            ], check=True, capture_output=True, timeout=60)
            try:
                os.remove(audio_path)
            except:
                pass
            log("🔊 Audio mezclado correctamente en el video", 'exito')
        else:
            # Sin audio: solo video
            import shutil
            shutil.copy(video_sin_audio, video_final)
            log("⚠️ Video sin audio (TTS falló)", 'advertencia')

        try:
            os.remove(video_sin_audio)
        except:
            pass

        if os.path.exists(video_final) and os.path.getsize(video_final) > 50_000:
            log(f"🎬 Video listo: {os.path.getsize(video_final)//1024} KB", 'exito')
            return video_final

    except Exception as e:
        log(f"Error generando video: {e}", 'error')
        import traceback
        traceback.print_exc()

    return None


# ═══════════════════════════════════════════════════════════════
# IMAGEN — Descargar, overlay, backup
# ═══════════════════════════════════════════════════════════════

def descargar_imagen(url_imagen, titulo):
    if not url_imagen:
        return None
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        r = requests.get(url_imagen, headers=headers, timeout=15)
        if r.status_code != 200:
            return None
        if 'image' not in r.headers.get('content-type', ''):
            return None
        path = f'/tmp/orig_{generar_hash(titulo)}.jpg'
        with open(path, 'wb') as f:
            f.write(r.content)
        if os.path.getsize(path) > 10_000:
            log(f"Imagen descargada OK ({os.path.getsize(path)} bytes)", 'imagen')
            return path
        os.remove(path)
        return None
    except Exception as e:
        log(f"Error descargando imagen: {e}", 'error')
        return None

def crear_imagen_con_overlay(imagen_original_path, titulo, categoria='noticia'):
    try:
        img = Image.open(imagen_original_path).convert('RGB')
        img = img.resize((1200, 630), Image.Resampling.LANCZOS)
        draw = ImageDraw.Draw(img)

        # Fuentes
        def cargar_fuente(bold=True, size=42):
            rutas_bold = [
                '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
                '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
            ]
            rutas_regular = [
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            ]
            rutas = rutas_bold if bold else rutas_regular
            for r in rutas:
                try:
                    return ImageFont.truetype(r, size)
                except:
                    pass
            return ImageFont.load_default()

        font_titulo    = cargar_fuente(True,  40)
        font_cat       = cargar_fuente(True,  24)
        font_cta_small = cargar_fuente(False, 18)
        font_footer    = cargar_fuente(False, 18)

        color_barra = COLORES_BACKUP.get(categoria, COLORES_BACKUP['neutral'])

        # Barra superior con logo
        draw.rectangle([(0, 0), (1200, 58)], fill=color_barra)
        draw.text((16, 14), '🇨🇱 VERDAD HOY — NOTICIAS CHILE', font=font_cat, fill=(255, 255, 255))

        # Franja roja lateral izquierda (acento patrio)
        draw.rectangle([(0, 58), (8, 630)], fill=(210, 16, 52))

        # Banda inferior semitransparente (oscura con gradiente)
        altura_banda = 220
        for i in range(altura_banda):
            alpha = int(200 * (i / altura_banda))
            draw.rectangle([(0, 630 - altura_banda + i), (1200, 631 - altura_banda + i)],
                           fill=(0, 0, 0))

        # Título
        titulo_limpio = titulo[:140]
        lineas = textwrap.wrap(titulo_limpio, width=34)[:3]
        if len(lineas) == 3 and len(lineas[-1]) > 30:
            lineas[-1] = lineas[-1][:28] + '…'

        y = 630 - altura_banda + 18
        for linea in lineas:
            draw.text((22, y + 2), linea, font=font_titulo, fill=(0, 0, 0))
            draw.text((20, y),     linea, font=font_titulo, fill=(255, 255, 255))
            y += 50

        # Separador
        draw.rectangle([(20, y + 4), (400, y + 6)], fill=(210, 16, 52))

        # Footer
        fecha_str = datetime.now().strftime('%d/%m/%Y %H:%M')
        draw.text((20, 605), f'verdadhoy.cl  |  {fecha_str}', font=font_footer, fill=(180, 180, 180))

        path = f'/tmp/verdadhoy_{generar_hash(titulo[:50])}.jpg'
        img.save(path, 'JPEG', quality=95)
        log(f"Imagen overlay lista: {path}", 'exito')
        return path
    except Exception as e:
        log(f"Error overlay: {e}", 'error')
        return None

def crear_imagen_backup(titulo, categoria='noticia'):
    try:
        w, h = 1200, 630
        color_fondo = COLORES_BACKUP.get(categoria, COLORES_BACKUP['neutral'])
        img = Image.new('RGB', (w, h), color_fondo)
        draw = ImageDraw.Draw(img)

        def cargar_fuente(bold=True, size=48):
            rutas = [
                f'/usr/share/fonts/truetype/dejavu/DejaVuSans-{"Bold" if bold else ""}.ttf',
                f'/usr/share/fonts/truetype/liberation/LiberationSans-{"Bold" if bold else "Regular"}.ttf',
            ]
            for r in rutas:
                try:
                    return ImageFont.truetype(r, size)
                except:
                    pass
            return ImageFont.load_default()

        font_titulo  = cargar_fuente(True,  46)
        font_sub     = cargar_fuente(False, 22)
        font_cat     = cargar_fuente(False, 20)

        # Franja roja superior
        draw.rectangle([(0, 0), (w, 12)], fill=(210, 16, 52))
        # Franja blanca
        draw.rectangle([(0, 12), (w, 22)], fill=(255, 255, 255))
        # Logo texto
        draw.text((30, 30), '🇨🇱 VERDAD HOY — NOTICIAS CHILE', font=font_cat, fill=(220, 220, 220))
        draw.text((30, 54), categoria.upper(), font=font_cat, fill=(255, 200, 50))

        # Título centrado
        lineas = textwrap.wrap(titulo[:140], width=26)[:4]
        if len(lineas) == 4 and len(lineas[-1]) > 24:
            lineas[-1] = lineas[-1][:22] + '…'

        altura_bloque = len(lineas) * 58
        y = ((h - altura_bloque) // 2) - 10

        for linea in lineas:
            for off in [(3, 3), (2, 2), (1, 1)]:
                draw.text((60 + off[0], y + off[1]), linea, font=font_titulo, fill=(0, 0, 0))
            draw.text((60, y), linea, font=font_titulo, fill=(255, 255, 255))
            y += 58

        # Footer
        draw.rectangle([(0, h - 60), (w, h - 58)], fill=(210, 16, 52))
        fecha = datetime.now().strftime('%d/%m/%Y %H:%M')
        draw.text((30, h - 48), f'verdadhoy.cl  |  {fecha}', font=font_sub, fill=(200, 200, 200))

        path = f'/tmp/verdadhoy_backup_{generar_hash(titulo[:50])}.jpg'
        img.save(path, 'JPEG', quality=95)
        log(f"Imagen backup lista: {path}", 'exito')
        return path
    except Exception as e:
        log(f"Error backup: {e}", 'error')
        return None

def procesar_imagen(noticia):
    titulo    = noticia.get('titulo', '')
    url_img   = noticia.get('imagen')
    categoria = noticia.get('categoria', 'noticia')

    if url_img:
        orig = descargar_imagen(url_img, titulo)
        if orig:
            resultado = crear_imagen_con_overlay(orig, titulo, categoria)
            try:
                os.remove(orig)
            except:
                pass
            if resultado:
                return resultado, 'original+overlay'

    log("Sin imagen original, creando backup...", 'imagen')
    return crear_imagen_backup(titulo, categoria), 'backup'


# ═══════════════════════════════════════════════════════════════
# HISTORIAL
# ═══════════════════════════════════════════════════════════════

def cargar_historial():
    default = {
        'urls': [], 'urls_normalizadas': [], 'hashes': [], 'timestamps': [],
        'titulos': [], 'estadisticas': {'total_publicadas': 0}
    }
    h = cargar_json(HISTORIAL_PATH, default)
    for k in default:
        if k not in h:
            h[k] = default[k]
    return h

def noticia_ya_publicada(historial, url, titulo):
    if not historial:
        return False, 'sin_historial'
    if es_titulo_generico(titulo):
        return True, 'titulo_generico'
    if normalizar_url(url) in historial.get('urls_normalizadas', []):
        return True, 'url_duplicada'
    if generar_hash(titulo) in historial.get('hashes', []):
        return True, 'hash_duplicado'
    for t_hist in historial.get('titulos', []):
        if calcular_similitud(titulo, t_hist) >= UMBRAL_SIMILITUD_TITULO:
            return True, 'similar'
    return False, 'nuevo'

def guardar_historial(historial, url, titulo):
    historial['urls'].append(url)
    historial['urls_normalizadas'].append(normalizar_url(url))
    historial['hashes'].append(generar_hash(titulo))
    historial['timestamps'].append(datetime.now().isoformat())
    historial['titulos'].append(titulo)
    stats = historial.get('estadisticas', {'total_publicadas': 0})
    stats['total_publicadas'] = stats.get('total_publicadas', 0) + 1
    historial['estadisticas'] = stats
    for key in ['urls', 'urls_normalizadas', 'hashes', 'timestamps', 'titulos']:
        if len(historial[key]) > MAX_TITULOS_HISTORIA:
            historial[key] = historial[key][-MAX_TITULOS_HISTORIA:]
    guardar_json(HISTORIAL_PATH, historial)
    return historial


# ═══════════════════════════════════════════════════════════════
# FUENTES RSS — CHILE PRIMERO
# ═══════════════════════════════════════════════════════════════

# ── PRIORIDAD 1: Medios nacionales chilenos ──────────────────
FEEDS_CHILE_NACIONAL = [
    # Grandes medios
    'https://www.emol.com/rss/nacional.xml',
    'https://www.emol.com/rss/economia.xml',
    'https://www.emol.com/rss/policiales.xml',
    'https://www.emol.com/rss/deportes.xml',
    'https://www.emol.com/rss/tendencias.xml',
    'https://www.latercera.com/feed/',
    'https://www.biobiochile.cl/feed/',
    'https://www.cooperativa.cl/noticias/rss/',
    'https://www.lacuarta.com/feed/',
    'https://www.24horas.cl/rss/',
    'https://www.cnnchile.com/feed/',
    'https://www.meganoticias.cl/feed/',
    'https://www.t13.cl/rss/',
    'https://www.adnradio.cl/feed/',
    'https://www.df.cl/feed/',                      # economía/finanzas
    'https://www.eldinamo.cl/feed/',
    'https://www.eldesconcierto.cl/feed/',
    'https://www.publimetro.cl/feed/',
    'https://www.lun.com/rss/',
    'https://www.soychile.cl/feed/',
    'https://www.elmostrador.cl/feed/',
    'https://www.elciudadano.com/feed/',
    'https://www.radiobio.cl/feed/',
    'https://www.radiosantiago.cl/feed/',
]

# ── PRIORIDAD 2: Medios regionales chilenos ──────────────────
FEEDS_CHILE_REGIONAL = [
    # Norte
    'https://www.estrelladelnorte.cl/feed/',        # Iquique
    'https://www.estrellaarica.cl/feed/',           # Arica
    'https://www.mercurioantofagasta.cl/feed/',     # Antofagasta
    'https://www.atacamahoy.cl/feed/',              # Atacama
    # Centro-Norte
    'https://www.diarioeldia.cl/feed/',             # La Serena
    'https://www.mercuriovalpo.cl/feed/',           # Valparaíso
    # Centro
    'https://www.rancaguahoy.cl/feed/',             # Rancagua
    'https://www.diariotalca.cl/feed/',             # Talca
    # Sur
    'https://www.biobiochile.cl/noticias/nacional/region-del-biobio/feed/',
    'https://www.latercera.com/regional/biobio/feed/',
    'https://www.diarioaustral.cl/feed/',           # Valdivia
    'https://www.ellugarino.com/feed/',             # Los Lagos
    'https://www.patagoniachile.cl/feed/',          # Aysén
    'https://www.laprensaaustral.cl/feed/',         # Magallanes
    # Araucanía (tema sensible, seguimiento especial)
    'https://www.elperiodico.cl/feed/',
    'https://www.ellibero.cl/feed/',
]

# ── PRIORIDAD 3: Internacional con mención Chile ────────────
FEEDS_INTERNACIONAL_CHILE = [
    'https://www.infobae.com/arc/outboundfeeds/rss/america/chile/',
    'https://www.lanacion.com.ar/rss/mundo.xml',    # Argentina cubre Chile
    'https://www.bbc.com/mundo/topics/c3xnz37krqvt.rss',  # BBC Chile
    'https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/america/portada',
    'https://www.dw.com/es/rss/america-latina/s-3500',
    'https://www.france24.com/es/rss',
    'https://www.rtve.es/rss/noticias/internacional/',
]

ALL_FEEDS_CHILE = FEEDS_CHILE_NACIONAL + FEEDS_CHILE_REGIONAL + FEEDS_INTERNACIONAL_CHILE


# ═══════════════════════════════════════════════════════════════
# OBTENER NOTICIAS
# ═══════════════════════════════════════════════════════════════

def obtener_rss_chile(feeds, max_noticias=60):
    """Obtiene noticias de feeds, filtra solo las de Chile"""
    noticias = []
    urls_vistas = set()

    for feed_url in feeds:
        try:
            r = requests.get(feed_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=8)
            if r.status_code != 200:
                continue
            feed = feedparser.parse(r.content)
            if not feed or not feed.entries:
                continue

            fuente = feed.feed.get('title', feed_url.split('/')[2])[:30]
            es_fuente_cl = '.cl' in feed_url

            for entry in feed.entries[:5]:
                titulo = limpiar_texto(entry.get('title', ''))
                if not titulo or es_titulo_generico(titulo):
                    continue

                link = entry.get('link', '')
                if not link or normalizar_url(link) in urls_vistas:
                    continue

                desc = limpiar_texto(
                    entry.get('summary', '') or entry.get('description', '')
                )

                # Filtro Chile
                es_chile, nivel = es_noticia_chile(titulo, desc, fuente)
                if not es_chile:
                    # Si la fuente es internacional, descartar sin mención a Chile
                    if not es_fuente_cl:
                        continue
                    # Si es fuente .cl y no menciona Chile explícitamente, asumimos que es Chile
                    nivel = 'directo'

                # Buscar imagen
                imagen = None
                for campo in ['media_content', 'media_thumbnail', 'links']:
                    if campo == 'media_content' and hasattr(entry, 'media_content'):
                        imgs = entry.get('media_content', [])
                        if imgs:
                            imagen = imgs[0].get('url')
                            break
                    elif campo == 'media_thumbnail' and hasattr(entry, 'media_thumbnail'):
                        imgs = entry.get('media_thumbnail', [])
                        if imgs:
                            imagen = imgs[0].get('url')
                            break
                    elif campo == 'links':
                        for lk in entry.get('links', []):
                            if lk.get('type', '').startswith('image/'):
                                imagen = lk.get('href')
                                break

                # Algunos feeds incluyen imagen en enclosures
                if not imagen:
                    for enc in entry.get('enclosures', []):
                        if enc.get('type', '').startswith('image/'):
                            imagen = enc.get('href') or enc.get('url')
                            break

                categoria = detectar_categoria(titulo, desc)
                tiene_imagen = bool(imagen)

                noticias.append({
                    'titulo':      titulo,
                    'descripcion': desc,
                    'url':         link,
                    'imagen':      imagen,
                    'tiene_imagen': tiene_imagen,
                    'fuente':      f"RSS:{fuente}",
                    'fecha':       entry.get('published', ''),
                    'categoria':   categoria,
                    'nivel_chile': nivel,
                    'puntaje':     calcular_puntaje_viral(
                                       titulo, desc,
                                       tiene_imagen=tiene_imagen,
                                       fuente=fuente,
                                       nivel_chile=nivel
                                   ),
                })
                urls_vistas.add(normalizar_url(link))

                if len(noticias) >= max_noticias:
                    return noticias

        except Exception as e:
            log(f"Error RSS {feed_url[:50]}: {e}", 'error')
            continue

    return noticias


def obtener_newsapi_chile():
    """Obtiene noticias de NewsAPI filtradas a Chile"""
    if not NEWS_API_KEY:
        return []

    noticias = []
    queries_chile = [
        'Chile Kast gobierno 2026',
        'Chile economía inflación dólar',
        'Chile crimen delincuencia seguridad',
        'Chile terremoto tsunami emergencia',
        'Chile protestas manifestaciones',
        'Santiago noticias hoy',
        'Chile política senado diputados',
        'Chile deporte selección fútbol',
        'Chile salud hospital minsal',
        'Chile minería litio cobre',
        'Chile educación universidades',
        'Araucanía conflicto mapuche',
        'Chile medioambiente incendio',
        'Chile Johannes Kaiser economía',
        'Chile partido republicano gobierno',
    ]

    for query in queries_chile:
        try:
            r = requests.get(
                'https://newsapi.org/v2/everything',
                params={
                    'apiKey':   NEWS_API_KEY,
                    'q':        query,
                    'language': 'es',
                    'sortBy':   'publishedAt',
                    'pageSize': 5,
                },
                timeout=10
            ).json()

            if r.get('status') != 'ok':
                continue

            for art in r.get('articles', []):
                titulo = limpiar_texto(art.get('title', ''))
                if not titulo or '[Removed]' in titulo:
                    continue

                desc = limpiar_texto(art.get('description', ''))
                imagen = art.get('urlToImage')

                es_chile, nivel = es_noticia_chile(titulo, desc)
                if not es_chile:
                    continue

                categoria = detectar_categoria(titulo, desc)
                tiene_imagen = bool(imagen)

                noticias.append({
                    'titulo':       titulo,
                    'descripcion':  desc,
                    'url':          art.get('url', ''),
                    'imagen':       imagen,
                    'tiene_imagen': tiene_imagen,
                    'fuente':       f"NewsAPI:{art.get('source', {}).get('name', '')}",
                    'fecha':        art.get('publishedAt', ''),
                    'categoria':    categoria,
                    'nivel_chile':  nivel,
                    'puntaje':      calcular_puntaje_viral(
                                        titulo, desc,
                                        tiene_imagen=tiene_imagen,
                                        nivel_chile=nivel
                                    ),
                })
        except Exception as e:
            log(f"Error NewsAPI query '{query}': {e}", 'error')

    log(f"NewsAPI Chile: {len(noticias)} noticias", 'info')
    return noticias


def obtener_newsdata_chile():
    """Obtiene noticias de NewsData.io filtradas a Chile (API previamente sin implementar)"""
    if not NEWSDATA_API_KEY:
        return []

    noticias = []
    queries = ['Chile noticias hoy', 'Chile gobierno Kast', 'Chile economía seguridad']

    for query in queries:
        try:
            r = requests.get(
                'https://newsdata.io/api/1/news',
                params={
                    'apikey':   NEWSDATA_API_KEY,
                    'q':        query,
                    'language': 'es',
                    'country':  'cl',
                    'size':     5,
                },
                timeout=10
            )
            if r.status_code != 200:
                log(f"NewsData HTTP {r.status_code}", 'advertencia')
                continue
            data = r.json()
            if data.get('status') != 'success':
                continue

            for art in data.get('results', []):
                titulo = limpiar_texto(art.get('title', ''))
                if not titulo or es_titulo_generico(titulo):
                    continue
                # NewsData entrega content (texto más completo que description)
                desc = limpiar_texto(art.get('content', '') or art.get('description', ''))
                imagen = art.get('image_url')

                es_chile, nivel = es_noticia_chile(titulo, desc)
                if not es_chile:
                    nivel = 'directo'   # ya filtrado por country=cl

                categoria    = detectar_categoria(titulo, desc)
                tiene_imagen = bool(imagen)

                noticias.append({
                    'titulo':       titulo,
                    'descripcion':  desc,
                    'url':          art.get('link', ''),
                    'imagen':       imagen,
                    'tiene_imagen': tiene_imagen,
                    'fuente':       f"NewsData:{art.get('source_id', '')}",
                    'fecha':        art.get('pubDate', ''),
                    'categoria':    categoria,
                    'nivel_chile':  nivel,
                    'puntaje':      calcular_puntaje_viral(
                                        titulo, desc,
                                        tiene_imagen=tiene_imagen,
                                        nivel_chile=nivel
                                    ),
                })
        except Exception as e:
            log(f"Error NewsData query '{query}': {e}", 'error')

    log(f"NewsData Chile: {len(noticias)} noticias", 'info')
    return noticias


def obtener_gnews_chile():
    """Obtiene noticias de GNews filtradas a Chile"""
    if not GNEWS_API_KEY:
        return []

    noticias = []
    try:
        r = requests.get(
            'https://gnews.io/api/v4/top-headlines',
            params={
                'apikey':   GNEWS_API_KEY,
                'lang':     'es',
                'country':  'cl',
                'max':      10,
            },
            timeout=10
        ).json()

        for art in r.get('articles', []):
            titulo = limpiar_texto(art.get('title', ''))
            if not titulo:
                continue
            desc    = limpiar_texto(art.get('description', ''))
            imagen  = art.get('image')
            es_chile, nivel = es_noticia_chile(titulo, desc)
            if not es_chile:
                nivel = 'directo'   # GNews ya filtra por country=cl

            categoria   = detectar_categoria(titulo, desc)
            tiene_imagen = bool(imagen)

            noticias.append({
                'titulo':       titulo,
                'descripcion':  desc,
                'url':          art.get('url', ''),
                'imagen':       imagen,
                'tiene_imagen': tiene_imagen,
                'fuente':       f"GNews:{art.get('source', {}).get('name', '')}",
                'fecha':        art.get('publishedAt', ''),
                'categoria':    categoria,
                'nivel_chile':  nivel,
                'puntaje':      calcular_puntaje_viral(
                                    titulo, desc,
                                    tiene_imagen=tiene_imagen,
                                    nivel_chile=nivel
                                ),
            })
    except Exception as e:
        log(f"Error GNews: {e}", 'error')

    log(f"GNews Chile: {len(noticias)} noticias", 'info')
    return noticias


# ═══════════════════════════════════════════════════════════════
# VERIFICACIÓN DE FUENTE
# ═══════════════════════════════════════════════════════════════

# Mapa de prefijos de fuente → nombre legible + ícono de verificación
FUENTES_VERIFICACION = {
    # APIs externas
    'newsapi':    ('Google News',    '🔵'),
    'gnews':      ('GNews',          '🟢'),
    'newsdata':   ('NewsData.io',    '🟡'),
    # Medios nacionales chilenos reconocibles
    'emol':       ('Emol',           '✅'),
    'latercera':  ('La Tercera',     '✅'),
    'biobio':     ('BioBío Chile',   '✅'),
    'cooperativa':('Cooperativa',    '✅'),
    'cnnchile':   ('CNN Chile',      '✅'),
    't13':        ('T13',            '✅'),
    '24horas':    ('24 Horas',       '✅'),
    'meganoticias':('Meganoticias',  '✅'),
    'df':         ('Diario Financiero','✅'),
    'elmostrador':('El Mostrador',   '✅'),
    'lacuarta':   ('La Cuarta',      '✅'),
    'lun':        ('Las Últimas Noticias','✅'),
    'adnradio':   ('ADN Radio',      '✅'),
    'eldinamo':   ('El Dínamo',      '✅'),
    'publimetro': ('Publimetro',     '✅'),
    'eldesconcierto':('El Desconcierto','✅'),
    # Medios internacionales con sección Chile
    'infobae':    ('Infobae',        '🔵'),
    'bbc':        ('BBC Mundo',      '🔵'),
    'elpais':     ('El País',        '🔵'),
    'france24':   ('France 24',      '🔵'),
    'dw':         ('DW Español',     '🔵'),
}

def formatear_fuente_verificacion(fuente_raw, url=''):
    """
    Recibe el campo 'fuente' de la noticia (ej: 'RSS:Emol', 'NewsAPI:El Mostrador')
    y retorna una línea de verificación formateada para el post de Facebook.
    """
    fuente_lower = fuente_raw.lower()
    url_lower    = url.lower()

    # Buscar coincidencia en el mapa
    for clave, (nombre, icono) in FUENTES_VERIFICACION.items():
        if clave in fuente_lower or clave in url_lower:
            # Distinguir entre API de agregación y medio original
            if fuente_lower.startswith('newsapi:'):
                medio = fuente_raw.split(':', 1)[-1].strip() or nombre
                return f"🔵 Noticia indexada por Google News · Fuente original: {medio}"
            elif fuente_lower.startswith('gnews:'):
                medio = fuente_raw.split(':', 1)[-1].strip() or nombre
                return f"🟢 Verificado por GNews · Fuente original: {medio}"
            elif fuente_lower.startswith('newsdata:'):
                medio = fuente_raw.split(':', 1)[-1].strip() or nombre
                return f"🟡 Verificado por NewsData.io · Fuente original: {medio}"
            else:
                # RSS directo del medio
                return f"{icono} Fuente verificada: {nombre}"

    # Fuente RSS genérica: extraer el nombre del medio del campo fuente
    if ':' in fuente_raw:
        nombre_medio = fuente_raw.split(':', 1)[-1].strip()
    else:
        nombre_medio = fuente_raw.strip()

    if nombre_medio:
        return f"📰 Fuente: {nombre_medio}"

    return "📰 Fuente periodística verificada"


# ═══════════════════════════════════════════════════════════════
# PUBLICACIÓN FACEBOOK
# ═══════════════════════════════════════════════════════════════

def publicar_facebook(titulo, descripcion, imagen_path, hashtags, cta, fuente='', url=''):
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("Faltan credenciales Facebook", 'error')
        return False
    if not imagen_path or not os.path.exists(imagen_path):
        log("Sin imagen para publicar", 'error')
        return False

    # Línea de verificación de fuente
    linea_fuente = formatear_fuente_verificacion(fuente, url)

    # descripcion ya viene procesada por obtener_descripcion_completa()
    # Solo ajustamos si el mensaje total excede el límite de Facebook (63.206 chars,
    # pero para posts de foto el límite práctico es ~2.200)
    MAX_DESC_POST = 58000  # límite real Facebook ~63.000 chars; dejamos margen
    desc_post = descripcion if len(descripcion) <= MAX_DESC_POST else descripcion[:MAX_DESC_POST].rstrip() + '…'

    mensaje = (
        f"🔴 {titulo}\n\n"
        f"{desc_post}\n\n"
        f"{'─' * 30}\n"
        f"{linea_fuente}\n"
        f"{'─' * 30}\n"
        f"{cta}\n\n"
        f"{hashtags}\n\n"
        f"📰 Verdad Hoy — Noticias Chile 🇨🇱"
    )

    # Facebook permite hasta ~63.000 chars; solo cortamos como último recurso
    if len(mensaje) > 62000:
        mensaje = mensaje[:61900] + '…'

    fb_url = f"https://graph.facebook.com/{FB_API_VERSION}/{FB_PAGE_ID}/photos"
    for intento in range(1, FB_MAX_REINTENTOS + 1):
        try:
            with open(imagen_path, 'rb') as img_f:
                r = requests.post(
                    fb_url,
                    files={'file': ('imagen.jpg', img_f, 'image/jpeg')},
                    data={
                        'message':      mensaje,
                        'access_token': FB_ACCESS_TOKEN,
                        'published':    'true',
                    },
                    timeout=60
                )
            resultado = r.json()
            if 'id' in resultado:
                log(f"Publicado OK — ID: {resultado['id']}", 'exito')
                return True
            else:
                error = resultado.get('error', {})
                log(f"Error FB (intento {intento}): {error.get('message','?')} (código {error.get('code','?')})", 'error')
                if intento < FB_MAX_REINTENTOS:
                    time_module.sleep(5 * intento)
        except Exception as e:
            log(f"Excepción FB (intento {intento}): {e}", 'error')
            if intento < FB_MAX_REINTENTOS:
                time_module.sleep(5 * intento)
    return False


def publicar_facebook_video(titulo, descripcion, video_path, hashtags, cta, fuente='', url=''):
    """Publica un video nativo en Facebook vía /videos endpoint"""
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("Faltan credenciales Facebook", 'error')
        return False
    if not video_path or not os.path.exists(video_path):
        log("Sin video para publicar", 'error')
        return False

    linea_fuente = formatear_fuente_verificacion(fuente, url)
    MAX_DESC = 58000  # límite real Facebook ~63.000 chars; dejamos margen
    desc_post = descripcion if len(descripcion) <= MAX_DESC else descripcion[:MAX_DESC].rstrip() + '…'

    mensaje = (
        f"🔴 {titulo}\n\n"
        f"{desc_post}\n\n"
        f"{'─' * 30}\n"
        f"{linea_fuente}\n"
        f"{'─' * 30}\n"
        f"{cta}\n\n"
        f"{hashtags}\n\n"
        f"📰 Verdad Hoy — Noticias Chile 🇨🇱"
    )

    if len(mensaje) > 60000:
        mensaje = mensaje[:59900] + '…'

    fb_url = f"https://graph.facebook.com/{FB_API_VERSION}/{FB_PAGE_ID}/videos"

    for intento in range(1, FB_MAX_REINTENTOS + 1):
        try:
            with open(video_path, 'rb') as vf:
                r = requests.post(
                    fb_url,
                    files={'source': ('video.mp4', vf, 'video/mp4')},
                    data={
                        'description':  mensaje,
                        'access_token': FB_ACCESS_TOKEN,
                        'published':    'true',
                    },
                    timeout=180
                )
            resultado = r.json()
            if 'id' in resultado:
                log(f"📹 Video publicado OK — ID: {resultado['id']}", 'exito')
                return True
            else:
                error = resultado.get('error', {})
                log(f"Error FB video (intento {intento}): {error.get('message','?')}", 'error')
                if intento < FB_MAX_REINTENTOS:
                    time_module.sleep(5 * intento)
        except Exception as e:
            log(f"Excepción FB video (intento {intento}): {e}", 'error')
            if intento < FB_MAX_REINTENTOS:
                time_module.sleep(5 * intento)

    return False


def publicar_wordpress(titulo, descripcion, imagen_path, categoria, url_fuente=''):
    """Publica el artículo en WordPress vía REST API. Retorna True si OK."""
    if not WP_URL or not WP_USER or not WP_APP_PASSWORD:
        return False   # no configurado, silencio total

    try:
        import base64
        creds   = base64.b64encode(f"{WP_USER}:{WP_APP_PASSWORD}".encode()).decode()
        headers = {
            'Authorization': f'Basic {creds}',
            'Content-Type':  'application/json',
        }
        wp_api = WP_URL.rstrip('/') + '/wp-json/wp/v2'

        # Subir imagen destacada si existe
        media_id = None
        if imagen_path and os.path.exists(imagen_path):
            try:
                with open(imagen_path, 'rb') as img_f:
                    img_data = img_f.read()
                media_r = requests.post(
                    f'{wp_api}/media',
                    headers={
                        'Authorization': f'Basic {creds}',
                        'Content-Disposition': f'attachment; filename="noticia.jpg"',
                        'Content-Type': 'image/jpeg',
                    },
                    data=img_data,
                    timeout=30
                )
                media_id = media_r.json().get('id')
            except Exception as e:
                log(f"WP media upload: {e}", 'advertencia')

        # Contenido del post
        contenido_html = f"<p>{descripcion}</p>"
        if url_fuente:
            contenido_html += f'<p><a href="{url_fuente}" target="_blank" rel="nofollow">Ver noticia original</a></p>'

        post_data = {
            'title':   titulo,
            'content': contenido_html,
            'status':  'publish',
            'categories': [],
        }
        if media_id:
            post_data['featured_media'] = media_id

        r = requests.post(f'{wp_api}/posts', headers=headers,
                          json=post_data, timeout=30)
        if r.status_code in (200, 201):
            wp_link = r.json().get('link', '')
            log(f"✅ WordPress publicado: {wp_link}", 'exito')
            return True
        else:
            log(f"WP error {r.status_code}: {r.text[:200]}", 'error')
            return False

    except Exception as e:
        log(f"Error WordPress: {e}", 'error')
        return False


# ═══════════════════════════════════════════════════════════════
# CONTROL DE TIEMPO
# ═══════════════════════════════════════════════════════════════

def verificar_tiempo():
    estado = cargar_json(ESTADO_PATH, {'ultima_publicacion': None})
    ultima = estado.get('ultima_publicacion')

    # En GitHub Actions siempre publicar (el workflow controla el cron)
    if os.getenv('GITHUB_RUN_NUMBER'):
        return True

    if not ultima:
        return True

    try:
        dt = datetime.fromisoformat(ultima)
        mins = (datetime.now() - dt).total_seconds() / 60
        if mins < TIEMPO_ENTRE_PUBLICACIONES:
            log(f"Última publicación hace {mins:.0f} min — esperando", 'info')
            return False
    except:
        pass
    return True


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    print("\n" + "=" * 65)
    print("  VERDAD HOY — NOTICIAS CHILE 24/7  V7.0")
    print("  Noticias nacionales + internacionales relacionadas con Chile")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if FORZAR_PUBLICACION:
        print("  ⚡ MODO FORZADO ACTIVO")
    print("=" * 65)

    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("Faltan credenciales Facebook (FB_PAGE_ID / FB_ACCESS_TOKEN)", 'error')
        return False

    # ── Verificaciones previas ────────────────────────────────
    if not FORZAR_PUBLICACION:
        if not verificar_tiempo():
            return None    # muy pronto → salida normal

        if not esta_en_horario_pico():
            log("Fuera de horario pico — esperando próxima ventana", 'info')
            return None

    historial = cargar_historial()
    log(f"Historial: {len(historial.get('urls', []))} URLs publicadas", 'info')

    if limite_diario_alcanzado(historial):
        log(f"Límite diario alcanzado ({MAX_POSTS_POR_DIA} posts) — hasta mañana", 'info')
        return None

    # ── Recolectar noticias ───────────────────────────────────
    noticias = []

    log("Obteniendo RSS Chile nacional...", 'info')
    rss_nac = obtener_rss_chile(FEEDS_CHILE_NACIONAL, max_noticias=50)
    noticias.extend(rss_nac)
    log(f"RSS nacional: {len(rss_nac)}", 'info')

    log("Obteniendo RSS Chile regional...", 'info')
    rss_reg = obtener_rss_chile(FEEDS_CHILE_REGIONAL, max_noticias=30)
    noticias.extend(rss_reg)
    log(f"RSS regional: {len(rss_reg)}", 'info')

    log("Obteniendo RSS internacional con mención Chile...", 'info')
    rss_int = obtener_rss_chile(FEEDS_INTERNACIONAL_CHILE, max_noticias=20)
    noticias.extend(rss_int)
    log(f"RSS internacional: {len(rss_int)}", 'info')

    if NEWS_API_KEY:
        noticias.extend(obtener_newsapi_chile())
    if NEWSDATA_API_KEY:
        noticias.extend(obtener_newsdata_chile())
    if GNEWS_API_KEY:
        noticias.extend(obtener_gnews_chile())

    if not noticias:
        log("No se encontraron noticias", 'advertencia')
        return None

    log(f"Total noticias recolectadas: {len(noticias)}", 'info')

    # ── Filtrar duplicadas ────────────────────────────────────
    noticias_unicas = []
    urls_vistas     = set()
    for n in noticias:
        url_norm = normalizar_url(n.get('url', ''))
        if url_norm in urls_vistas:
            continue
        duplicada, _ = noticia_ya_publicada(historial, n['url'], n['titulo'])
        if duplicada:
            continue
        urls_vistas.add(url_norm)
        noticias_unicas.append(n)

    log(f"Noticias únicas disponibles: {len(noticias_unicas)}", 'info')

    if not noticias_unicas:
        log("Todas las noticias ya fueron publicadas", 'advertencia')
        return None

    # ── Seleccionar la mejor noticia ─────────────────────────
    con_imagen = sorted(
        [n for n in noticias_unicas if n.get('tiene_imagen')],
        key=lambda x: x.get('puntaje', 0), reverse=True
    )
    sin_imagen = sorted(
        [n for n in noticias_unicas if not n.get('tiene_imagen')],
        key=lambda x: x.get('puntaje', 0), reverse=True
    )
    candidatas   = con_imagen + sin_imagen
    seleccionada = candidatas[0]
    categoria    = seleccionada.get('categoria', 'default')
    nivel_chile  = seleccionada.get('nivel_chile', 'directo')

    log(f"Seleccionada: {seleccionada['titulo'][:70]}", 'info')
    log(f"Categoría: {categoria} | Nivel: {nivel_chile} | "
        f"Puntaje: {seleccionada.get('puntaje',0)} | "
        f"Imagen: {'SÍ' if seleccionada.get('tiene_imagen') else 'NO'}", 'info')

    # ── Procesar imagen ───────────────────────────────────────
    imagen_path, tipo_imagen = procesar_imagen(seleccionada)
    if not imagen_path:
        log("No se pudo crear imagen, abortando", 'error')
        return False
    log(f"Tipo imagen: {tipo_imagen}", 'imagen')

    # ── Texto completo ────────────────────────────────────────
    log("Obteniendo texto completo del artículo...", 'info')
    descripcion_completa = obtener_descripcion_completa(seleccionada, max_chars=8000)
    log(f"Texto final: {len(descripcion_completa)} chars", 'info')

    # ── CTAs y hashtags ───────────────────────────────────────
    hashtags  = generar_hashtags(seleccionada['titulo'],
                                  seleccionada.get('descripcion', ''), categoria)
    cta_post  = obtener_cta(categoria, seleccionada['titulo'])
    cta_video = obtener_cta_video(categoria, seleccionada['titulo'])

    log(f"Hashtags: {hashtags}", 'info')
    log(f"CTA post: {cta_post}", 'info')
    log(f"CTA video: {cta_video}", 'info')

    # ── Intentar publicar como VIDEO ──────────────────────────
    exito = False
    video_path = crear_video_noticia(imagen_path, seleccionada['titulo'],
                                      descripcion_completa[:400], categoria, cta_video)
    if video_path:
        log("🎬 Intentando publicar como video...", 'info')
        exito = publicar_facebook_video(
            titulo      = seleccionada['titulo'],
            descripcion = descripcion_completa,
            video_path  = video_path,
            hashtags    = hashtags,
            cta         = cta_post,
            fuente      = seleccionada.get('fuente', ''),
            url         = seleccionada.get('url', ''),
        )
        try:
            os.remove(video_path)
        except:
            pass

    # ── Fallback: publicar como imagen si el video falló ─────
    if not exito:
        log("Fallback: publicando como imagen...", 'info')
        exito = publicar_facebook(
            titulo      = seleccionada['titulo'],
            descripcion = descripcion_completa,
            imagen_path = imagen_path,
            hashtags    = hashtags,
            cta         = cta_post,
            fuente      = seleccionada.get('fuente', ''),
            url         = seleccionada.get('url', ''),
        )

    # ── WordPress (opcional) ──────────────────────────────────
    if exito and WP_URL:
        log("Publicando en WordPress...", 'info')
        publicar_wordpress(
            titulo      = seleccionada['titulo'],
            descripcion = descripcion_completa,
            imagen_path = imagen_path,
            categoria   = categoria,
            url_fuente  = seleccionada.get('url', ''),
        )

    # Limpiar imagen
    try:
        if imagen_path and os.path.exists(imagen_path):
            os.remove(imagen_path)
    except:
        pass

    if exito:
        guardar_historial(historial, seleccionada['url'], seleccionada['titulo'])
        guardar_json(ESTADO_PATH, {
            'ultima_publicacion': datetime.now().isoformat(),
            'ultima_noticia':     seleccionada['titulo'][:60],
            'ultima_categoria':   categoria,
            'nivel_chile':        nivel_chile,
            'tenia_imagen':       seleccionada.get('tiene_imagen', False),
        })
        total = historial.get('estadisticas', {}).get('total_publicadas', 0) + 1
        log(f"✅ ÉXITO — Total publicadas: {total}", 'exito')
        return True
    else:
        log("❌ PUBLICACIÓN FALLIDA", 'error')
        return False


if __name__ == "__main__":
    # Códigos de salida:
    #   0 = publicación exitosa O salida normal (tiempo, horario, límite)
    #   1 = error real (credenciales, Facebook API, excepción)
    try:
        resultado = main()
        if resultado is True:
            exit(0)    # publicó OK
        elif resultado is None:
            exit(0)    # salida normal (tiempo, horario pico, límite diario)
        else:
            exit(1)    # error real
    except Exception as e:
        log(f"Error crítico: {e}", 'error')
        import traceback
        traceback.print_exc()
        exit(1)
