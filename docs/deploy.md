# Deploy CropDoc GB online (use it anywhere, on any phone)

On your own computer, `start.bat` / `start.sh` is enough, and **phone mode** (`start-phone.bat`,
`./start.sh --phone`) lets phones on the same Wi-Fi use Live Scan. To use the app **without the laptop**,
for example in the field on mobile data, put it on a cloud host. Every host below gives an `https://` address,
which phones need for the live camera.

The repository builds as one Docker image (root `Dockerfile`): the API, the built web app and the ONNX model.
It needs no GPU and no PyTorch; 512 MB of RAM is enough.

> **Before you share a public link, read "Privacy" below.** The app has no user accounts, so everyone who opens
> the same address shares one history and dashboard.

## Option A: Hugging Face Spaces (free, always-on CPU)
1. Create a free account at huggingface.co → **New Space**.
2. Name it (for example `cropdoc-gb`), choose **Docker** → **Blank**, hardware **CPU basic (free)**, and choose
   Public or Private (see Privacy).
3. Push this repository to the Space:
   ```bash
   git remote add space https://huggingface.co/spaces/<your-username>/cropdoc-gb
   ```
   ```bash
   git push space main
   ```
   (Hugging Face asks for your username and an access token with *write* permission as the password.)
4. In the Space, edit `README.md` and put this block at the very top (Spaces read their settings from it):
   ```yaml
   ---
   title: CropDoc GB
   emoji: 🌿
   colorFrom: green
   colorTo: green
   sdk: docker
   app_port: 8000
   ---
   ```
5. Wait for the build (a few minutes). Your app is at `https://<your-username>-cropdoc-gb.hf.space`.
   Open it on a phone → **Live Scan** → allow the camera. "Add to Home screen" installs it like an app.

## Option B: Render (free web service, sleeps when idle)
1. Create a free account at render.com and connect your GitHub account.
2. **New → Web Service** → pick `cropdoc-gb` → Render detects the `Dockerfile`.
3. Instance type **Free** → **Create Web Service**. Render sets `PORT`; the image listens on it.
4. Your app is at `https://cropdoc-gb-xxxx.onrender.com`. On the free plan it sleeps after some idle time, and the
   first visit after that takes about a minute to wake up.

## Option C: any server with Docker
```bash
docker compose up --build -d
```
This serves on port 8000 and keeps history in the `cropdoc-data` volume. Put it behind an HTTPS reverse proxy
(for example Caddy or nginx with a Let's Encrypt certificate). Without HTTPS, phones cannot use the live camera.

## Settings (environment variables)
| variable | default | meaning |
|---|---|---|
| `PORT` | `8000` | port inside the container (set automatically by Render and similar hosts) |
| `CROPDOC_RATE_LIMIT_PER_MINUTE` | `30` | photo scans and contributions per IP per minute |
| `CROPDOC_LIVE_RATE_LIMIT_PER_MINUTE` | `240` | live-camera frames per IP per minute (the app sends at most about 2 per second) |
| `CROPDOC_MAX_UPLOAD_MB` | `5` | largest accepted photo |
| `CROPDOC_CORS_ORIGINS` | localhost dev server | only needed if the web app is served from a different domain |

## Privacy (read before sharing a link)
- **Live Scan frames are never stored.** Only "Save & full report" and the photo scanner (with "Save" ticked)
  store a scan: an EXIF-free photo, its heatmap and the result. No GPS, no names, no accounts.
- **One deployment = one shared history.** Everyone using the same address sees the same My Scoutings list and
  dashboard. That is fine for one farmer, a family, or an extension team. For a public link, tell users not to
  save photos they consider private, or deploy a separate copy per group.
- **Free hosts may wipe saved scans** when the service restarts or redeploys (their disks are temporary unless
  you add a paid persistent disk). The app itself keeps working.

## Same limits as on your computer
The deployed model is the same quick model trained on lab photos: it is accurate on PlantVillage-style photos and
much weaker on real field photos (see the README's lab → field results). The app says "not sure" or "unsupported"
when the photo does not look like its training data. It covers 38 classes from 14 crops. General guidance only,
not a diagnosis.
