# HEICto-

A web tool to convert HEIC, HEIF, AVIF, and DNG images to PNG, JPG, or WebP.

## Features

- **Color Management**: Converts Display P3 colors to standard sRGB without color distortion.
- **Quality Control**: Select output format (PNG, JPG, WebP) and adjust compression quality.
- **Batch Processing**: Convert multiple images at once and download them individually or as a ZIP archive.
- **Clipboard Support**: Paste images directly with Cmd+V / Ctrl+V to convert immediately.
- **Client-Side Processing**: Converts images locally in the browser without uploading files to an external server.

## Local Usage

### macOS
Double-click `start.command` in Finder to launch the local server and open the tool in your browser (`http://localhost:5173`).

### Terminal
```bash
./start.sh
```
Or run directly with Python:
```bash
python3 app.py
```

### Command Line
```bash
python3 converter.py photo.heic output.png
```

## Deployment

### GitHub Pages
Deploy the `web/` folder or `gh-pages` branch as a static site in your repository settings under **Pages**.

### Containers
A `Dockerfile` is included for container deployments:
```bash
docker build -t heicto .
docker run -d -p 5173:5173 heicto
```

## Privacy

Conversions run locally on your machine or in the browser. No files are uploaded to third-party services.

## License

MIT License.
