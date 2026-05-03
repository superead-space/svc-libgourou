# svc-libgourou

Dockerized version of libgourou with an HTTP front-end. libgourou is a free implementation of Adobe's ADEPT protocol — used to manage DRM in loaned ePub/PDF files.

This image exposes the `acsmdownloader` + `adept_remove` pipeline over HTTP so other services on the same Docker network can convert ACSM → EPUB/PDF without `docker exec` shell-outs. Files are exchanged over a bind-mounted directory; no upload is involved.

## HTTP API

Default port: `3000`. No authentication — intended for internal Docker networks only.

### Endpoints

- `GET /health` → `{ "ok": true, "version": "..." }`
- `POST /dedrm` → run `acsmdownloader` then `adept_remove`

All paths in the request are **relative to `DATA_DIR`** (default `/home/libgourou/files`). Path traversal is rejected.

```http
POST /dedrm
Content-Type: application/json

{
  "acsm_file":   "admin/abc.acsm",
  "drm_file":    "admin/abc.drm",
  "output_dir":  "admin",
  "output_file": "abc.epub"
}
```

Success (`200`):
```json
{ "ok": true, "output_path": "admin/abc.epub", "duration_ms": 3421 }
```

Failure (`400` invalid path, `502` libgourou subprocess error, `504` timeout):
```json
{ "ok": false, "stage": "acsmdownloader", "exit_code": 1, "stderr": "..." }
```

The intermediate `.drm` file is **not deleted** on success.

### Environment variables

| Var | Default | Description |
|---|---|---|
| `DATA_DIR` | `/home/libgourou/files` | bind-mounted shared directory |
| `ADEPT_DIR` | `/home/libgourou/.adept` | Adobe activation files |
| `REQUEST_TIMEOUT` | `180` | per-stage subprocess timeout (s) |
| `MAX_CONCURRENT` | `1` | concurrent dedrm jobs (semaphore) |
| `LOG_LEVEL` | `info` | `debug` / `info` / `warning` / `error` |

### Build & run

```bash
docker build -t svc-libgourou .

docker network create superead_internal   # if not already present

docker run -d \
  --name svc-libgourou \
  --network superead_internal \
  -p 127.0.0.1:3000:3000 \
  -v /home/forge/api.superead.com/storage/app/gardner-book/acsm:/home/libgourou/files \
  -v /home/forge/api.superead.com/storage/app/keys/adobe:/home/libgourou/.adept \
  --restart unless-stopped \
  svc-libgourou
```

Other containers on `superead_internal` reach the API at `http://svc-libgourou:3000`.

Swagger UI is served at `/docs`.

### Activating an Adobe ID

Device activation is a one-time, interactive step. Run a one-shot container that overrides the entrypoint:

```bash
docker run --rm -it \
  -v /home/forge/api.superead.com/storage/app/keys/adobe:/home/libgourou/.adept \
  --entrypoint /bin/bash \
  svc-libgourou \
  -c "adept_activate --random-serial -u <AdobeID> -O /home/libgourou/.adept"
```

---

## Legacy CLI (interactive / one-shot)

The original CLI scripts (`scripts/entrypoint.sh`, `scripts/dedrm.sh`) still ship inside the image at `/home/libgourou/scripts/` for ad-hoc use. Override the entrypoint to invoke them.

## libgourou

libgourou requires an Adobe ID but runs on Linux platforms (no WINE-based workaround required).

https://indefero.soutade.fr/p/libgourou/

### utils

This container compiles the reference implementation utilities for libgourou (master branch) and places them in `/usr/local/bin` for easy access. 

- `acsmdownloader` for downloading ePub/PDF files from Adobe's CDN
- `adept_activate` for activating user device via Adobe ID
- `adept_loan_mgt` for managing ADEPT loan library
- `adept_remove` for removing ADEPT DRM from an ADEPT-protected ePub/PDF

## Usage (legacy CLI)

### Interactive Terminal

To manually run libgourou utils, run the container interactively and overide the docker entrypoint:
```bash
> docker run \
    -v {$PATH_TO_ADOBE_CREDS}:/home/libgourou/.adept \
    -v $(pwd):/home/libgourou/files \
    -it --entrypoint /bin/bash \
    svc-libgourou
```

#### Commands

Use the bash shell to run the libgourou utility scripts. See the `libgourou` [README](https://indefero.soutade.fr/p/libgourou/source/tree/master/README.md) and/or the included manpages for additional usage.

To activate a new device with a AdobeID :
```
adept_activate -u <AdobeID USERNAME> [--output-dir output_directory]
```
By default, configuration files will be saved in `/home/libgourou/.adept`. Users should save contents to a mounted volume for reuse at a later date.

To download an ePub/PDF :
```
acsmdownloader <ACSM_FILE>
```
To export your private key (for use with Calibre, for example) :
```
acsmdownloader --export-private-key [-o adobekey_1.der]
```
To remove ADEPT DRM :
```
adept_remove <encrypted_file>
```
To list loaned books :
```
adept_loan_mgt [-l]
```
To return a loaned book :
```
adept_loan_mgt -r <id>
```

### Bash Script

A "de-DRM" bash script is provided (`./scripts/dedrm.sh`) to simplify running and using the docker-libgourou image.

```bash
> chmod +x scripts/dedrm.sh
> cp scripts/dedrm.sh ~/.local/bin/dedrm
```

To launch an interactive terminal with access to the libgourou utils:
```bash
> dedrm
!!!    WARNING: no ADEPT keys detected (argument $2, or "$HOME_DIR/.config/adept").
!!!    Launching interactive terminal for credentials creation (device activation). Run this:

 > adept_activate --random-serial \
       --username {USERNAME} \
       --password {PASSWORD} \
       --output-dir files/adept

!!!     (*) use --anonymous in place of --username, --password if you do not have an ADE account.
!!!     (*) credentials will be saved in the following path: "$(pwd)/adept"

!!!    WARNING: no ACSM file detected (argument $1).
!!!    Launching interactive terminal for manual loan management. Example commands below:

 > acsmdownloader \
       --adept-directory .adept \
       --output-file encrypted_file.drm \
       "files/{ACSM_FILE}"
 > adept_remove \
       --adept-directory .adept \
       --output-dir files \
       --output-file "{OUTPUT_FILE}" \
       encrypted_file.drm

Mounted Volumes
   (current path e.g. $pwd) --> /home/libgourou/files/

root@..:/home/libgourou# 
```

If you already have ADEPT keys saved (i.e. in `.adept` or `~/.config/adept`), append the encrypted ACSM file path in order to automatically generate a DRM-removed PDF/ePub file (this simply replicates the command at the top of this section):
```bash
> dedrm {ACSM_FILE}
```

To generate a DRM-free PDF/ePub file using credentials in a specific path:
```bash
> dedrm {ACSM_FILE} {CREDENTIALS_PATH}
```