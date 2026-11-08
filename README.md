# Libtex Library Manager

A small, offline library management app built with Python and Tkinter. Libtex runs as a desktop window and stores its records locally in SQLite.

## Features

- Add and edit books, including summaries and local cover images
- Create and search member records
- Check books out and record returns
- Search the catalog and filter by availability
- See book covers, with generated covers for books that do not have an image
- Start with an empty library; no demo records are added
- Keep working without an internet connection

## Requirements

- Python 3.8 or newer
- Tkinter, usually included with Python on Windows

Libtex uses only Python's standard library. It does not need a web server, JavaScript, or third-party packages.

## Run

Open a terminal in the project folder and run:

```powershell
python app.py
```

The Libtex desktop window will open. Use **Add a book** or **Add a member** to get started.

## Book covers

Choose a local PNG, GIF, PPM, or PGM image when adding or editing a book. Libtex copies the image into its own data folder, so the cover stays available if the original image is moved. Books without a selected cover display a generated typographic cover.

Summaries are entered and edited in the book form. Libtex does not fetch online book information, so the app works without internet access.

## Data location

The SQLite database and copied cover images are saved under:

```text
%LOCALAPPDATA%\Libtex\
```

The project folder only needs `app.py` to run the application.
