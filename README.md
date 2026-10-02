# Prezi2PDF

[Español](#español) | [English](#english)

---

<a name="español"></a>
## 🇪🇸 Español

Script para convertir presentaciones de Prezi en archivos PDF descargables y descargar videos de Prezi Video o videos incrustados.

### Instalación de dependencias
```bash
python -m pip install -r requirements.txt
```

### Modo de uso

#### Modo interactivo (más fácil)
Simplemente ejecuta el script y te pedirá la URL o ID, además de preguntarte si deseas filtrar transiciones o descargar videos si se detectan:
```bash
python prezi2pdf.py
```

#### Por línea de comandos
Pasa el enlace directamente con `-u` o `--url`:
```bash
python prezi2pdf.py -u "https://prezi.com/p/bnnvwhp3j0fy/solar-system/"
```

O utilizando solo el ID de la presentación:
```bash
python prezi2pdf.py -u bnnvwhp3j0fy
```

#### Discriminación inteligente de transiciones y efectos
Por defecto, el programa discrimina automáticamente las transiciones y efectos progresivos (animaciones donde van apareciendo viñetas, textos o imágenes paso a paso) para incluir en el PDF **únicamente la versión completa de cada diapositiva con toda su información**, ahorrando páginas repetitivas y tiempo de descarga.

Si por algún motivo deseas conservar todos los pasos intermedios de las animaciones, usa `-a` o `--all-steps`:
```bash
python prezi2pdf.py -u "URL" --all-steps
```

#### Descarga de videos incrustados dentro de la presentación
Si la presentación contiene videos incrustados (videos MP4 de Prezi, YouTube, Vimeo, etc.), el script los detectará automáticamente:
- **Modo interactivo:** Si se detectan videos, el programa te preguntará si deseas descargarlos en máxima calidad (`[S/n]`).
- **Por terminal para forzar la descarga de videos:** Usa `-v` o `--download-videos`:
  ```bash
  python prezi2pdf.py -u "URL" -v
  ```
- **Por terminal para omitir la descarga de videos:** Usa `--no-videos`:
  ```bash
  python prezi2pdf.py -u "URL" --no-videos
  ```

Los videos se guardan organizados en carpetas individuales dentro de `videos/{nombre_presentacion}/`.

#### Guardar también metadatos JSON
```bash
python prezi2pdf.py -u "URL" -j
```

Los PDFs generados se guardan automáticamente en la carpeta `presentations/`.

---

<a name="english"></a>
## 🇬🇧 English

Script to convert Prezi presentations into downloadable PDF documents and download Prezi Videos as well as embedded videos.

### Dependency Installation
```bash
python -m pip install -r requirements.txt
```

### Usage

#### Interactive Mode (easiest)
Simply run the script and it will prompt you for the URL or ID, along with options to filter transitions or download videos if detected:
```bash
python prezi2pdf.py
```

#### Via Command Line
Pass the link directly using `-u` or `--url`:
```bash
python prezi2pdf.py -u "https://prezi.com/p/bnnvwhp3j0fy/solar-system/"
```

Or using just the presentation ID:
```bash
python prezi2pdf.py -u bnnvwhp3j0fy
```

#### Smart Transition and Animation Filtering
By default, the program automatically discriminates progressive transitions and effects (animations where bullet points, text, or images appear step-by-step) to include in the PDF **only the complete version of each slide with all its information**, eliminating repetitive pages and speeding up download times.

If you wish to keep every intermediate step of the animations, use `-a` or `--all-steps`:
```bash
python prezi2pdf.py -u "URL" --all-steps
```

#### Download Embedded Videos Inside Presentations
If the presentation contains embedded videos (Prezi-hosted MP4s, YouTube, Vimeo, etc.), the script detects them automatically:
- **Interactive Mode:** If videos are detected, the program will ask whether you want to download them in maximum quality (`[Y/n]`).
- **Command Line - Force video download:** Use `-v` or `--download-videos`:
  ```bash
  python prezi2pdf.py -u "URL" -v
  ```
- **Command Line - Skip video download:** Use `--no-videos`:
  ```bash
  python prezi2pdf.py -u "URL" --no-videos
  ```

Videos are organized and saved into subfolders inside `videos/{presentation_name}/`.

#### Save JSON Metadata
```bash
python prezi2pdf.py -u "URL" -j
```

Generated PDFs are automatically saved in the `presentations/` directory.