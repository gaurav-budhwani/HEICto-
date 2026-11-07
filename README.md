# 🍎 HEICto- — Professional Image Converter

A minimalist, high-fidelity image converter designed for the Apple/iOS ecosystem. Converts **HEIC**, **HEIF**, **AVIF**, and **ProRAW/DNG** images to **PNG**, **JPG**, or **WebP** with **Apple ColorSync** color fidelity.

Deployable anywhere: Docker, Render, Railway, Fly.io, Vercel, Netlify, or locally on macOS.

---

## ✨ Features

- **ColorSync & Color Management**: Converts Apple wide-gamut **Display P3** into standard **sRGB** without color shifting or desaturation.
- **100% Quality & Lossless Conversion**: Pixel-for-pixel accuracy with optional quality tuning.
- **Minimalist Aesthetic**: Monochromatic palette, segmented controls, live status badges, and floating batch download pill.
- **Batch Processing & ZIP Export**: Drag & drop dozens of files, convert in parallel, and export as a single `.zip`.
- **Keyboard Shortcuts**: Press <kbd>⌘V</kbd> / <kbd>Ctrl+V</kbd> anywhere on the page to paste and convert images directly from clipboard.
- **Universal Deployment**: Runs natively on macOS, Linux containers (Docker), or static hosting (Vercel, Netlify, Cloudflare Pages).

---

## 🚀 Local Development

### 1. macOS Finder (Easiest)
Double-click **`start.command`** in Finder. It launches the local server and automatically opens `http://localhost:5173`.

### 2. Terminal
```bash
cd heicTOpng
./start.sh
```
Or directly:
```bash
python3 app.py
```
Open **`http://localhost:5173`** in your browser.

### 3. CLI Direct Conversion
```bash
python3 converter.py photo.heic output.png
```

---

## 🌐 Cloud Deployment Options

### Option A: 1-Click Static Deployment (Vercel / Netlify / Cloudflare Pages)
*No server configuration or Python required.* The frontend includes client-side in-browser WebAssembly conversion fallback.

- **Vercel**: Run `vercel` or connect your Git repo. Configuration is pre-set in [`vercel.json`](vercel.json).
- **Netlify**: Connect your Git repo or run `netlify deploy --prod`. Configuration is pre-set in [`netlify.toml`](netlify.toml).
- **GitHub Pages**: Deploy the [`web/`](web/) folder as a static site.

---

### Option B: Container / Full-Stack Deployment (Render, Railway, Fly.io, Cloud Run)

#### 1. Render
1. Push this folder to a Git repository.
2. In Render Dashboard, click **New +** -> **Blueprint** and select your repo (uses [`render.yaml`](render.yaml)).
3. Render will build the container with [`Dockerfile`](Dockerfile) and deploy automatically.

#### 2. Railway
1. Install Railway CLI or connect via GitHub: `railway up`.
2. Railway detects [`Dockerfile`](Dockerfile), builds dependencies (`libheif`), and assigns a live HTTPS URL.

#### 3. Fly.io
```bash
fly launch
fly deploy
```

#### 4. Custom VPS or Docker
```bash
docker build -t heic-studio .
docker run -d -p 5173:5173 --name heic-studio heic-studio
```
Access at `http://YOUR_SERVER_IP:5173`.

---

## 🔒 Privacy

All conversions are performed either on your private server or directly inside the client browser. No images are ever sent to third parties.
