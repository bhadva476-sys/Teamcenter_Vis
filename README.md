# JT Studio

JT Studio is a local Windows application for previewing JT models in a browser,
converting them to glTF/GLB, and optionally opening the original JT file in
Siemens Teamcenter Visualization.

## Features

- Convert JT files to GLB for interactive browser preview.
- Download the original JT file from the browser.
- Open a selected JT model in Teamcenter Visualization.
- Convert and download a `.glb` or `.gltf` file through the API.
- Inspect JT model data and check whether the conversion engine is available.
- Cache preview conversions so the same file does not need to be converted again.
- Register original JT files and their metadata in the MySQL `PLM.jtweb_client` table.
- Choose a thumbnail image for JT files with preview geometry; files without
  preview geometry can still be uploaded without a thumbnail.

> **Note:** Conversion requires the Aspose.3D Python package to load successfully.
> The browser's 3D viewer is loaded from Google's CDN, so an internet connection
> is needed to load that viewer script. Teamcenter Visualization integration
> requires it to be installed and the server to run in the logged-in Windows
> desktop session.

## Requirements

- Windows
- Python 3.10 or newer recommended
- Siemens Teamcenter Visualization installed for the optional open-file feature
- Internet connection to load the browser 3D viewer

## Setup

Open PowerShell at the repository root and create a virtual environment:

```powershell
py -m venv venv
```

Install the Python dependencies:

```powershell
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt
```

The dependencies include Flask, Waitress, Aspose.3D, pywinauto, and
mysql-connector-python. Aspose.3D must be importable for conversion and preview;
MySQL must be configured for the **Upload to server** feature.

## MySQL configuration

Create the `PLM` database in MySQL. On the first server-side JT upload, the app
creates `jtweb_client` if it does not exist. It inspects an existing table and
adds only missing required columns; it does not drop or rewrite existing data.
If an existing primary-key layout is incompatible, registration stops and
reports an error rather than changing that key automatically.

Set the connection details in the environment before starting the server. Do
not put the database password in source code:

```powershell
$env:DB_HOST = "localhost"
$env:DB_PORT = "3306"
$env:DB_USER = "your_mysql_username"
$env:DB_PASSWORD = "your_mysql_password"
$env:DB_NAME = "PLM"
```

The upload route stores file bytes in `Backend/ServerUploads/` by default and
stores the filename, `.jt` type, server path, byte size, timestamps, and owner
in `PLM.jtweb_client`. When a preview is available, a PNG, JPG, or WebP thumbnail
is saved under `Backend/ServerThumbnails/<APP_ENV>/`, and its path is recorded in
`Thumbnail_Location`. Thumbnails appear in both the All Files and My Files lists.
Files are stored on disk, not as binary data in MySQL. Since the
application currently has no authentication, `attribute_owner` is set to
`local-user`; this is a placeholder, not an authenticated identity.

## Development and production environments

Environment-specific settings are loaded from `config/.env.dev` by default.
Set `APP_ENV=prod` in the process environment to load `config/.env.prod`.
Process environment variables take precedence over values in either file.
Both files are ignored by Git; do not commit database credentials. Configure
the production database credentials in the production server's environment
before starting the application in production mode.

Each environment has a separate default JT file directory:

```text
Backend/ServerUploads/
├── dev/
└── prod/
```

Thumbnails are stored in the matching `Backend/ServerThumbnails/dev/` or
`Backend/ServerThumbnails/prod/` directory. `JT_SERVER_UPLOADS_DIR` and
`JT_SERVER_THUMBNAILS_DIR` may override these paths. Relative paths are resolved
from the repository root, not from the current working directory. Empty
`JT_UPLOADS_DIR` or `JT_CONVERTED_DIR` values retain the existing application
defaults. `JT_WEBCLIENT_TABLE` selects the metadata table; it must be a simple
SQL identifier. `MAX_THUMBNAIL_SIZE` defaults to 5 MiB.

## Run the application

From the repository root, either double-click `start_server.bat` or run:

```powershell
venv\Scripts\python.exe Backend\app\start.py
```

When startup succeeds, open [http://127.0.0.1:5000/](http://127.0.0.1:5000/).
Use **Ctrl+C** in the terminal to stop the server.

To run the entry point from the `Backend` directory instead:

```powershell
..\venv\Scripts\python.exe app\start.py
```

Opening a JT from the Upload File workspace always uses Teamcenter
Visualization's **File > Open** workflow so it opens as a separate document.
Opening a saved JT from **My Files** continues to use **Insert** (Ctrl+Shift+I)
when a model is already open, adding its geometry to the current model. Run
the server as your normal logged-in Windows user so it can control the desktop
application.

## Use the web application

1. Start the server and open the local URL.
2. Use the sidebar's **All Files** and **My Files** sections to browse database
   records. Since authentication is not enabled, **My Files** currently means
   files owned by the placeholder `local-user`.
3. Choose **Upload File** to open the JT upload and preview workspace.
4. Choose a `.jt` file. The app uploads it and converts it to GLB for preview.
5. Use the 3D preview to inspect the converted model.
6. Select **Upload to server** to save the original JT file and register its
   metadata in MySQL. Success is reported separately from preview conversion.
7. In **My Files**, select **Teamcenter Visualization** in the row action
   column to open a saved server upload.
8. Select **Download original .jt** to save the source file.
9. Select **Open in Teamcenter Visualization** in the upload workspace to open
   the currently selected source model.

The server accepts JT uploads up to 200 MB. Material colors in the preview
depend on the data Aspose.3D can read from the source JT file.

## HTTP API

All upload endpoints expect `multipart/form-data` with a file field named
`file`. Uploads must have a `.jt` filename.

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/` | Serves the web application. |
| `GET` | `/health` | Reports converter version and Aspose.3D availability. |
| `POST` | `/upload` | Converts a JT file to a cached GLB and returns its model URL. |
| `POST` | `/api/jt-files/upload` | Stores the original JT under `ServerUploads` and registers metadata in MySQL. |
| `GET` | `/list` | Returns up to 100 most recent registered JT file metadata records, including server file paths. |
| `GET` | `/models/<name>` | Serves a generated GLB model. Add `?download=1` to download it. |
| `POST` | `/convert` | Converts and downloads a `.glb` or `.gltf` file. Set `format` in the form or query string; defaults to `glb`. If conversion produces multiple files, they are returned in a ZIP archive. |
| `POST` | `/probe` | Returns JT inspection/probe information as plain text. |
| `POST` | `/inspect` | Returns material information read by Aspose.3D as JSON. |
| `POST` | `/add-to-teamcenter-visualization` | Opens the uploaded JT model, or inserts it into the current model if one is already open. |
| `POST` | `/api/jt-files/<id>/open-in-teamcenter-visualization` | Opens a registered server upload, or inserts it into the current model if one is already open. |

Example conversion request using curl:

```powershell
curl.exe -F "file=@C:\path\to\model.jt" "http://127.0.0.1:5000/convert?format=glb" --output model.glb
```

## Configuration

Configuration is read from environment variables when the app starts:

| Variable | Default | Description |
| --- | --- | --- |
| `HOST` | `127.0.0.1` | Address Waitress listens on. |
| `PORT` | `5000` | Port Waitress listens on. |
| `APP_ENV` | `dev` | Selects `config/.env.dev` or `config/.env.prod`. |
| `JT_UPLOADS_DIR` | `Backend/app/uploads` | Directory for temporary uploads opened in Teamcenter Visualization. |
| `JT_CONVERTED_DIR` | `Backend/app/converted` | Directory for cached GLB models. |
| `JT_SERVER_UPLOADS_DIR` | `Backend/ServerUploads/<APP_ENV>` | Directory for original JT files registered in MySQL. |
| `JT_SERVER_THUMBNAILS_DIR` | `Backend/ServerThumbnails/<APP_ENV>` | Directory for uploaded thumbnail images. |
| `DB_HOST` | `localhost` | MySQL server hostname. |
| `DB_PORT` | `3306` | MySQL server port. |
| `DB_USER` | unset | MySQL username. |
| `DB_PASSWORD` | unset | MySQL password. |
| `DB_NAME` | `PLM` | MySQL database name. |
| `JT_WEBCLIENT_TABLE` | `jtweb_client` | MySQL table used for JT upload metadata. |
| `MAX_CONTENT_LENGTH` | `209715200` | Maximum request size in bytes (200 MiB by default). |
| `MAX_THUMBNAIL_SIZE` | `5242880` | Maximum thumbnail size in bytes (5 MiB by default). |
| `CORS_ORIGIN` | unset | Optional value for the `Access-Control-Allow-Origin` response header. |

Example:

```powershell
$env:PORT = "5050"
$env:APP_ENV = "prod"
# Set DB_HOST, DB_USER, DB_PASSWORD, and DB_NAME for the production database.
venv\Scripts\python.exe Backend\app\start.py
```

Uploads and converted models are runtime data and should not be committed to
source control. Registered JT uploads are stored separately in
`Backend/ServerUploads/`.

## Project structure

```text
.
├── config/
│   ├── .env.dev             # Local development settings (ignored by Git)
│   └── .env.prod            # Production settings (ignored by Git)
├── Backend/
│   ├── teamcenter_visualization_watcher.py # Optional Teamcenter dialog watcher
│   ├── ServerUploads/
│   │   ├── dev/
│   │   └── prod/
│   └── app/
│       ├── __init__.py       # Flask application factory and Blueprint setup
│       ├── config.py         # Server settings and runtime directories
│       ├── start.py          # Waitress entry point
│       ├── routes/           # Web, conversion, and Teamcenter Visualization endpoints
│       ├── services/         # Conversion, JT inspection, and Teamcenter Visualization automation
│       ├── utils/            # Upload validation and error handlers
│       ├── static/
│       │   ├── index.html    # Small frontend shell
│       │   ├── css/          # Variables, base, layout, components, pages, responsive
│       │   ├── pages/        # Upload and file-list HTML templates
│       │   └── js/           # App entry, navigation, page modules, shared utilities
│       └── tests/            # Backend route tests
├── requirements.txt
└── start_server.bat
```

## Run tests

From the `Backend` directory:

```powershell
..\venv\Scripts\python.exe -m unittest discover -s app\tests
```

## Local use and security

The default server address is `127.0.0.1`, which keeps it accessible only from
the local machine. The API has no authentication and includes a route that
controls a desktop application; do not expose it to an untrusted network.
