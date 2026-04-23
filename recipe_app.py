import tkinter as tk
from tkinter import ttk, filedialog
from PIL import Image, ImageTk
import fitz
import os
import io

RECIPE_FOLDER = os.path.expanduser("~/Documents/レシピPDF")

class RecipeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("野菜レシピ集")
        self.root.geometry("1100x750")
        self.recipes = []
        self.current_images = []
        self._build_ui()
        self._load_recipes()

    def _build_ui(self):
        # ヘッダー
        header = tk.Frame(self.root, bg="#4a7c59", pady=12)
        header.pack(fill="x")
        tk.Label(header, text="野菜レシピ集", font=("Helvetica", 20, "bold"),
                 bg="#4a7c59", fg="white").pack(side="left", padx=20)
        tk.Button(header, text="フォルダを選択", command=self._choose_folder,
                  bg="white", fg="#4a7c59", font=("Helvetica", 11),
                  relief="flat", padx=10, pady=4).pack(side="right", padx=20)

        # 検索
        search_bar = tk.Frame(self.root, bg="#e8f0e9", pady=8)
        search_bar.pack(fill="x")
        tk.Label(search_bar, text="検索：", font=("Helvetica", 12),
                 bg="#e8f0e9").pack(side="left", padx=10)
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *a: self._search())
        tk.Entry(search_bar, textvariable=self.search_var,
                 font=("Helvetica", 12), width=30).pack(side="left")

        # メイン
        main = tk.PanedWindow(self.root, orient="horizontal", sashwidth=5)
        main.pack(fill="both", expand=True, padx=10, pady=10)

        # 左パネル
        left = tk.Frame(main, width=260)
        main.add(left, minsize=200)

        self.count_label = tk.Label(left, text="", font=("Helvetica", 10), fg="#666")
        self.count_label.pack(anchor="w", padx=5, pady=(0, 3))

        frame_list = tk.Frame(left)
        frame_list.pack(fill="both", expand=True)
        sb = ttk.Scrollbar(frame_list)
        sb.pack(side="right", fill="y")
        self.listbox = tk.Listbox(frame_list, yscrollcommand=sb.set,
                                  font=("Helvetica", 12), selectbackground="#4a7c59",
                                  selectforeground="white", activestyle="none",
                                  relief="sunken", bd=1)
        self.listbox.pack(side="left", fill="both", expand=True)
        sb.config(command=self.listbox.yview)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)

        # 右パネル
        right = tk.Frame(main, bg="white")
        main.add(right)

        self.canvas = tk.Canvas(right, bg="white", highlightthickness=0)
        vbar = ttk.Scrollbar(right, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vbar.set)
        vbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.detail = tk.Frame(self.canvas, bg="white")
        self.win_id = self.canvas.create_window((0, 0), window=self.detail, anchor="nw")
        self.detail.bind("<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>",
            lambda e: self.canvas.itemconfig(self.win_id, width=e.width))
        self.canvas.bind_all("<MouseWheel>",
            lambda e: self.canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        tk.Label(self.detail, text="← レシピを選んでください",
                 font=("Helvetica", 14), bg="white", fg="#aaa").pack(pady=60)

    def _choose_folder(self):
        folder = filedialog.askdirectory(title="PDFフォルダを選択")
        if folder:
            global RECIPE_FOLDER
            RECIPE_FOLDER = folder
            self._load_recipes()

    def _load_recipes(self):
        self.recipes = []
        if os.path.exists(RECIPE_FOLDER):
            for f in sorted(os.listdir(RECIPE_FOLDER)):
                if f.lower().endswith(".pdf"):
                    self.recipes.append({
                        "name": os.path.splitext(f)[0],
                        "path": os.path.join(RECIPE_FOLDER, f)
                    })
        self._render_list(self.recipes)

    def _search(self):
        q = self.search_var.get().lower()
        filtered = [r for r in self.recipes if q in r["name"].lower()]
        self._render_list(filtered)

    def _render_list(self, items):
        self.listbox.delete(0, tk.END)
        self._shown = items
        for r in items:
            self.listbox.insert(tk.END, r["name"])
        self.count_label.config(text=f"{len(items)}件")

    def _on_select(self, event):
        sel = self.listbox.curselection()
        if not sel:
            return
        self._show_recipe(self._shown[sel[0]])

    def _show_recipe(self, recipe):
        for w in self.detail.winfo_children():
            w.destroy()
        self.current_images = []

        tk.Label(self.detail, text=recipe["name"],
                 font=("Helvetica", 16, "bold"), bg="white", fg="#2d5a3d",
                 wraplength=700, justify="left").pack(anchor="w", padx=20, pady=15)
        ttk.Separator(self.detail).pack(fill="x", padx=20)

        try:
            doc = fitz.open(recipe["path"])
            for i, page in enumerate(doc):
                text = page.get_text().strip()
                if text:
                    tk.Label(self.detail, text=text, font=("Helvetica", 12),
                             bg="white", fg="#333", wraplength=700,
                             justify="left").pack(anchor="w", padx=20, pady=8)

                for img_info in page.get_images(full=True):
                    try:
                        xref = img_info[0]
                        base = doc.extract_image(xref)
                        pil_img = Image.open(io.BytesIO(base["image"]))
                        max_w = 680
                        if pil_img.width > max_w:
                            ratio = max_w / pil_img.width
                            pil_img = pil_img.resize(
                                (max_w, int(pil_img.height * ratio)), Image.LANCZOS)
                        tk_img = ImageTk.PhotoImage(pil_img)
                        self.current_images.append(tk_img)
                        tk.Label(self.detail, image=tk_img, bg="white").pack(padx=20, pady=8)
                    except Exception:
                        pass

                if i < len(doc) - 1:
                    ttk.Separator(self.detail).pack(fill="x", padx=20, pady=4)
            doc.close()
        except Exception as e:
            tk.Label(self.detail, text=f"エラー: {e}",
                     bg="white", fg="red", font=("Helvetica", 11)).pack(padx=20, pady=20)

        self.canvas.yview_moveto(0)


if __name__ == "__main__":
    root = tk.Tk()
    app = RecipeApp(root)
    root.mainloop()
