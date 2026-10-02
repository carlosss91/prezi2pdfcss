import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
import re
import shutil
import sys
import time
from img2pdf import convert
import requests
import yt_dlp

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)


def extract_id(url):
    """Extrae el identificador de una URL de Prezi o valida si es un ID directo."""
    patterns = [
        r'/p/(?:edit/)?([a-zA-Z0-9_-]{10,32})',
        r'/v/([a-zA-Z0-9_-]{10,32})',
        r'/view/([a-zA-Z0-9_-]{10,32})',
        r'/i/([a-zA-Z0-9_-]{10,32})',
        r'prezi\.com/([a-zA-Z0-9_-]{10,32})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    trimmed = url.strip().strip('/')
    if re.fullmatch(r'[a-zA-Z0-9_-]{10,32}', trimmed):
        return trimmed

    fallback = re.findall(r'([a-zA-Z0-9_-]{10,32})', url)
    if fallback:
        return fallback[0]

    return None


def resolve_presentation_info(input_str):
    """
    Analiza la URL o ID proporcionado.
    Si es un enlace compartido (/view/), resuelve la página para obtener:
    - prezi_oid: el ID interno real de la presentación
    - prezilink: el token de acceso compartido requerido por la API
    - title: el título de la presentación
    - is_video: booleano indicando si es Prezi Video
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }

    input_clean = input_str.strip()
    is_video = "prezi.com/v/" in input_clean

    is_url = input_clean.startswith("http://") or input_clean.startswith("https://") or "prezi.com" in input_clean
    if not is_url and len(input_clean) >= 18:
        view_url = f"https://prezi.com/view/{input_clean}/"
    elif is_url:
        view_url = input_clean if input_clean.startswith("http") else f"https://{input_clean}"
    else:
        view_url = None

    if view_url and ("/view/" in view_url or len(input_clean) >= 18):
        try:
            print("Analizando enlace compartido de Prezi...")
            r = requests.get(view_url, headers=headers, timeout=20)
            if r.status_code == 200:
                html = r.text
                oid_matches = re.findall(r'prezi_oid[\"\'\\]*:\s*[\"\'\\]*([a-zA-Z0-9_-]+)', html)
                if not oid_matches:
                    oid_matches = re.findall(r'oid[\"\'\\]*:\s*[\"\'\\]*([a-zA-Z0-9_-]+)', html)

                link_matches = re.findall(r'link_id[\"\'\\]*:\s*[\"\'\\]*([a-zA-Z0-9_-]+)', html)
                if not link_matches:
                    token_match = re.search(r'/view/([a-zA-Z0-9_-]+)', view_url)
                    if token_match:
                        link_matches = [token_match.group(1)]

                title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
                title = None
                if title_match:
                    title = title_match.group(1).replace(" | Prezi", "").replace("&amp;", "&").strip()

                if oid_matches:
                    oid = oid_matches[0]
                    prezilink = link_matches[0] if link_matches else None
                    return oid, prezilink, title, is_video
        except Exception as e:
            print(f"Aviso al analizar enlace: {e}")

    oid = extract_id(input_clean)
    return oid, None, None, is_video


def download_video(id, download_json=False):
    """Descarga un video de Prezi Video."""
    url = f"https://prezi.com/api/v5/presentation-content/{id}/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=30)
    except requests.RequestException as e:
        print(f"Error de conexión: {e}")
        return False

    if response.status_code != 200:
        print(f"Error al obtener datos del video (HTTP {response.status_code})")
        return False

    try:
        data = response.json()
    except Exception:
        print("Error al decodificar la respuesta JSON del video.")
        return False

    os.makedirs("./videos", exist_ok=True)
    title = data.get('meta', {}).get('title', id)
    print(f"Descargando video: {title}")
    video_url = data.get('meta', {}).get('video_signed_url_with_title')
    if not video_url:
        print("No se encontró la URL del video en la respuesta.")
        return False

    ydl_opts = {
        'outtmpl': os.path.join('.', 'videos', f'{id}.%(ext)s'),
        'merge_output_format': 'mp4',
        'ignoreerrors': True,
        'writethumbnail': True,
        'retries': 100,
        'add_header': ['user-agent:Mozilla/5.0 (Windows NT 10.0; Win64; x64)'],
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(video_url, download=True)
        print(f"\n¡Éxito! Video guardado en la carpeta './videos'")
    except Exception as e:
        print(f"Error al descargar el video con yt-dlp: {e}")
        return False

    if download_json:
        json_filename = os.path.join("videos", f"{id}.json")
        with open(json_filename, 'w', encoding='utf-8') as outfile:
            json.dump(data, outfile, indent=4, ensure_ascii=False)
        print(f"Archivo JSON guardado en: {os.path.abspath(json_filename)}")

    return True


def are_same_view(s1, s2):
    """
    Determina si dos pasos consecutivos pertenecen a la misma vista/diapositiva
    (es decir, representan efectos o transiciones incrementales sobre el mismo lienzo).
    """
    c1 = s1.get('camera')
    c2 = s2.get('camera')
    if c1 and c2:
        try:
            return (abs(c1['x'] - c2['x']) < 1e-3 and
                    abs(c1['y'] - c2['y']) < 1e-3 and
                    abs(c1['zoom'] - c2['zoom']) < 1e-3 and
                    abs(c1.get('rotation', 0) - c2.get('rotation', 0)) < 1e-3)
        except (KeyError, TypeError):
            pass

    # Si falta la cámara, comparar step_index y tipo de animación
    si1 = s1.get('step_index')
    si2 = s2.get('step_index')
    if si1 is not None and si2 is not None and si1 == si2:
        if s2.get('type') == 'animation':
            return True

    return False


def filter_transition_steps(steps):
    """
    Agrupa los pasos consecutivos que comparten la misma vista (cámara o animación)
    y conserva únicamente el último paso de cada grupo, el cual contiene
    toda la información y los elementos desplegados en su totalidad.
    """
    if not steps:
        return []

    filtered = []
    n = len(steps)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and are_same_view(steps[j], steps[j + 1]):
            j += 1
        # El paso j es el último de la secuencia y tiene todos los efectos acumulados
        filtered.append((j, steps[j]))
        i = j + 1

    return filtered


def extract_embedded_videos(steps):
    """
    Examina los pasos de la presentación para extraer URLs únicas de videos incrustados
    (tanto videos MP4 directos alojados en Prezi como videos externos de YouTube, Vimeo, etc.).
    """
    videos = []
    seen_urls = set()
    for i, s in enumerate(steps):
        v_url = s.get('url')
        if not v_url and isinstance(s.get('video'), dict):
            v_url = s['video'].get('url')
        service = s.get('videoService', '')
        stype = s.get('type', '')

        is_video_step = (stype == 'video' or bool(service) or
                         (v_url and any(ext in v_url.lower() for ext in ['.mp4', '.webm', 'youtube', 'youtu.be', 'vimeo'])))

        if is_video_step and v_url:
            clean_url = v_url.strip()
            if clean_url not in seen_urls:
                seen_urls.add(clean_url)
                videos.append({
                    'step': i + 1,
                    'service': service or 'video',
                    'url': clean_url
                })
    return videos


def download_embedded_videos(videos, presentation_name):
    """
    Descarga una lista de videos incrustados en la máxima calidad disponible.
    Los videos se guardan organizados en una subcarpeta dentro de 'videos/'.
    """
    if not videos:
        return

    safe_title = re.sub(r'[\\/*?:"<>|]', "", presentation_name).strip()
    video_dir = os.path.join("videos", safe_title)
    os.makedirs(video_dir, exist_ok=True)

    has_ffmpeg = bool(shutil.which('ffmpeg'))
    # Si ffmpeg está disponible, mergea las mejores pistas de video y audio
    # Si no, selecciona el mejor archivo contenedor mp4 completo existente
    format_selector = 'bestvideo+bestaudio/best' if has_ffmpeg else 'best[ext=mp4]/best'

    print(f"\nDescargando {len(videos)} video(s) en máxima calidad en: {os.path.abspath(video_dir)}")

    for idx, vid in enumerate(videos, 1):
        v_url = vid['url']
        service = vid.get('service', 'video')
        print(f"\n[{idx}/{len(videos)}] Descargando video ({service}): {v_url}")

        ydl_opts = {
            'outtmpl': os.path.join(video_dir, f'video_{idx:02d}_%(title).80s.%(ext)s'),
            'format': format_selector,
            'merge_output_format': 'mp4',
            'ignoreerrors': True,
            'retries': 10,
            'no_warnings': True,
            'add_header': ['user-agent:Mozilla/5.0 (Windows NT 10.0; Win64; x64)'],
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([v_url])
        except Exception as e:
            print(f"Aviso al descargar video {idx}: {e}")

    print(f"\n¡Videos guardados correctamente en la carpeta: {os.path.abspath(video_dir)}!")


def download_presentation(id, prezilink=None, title=None, download_json=False, filter_transitions=True, download_videos=None):
    """Descarga diapositivas de Prezi y las une en un documento PDF, con opción de descargar videos incrustados."""
    url = f"https://prezi.com/api/v2/storyboard/{id}/"
    if prezilink:
        url += f"?prezilink={prezilink}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
    }
    print("Solicitando datos a la API de Prezi...")
    max_retries = 30
    data = None

    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=60)
        except requests.RequestException as e:
            print(f"Error de red al conectar con Prezi: {e}")
            return False

        if response.status_code == 403:
            print(f"Error 403 (Prohibido): La presentación '{id}' es privada o no permite conversión.")
            return False
        elif response.status_code == 404:
            print(f"Error 404 (No encontrada): No se encontró la presentación con ID '{id}'.")
            return False
        elif response.status_code != 200:
            print(f"Error del servidor Prezi (código {response.status_code}): {response.text}")
            return False

        try:
            data = response.json()
        except Exception:
            print("Error al decodificar la respuesta JSON del servidor.")
            return False

        status = data.get('status')
        if status == 'wait':
            print(f"Prezi está procesando las diapositivas ({attempt + 1}/{max_retries}), esperando 3 segundos...")
            time.sleep(3)
            continue
        elif status == 'success' or 'steps' in data:
            break
        else:
            print(f"Respuesta inesperada de Prezi: {data}")
            return False
    else:
        print("Tiempo de espera agotado esperando que Prezi genere las diapositivas.")
        return False

    steps = data.get('steps', [])
    if not steps:
        print("No se encontraron diapositivas en la presentación.")
        return False

    original_total = len(steps)
    skipped = 0
    if filter_transitions:
        filtered_steps = filter_transition_steps(steps)
        skipped = original_total - len(filtered_steps)
        if skipped > 0:
            print(f"Modo diapositivas completas activado: detectados {skipped} pasos de transición.")
            print(f"Descargando únicamente las {len(filtered_steps)} diapositivas finales completas (de {original_total} pasos totales).")
        steps_to_download = filtered_steps
    else:
        steps_to_download = [(i, s) for i, s in enumerate(steps)]

    total = len(steps_to_download)
    presentation_name = title if title else id
    print(f"Presentación: '{presentation_name}' | Total a procesar: {total} diapositivas")

    # Descarga rápida en paralelo preservando el orden
    session = requests.Session()
    session.headers.update(headers)

    def fetch_slide(item):
        idx, frame = item
        images = frame.get('images', [])
        if not images or 'url' not in images[0]:
            return idx, None
        img_url = images[0]['url']
        for _ in range(3):
            try:
                r = session.get(img_url, timeout=30)
                if r.status_code == 200:
                    return idx, r.content
            except Exception:
                time.sleep(1)
        return idx, None

    slide_contents = [None] * total
    completed = 0
    print(f"Descargando diapositivas en paralelo...")

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_slide, (i, step)): i for i, (orig_idx, step) in enumerate(steps_to_download)}
        for future in as_completed(futures):
            idx, content = future.result()
            if content:
                slide_contents[idx] = content
            completed += 1
            print(f"\rProgreso: {completed}/{total} diapositivas descargadas", end="", flush=True)

    print()

    # Filtrar posibles diapositivas nulas y duplicados idénticos consecutivos
    valid_slides = []
    last_hash = None
    duplicates_omitted = 0
    for c in slide_contents:
        if c is not None:
            if filter_transitions:
                h = hashlib.sha256(c).digest()
                if h == last_hash:
                    duplicates_omitted += 1
                    continue
                last_hash = h
            valid_slides.append(c)

    if not valid_slides:
        print("No se pudo descargar ninguna imagen de la presentación.")
        return False

    if duplicates_omitted > 0:
        print(f"Se omitieron {duplicates_omitted} diapositivas consecutivas idénticas.")

    os.makedirs("./presentations", exist_ok=True)
    safe_title = re.sub(r'[\\/*?:"<>|]', "", presentation_name).strip()
    pdf_filename = os.path.join("presentations", f"{safe_title}.pdf")

    print("Generando archivo PDF...")
    try:
        with open(pdf_filename, 'wb') as pdf:
            pdf.write(convert(valid_slides))
        print(f"\n¡Éxito! PDF con {len(valid_slides)} páginas guardado correctamente en: {os.path.abspath(pdf_filename)}")
        if filter_transitions and (skipped > 0 or duplicates_omitted > 0):
            print(f"-> Se discriminaron {skipped + duplicates_omitted} pasos intermedios/duplicados para conservar solo las pantallas completas.")
    except Exception as e:
        print(f"Error al generar el archivo PDF: {e}")
        return False

    if download_json:
        json_filename = os.path.join("presentations", f"{safe_title}.json")
        with open(json_filename, 'w', encoding='utf-8') as outfile:
            json.dump(data, outfile, indent=4, ensure_ascii=False)
        print(f"Archivo JSON guardado en: {os.path.abspath(json_filename)}")

    # Detectar y procesar videos incrustados dentro del Prezi
    embedded_videos = extract_embedded_videos(steps)
    if embedded_videos:
        print(f"\nSe detectaron {len(embedded_videos)} video(s) incrustado(s) dentro de la presentación.")
        should_download_videos = download_videos
        if should_download_videos is None:
            try:
                opt_v = input(f"¿Deseas descargar también los {len(embedded_videos)} video(s) en máxima calidad? [S/n]: ").strip().lower()
                should_download_videos = opt_v not in ['n', 'no']
            except (KeyboardInterrupt, EOFError):
                print("\nDescarga de videos cancelada por el usuario.")
                should_download_videos = False

        if should_download_videos:
            download_embedded_videos(embedded_videos, presentation_name)
        else:
            print("Descarga de videos incrustados omitida.")

    return True


def main():
    parser = argparse.ArgumentParser(description='Descargar presentaciones y videos de Prezi a PDF/MP4')
    parser.add_argument('--url', '-u', dest='url', action='store', help='URL de Prezi o ID de la presentación', required=False)
    parser.add_argument('--download-json', '-j', dest='download_json', action='store_true', help='Descargar metadatos JSON', required=False)
    parser.add_argument('--all-steps', '-a', dest='all_steps', action='store_true',
                        help='Guardar todos los pasos y transiciones intermedias (por defecto se omiten y solo se guarda la diapositiva final completa)',
                        required=False)
    parser.add_argument('--download-videos', '-v', dest='download_videos', action='store_true', default=None,
                        help='Descargar todos los videos incrustados dentro de la presentación en máxima calidad',
                        required=False)
    parser.add_argument('--no-videos', dest='download_videos', action='store_false',
                        help='No descargar los videos incrustados en la presentación',
                        required=False)

    args = parser.parse_args()

    filter_transitions = not args.all_steps

    url = args.url
    if not url:
        try:
            url = input("Introduce la URL o ID de la presentación de Prezi: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nOperación cancelada.")
            return

    if not url:
        print("Error: No se proporcionó ninguna URL o ID.")
        return

    # Si se ejecuta en modo interactivo y no se indicó --all-steps, permitir elegir o usar Enter por defecto
    if not args.url and not args.all_steps:
        try:
            opt = input("¿Omitir transiciones intermedias y guardar solo diapositivas completas? [S/n]: ").strip().lower()
            if opt in ['n', 'no']:
                filter_transitions = False
            else:
                filter_transitions = True
        except (KeyboardInterrupt, EOFError):
            print("\nOperación cancelada.")
            return

    oid, prezilink, title, is_video = resolve_presentation_info(url)
    if not oid:
        print("Error: No se pudo encontrar un identificador válido de Prezi en la entrada proporcionada.")
        print("Ejemplos válidos:")
        print("  - https://prezi.com/view/ibRMyKC2Eb74TAqJ6coM/")
        print("  - https://prezi.com/p/bnnvwhp3j0fy/solar-system/")
        print("  - bnnvwhp3j0fy")
        return

    print(f"ID detectado: {oid}")
    if prezilink:
        print(f"Token de acceso compartido detectado: {prezilink}")
    if title:
        print(f"Título: {title}")

    if is_video:
        download_video(oid, download_json=args.download_json)
    elif "prezi.com/i/" in url:
        print("El formato Prezi Design no está soportado actualmente.")
    else:
        download_presentation(oid, prezilink=prezilink, title=title, download_json=args.download_json,
                              filter_transitions=filter_transitions, download_videos=args.download_videos)


if __name__ == '__main__':
    main()

