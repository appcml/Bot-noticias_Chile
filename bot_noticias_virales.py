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
                log(f"Imagen descargada: {img_path}", 'exito')
                return img_path
            else:
                os.remove(img_path)
                return None
        else:
            log(f"Error HTTP {response.status_code}", 'error')
            return None
            
    except Exception as e:
        log(f"Error descargando: {e}", 'error')
        return None


# ═══════════════════════════════════════════════════════════════
# CREAR IMAGEN CON OVERLAY (Título sobre imagen original)
# ═══════════════════════════════════════════════════════════════

def crear_imagen_con_overlay(imagen_original_path, titulo, categoria="noticia"):
    """
    Agrega overlay de texto sobre imagen original:
    - Barra superior con categoría de color
    - Título grande en parte inferior con fondo oscuro
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
        import textwrap
        
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
            font_titulo = ImageFont.load_default()
            font_categoria = font_footer = font_titulo
        
        # Color según categoría
        color_barra = {
            'urgente': (220, 20, 60),      # Rojo
            'politica': (75, 0, 130),       # Púrpura
            'deporte': (255, 140, 0),       # Naranja
            'noticia': (25, 25, 112)        # Azul oscuro
        }.get(categoria, (25, 25, 112))
        
        # 1. BARRA SUPERIOR
        draw.rectangle([(0, 0), (1200, 60)], fill=color_barra)
        draw.text((20, 15), categoria.upper(), font=font_categoria, fill=(255, 255, 255))
        draw.rectangle([(0, 60), (1200, 65)], fill=(255, 255, 255))
        
        # 2. BANDA INFERIOR OSCURA (gradiente)
        altura_banda = 200
        for i in range(altura_banda):
            alpha = int(255 * (0.7 * (i / altura_banda)))  # 70% opacidad max
            draw.rectangle([(0, 630-altura_banda+i), (1200, 630-altura_banda+i+1)], 
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
            draw.text((22, y+2), linea, font=font_titulo, fill=(0, 0, 0))
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
        return None


# ═══════════════════════════════════════════════════════════════
# PROCESAR IMAGEN (decidir: original+overlay vs backup)
# ═══════════════════════════════════════════════════════════════

def procesar_imagen(noticia):
    """
    Decide qué tipo de imagen crear:
    1. Si hay imagen original -> descargar + overlay
    2. Si no hay imagen -> backup con color sólido
    """
    titulo = noticia.get('titulo', '')
    url_imagen = noticia.get('imagen')
    
    # Detectar categoría
    categoria = "noticia"
    titulo_lower = titulo.lower()
    if any(p in titulo_lower for p in ['trump', 'biden', 'presidente', 'gobierno']):
        categoria = "politica"
    elif any(p in titulo_lower for p in ['fútbol', 'mundial', 'deporte', 'gol']):
        categoria = "deporte"
    elif any(p in titulo_lower for p in ['urgente', 'crisis', 'muerte', 'ataque']):
        categoria = "urgente"
    
    log(f"Categoría: {categoria}", 'info')
    
    # Intentar usar imagen original
    if url_imagen:
        log(f"Descargando imagen original...", 'imagen')
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
    
    # Fallback: crear backup
    log("Creando imagen backup...", 'imagen')
    return crear_imagen_backup(titulo, categoria), "backup"
