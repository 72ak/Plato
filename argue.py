import os
import sys
import json
import time
import random
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox
import tkinter.font as tkfont

from PIL import Image, ImageTk, ImageOps, ImageDraw, ImageStat

try:
    from PIL import ImageGrab
except Exception:  
    ImageGrab = None

def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


DATA_DIR = os.path.join(app_dir(), "argue_data")
SESS_DIR = os.path.join(DATA_DIR, "sessions")
PICS_DIR = os.path.join(DATA_DIR, "pics")
for _d in (DATA_DIR, SESS_DIR, PICS_DIR):
    os.makedirs(_d, exist_ok=True)

NARRATOR_COLOR = "#444444"
IMG_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")

def hextorgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(int(max(0, min(255, c))) for c in rgb)


def random_color():
    return rgb_to_hex((random.randint(40, 210),
                       random.randint(40, 210),
                       random.randint(40, 210)))


def average_color(image_path):
    try:
        img = Image.open(image_path).convert("RGB")
        img.thumbnail((80, 80))
        mean = ImageStat.Stat(img).mean
        return rgb_to_hex(mean)
    except Exception:
        return random_color()


def contrast_text(hex_color):
    r, g, b = hextorgb(hex_color)
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return "#000000" if luminance > 140 else "#ffffff"


def tint(hex_color, amount=0.85):
    r, g, b = hextorgb(hex_color)
    r = r + (255 - r) * amount
    g = g + (255 - g) * amount
    b = b + (255 - b) * amount
    return rgb_to_hex((r, g, b))


class ArgueApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("argue with yourself")
        self.geometry("1120x720")
        self.minsize(820, 560)
        self.configure(bg="white")

        self._img_cache = {}   
        self.bold = tkfont.Font(family="Segoe UI", size=11, weight="bold")
        self.big = tkfont.Font(family="Segoe UI", size=22, weight="bold")
        self.normal = tkfont.Font(family="Segoe UI", size=10)

        self.container = tk.Frame(self, bg="white")
        self.container.pack(fill="both", expand=True, padx=3, pady=3)

        self.topic = ""
        self.people = []

        self.show_setup()

    def clear_container(self):
        for w in self.container.winfo_children():
            w.destroy()

    def avatar(self, image_path, color, size):
        key = "%s|%s|%d" % (image_path or "", color, size)
        if key in self._img_cache:
            return self._img_cache[key]
        if image_path and os.path.exists(image_path):
            try:
                img = Image.open(image_path).convert("RGBA")
            except Exception:
                img = Image.new("RGBA", (size, size), hextorgb(color) + (255,))
        else:
            img = Image.new("RGBA", (size, size), hextorgb(color) + (255,))
        img = ImageOps.fit(img, (size, size), Image.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
        img.putalpha(mask)
        photo = ImageTk.PhotoImage(img)
        self._img_cache[key] = photo
        return photo

    def thumb(self, image_path, size):
        key = "thumb|%s|%d" % (image_path, size)
        if key in self._img_cache:
            return self._img_cache[key]
        img = Image.open(image_path).convert("RGB")
        img.thumbnail((size, size), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        self._img_cache[key] = photo
        return photo

    def show_setup(self):
        self.clear_container()
        wrap = tk.Frame(self.container, bg="white")
        wrap.pack(fill="both", expand=True, padx=3, pady=3)

        tk.Label(wrap, text="what will you be arguing",
                 font=self.big, bg="white", fg="#111111").pack(anchor="w", padx=3, pady=3)

        tk.Label(wrap, text="Topic of discussion", font=self.bold,
                 bg="white").pack(anchor="w", padx=3, pady=3)
        topic_var = tk.StringVar(value=self.topic)
        topic_entry = tk.Entry(wrap, textvariable=topic_var, font=self.normal,
                               width=70)
        topic_entry.pack(anchor="w", fill="x", padx=3, pady=3)

        tk.Label(wrap, text="how many people will be arguing", font=self.bold,
                 bg="white").pack(anchor="w", padx=3, pady=3)
        count_var = tk.IntVar(value=max(1, len(self.people)) if self.people else 2)
        scale = tk.Scale(wrap, from_=1, to=8, orient="horizontal",
                         variable=count_var, bg="white", highlightthickness=0,
                         length=260, command=lambda _=None: rebuild_rows())
        scale.pack(anchor="w", padx=3, pady=3)

        rowsframe = tk.Frame(wrap, bg="white")
        rowsframe.pack(anchor="w", fill="both", expand=True, padx=3, pady=3)
        canvas = tk.Canvas(rowsframe, bg="white", highlightthickness=0)
        scrollbar = tk.Scrollbar(rowsframe, orient="vertical",
                                 command=canvas.yview)
        inner = tk.Frame(canvas, bg="white")
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=3, pady=3)
        scrollbar.pack(side="right", fill="y", padx=3, pady=3)

        row_state = []
        for p in self.people:
            row_state.append({"name": tk.StringVar(value=p["name"]),
                              "desc": tk.StringVar(value=p["desc"]),
                              "image_path": p.get("image_path")})

        def ensure_rows(n):
            while len(row_state) < n:
                row_state.append({"name": tk.StringVar(),
                                  "desc": tk.StringVar(),
                                  "image_path": None})

        def choose_pic(idx, label):
            path = filedialog.askopenfilename(
                title="choose a picture",
                filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"),
                           ("All files", "*.*")])
            if path:
                row_state[idx]["image_path"] = path
                label.config(text=os.path.basename(path))

        def clear_pic(idx, label):
            row_state[idx]["image_path"] = None
            label.config(text="there is no picture")

        def rebuild_rows():
            n = count_var.get()
            ensure_rows(n)
            for w in inner.winfo_children():
                w.destroy()
            for i in range(n):
                st = row_state[i]
                card = tk.Frame(inner, bg="white", bd=1, relief="solid")
                card.pack(fill="x", padx=3, pady=3)
                tk.Label(card, text="person %d" % (i + 1), font=self.bold,
                         bg="white").grid(row=0, column=0, columnspan=2,
                                          sticky="w", padx=3, pady=3)
                tk.Label(card, text="name", bg="white").grid(
                    row=1, column=0, sticky="e", padx=3, pady=3)
                tk.Entry(card, textvariable=st["name"], width=28).grid(
                    row=1, column=1, sticky="w", padx=3, pady=3)
                tk.Label(card, text="description", bg="white").grid(
                    row=2, column=0, sticky="e", padx=3, pady=3)
                tk.Entry(card, textvariable=st["desc"], width=40).grid(
                    row=2, column=1, sticky="w", padx=3, pady=3)

                pic_label = tk.Label(
                    card, bg="white",
                    text=os.path.basename(st["image_path"]) if st["image_path"]
                    else "there is not a picture")
                pic_label.grid(row=3, column=1, sticky="w", padx=3, pady=3)
                btns = tk.Frame(card, bg="white")
                btns.grid(row=3, column=0, sticky="e", padx=3, pady=3)
                tk.Button(btns, text="choose picture",
                          command=lambda i=i, l=pic_label: choose_pic(i, l)
                          ).pack(side="left", padx=3, pady=3)
                tk.Button(btns, text="clear",
                          command=lambda i=i, l=pic_label: clear_pic(i, l)
                          ).pack(side="left", padx=3, pady=3)

        rebuild_rows()

        def on_continue():
            topic = topic_var.get().strip()
            if not topic:
                messagebox.showwarning("there is no topic.")
                return
            n = count_var.get()
            people = []
            for i in range(n):
                st = row_state[i]
                name = st["name"].get().strip() or ("Person %d" % (i + 1))
                desc = st["desc"].get().strip()
                src = st["image_path"]
                stored_path = None
                if src and os.path.exists(src):
                    ext = os.path.splitext(src)[1].lower() or ".png"
                    stored_path = os.path.join(
                        PICS_DIR, "p_%d_%s%s" % (i, int(time.time() * 1000), ext))
                    try:
                        shutil.copy2(src, stored_path)
                    except Exception:
                        stored_path = src
                if stored_path:
                    color = average_color(stored_path)
                else:
                    color = random_color()
                people.append({"name": name, "desc": desc,
                               "image_path": stored_path, "color": color})
            self.topic = topic
            self.people = people
            self.show_summary()

        bar = tk.Frame(wrap, bg="white")
        bar.pack(anchor="w", padx=3, pady=3)
        tk.Button(bar, text="Continue", font=self.bold,
                  command=on_continue).pack(side="left", padx=3, pady=3)
        tk.Button(bar, text="view preiovus arguments",
                  command=self.show_chat_browser).pack(side="left", padx=3, pady=3)

    def show_summary(self):
        self.clear_container()
        wrap = tk.Frame(self.container, bg="white")
        wrap.pack(fill="both", expand=True, padx=3, pady=3)

        tk.Label(wrap, text="ready", font=self.big,
                 bg="white", fg="#111111").pack(anchor="w", padx=3, pady=3)
        tk.Label(wrap, text="Topic of discussion", font=self.bold,
                 bg="white").pack(anchor="w", padx=3, pady=3)
        tk.Label(wrap, text=self.topic, font=self.normal, bg="white",
                 fg="#333333", wraplength=900, justify="left").pack(anchor="w", padx=3, pady=3)

        tk.Label(wrap, text="who will be arguing", font=self.bold,
                 bg="white").pack(anchor="w", padx=3, pady=3)

        grid = tk.Frame(wrap, bg="white")
        grid.pack(anchor="w", fill="x", padx=3, pady=3)
        for i, p in enumerate(self.people):
            card = tk.Frame(grid, bg="white", bd=1, relief="solid")
            card.grid(row=i // 2, column=i % 2, sticky="w", padx=3, pady=3)
            photo = self.avatar(p["image_path"], p["color"], 56)
            tk.Label(card, image=photo, bg="white").grid(
                row=0, column=0, rowspan=2, padx=3, pady=3)
            tk.Label(card, text=p["name"], font=self.bold, bg="white",
                     fg=p["color"]).grid(row=0, column=1, sticky="w", padx=3, pady=3)
            tk.Label(card, text=p["desc"] or "—", bg="white", fg="#555555",
                     wraplength=280, justify="left").grid(
                row=1, column=1, sticky="w", padx=3, pady=3)

        bar = tk.Frame(wrap, bg="white")
        bar.pack(anchor="w", padx=3, pady=3)
        tk.Button(bar, text="back", command=self.show_setup).pack(side="left", padx=3, pady=3)
        tk.Button(bar, text="start", font=self.bold,
                  command=self.start_discussion).pack(side="left", padx=3, pady=3)

    def start_discussion(self):
        order = list(range(len(self.people)))
        random.shuffle(order)
        session = {
            "id": str(int(time.time() * 1000)),
            "topic": self.topic,
            "created": time.time(),
            "people": self.people,
            "order": order,
            "turn_index": 0,
            "messages": [],
            "ended": False,
        }
        self.save_session(session)
        self.show_chat(session)

    def session_path(self, session):
        return os.path.join(SESS_DIR, session["id"] + ".json")

    def save_session(self, session):
        try:
            with open(self.session_path(session), "w", encoding="utf-8") as f:
                json.dump(session, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("save failed:", e)

    def list_sessions(self):
        out = []
        for fn in os.listdir(SESS_DIR):
            if not fn.endswith(".json"):
                continue
            try:
                with open(os.path.join(SESS_DIR, fn), encoding="utf-8") as f:
                    data = json.load(f)
                out.append(data)
            except Exception:
                continue
        out.sort(key=lambda s: s.get("created", 0), reverse=True)
        return out

    def show_chat_browser(self):
        sessions = self.list_sessions()
        if sessions:
            self.show_chat(sessions[0])
        else:
            messagebox.showinfo("there are no arguments")

    def show_chat(self, session):
        self.clear_container()
        self.session = session
        self.narrator_mode = session.get("ended", False)
        self.pending_attachments = []

        paned = tk.PanedWindow(self.container, orient="horizontal",
                               sashwidth=6, bg="#dddddd")
        paned.pack(fill="both", expand=True, padx=3, pady=3)

        # ---- left: saved chats ---- #
        left = tk.Frame(paned, bg="#f5f5f5")
        tk.Label(left, text="arguments", font=self.bold, bg="#f5f5f5").pack(
            anchor="w", padx=3, pady=3)
        tk.Button(left, text="New argument",
                  command=self.new_argument).pack(fill="x", padx=3, pady=3)
        self.sess_list = tk.Listbox(left, activestyle="none",
                                    font=self.normal, bd=0,
                                    highlightthickness=0)
        self.sess_list.pack(fill="both", expand=True, padx=3, pady=3)
        self.sess_list.bind("<<ListboxSelect>>", self.on_pick_session)
        paned.add(left, minsize=140, width=200)

        center = tk.Frame(paned, bg="white")
        self.topic_label = tk.Label(center, text=session["topic"],
                                    font=self.bold, bg="white", fg="#111111",
                                    anchor="w", wraplength=520, justify="left")
        self.topic_label.pack(fill="x", padx=3, pady=3)

        transcript_wrap = tk.Frame(center, bg="white")
        transcript_wrap.pack(fill="both", expand=True, padx=3, pady=3)
        self.transcript = tk.Text(transcript_wrap, wrap="word", bd=1,
                                  relief="solid", bg="white", font=self.normal,
                                  state="disabled", spacing3=4)
        tsb = tk.Scrollbar(transcript_wrap, command=self.transcript.yview)
        self.transcript.configure(yscrollcommand=tsb.set)
        tsb.pack(side="right", fill="y", padx=3, pady=3)
        self.transcript.pack(side="left", fill="both", expand=True, padx=3, pady=3)

        self.attach_bar = tk.Frame(center, bg="white")
        self.attach_bar.pack(fill="x", padx=3, pady=3)

        inbox = tk.Frame(center, bg="white")
        inbox.pack(fill="x", padx=3, pady=3)
        self.input = tk.Text(inbox, height=3, wrap="word", bd=1, relief="solid",
                             font=self.normal)
        self.input.pack(side="left", fill="both", expand=True, padx=3, pady=3)
        self.input.bind("<Return>", self._on_return)
        self.input.bind("<Shift-Return>", lambda e: None)
        self.input.bind("<Control-v>", self._on_paste)
        btncol = tk.Frame(inbox, bg="white")
        btncol.pack(side="left", fill="y", padx=3, pady=3)
        tk.Button(btncol, text="Attach…", command=self.attach_file).pack(
            fill="x", padx=3, pady=3)
        self.send_btn = tk.Button(btncol, text="Send", font=self.bold,
                                  command=self.on_send)
        self.send_btn.pack(fill="x", padx=3, pady=3)
        paned.add(center, minsize=320)

        self.right = tk.Frame(paned, bg="white")
        self.turn_hint = tk.Label(self.right, text="", font=self.normal,
                                  bg="white")
        self.turn_hint.pack(fill="x", padx=3, pady=3)
        self.avatar_label = tk.Label(self.right, bg="white")
        self.avatar_label.pack(padx=3, pady=3)
        self.name_label = tk.Label(self.right, text="", font=self.big,
                                   bg="white")
        self.name_label.pack(padx=3, pady=3)
        self.desc_label = tk.Label(self.right, text="", font=self.normal,
                                   bg="white", wraplength=220, justify="center")
        self.desc_label.pack(padx=3, pady=3)

        self.narrator_btn = tk.Button(self.right, text="Narrator",
                                      command=self.toggle_narrator)
        self.narrator_btn.pack(fill="x", padx=3, pady=3)
        self.end_btn = tk.Button(self.right, text="end",
                                 command=self.end_discussion)
        paned.add(self.right, minsize=180, width=260)

        self.right_widgets = [self.right, self.turn_hint, self.avatar_label,
                              self.name_label, self.desc_label]

        self.render_transcript()
        self.refresh_session_list()
        self.update_speaker_panel()

    def refresh_session_list(self):
        self._sessions_cache = self.list_sessions()
        self.sess_list.delete(0, tk.END)
        for s in self._sessions_cache:
            when = time.strftime("%d %b %H:%M", time.localtime(s.get("created", 0)))
            topic = s.get("topic", "(untitled)")
            if len(topic) > 26:
                topic = topic[:25] + "…"
            flag = "  ✔" if s.get("ended") else ""
            self.sess_list.insert(tk.END, "%s\n   %s%s" % (topic, when, flag))
            if s["id"] == self.session["id"]:
                self.sess_list.itemconfig(tk.END, bg="#e5e5e5")

    def on_pick_session(self, _evt):
        sel = self.sess_list.curselection()
        if not sel:
            return
        chosen = self._sessions_cache[sel[0]]
        if chosen["id"] == self.session["id"]:
            return
        self.show_chat(chosen)

    def new_argument(self):
        self.topic = ""
        self.people = []
        self.show_setup()
    def current_person(self):
        order = self.session["order"]
        if not order:
            return None
        idx = order[self.session["turn_index"] % len(order)]
        return self.session["people"][idx]

    def active_speaker(self):
        if self.session.get("ended") or self.narrator_mode:
            return ("narrator", "Speaking outside the argument.",
                    NARRATOR_COLOR, None, True)
        p = self.current_person()
        if p is None:
            return ("Narrator", "", NARRATOR_COLOR, None, True)
        return (p["name"], p["desc"], p["color"], p["image_path"], False)

    def update_speaker_panel(self):
        name, desc, color, image_path, is_narrator = self.active_speaker()
        text_fg = contrast_text(color)
        for w in self.right_widgets:
            w.configure(bg=color)
        self.name_label.configure(fg=text_fg)
        self.desc_label.configure(fg=text_fg, text=desc or "—")
        self.name_label.configure(text=name)

        photo = self.avatar(image_path, color, 130)
        self.avatar_label.configure(image=photo, bg=color)
        self.avatar_label.image = photo

        if self.session.get("ended"):
            hint = "argument OVER. narrator only"
        elif is_narrator:
            hint = "narrator is speaking"
        else:
            hint = ""
        self.turn_hint.configure(text=hint, fg=text_fg)

        if self.session.get("ended"):
            self.narrator_btn.configure(state="disabled", text="Narrator")
            self.end_btn.pack_forget()
        else:
            self.narrator_btn.configure(state="normal")
            if self.narrator_mode:
                self.narrator_btn.configure(text="Back to speakers")
                self.end_btn.pack(fill="x", padx=3, pady=3)
            else:
                self.narrator_btn.configure(text="Narrator")
                self.end_btn.pack_forget()

    def attach_file(self):
        paths = filedialog.askopenfilenames(title="Attach")
        for p in paths:
            self.add_attachment(p)

    def add_attachment(self, path):
        self.pending_attachments.append(path)
        self.render_attach_bar()

    def render_attach_bar(self):
        for w in self.attach_bar.winfo_children():
            w.destroy()
        for i, path in enumerate(self.pending_attachments):
            chip = tk.Frame(self.attach_bar, bg="#eeeeee", bd=1, relief="solid")
            chip.pack(side="left", padx=3, pady=3)
            tk.Label(chip, text="attached: " + os.path.basename(path), bg="#eeeeee").pack(
                side="left", padx=3, pady=3)
            tk.Button(chip, text="✕", bd=0, bg="#eeeeee",
                      command=lambda i=i: self.remove_attachment(i)).pack(
                side="left", padx=3, pady=3)

    def remove_attachment(self, i):
        if 0 <= i < len(self.pending_attachments):
            self.pending_attachments.pop(i)
            self.render_attach_bar()

    def _on_paste(self, _evt):
        if ImageGrab is None:
            return
        try:
            grabbed = ImageGrab.grabclipboard()
        except Exception:
            return
        if isinstance(grabbed, list):
            for p in grabbed:
                if os.path.exists(p):
                    self.add_attachment(p)
            return "break"
        if Image is not None and isinstance(grabbed, Image.Image):
            fn = os.path.join(PICS_DIR, "paste_%d.png" % int(time.time() * 1000))
            try:
                grabbed.save(fn)
                self.add_attachment(fn)
            except Exception:
                pass
            return "break"
        return None

    def _store_attachments(self):
        stored = []
        for src in self.pending_attachments:
            if not os.path.exists(src):
                continue
            base = os.path.basename(src)
            dst = os.path.join(PICS_DIR, "att_%d_%s" % (
                int(time.time() * 1000), base))
            try:
                shutil.copy2(src, dst)
                stored.append(dst)
            except Exception:
                stored.append(src)
        return stored

    def _on_return(self, _evt):
        self.on_send()
        return "break"

    def on_send(self):
        text = self.input.get("1.0", tk.END).strip()
        attachments = self._store_attachments()
        if not text and not attachments:
            return
        name, desc, color, image_path, is_narrator = self.active_speaker()
        msg = {"is_narrator": is_narrator, "name": name, "color": color,
               "image_path": image_path, "text": text,
               "attachments": attachments}
        self.session["messages"].append(msg)
        self.render_message(msg)

        if not is_narrator:
            order = self.session["order"]
            if order:
                self.session["turn_index"] = (
                    self.session["turn_index"] + 1) % len(order)

        self.input.delete("1.0", tk.END)
        self.pending_attachments = []
        self.render_attach_bar()
        self.save_session(self.session)
        self.update_speaker_panel()

    def render_transcript(self):
        self.transcript.configure(state="normal")
        self.transcript.delete("1.0", tk.END)
        self.transcript.configure(state="disabled")
        for msg in self.session["messages"]:
            self.render_message(msg)

    def render_message(self, msg):
        color = msg["color"]
        name_tag = "name_" + color.lstrip("#")
        body_tag = "body_" + color.lstrip("#")
        self.transcript.tag_configure(name_tag, foreground=color,
                                      font=self.bold)
        self.transcript.tag_configure(body_tag, background=tint(color, 0.88),
                                      lmargin1=8, lmargin2=8, rmargin=8)

        self.transcript.configure(state="normal")
        self.transcript.insert(tk.END, msg["name"] + "\n", name_tag)
        if msg["text"]:
            self.transcript.insert(tk.END, msg["text"] + "\n", body_tag)
        for path in msg.get("attachments", []):
            ext = os.path.splitext(path)[1].lower()
            if ext in IMG_EXTS and os.path.exists(path):
                try:
                    photo = self.thumb(path, 180)
                    self.transcript.image_create(tk.END, image=photo)
                    self.transcript.insert(tk.END, "\n")
                    continue
                except Exception:
                    pass
            self.transcript.insert(tk.END,
                                   "📎 " + os.path.basename(path) + "\n",
                                   body_tag)
        self.transcript.insert(tk.END, "\n")
        self.transcript.configure(state="disabled")
        self.transcript.see(tk.END)

    def toggle_narrator(self):
        if self.session.get("ended"):
            return
        self.narrator_mode = not self.narrator_mode
        self.update_speaker_panel()

    def end_discussion(self):
        if not messagebox.askyesno(
                "End discussion",
                "End the discussion? Afterwards only the Narrator can speak."):
            return
        self.session["ended"] = True
        self.narrator_mode = True
        self.save_session(self.session)
        self.refresh_session_list()
        self.update_speaker_panel()


if __name__ == "__main__":
    ArgueApp().mainloop()
