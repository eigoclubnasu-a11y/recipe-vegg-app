from flask import Flask, render_template, jsonify, request, send_file
import fitz
import os
import io
import base64

app = Flask(__name__)
RECIPE_FOLDER = os.path.join(os.path.dirname(__file__), "static/pdfs")

def get_recipes():
    recipes = []
    if not os.path.exists(RECIPE_FOLDER):
        return recipes
    for root, dirs, files in os.walk(RECIPE_FOLDER):
        dirs.sort()
        folder_name = os.path.relpath(root, RECIPE_FOLDER)
        for f in sorted(files):
            if f.lower().endswith(".pdf"):
                rel_path = os.path.join(folder_name, f) if folder_name != "." else f
                category = folder_name if folder_name != "." else ""
                import re as _re
                name = _re.sub(r'\s*[-－]\s*シート\d+', '', os.path.splitext(f)[0])
                recipes.append({
                    "name": name,
                    "file": rel_path,
                    "category": category
                })
    return recipes

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/recipes")
def api_recipes():
    q = request.args.get("q", "").lower()
    recipes = get_recipes()
    if q:
        recipes = [r for r in recipes if q in r["name"].lower()]
    return jsonify(recipes)

@app.route("/api/recipe/<path:filename>")
def api_recipe(filename):
    path = os.path.join(RECIPE_FOLDER, filename)
    if not os.path.exists(path):
        return jsonify({"error": "見つかりません"}), 404

    doc = fitz.open(path)
    seen_paragraphs = set()
    pages = []
    for page in doc:
        raw_text = page.get_text().strip()
        import re
        EXCLUDE = ["那須高原こたろうファーム", "夢屋さんでは", "牛乳入れることもあります", "に使います", "by古民家カフェ夢屋", "大きめズッキーニのポタージュ", "ズッキーニのレシピ①", "☆他にも、味噌汁", "ズッキーニは淡白な味わいなので", "和・洋・中・何の料理にもよく合います", "こたろうレシピ", "バターナッツのポタージュ", "バターナッツの", "ルッコラレシピ", "寒い日は身体の中から温まろう", "スイスチャードのレシピ", "コラーゲンたっぷり大根と手羽先煮", "菊芋を千切り", "菊芋の漬け物", "グラタンより楽ちん", "グラタンより楽チン", "☆菜花のナムル", "☆菜花とアサリ蒸し", "☆菜花の卵焼き", "③アサリとオリーブオイル"]
        TITLE_BREAK = ["凍み白菜で絶品鍋"]
        EXCLUDE_EXACT = {"ポタージュ", "サラダ", "など）"}
        BREAK_PATTERN = re.compile(r'^([①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮☆⭐★◎＜<＊\*]|[１２３４５６７８９0-9\d]+[\.．\s　]|材料)')

        # 行を段落に結合
        paragraphs = []
        current = ""
        after_break = False
        seen_lines = set()
        for line in raw_text.split("\n"):
            stripped = line.strip()
            if any(ex in stripped for ex in EXCLUDE) or stripped in EXCLUDE_EXACT:
                continue
            if stripped and stripped in seen_lines:
                continue
            if stripped:
                seen_lines.add(stripped)
            if not stripped:
                if current:
                    paragraphs.append(current.strip())
                    current = ""
                after_break = False
            elif BREAK_PATTERN.match(stripped) or any(tb in stripped for tb in TITLE_BREAK):
                if current:
                    paragraphs.append(current.strip())
                current = stripped
                after_break = True
            else:
                if after_break:
                    current = current + "\n" + stripped
                    after_break = False
                else:
                    current = (current + stripped) if current else stripped
        if current:
            paragraphs.append(current.strip())

        # 段落レベルで重複除去（全空白を除去して比較）
        TEXT_FIXES = {
            "焦げ目がつくまで": "焦げ目がつくまで焼く",
            "＜野菜の菜花・美味しいレシピ＞": "＜野菜の菜花・美味しいレシピ＞\n☆菜花のナムル",
            "①菜花を食べやすい大きさに切る": "①菜花を食べやすい大きさに切る",
            "②熱湯で３０秒くらい茹でて、水気を切る": "②熱湯で３０秒くらい茹でて、水気を切る\n③アサリとオリーブオイル、白ワインをフライパンに入れて、中火で蒸す",
            "①菜花を茹でて小さめにカットする": "☆菜花の卵焼き\n①菜花を茹でて小さめにカットする",
            "サンマルツァーノリゼルバなら5〜6個": "",
            "サンマルツァーノリゼルバ": "トマト",
            "使ってみまし": "使ってみましょう",
            "肉料理、\n揚げ物": "肉料理、揚げ物",
        }
        unique_paras = []
        for para in paragraphs:
            for old, new in TEXT_FIXES.items():
                if old in para and new not in para:
                    para = para.replace(old, new)
            key = re.sub(r'[\s\u3000]+', '', para)
            if key not in seen_paragraphs:
                seen_paragraphs.add(key)
                unique_paras.append(para)
        # 他の段落の先頭部分と一致する短い段落を除去
        keys = [re.sub(r'[\s\u3000]+', '', p) for p in unique_paras]
        unique_paras = [p for i, p in enumerate(unique_paras)
                        if not any(keys[j].startswith(keys[i]) and len(keys[j]) > len(keys[i])
                                   for j in range(len(keys)))]
        # 最初の段落と同じ言葉が最後に出てきたら削除
        if len(unique_paras) >= 2:
            first_key = re.sub(r'[\s\u3000]+', '', unique_paras[0])
            last_key = re.sub(r'[\s\u3000]+', '', unique_paras[-1])
            if first_key == last_key or first_key.startswith(last_key) or last_key.startswith(first_key):
                unique_paras = unique_paras[:-1]
        text = "\n\n".join(unique_paras)

        pages.append({"text": text, "images": []})
    doc.close()
    name = re.sub(r'\s*[-－]\s*シート\d+', '', os.path.splitext(os.path.basename(filename))[0])
    return jsonify({"name": name, "pages": pages})

if __name__ == "__main__":
    import webbrowser, threading
    threading.Timer(1.0, lambda: webbrowser.open("http://localhost:8765")).start()
    app.run(host="0.0.0.0", port=10000, debug=False)
