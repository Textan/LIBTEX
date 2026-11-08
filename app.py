import datetime
import os
import shutil
import sqlite3
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from uuid import uuid4

APP_FOLDER = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Libtex"
APP_FOLDER.mkdir(parents=True, exist_ok=True)
COVER_FOLDER = APP_FOLDER / "covers"
COVER_FOLDER.mkdir(parents=True, exist_ok=True)
DATABASE = APP_FOLDER / "library.db"
GREEN = "#527866"
BACKGROUND = "#f5f5f2"
WHITE = "#ffffff"
INK = "#292b27"
MUTED = "#85877f"
LINE = "#e5e7e1"


def connect_database():
    database = sqlite3.connect(DATABASE)
    database.row_factory = sqlite3.Row
    database.execute("PRAGMA foreign_keys = ON")
    return database


def create_database():
    with connect_database() as database:
        database.executescript("""
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                author TEXT NOT NULL DEFAULT '',
                isbn TEXT NOT NULL DEFAULT '',
                summary TEXT NOT NULL DEFAULT '',
                cover TEXT NOT NULL DEFAULT '',
                copies INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL DEFAULT '',
                joined TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS loans (
                id INTEGER PRIMARY KEY,
                book_id INTEGER NOT NULL REFERENCES books(id),
                member_id INTEGER NOT NULL REFERENCES members(id),
                borrowed TEXT NOT NULL,
                returned TEXT
            );
        """)


class LibraryApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Libtex Library")
        self.geometry("1180x760")
        self.minsize(850, 580)
        self.configure(bg=BACKGROUND)
        self.page = "books"
        self.book_filter = "All books"
        self.book_query = tk.StringVar()
        self.member_query = tk.StringVar()
        self.cover_images = []
        self.color_animations = {}
        self.book_columns = 0
        self.content = None
        self._setup_style()
        self._build_window()
        self.show_page("books")
        self.bind("<Control-f>", lambda event: self.search_box.focus_set())

    def _setup_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview", background=WHITE, fieldbackground=WHITE, foreground=INK, rowheight=35, borderwidth=0, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background=WHITE, foreground=MUTED, relief="flat", font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", "#e7efe9")], foreground=[("selected", INK)])
        style.configure("Vertical.TScrollbar", background=BACKGROUND, troughcolor=BACKGROUND, bordercolor=BACKGROUND, arrowcolor=MUTED)

    def _build_window(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        sidebar = tk.Frame(self, width=205, bg="#fbfbf9", highlightbackground=LINE, highlightthickness=1)
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_propagate(False)
        tk.Label(sidebar, text="▤  Libtex", bg="#fbfbf9", fg=GREEN, font=("Segoe UI", 17, "bold")).pack(anchor="w", padx=21, pady=(26, 36))
        tk.Label(sidebar, text="LIBRARY", bg="#fbfbf9", fg="#999b93", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=22, pady=(0, 9))
        self.nav_buttons = {}
        for key, label in (("books", "▤   Book catalog"), ("members", "♙   Members"), ("loans", "↗   Borrowing")):
            button = tk.Button(sidebar, text=label, anchor="w", padx=13, pady=9, bd=0, relief="flat", cursor="hand2", font=("Segoe UI", 10), command=lambda page=key: self.show_page(page))
            button.pack(fill="x", padx=11, pady=2)
            button.bind("<Enter>", lambda event, item=button: self.animate_background(item, "#f0f1ed"))
            button.bind("<Leave>", lambda event, item=button, name=key: self.animate_background(item, "#e9efeb" if self.page == name else "#fbfbf9"))
            self.nav_buttons[key] = button
        tk.Label(sidebar, text="Your library, in one place", bg="#fbfbf9", fg=MUTED, font=("Segoe UI", 9)).pack(side="bottom", anchor="w", padx=20, pady=19)
        self.main = tk.Frame(self, bg=BACKGROUND)
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.columnconfigure(0, weight=1)
        self.main.rowconfigure(2, weight=1)
        self.header = tk.Frame(self.main, bg=BACKGROUND)
        self.header.grid(row=0, column=0, sticky="ew", padx=40, pady=(29, 8))
        self.header.columnconfigure(0, weight=1)
        self.crumb = tk.Label(self.header, text="LIBRARY  /  BOOK CATALOG", bg=BACKGROUND, fg=MUTED, font=("Segoe UI", 9, "bold"))
        self.crumb.grid(row=0, column=0, sticky="w")
        self.heading = tk.Label(self.header, text="Book catalog", bg=BACKGROUND, fg=INK, font=("Segoe UI", 26, "bold"))
        self.heading.grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.subtitle = tk.Label(self.header, text="Your books, ready to be organized.", bg=BACKGROUND, fg=MUTED, font=("Segoe UI", 10))
        self.subtitle.grid(row=2, column=0, sticky="w", pady=(1, 0))
        self.add_button = tk.Button(self.header, text="＋  Add a book", bg=GREEN, fg=WHITE, activebackground="#416551", activeforeground=WHITE, relief="flat", bd=0, padx=14, pady=9, cursor="hand2", font=("Segoe UI", 10, "bold"), command=self.add_book)
        self.add_button.grid(row=1, column=1, rowspan=2, sticky="e", padx=(12, 0))
        self.stats = tk.Frame(self.main, bg=BACKGROUND)
        self.stats.grid(row=1, column=0, sticky="ew", padx=40, pady=(19, 18))
        for column in range(3):
            self.stats.columnconfigure(column, weight=1, uniform="stats")
        self.stat_values = []
        for column, label in enumerate(("Books in library", "Active members", "Books on loan")):
            card = tk.Frame(self.stats, bg=WHITE, highlightbackground=LINE, highlightthickness=1, padx=15, pady=11)
            card.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 8, 0))
            tk.Label(card, text=label, bg=WHITE, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w")
            value = tk.Label(card, text="0", bg=WHITE, fg=INK, font=("Segoe UI", 20, "bold"))
            value.pack(anchor="w", pady=(1, 0))
            self.stat_values.append(value)
        self.body = tk.Frame(self.main, bg=BACKGROUND)
        self.body.grid(row=2, column=0, sticky="nsew", padx=40, pady=(0, 28))
        self.body.columnconfigure(0, weight=1)
        self.body.rowconfigure(0, weight=1)
        self.bind_all("<MouseWheel>", self.scroll_books)

    def animate_background(self, widget, target):
        previous = self.color_animations.pop(widget, None)
        if previous:
            self.after_cancel(previous)
        start = widget.cget("bg")
        try:
            start_rgb = tuple(int(start[index:index + 2], 16) for index in (1, 3, 5))
            end_rgb = tuple(int(target[index:index + 2], 16) for index in (1, 3, 5))
        except ValueError:
            widget.config(bg=target)
            return

        def step(number=0):
            if not widget.winfo_exists():
                return
            amount = min(number / 6, 1)
            color = "#" + "".join(f"{round(start_rgb[i] + (end_rgb[i] - start_rgb[i]) * amount):02x}" for i in range(3))
            widget.config(bg=color)
            if number < 6:
                self.color_animations[widget] = self.after(16, lambda: step(number + 1))
            else:
                self.color_animations.pop(widget, None)

        step()

    def refresh_stats(self):
        with connect_database() as database:
            copies = database.execute("SELECT COALESCE(SUM(copies),0) FROM books").fetchone()[0]
            members = database.execute("SELECT COUNT(*) FROM members").fetchone()[0]
            loans = database.execute("SELECT COUNT(*) FROM loans WHERE returned IS NULL").fetchone()[0]
        for label, value in zip(self.stat_values, (copies, members, loans)):
            label.config(text=str(value))

    def show_page(self, page):
        self.page = page
        pages = {
            "books": ("Book catalog", "Your books, ready to be organized.", "BOOK CATALOG"),
            "members": ("Members", "Manage the people who use your library.", "MEMBERS"),
            "loans": ("Borrowing", "Track checkouts and returns.", "BORROWING")
        }
        title, subtitle, crumb = pages[page]
        self.heading.config(text=title)
        self.subtitle.config(text=subtitle)
        self.crumb.config(text="LIBRARY  /  " + crumb)
        self.add_button.config(text="＋  Add a member" if page == "members" else "＋  Add a book")
        self.add_button.grid() if page != "loans" else self.add_button.grid_remove()
        for key, button in self.nav_buttons.items():
            button.config(bg="#e9efeb" if key == page else "#fbfbf9", fg=GREEN if key == page else "#62645e")
        for child in self.body.winfo_children():
            child.destroy()
        self.refresh_stats()
        if page == "books":
            self.draw_books()
        elif page == "members":
            self.draw_members()
        else:
            self.draw_loans()

    def draw_books(self):
        toolbar = tk.Frame(self.body, bg=BACKGROUND)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        toolbar.columnconfigure(0, weight=1)
        search = tk.Entry(toolbar, textvariable=self.book_query, relief="flat", bd=0, bg=WHITE, fg=INK, insertbackground=INK, font=("Segoe UI", 10))
        search.grid(row=0, column=0, sticky="ew", ipady=9, padx=(0, 10))
        search.insert(0, "")
        self.search_box = search
        for index, text in enumerate(("All books", "Available", "On loan"), 1):
            button = tk.Button(toolbar, text=text, relief="flat", bd=0, cursor="hand2", padx=10, pady=8, font=("Segoe UI", 9, "bold" if text == self.book_filter else "normal"), bg="#e9efeb" if text == self.book_filter else BACKGROUND, fg=GREEN if text == self.book_filter else MUTED, command=lambda value=text: self.set_filter(value))
            button.grid(row=0, column=index, padx=2)
        search.bind("<KeyRelease>", lambda event: self.refresh_book_cards())
        self.book_canvas = tk.Canvas(self.body, bg=BACKGROUND, highlightthickness=0)
        self.book_canvas.grid(row=1, column=0, sticky="nsew")
        self.body.rowconfigure(1, weight=1)
        scroll = ttk.Scrollbar(self.body, orient="vertical", command=self.book_canvas.yview)
        scroll.grid(row=1, column=1, sticky="ns")
        self.book_canvas.configure(yscrollcommand=scroll.set)
        self.book_frame = tk.Frame(self.book_canvas, bg=BACKGROUND)
        self.book_window = self.book_canvas.create_window((0, 0), window=self.book_frame, anchor="nw")
        self.book_frame.bind("<Configure>", lambda event: self.book_canvas.configure(scrollregion=self.book_canvas.bbox("all")))
        self.book_canvas.bind("<Configure>", self.resize_book_grid)
        self.refresh_book_cards()

    def set_filter(self, value):
        self.book_filter = value
        self.show_page("books")

    def resize_book_grid(self, event):
        self.book_canvas.itemconfigure(self.book_window, width=event.width)
        columns = max(1, min(4, event.width // 285))
        if columns != self.book_columns:
            self.book_columns = columns
            self.refresh_book_cards()

    def scroll_books(self, event):
        if self.page == "books" and self.book_canvas.winfo_exists():
            self.book_canvas.yview_scroll(int(-event.delta / 120), "units")

    def refresh_book_cards(self):
        if not hasattr(self, "book_frame") or not self.book_frame.winfo_exists():
            return
        for child in self.book_frame.winfo_children():
            child.destroy()
        self.cover_images.clear()
        query = self.book_query.get().strip().lower()
        with connect_database() as database:
            books = database.execute("""
                SELECT books.*,
                copies - (SELECT COUNT(*) FROM loans WHERE loans.book_id=books.id AND returned IS NULL) AS available
                FROM books ORDER BY title
            """).fetchall()
        books = [book for book in books if query in (book["title"] + " " + book["author"] + " " + book["isbn"]).lower()]
        if self.book_filter == "Available":
            books = [book for book in books if book["available"] > 0]
        elif self.book_filter == "On loan":
            books = [book for book in books if book["available"] < book["copies"]]
        if not books:
            message = "No books yet. Add one to start your catalog." if not query else "No books match your search."
            tk.Label(self.book_frame, text=message, bg=BACKGROUND, fg=MUTED, font=("Segoe UI", 11)).grid(row=0, column=0, sticky="w", padx=10, pady=35)
            return
        columns = max(1, self.book_columns)
        for index, book in enumerate(books):
            self.draw_book_card(book, index // columns, index % columns)

    def draw_book_card(self, book, row, column):
        card = tk.Frame(self.book_frame, bg=WHITE, highlightbackground=LINE, highlightthickness=1, padx=12, pady=12)
        card.grid(row=row, column=column, sticky="nsew", padx=(0, 10), pady=(0, 10))
        card.columnconfigure(1, weight=1)
        cover = self.make_cover(card, book)
        cover.grid(row=0, column=0, rowspan=5, sticky="nw", padx=(0, 12))
        tk.Label(card, text=book["title"], bg=WHITE, fg=INK, font=("Segoe UI", 11, "bold"), wraplength=180, justify="left").grid(row=0, column=1, sticky="nw")
        tk.Label(card, text=book["author"] or "Author not listed", bg=WHITE, fg=MUTED, font=("Segoe UI", 9), wraplength=180).grid(row=1, column=1, sticky="nw", pady=(3, 0))
        summary = book["summary"] or "No summary saved. Edit details to add one."
        tk.Label(card, text=summary, bg=WHITE, fg="#686b64", font=("Segoe UI", 9), wraplength=180, justify="left", height=3, anchor="nw").grid(row=2, column=1, sticky="new", pady=(8, 2))
        tk.Label(card, text=f"{book['available']} of {book['copies']} available", bg=WHITE, fg=GREEN, font=("Segoe UI", 9)).grid(row=3, column=1, sticky="w", pady=(2, 4))
        actions = tk.Frame(card, bg=WHITE)
        actions.grid(row=4, column=1, sticky="w")
        tk.Button(actions, text="Check out", command=lambda item=book: self.checkout(item), bg="#e9efeb", fg=GREEN, relief="flat", bd=0, padx=8, pady=5, state="normal" if book["available"] else "disabled").pack(side="left")
        tk.Button(actions, text="Edit", command=lambda item=book: self.edit_book(item), bg=WHITE, fg=MUTED, relief="flat", bd=0, padx=8, pady=5).pack(side="left")
        card.bind("<Enter>", lambda event, item=card: item.config(highlightbackground="#b8c8bd"))
        card.bind("<Leave>", lambda event, item=card: item.config(highlightbackground=LINE))

    def make_cover(self, parent, book):
        cover = tk.Frame(parent, width=78, height=112, bg="#61766a", highlightthickness=0)
        cover.pack_propagate(False)
        path = Path(book["cover"]) if book["cover"] else None
        if path and path.is_file():
            try:
                image = tk.PhotoImage(file=str(path))
                scale = max(1, (image.width() + 77) // 78, (image.height() + 111) // 112)
                if scale > 1:
                    image = image.subsample(scale, scale)
                label = tk.Label(cover, image=image, bg=WHITE)
                label.image = image
                label.pack(expand=True)
                self.cover_images.append(image)
                return cover
            except tk.TclError:
                pass
        palette = ("#61766a", "#8b6c5c", "#67758b", "#778260", "#8a6570", "#557585")
        cover.config(bg=palette[book["id"] % len(palette)])
        initials = "".join(word[0] for word in book["title"].split()[:2]).upper()
        tk.Label(cover, text=initials, bg=cover["bg"], fg=WHITE, font=("Georgia", 20, "bold")).pack(expand=True, pady=(12, 0))
        tk.Label(cover, text=book["title"][:35], bg=cover["bg"], fg=WHITE, font=("Segoe UI", 7), wraplength=66, justify="center").pack(pady=(0, 9))
        return cover

    def choose_cover(self, variable):
        filename = filedialog.askopenfilename(title="Choose a book cover", filetypes=[("Tkinter images", "*.png *.gif *.ppm *.pgm"), ("All files", "*.*")])
        if not filename:
            return
        source = Path(filename)
        destination = COVER_FOLDER / (uuid4().hex + source.suffix.lower())
        try:
            shutil.copy2(source, destination)
            variable.set(str(destination))
        except OSError as error:
            messagebox.showerror("Cover could not be saved", str(error), parent=self)

    def book_form(self, book=None):
        editing = book is not None
        window = tk.Toplevel(self)
        window.title("Edit book" if editing else "Add a book")
        window.configure(bg=WHITE)
        window.resizable(False, False)
        window.transient(self)
        window.grab_set()
        panel = tk.Frame(window, bg=WHITE, padx=22, pady=19)
        panel.pack(fill="both", expand=True)
        tk.Label(panel, text="Edit book details" if editing else "Add a book", bg=WHITE, fg=INK, font=("Segoe UI", 17, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 14))
        entries = {}
        fields = (("Title", "title"), ("Author", "author"), ("ISBN", "isbn"))
        for row, (label, key) in enumerate(fields, 1):
            tk.Label(panel, text=label, bg=WHITE, fg=MUTED, font=("Segoe UI", 9)).grid(row=row, column=0, sticky="w", pady=5)
            field = tk.Entry(panel, width=43, relief="solid", bd=1, font=("Segoe UI", 10))
            field.grid(row=row, column=1, sticky="ew", padx=(12, 0), pady=5, ipady=5)
            field.insert(0, book[key] or "" if editing else "")
            entries[key] = field
        copies_row = 4
        copies_var = tk.StringVar(value=str(book["copies"]) if editing else "1")
        if not editing:
            tk.Label(panel, text="Copies", bg=WHITE, fg=MUTED, font=("Segoe UI", 9)).grid(row=copies_row, column=0, sticky="w", pady=5)
            copies_entry = tk.Entry(panel, textvariable=copies_var, width=8, relief="solid", bd=1, font=("Segoe UI", 10))
            copies_entry.grid(row=copies_row, column=1, sticky="w", padx=(12, 0), pady=5, ipady=5)
        else:
            copies_entry = None
        summary_row = 5
        tk.Label(panel, text="Summary", bg=WHITE, fg=MUTED, font=("Segoe UI", 9)).grid(row=summary_row, column=0, sticky="nw", pady=6)
        summary = tk.Text(panel, width=43, height=5, wrap="word", relief="solid", bd=1, font=("Segoe UI", 10))
        summary.grid(row=summary_row, column=1, sticky="ew", padx=(12, 0), pady=5)
        if editing:
            summary.insert("1.0", book["summary"] or "")
        cover_var = tk.StringVar(value=(book["cover"] if editing else ""))
        cover_row = summary_row + 1
        tk.Label(panel, text="Cover", bg=WHITE, fg=MUTED, font=("Segoe UI", 9)).grid(row=cover_row, column=0, sticky="w", pady=5)
        cover_line = tk.Frame(panel, bg=WHITE)
        cover_line.grid(row=cover_row, column=1, sticky="ew", padx=(12, 0), pady=5)
        tk.Entry(cover_line, textvariable=cover_var, width=31, relief="solid", bd=1, font=("Segoe UI", 9), state="readonly").pack(side="left", ipady=5)
        tk.Button(cover_line, text="Browse", command=lambda: self.choose_cover(cover_var), bg="#e9efeb", fg=GREEN, relief="flat", bd=0, padx=10, pady=6).pack(side="left", padx=(7, 0))
        tk.Label(panel, text="Choose a PNG, GIF, PPM, or PGM image. Everything works offline.", bg=WHITE, fg=MUTED, font=("Segoe UI", 8)).grid(row=cover_row + 1, column=1, sticky="w", padx=(12, 0), pady=(0, 10))
        buttons = tk.Frame(panel, bg=WHITE)
        buttons.grid(row=cover_row + 2, column=0, columnspan=2, sticky="e", pady=(5, 0))
        tk.Button(buttons, text="Cancel", command=window.destroy, bg=WHITE, fg=MUTED, relief="flat", bd=0, padx=12, pady=8).pack(side="left", padx=5)

        def save():
            title = entries["title"].get().strip()
            if not title:
                messagebox.showwarning("Missing title", "Enter a book title.", parent=window)
                return
            try:
                values = (title, entries["author"].get().strip(), entries["isbn"].get().strip(), summary.get("1.0", "end-1c").strip(), cover_var.get())
                with connect_database() as database:
                    if editing:
                        database.execute("UPDATE books SET title=?,author=?,isbn=?,summary=?,cover=? WHERE id=?", (*values, book["id"]))
                    else:
                        copies = int(copies_var.get())
                        if copies < 1:
                            raise ValueError
                        database.execute("INSERT INTO books(title,author,isbn,summary,cover,copies) VALUES(?,?,?,?,?,?)", (*values, copies))
                window.destroy()
                self.show_page("books")
            except ValueError:
                messagebox.showwarning("Invalid copies", "Enter a whole number of copies, at least 1.", parent=window)
            except sqlite3.Error as error:
                messagebox.showerror("Book could not be saved", str(error), parent=window)

        tk.Button(buttons, text="Save book", command=save, bg=GREEN, fg=WHITE, activebackground="#416551", activeforeground=WHITE, relief="flat", bd=0, padx=14, pady=8).pack(side="left")
        window.bind("<Return>", lambda event: save())
        entries["title"].focus_set()
        window.wait_visibility()
        window.focus_set()

    def add_book(self):
        if self.page == "members":
            self.member_form()
        else:
            self.book_form()

    def edit_book(self, book):
        self.book_form(book)

    def member_form(self):
        window = tk.Toplevel(self)
        window.title("Add a member")
        window.configure(bg=WHITE)
        window.resizable(False, False)
        window.transient(self)
        window.grab_set()
        panel = tk.Frame(window, bg=WHITE, padx=22, pady=19)
        panel.pack(fill="both", expand=True)
        tk.Label(panel, text="Add a member", bg=WHITE, fg=INK, font=("Segoe UI", 17, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 13))
        entries = {}
        for row, (label, key) in enumerate((("Name", "name"), ("Email", "email")), 1):
            tk.Label(panel, text=label, bg=WHITE, fg=MUTED, font=("Segoe UI", 9)).grid(row=row, column=0, sticky="w", pady=6)
            field = tk.Entry(panel, width=38, relief="solid", bd=1, font=("Segoe UI", 10))
            field.grid(row=row, column=1, padx=(12, 0), pady=6, ipady=5)
            entries[key] = field
        actions = tk.Frame(panel, bg=WHITE)
        actions.grid(row=3, column=0, columnspan=2, sticky="e", pady=(12, 0))
        tk.Button(actions, text="Cancel", command=window.destroy, bg=WHITE, fg=MUTED, relief="flat", bd=0, padx=12, pady=8).pack(side="left", padx=5)

        def save():
            name = entries["name"].get().strip()
            if not name:
                messagebox.showwarning("Missing name", "Enter a member name.", parent=window)
                return
            with connect_database() as database:
                database.execute("INSERT INTO members(name,email,joined) VALUES(?,?,?)", (name, entries["email"].get().strip(), datetime.date.today().isoformat()))
            window.destroy()
            self.show_page("members")

        tk.Button(actions, text="Save member", command=save, bg=GREEN, fg=WHITE, relief="flat", bd=0, padx=14, pady=8).pack(side="left")
        entries["name"].focus_set()

    def draw_members(self):
        toolbar = tk.Frame(self.body, bg=BACKGROUND)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        toolbar.columnconfigure(0, weight=1)
        search = tk.Entry(toolbar, textvariable=self.member_query, relief="flat", bd=0, bg=WHITE, fg=INK, font=("Segoe UI", 10))
        search.grid(row=0, column=0, sticky="ew", ipady=9)
        self.member_tree = ttk.Treeview(self.body, columns=("name", "email", "joined", "loans"), show="headings")
        self.member_tree.grid(row=1, column=0, sticky="nsew")
        for key, title, width in (("name", "NAME", 230), ("email", "EMAIL", 250), ("joined", "JOINED", 130), ("loans", "BOOKS OUT", 110)):
            self.member_tree.heading(key, text=title)
            self.member_tree.column(key, width=width, anchor="w")
        self.body.rowconfigure(1, weight=1)
        search.bind("<KeyRelease>", lambda event: self.refresh_members())
        self.refresh_members()

    def refresh_members(self):
        if not hasattr(self, "member_tree") or not self.member_tree.winfo_exists():
            return
        for row in self.member_tree.get_children():
            self.member_tree.delete(row)
        query = self.member_query.get().strip().lower()
        with connect_database() as database:
            members = database.execute("""
                SELECT members.*, COUNT(CASE WHEN loans.returned IS NULL THEN 1 END) AS active_loans
                FROM members LEFT JOIN loans ON loans.member_id=members.id
                GROUP BY members.id ORDER BY members.name
            """).fetchall()
        for member in members:
            if query in (member["name"] + " " + member["email"]).lower():
                self.member_tree.insert("", "end", values=(member["name"], member["email"], member["joined"], member["active_loans"]))

    def draw_loans(self):
        toolbar = tk.Frame(self.body, bg=BACKGROUND)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self.return_button = tk.Button(toolbar, text="Return selected book", command=self.return_selected, bg="#e9efeb", fg=GREEN, relief="flat", bd=0, padx=12, pady=8, state="disabled")
        self.return_button.pack(side="left")
        self.loan_tree = ttk.Treeview(self.body, columns=("book", "member", "borrowed", "returned", "status"), show="headings")
        self.loan_tree.grid(row=1, column=0, sticky="nsew")
        for key, title, width in (("book", "BOOK", 240), ("member", "MEMBER", 190), ("borrowed", "CHECKED OUT", 130), ("returned", "RETURNED", 130), ("status", "STATUS", 110)):
            self.loan_tree.heading(key, text=title)
            self.loan_tree.column(key, width=width, anchor="w")
        self.body.rowconfigure(1, weight=1)
        self.loan_tree.bind("<<TreeviewSelect>>", self.update_return_button)
        self.refresh_loans()

    def refresh_loans(self):
        for row in self.loan_tree.get_children():
            self.loan_tree.delete(row)
        with connect_database() as database:
            loans = database.execute("""
                SELECT loans.*, books.title, members.name FROM loans
                JOIN books ON books.id=loans.book_id
                JOIN members ON members.id=loans.member_id ORDER BY loans.id DESC
            """).fetchall()
        for loan in loans:
            status = "Returned" if loan["returned"] else "On loan"
            self.loan_tree.insert("", "end", iid=str(loan["id"]), values=(loan["title"], loan["name"], loan["borrowed"], loan["returned"] or "—", status))

    def update_return_button(self, event=None):
        selected = self.loan_tree.selection()
        if not selected:
            self.return_button.config(state="disabled")
            return
        values = self.loan_tree.item(selected[0], "values")
        self.return_button.config(state="normal" if values[-1] == "On loan" else "disabled")

    def return_selected(self):
        selected = self.loan_tree.selection()
        if not selected:
            return
        with connect_database() as database:
            database.execute("UPDATE loans SET returned=? WHERE id=? AND returned IS NULL", (datetime.date.today().isoformat(), int(selected[0])))
        self.show_page("loans")

    def checkout(self, book):
        with connect_database() as database:
            members = database.execute("SELECT id,name FROM members ORDER BY name").fetchall()
        if not members:
            messagebox.showinfo("Add a member first", "Create a member record before checking out a book.", parent=self)
            return
        window = tk.Toplevel(self)
        window.title("Check out a book")
        window.configure(bg=WHITE)
        window.resizable(False, False)
        window.transient(self)
        window.grab_set()
        panel = tk.Frame(window, bg=WHITE, padx=22, pady=20)
        panel.pack(fill="both", expand=True)
        tk.Label(panel, text="Check out this book", bg=WHITE, fg=INK, font=("Segoe UI", 16, "bold")).pack(anchor="w")
        tk.Label(panel, text=book["title"], bg=WHITE, fg=MUTED, font=("Segoe UI", 10), wraplength=330).pack(anchor="w", pady=(4, 15))
        names = [member["name"] for member in members]
        member_choice = tk.StringVar(value=names[0])
        ttk.Combobox(panel, textvariable=member_choice, values=names, state="readonly", width=34).pack(fill="x", ipady=4)

        def save():
            member = next(item for item in members if item["name"] == member_choice.get())
            with connect_database() as database:
                available = database.execute("SELECT copies-(SELECT COUNT(*) FROM loans WHERE book_id=? AND returned IS NULL) FROM books WHERE id=?", (book["id"], book["id"])).fetchone()[0]
                if available < 1:
                    messagebox.showwarning("No copies available", "All copies are currently on loan.", parent=window)
                    return
                database.execute("INSERT INTO loans(book_id,member_id,borrowed) VALUES(?,?,?)", (book["id"], member["id"], datetime.date.today().isoformat()))
            window.destroy()
            self.show_page("books")

        actions = tk.Frame(panel, bg=WHITE)
        actions.pack(anchor="e", pady=(16, 0))
        tk.Button(actions, text="Cancel", command=window.destroy, bg=WHITE, fg=MUTED, relief="flat", bd=0, padx=10, pady=7).pack(side="left")
        tk.Button(actions, text="Check out", command=save, bg=GREEN, fg=WHITE, relief="flat", bd=0, padx=12, pady=7).pack(side="left")


if __name__ == "__main__":
    create_database()
    LibraryApp().mainloop()
