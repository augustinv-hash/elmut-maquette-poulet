"""Maquette SEO annotée de https://elmut.fr/produits-chien/frais/poulet.

Rend la page réelle avec Playwright, retire le JavaScript et les traceurs,
applique la v2 des recommandations (title, meta, petit H1 en surtitre, alt, H2 doublé
sans espace, FAQ propre au poulet), suite au retour d'Elmut du 21/10/2026 : aucun bloc
en bas de page.
Le texte existant de la page n'est pas modifié.

Usage : ~/Documents/CODE/seo-tools/.venv/bin/python -I scripts/build.py
"""
import asyncio
import copy
import re
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scripts" / "cache"
FONTS = ROOT / "assets" / "fonts"
SOURCE_URL = "https://elmut.fr/produits-chien/frais/poulet"
ORIGIN = "https://elmut.fr"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"

# Polices libres (OFL) hébergées par elmut.fr : copiées en local.
OFL_FAMILIES = {"Geist", "Geist Mono", "Chango", "Inter"}
# Polices commerciales (PP Pangaia, Maison Neue) : remplacées par des équivalents Google Fonts.
SUBSTITUTES = {
    "Pangaia": "Playfair+Display:ital,wght@0,400;0,500;1,500",
    "MaisonNeue": "Archivo:wght@400;700",
}


# ---------------------------------------------------------------- rendu
async def render() -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 900}, locale="fr-FR")
        await page.goto(SOURCE_URL, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(2000)
        for _ in range(20):
            await page.mouse.wheel(0, 700)
            await page.wait_for_timeout(150)
        await page.wait_for_timeout(1500)
        html = await page.content()
        await browser.close()
    (CACHE / "rendered.html").write_text(html, encoding="utf-8")
    return html


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


# ---------------------------------------------------------------- CSS et polices
def localize_css(css: str) -> str:
    """Polices OFL en local, polices commerciales neutralisées, autres URLs en absolu."""
    FONTS.mkdir(parents=True, exist_ok=True)

    def face(m):
        block = m.group(0)
        family = re.search(r"font-family:([^;]+);", block).group(1).strip().strip('"')
        if any(k in family for k in SUBSTITUTES):
            return ""  # redéfinie plus bas avec une police libre
        if family in OFL_FAMILIES:
            def dl(u):
                path = u.group(1)
                name = path.split("/")[-1].split("?")[0]
                target = FONTS / name
                if not target.exists():
                    target.write_bytes(fetch(ORIGIN + path))
                return f"url(assets/fonts/{name})"
            return re.sub(r"url\((/_next/static/media/[^)]+)\)", dl, block)
        return block

    css = re.sub(r"@font-face\{[^}]*\}", face, css)
    css = re.sub(r"url\((/[^)]+)\)", lambda m: f"url({ORIGIN}{m.group(1)})", css)
    return css


def substitute_faces() -> str:
    """@font-face qui réutilisent les noms de famille d'origine avec des fichiers libres."""
    faces = []
    specs = [
        ("Pangaia", "Playfair+Display:wght@500", "normal", "500"),
        ("Pangaia", "Playfair+Display:ital,wght@1,500", "italic", "500"),
        ("Pangaia", "Playfair+Display:wght@400", "normal", "200"),
        ("MaisonNeueExtendedBook", "Archivo:wght@400", "normal", "400"),
        ("MaisonNeueExtendedBold", "Archivo:wght@700", "normal", "700"),
    ]
    for family, query, style, weight in specs:
        css = fetch(f"https://fonts.googleapis.com/css2?family={query}&display=swap").decode()
        # dernier bloc = sous-ensemble latin
        src = re.findall(r"src: url\((https://[^)]+\.woff2)\)", css)[-1]
        name = f"{family}-{style}-{weight}.woff2"
        target = FONTS / name
        if not target.exists():
            target.write_bytes(fetch(src))
        faces.append(
            f'@font-face{{font-family:"{family}";font-style:{style};font-weight:{weight};'
            f"font-display:swap;src:url(assets/fonts/{name}) format(\"woff2\")}}"
        )
    return "\n".join(faces)


# ---------------------------------------------------------------- helpers DOM
def reco(soup, num, title, body, items=None):
    box = soup.new_tag("aside", attrs={"class": "reco", "data-reco": str(num)})
    head = soup.new_tag("p", attrs={"class": "reco-head"})
    badge = soup.new_tag("span", attrs={"class": "reco-num"})
    badge.string = str(num)
    head.append(badge)
    head.append(NavigableString(title))
    box.append(head)
    for para in body if isinstance(body, list) else [body]:
        p = soup.new_tag("p")
        p.append(BeautifulSoup(para, "html.parser"))
        box.append(p)
    if items:
        ul = soup.new_tag("ul")
        for it in items:
            li = soup.new_tag("li")
            li.append(BeautifulSoup(it, "html.parser"))
            ul.append(li)
        box.append(ul)
    return box


def find_h(soup, name, pattern):
    for h in soup.find_all(name):
        if re.search(pattern, h.get_text(" ", strip=True)) and h.get("aria-hidden") != "true":
            return h
    raise LookupError(pattern)


def set_text(tag, text):
    tag.clear()
    tag.append(NavigableString(text))


def mark_new(tag):
    tag["class"] = (tag.get("class") or []) + ["reco-new"]
    return tag



# ---------------------------------------------------------------- transformation
NEW_TITLE = "Nourriture pour chien au poulet : recette fraîche | Elmut"
NEW_META = ("Nourriture pour chien au poulet, fraîche et complète : 62 % de poulet, cuite à 90 °C, "
            "sans céréales ni conservateurs. Notre recette la plus légère.")
NEW_H1 = "Nourriture pour chien au poulet"

B = "https://elmut.fr/produits-chien/frais/"
# FAQ v2 : 1 question conservée (surpoids), 4 nouvelles. Chiffres relevés le 22/10/2026 sur les 5 fiches chien.
FAQ = [
    ("Qu'est-ce qui distingue la recette au poulet des autres recettes Elmut ?",
     "C'est la plus légère de nos cinq recettes pour chien : 121,6 kcal pour 100 g et 6,4 % de matières grasses, "
     "contre 129,1 à 144,0 kcal pour la dinde, le porc, le poisson et le bœuf. Rapportée à la matière sèche, "
     "c'est aussi la plus riche en protéines (53,7 %). Et comme c'est un aliment complet, elle peut composer "
     "tous ses repas, jour après jour.", True),
    ("Mon chien est en surpoids, votre recette au poulet est-elle adaptée ?", None, False),
    ("Le poulet cuit est-il bon pour mon chien ?",
     "Oui, et c'est cuit que nous le servons : nos boudins cuisent sous vide à 90 °C. Cette cuisson douce préserve "
     "le jus, le goût et les nutriments du poulet. Et pas d'os à surveiller dans la gamelle : les 62 % de poulet "
     "de la recette sont de la viande, du foie et du cœur. De quoi régaler votre poilu, sans rien à recracher.", True),
    ("Pourquoi du quinoa dans une recette sans céréales ?",
     "Parce que le quinoa n'est pas une céréale : c'est la graine d'une plante cousine de l'épinard et de la "
     "betterave, qu'on appelle souvent pseudo-céréale. Il apporte des protéines végétales que votre poilu digère "
     f'très bien. C\'est lui qui remplace le riz des recettes au <a href="{B}boeuf">bœuf</a> et au '
     f'<a href="{B}porc">porc</a> : poulet, dinde et poisson sont nos trois recettes sans céréales.', True),
    ("Mon chien est allergique au poulet : quelle recette choisir ?",
     f'Orientez-vous vers nos recettes au <a href="{B}boeuf">bœuf</a> ou au <a href="{B}porc">porc</a>, qui ne '
     f'contiennent pas de poulet. Attention, la <a href="{B}poisson">recette au poisson</a> contient du foie de '
     f'poulet. La <a href="{B}dinde">dinde</a> est une autre volaille : demandez l\'avis de votre vétérinaire '
     "avant de la proposer. Et si l'allergie alimentaire n'est qu'un soupçon, lui seul pourra la confirmer.", True),
]


def build(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    # 1. nettoyage : scripts, traceurs, bannière cookies, iframes
    for sel in ["script", "noscript", "iframe", "next-route-announcer", "link[rel=preload]",
                "link[rel=modulepreload]", "link[rel=canonical]", "link[rel=alternate]",
                "meta[property^='og:']", "meta[name^='twitter:']", "#axeptio_overlay", "section.Toastify"]:
        for t in soup.select(sel):
            t.decompose()
    for img in soup.find_all("img", src=re.compile(r"facebook\.com/tr|axeptio")):
        img.decompose()
    styles = soup.find_all("style")
    main_css = max(styles, key=lambda s: len(s.text))
    for st in styles:
        if st is not main_css and ("toastify" in st.text or "Axeptio" in st.text):
            st.decompose()
    main_css.string = localize_css(main_css.text)

    head = soup.head
    for m in head.find_all("meta", attrs={"name": ["robots", "description"]}):
        m.decompose()
    head.append(soup.new_tag("meta", attrs={"name": "robots", "content": "noindex, nofollow, noarchive"}))
    head.append(soup.new_tag("meta", attrs={"name": "description", "content": NEW_META}))
    head.title.string = "Maquette SEO recette poulet | Elmut x datashake"
    faces = soup.new_tag("style")
    faces.string = substitute_faces()
    head.append(faces)
    head.append(soup.new_tag("link", attrs={"rel": "stylesheet", "href": "assets/maquette.css"}))

    # 2. liens et médias en absolu vers elmut.fr
    for t in soup.find_all(href=True):
        if t.name == "a" and t["href"].startswith("/"):
            t["href"] = ORIGIN + t["href"]
    for t in soup.find_all(src=True):
        if t["src"].startswith("/"):
            t["src"] = ORIGIN + t["src"]
    for t in soup.find_all(srcset=True):
        t["srcset"] = re.sub(r"(^|,\s*)(/)", lambda m: m.group(1) + ORIGIN + "/", t["srcset"])
    for t in soup.find_all(style=True):
        t["style"] = re.sub(r"url\((['\"]?)(/)", lambda m: f"url({m.group(1)}{ORIGIN}/", t["style"])

    n = 0

    # 3. Title, meta et H1 : petit H1 en surtitre, le grand titre visible reste tel quel sans balise H1
    title = soup.find("h1")
    title.name = "p"
    h1 = soup.new_tag("h1", attrs={"class": "maquette-h1"})
    h1.string = NEW_H1
    title.insert_before(mark_new(h1))
    n += 1
    title.parent.append(reco(
        soup, n, "Balise title, meta description et H1",
        ["<strong>Title</strong> : « Recette Poulet pour chien | Elmut » devient <strong>« " + NEW_TITLE
         + " »</strong> (57 caractères).",
         "<strong>Meta description</strong> : « Aliment pour chien complet et équilibré, sans céréales, composé "
         "de délicieux poulet propre à la consommation humaine. » devient <strong>« " + NEW_META
         + " »</strong> (147 caractères).",
         "<strong>H1</strong> : <strong>« " + NEW_H1 + " »</strong>, en petit surtitre au-dessus du titre. Le grand "
         "titre « Notre recette au poulet » reste affiché à l'identique, sans balise H1."],
    ))

    # 4. Alt des visuels du hero : ils contiennent la balise <i> en texte brut
    hero_alt = {
        "elmut-sausage-chicken": "Boudin de nourriture fraîche pour chien au poulet Elmut",
        "half-bowl-chicken": "Gamelle de repas frais pour chien au poulet Elmut",
        "bowl-chicken": "Gamelle de nourriture pour chien au poulet Elmut",
    }
    for img in soup.find_all("img", alt="Notre <i>recette</i> au poulet"):
        for key, alt in hero_alt.items():
            if key in img["src"]:
                img["alt"] = alt
                break
    n += 1
    title.parent.append(reco(
        soup, n, "Corriger les alt des visuels du hero",
        "Les trois visuels du hero ont pour alt <strong>« Notre &lt;i&gt;recette&lt;/i&gt; au poulet »</strong> : "
        "la balise HTML du titre est recopiée telle quelle dans l'attribut. Proposition :",
        ["Boudin (elmut-sausage-chicken.webp) : « " + hero_alt["elmut-sausage-chicken"] + " »",
         "Gamelle (bowl-chicken.webp) : « " + hero_alt["bowl-chicken"] + " »",
         "Demi-gamelle (half-bowl-chicken.webp) : « " + hero_alt["half-bowl-chicken"] + " »"],
    ))

    # 5. Alt en anglais de la section protéine (H2 inchangé)
    h_prot = find_h(soup, "h2", r"^Le poulet, la protéine")
    sec_alt = {
        "Chicken dog recipe": "Blancs de poulet, courgette, carotte et quinoa, ingrédients de la recette au poulet Elmut",
        "Chicken dog recipe background": "",
        "Crown illustration": "",
    }
    for img in soup.find_all("img", alt=True):
        if img["alt"] in sec_alt:
            img["alt"] = sec_alt[img["alt"]]
    n += 1
    h_prot.insert_after(reco(
        soup, n, "Alt en anglais à traduire",
        "Les visuels de cette section ont des alt en anglais. Proposition :",
        ["« Chicken dog recipe » (polaroïd « Milou et sa gamelle préf' ») → « " + sec_alt["Chicken dog recipe"] + " »",
         "« Chicken dog recipe background » (fond décoratif) → alt vide (alt=\"\")",
         "« Crown illustration » (couronne décorative) → alt vide (alt=\"\")"],
    ))

    # 6. Informations nutritionnelles : H2 doublé, clone sans espace (texte du titre inchangé)
    new_info = "Informations nutritionnelles"
    clone = soup.find("h2", class_="sr-only", string=re.compile("nutritionnelles"))
    set_text(clone, new_info)
    visible = soup.find("h2", attrs={"data-has-accessible-clone": "true", "aria-label": re.compile("nutritionnelles")})
    n += 1
    visible.insert_after(reco(
        soup, n, "H2 doublé à corriger",
        ["Ce titre existe deux fois dans le code. Un premier H2 masqué (classe sr-only) porte le texte "
         "<strong>« Informationsnutritionnelles »</strong>, sans espace : c'est ce que lisent Google et les "
         "lecteurs d'écran. Le second H2, visible, est découpé lettre par lettre en balises span pour "
         "l'animation et marqué aria-hidden.",
         "Recommandation : un seul H2 lisible, <strong>« " + new_info + " »</strong>, avec l'espace entre les "
         "deux mots. Si l'animation est conservée, le H2 masqué doit porter ce texte exact et l'élément animé "
         "ne doit plus être une balise H2 (un div ou un p suffit)."],
    ))

    # 7. Alt de la tranche (H2 « Votre poilu est unique » inchangé)
    h_poilu = find_h(soup, "h2", r"poilu")
    for img in soup.find_all("img", alt="Sausage slice"):
        img["alt"] = "Tranche de nourriture fraîche pour chien au poulet, avec ses morceaux de légumes"
    n += 1
    h_poilu.insert_after(reco(
        soup, n, "Alt en anglais à traduire",
        "Alt « Sausage slice » (tranche de boudin) → <strong>« Tranche de nourriture fraîche pour chien au "
        "poulet, avec ses morceaux de légumes »</strong>.",
    ))

    # 8. FAQ : H2 inchangé, 5 questions propres au poulet (réponses dépliées dans la maquette)
    h_faq = find_h(soup, "h2", r"questions fraîches")
    items = h_faq.find_next_sibling("div").find_all("details", recursive=False)
    kept = {d.summary.p.get_text(strip=True): d for d in items}
    template = items[0]
    for d in items:
        d.extract()
    container = h_faq.find_next_sibling("div")
    for question, answer, is_new in FAQ:
        d = next(v for k, v in kept.items() if "surpoids" in k) if not is_new else copy.deepcopy(template)
        if is_new:
            set_text(d.summary.p, question)
            answer_p = d.select_one("div > div > p")
            answer_p.clear()
            answer_p.append(BeautifulSoup(answer, "html.parser"))
            mark_new(d)
        d["open"] = ""
        d["data-open"] = "true"
        container.append(d)
    n += 1
    h_faq.insert_after(reco(
        soup, n, "FAQ propre à la recette au poulet",
        ["Le H2 « Les questions fraîches » ne change pas. La FAQ passe à <strong>5 questions</strong> (environ "
         "300 mots), toutes centrées sur le poulet : 4 nouvelles en pointillés, et la question sur le surpoids, "
         "conservée telle quelle.",
         "Les questions « aspect des rations » et « cocktail de vitamines », identiques sur toutes les recettes, "
         "sortent de cette page. Les réponses restent dans l'accordéon actuel, qui alimente déjà le balisage "
         "FAQPage : elles sont dépliées ici pour la lecture."],
    ))

    # 9. Bandeau en bas d'écran
    body = soup.body
    body.insert(0, BeautifulSoup(BANNER_HTML.replace("{N}", str(n)), "html.parser"))
    body.append(BeautifulSoup(TOGGLE_JS, "html.parser"))
    return str(soup)


BANNER_HTML = """
<div class="maquette-banner">
  <div class="maquette-banner-inner">
    <p class="maquette-kicker">Maquette SEO · proposition datashake v2 · octobre 2026</p>
    <p class="maquette-title">elmut.fr/produits-chien/frais/poulet · requête cible « nourriture chien poulet »</p>
    <p class="maquette-legend">
      <span class="legend-box"></span> {N} recommandations en encadré vert
      <span class="legend-new"></span> contenu modifié ou ajouté en pointillés verts
    </p>
    <button type="button" class="maquette-toggle" aria-pressed="false">Masquer les recommandations</button>
  </div>
</div>
"""

TOGGLE_JS = """
<script>
document.querySelector('.maquette-toggle').addEventListener('click', function () {
  var hidden = document.body.classList.toggle('recos-hidden');
  this.textContent = hidden ? 'Afficher les recommandations' : 'Masquer les recommandations';
  this.setAttribute('aria-pressed', hidden);
});
</script>
"""


if __name__ == "__main__":
    cached = CACHE / "rendered.html"
    source = cached.read_text(encoding="utf-8") if cached.exists() else asyncio.run(render())
    (ROOT / "index.html").write_text(build(source), encoding="utf-8")
    print("index.html écrit")
