"""Maquette SEO annotée de https://elmut.fr/produits-chien/frais/poulet.

Rend la page réelle avec Playwright, retire le JavaScript et les traceurs,
applique les recommandations (title, meta, H1, H2, alt, H2 doublé) et ajoute
le contenu de bas de page de la v2 du draft Surfer « nourriture chien poulet ».
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
NEW_META = ("Nourriture pour chien au poulet, fraîche et complète : 62 % de poulet, cuisson douce à 90 °C, "
            "sans céréales ni conservateurs. Livrée chez vous.")


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

    # 3. Title, meta et H1
    h1 = soup.find("h1")
    h1.clear()
    h1.append(BeautifulSoup("Nourriture pour chien au poulet : notre <i>recette</i> fraîche", "html.parser"))
    mark_new(h1)
    n += 1
    h1.parent.append(reco(
        soup, n, "Balise title, meta description et H1",
        ["<strong>Title</strong> : « Recette Poulet pour chien | Elmut » devient <strong>« " + NEW_TITLE
         + " »</strong> (492 px sur 580).",
         "<strong>Meta description</strong> : « Aliment pour chien complet et équilibré, sans céréales, composé "
         "de délicieux poulet propre à la consommation humaine. » devient <strong>« " + NEW_META
         + " »</strong> (910 px sur 920).",
         "<strong>H1</strong> : « Notre recette au poulet » devient <strong>« Nourriture pour chien au poulet : "
         "notre recette fraîche »</strong>. L'italique sur « recette » peut être conservé."],
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
    h1.parent.append(reco(
        soup, n, "Corriger les alt des visuels du hero",
        "Les trois visuels du hero ont pour alt <strong>« Notre &lt;i&gt;recette&lt;/i&gt; au poulet »</strong> : "
        "la balise HTML du titre est recopiée telle quelle dans l'attribut. Proposition :",
        ["Boudin (elmut-sausage-chicken.webp) : « " + hero_alt["elmut-sausage-chicken"] + " »",
         "Gamelle (bowl-chicken.webp) : « " + hero_alt["bowl-chicken"] + " »",
         "Demi-gamelle (half-bowl-chicken.webp) : « " + hero_alt["half-bowl-chicken"] + " »"],
    ))

    # 5. H2 Les ingrédients
    h_ing = find_h(soup, "h2", r"^Les ingrédients$")
    set_text(h_ing, "Les ingrédients de notre nourriture pour chien au poulet")
    mark_new(h_ing)
    n += 1
    h_ing.insert_after(reco(
        soup, n, "H2 optimisé",
        "« Les ingrédients » devient <strong>« Les ingrédients de notre nourriture pour chien au poulet »</strong>.",
    ))

    # 6. H2 protéine + alt en anglais de la section
    h_prot = find_h(soup, "h2", r"^Le poulet, la protéine")
    set_text(h_prot, "Le poulet, une protéine animale de référence pour votre chien")
    mark_new(h_prot)
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
        soup, n, "H2 optimisé et alt en anglais",
        ["« Le poulet, la protéine de référence. » devient <strong>« Le poulet, une protéine animale de "
         "référence pour votre chien »</strong>.",
         "Les visuels de cette section ont des alt en anglais. Proposition :"],
        ["« Chicken dog recipe » (polaroïd « Milou et sa gamelle préf' ») → « " + sec_alt["Chicken dog recipe"] + " »",
         "« Chicken dog recipe background » (fond décoratif) → alt vide (alt=\"\")",
         "« Crown illustration » (couronne décorative) → alt vide (alt=\"\")"],
    ))

    # 7. Informations nutritionnelles : H2 doublé, clone sans espace
    new_info = "Informations nutritionnelles de la recette au poulet"
    clone = soup.find("h2", class_="sr-only", string=re.compile("nutritionnelles"))
    visible = soup.find("h2", attrs={"data-has-accessible-clone": "true", "aria-label": re.compile("nutritionnelles")})
    set_text(clone, new_info)
    set_text(visible, new_info)
    visible["aria-label"] = new_info
    mark_new(visible)
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

    # 8. Votre poilu est unique
    h_poilu = find_h(soup, "h2", r"poilu")
    h_poilu.clear()
    h_poilu.append(BeautifulSoup(
        'Votre poilu est <span class="text-pistachio-bright">unique</span>,<br/>sa gamelle au poulet aussi',
        "html.parser"))
    mark_new(h_poilu)
    for img in soup.find_all("img", alt="Sausage slice"):
        img["alt"] = "Tranche de nourriture fraîche pour chien au poulet, avec ses morceaux de légumes"
    n += 1
    h_poilu.insert_after(reco(
        soup, n, "H2 optimisé et alt",
        ["« Votre poilu est unique, sa gamelle aussi » devient <strong>« Votre poilu est unique, sa gamelle "
         "au poulet aussi »</strong>.",
         "Alt « Sausage slice » (tranche de boudin) → <strong>« Tranche de nourriture fraîche pour chien au "
         "poulet, avec ses morceaux de légumes »</strong>."],
    ))

    # 9. Un petit extra
    h_extra = find_h(soup, "h2", r"^Un petit extra")
    set_text(h_extra, "Un petit extra ? Nos friandises pour chien")
    mark_new(h_extra)
    n += 1
    h_extra.insert_after(reco(
        soup, n, "H2 optimisé",
        "« Un petit extra ? » devient <strong>« Un petit extra ? Nos friandises pour chien »</strong>.",
    ))

    # 10. FAQ
    h_faq = find_h(soup, "h2", r"questions fraîches")
    set_text(h_faq, "Les questions fraîches sur notre recette au poulet")
    mark_new(h_faq)
    n += 1
    h_faq.insert_after(reco(
        soup, n, "H2 optimisé",
        "« Les questions fraîches » devient <strong>« Les questions fraîches sur notre recette au poulet »</strong>. "
        "Les questions et réponses existantes ne changent pas.",
    ))

    # 11. Contenu de bas de page, après la FAQ
    faq_section = h_faq.find_parent("section")
    bottom = BeautifulSoup(BOTTOM_HTML, "html.parser").section
    faq_section.insert_after(bottom)
    words = len(bottom.get_text(" ", strip=True).split())
    n += 1
    bottom.find("div", class_="maquette-container").insert(0, reco(
        soup, n, "Contenu de bas de page (à placer après la FAQ, avant le footer)",
        [f"Environ {words} mots ajoutés, centrés sur « nourriture chien poulet » et ses variantes. C'est le seul "
         "contenu ajouté : le texte existant de la page ne change pas.",
         "Liens internes vers /produits-chien, les recettes bœuf, porc et poisson, et deux articles du blog."],
    ))

    # 12. Bandeau en bas d'écran
    body = soup.body
    body.insert(0, BeautifulSoup(BANNER_HTML.replace("{N}", str(n)), "html.parser"))
    body.append(BeautifulSoup(TOGGLE_JS, "html.parser"))
    return str(soup)


BANNER_HTML = """
<div class="maquette-banner">
  <div class="maquette-banner-inner">
    <p class="maquette-kicker">Maquette SEO · proposition datashake · octobre 2026</p>
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

BOTTOM_HTML = """
<section class="maquette-bottom reco-new-section">
 <div class="maquette-container">
  <h2>Pourquoi choisir une nourriture fraîche au poulet pour votre chien ?</h2>
  <p>Le poulet est l'une des viandes les plus utilisées dans l'alimentation du chien, et ce n'est pas un hasard.
  Cette volaille apporte des protéines animales de qualité, peu de matières grasses et un goût que la plupart des
  chiens apprécient. Chez Elmut, c'est notre best-seller : la recette que nos poilus réclament le plus.</p>
  <p>La différence se fait sur la façon de le préparer. Nos repas frais sont cuits doucement à 90 °C pour préserver
  les nutriments, puis livrés chez vous en boudins à conserver au réfrigérateur. Pas de légumineuses, qui peuvent
  réduire la digestibilité, pas de conservateurs ni d'additifs technologiques : uniquement des ingrédients de
  qualité humaine, pour plus de qualité et de traçabilité.</p>
  <p>Chaque ingrédient a un rôle précis dans la gamelle. La viande de poulet apporte l'essentiel des protéines. Le
  foie et le cœur, deux abats riches en nutriments, complètent cet apport : le foie est une source naturelle de
  vitamine A, le cœur de taurine. La courgette et la carotte apportent fibres et vitamines, le quinoa et la fécule
  de pomme de terre fournissent l'énergie, l'huile de colza les acides gras oméga 3 et oméga 6 utiles à la peau et
  au pelage, et le carbonate de calcium équilibre le rapport entre calcium et phosphore.</p>
  <p>Le résultat : une alimentation complète qui couvre les besoins quotidiens de votre chien, adaptée aussi bien
  aux gourmands qu'aux estomacs sensibles. Envie de varier ? Découvrez toutes nos
  <a href="https://elmut.fr/produits-chien">recettes de repas frais pour chien</a>.</p>

  <h2>Nourriture chien poulet : repas frais, croquettes ou pâtée ?</h2>
  <p>Le poulet se retrouve dans tous les types d'aliments pour chien, des croquettes au poulet aux pâtées en boîte.
  Mais à ingrédient égal, le mode de fabrication change tout : température de cuisson, teneur en eau, mode de
  conservation.</p>
  <div class="maquette-table-wrap">
  <table>
   <thead><tr><th>Critère</th><th>Repas frais Elmut au poulet</th><th>Croquettes pour chien</th><th>Pâtée industrielle</th></tr></thead>
   <tbody>
    <tr><td>Fabrication</td><td>Cuisson douce à 90 °C</td><td>Extrusion à haute température</td><td>Stérilisation en boîte ou en barquette</td></tr>
    <tr><td>Humidité</td><td>75,6 %</td><td>Environ 8 à 12 %</td><td>Souvent 75 à 80 %</td></tr>
    <tr><td>Texture</td><td>Viande et légumes, proche du fait maison</td><td>Granulés secs</td><td>Mousse ou bouchées en sauce</td></tr>
    <tr><td>Conservation</td><td>Réfrigérateur, 5 jours après ouverture, congélation possible</td><td>Température ambiante, sac bien fermé</td><td>Longue durée avant ouverture, puis réfrigérateur</td></tr>
   </tbody>
  </table>
  </div>
  <p>Les croquettes restent pratiques, mais leur faible teneur en eau pousse le chien à boire davantage pour
  compenser. Avec 75,6 % d'humidité, notre recette au poulet participe à l'hydratation de votre chien à chaque
  repas.</p>
  <p>Le mode de cuisson compte aussi. Les croquettes sont cuites par extrusion à haute température, un procédé qui
  permet une longue conservation à température ambiante. Notre recette est cuite à 90 °C puis conservée au froid :
  c'est le froid, et non des conservateurs, qui préserve sa fraîcheur. Pour aller plus loin sur la composition des
  croquettes, lisez notre article sur les
  <a href="https://elmut.fr/blog/articles/croquettes-avec-ou-sans-cereales">croquettes avec ou sans céréales</a>.</p>

  <h2>Quelle quantité de nourriture au poulet donner à votre chien ?</h2>
  <p>La bonne ration dépend du poids de votre chien, de son âge, de sa race, de son niveau d'activité et de sa
  stérilisation. C'est pour cela que chaque plan Elmut est personnalisé : vos réponses au questionnaire nous
  permettent de calculer la ration quotidienne adaptée à sa morphologie et à son mode de vie.</p>
  <p>Pour vous donner un repère, notre recette au poulet apporte 121,6 kcal pour 100 g. Pour un chiot, les besoins
  sont différents et évoluent vite : notre guide
  <a href="https://elmut.fr/blog/articles/quelle-quantite-de-nourriture-pour-un-chiot-">quelle quantité de
  nourriture pour un chiot</a> vous aide à y voir clair.</p>
  <p>Si votre chien mange aujourd'hui des croquettes, la transition se fait sur 7 jours : 25 % de repas Elmut les
  jours 1 et 2, 50 % les jours 3 et 4, 75 % les jours 5 et 6, puis 100 % à partir du jour 7. Son estomac s'adapte
  ainsi en douceur à sa nouvelle alimentation.</p>
  <p>Le prix suit la même logique : il dépend de la race de votre chien, de son âge, de son poids et de la formule
  choisie, demi-pension ou pension complète. Le questionnaire vous donne un tarif précis, et vous pouvez commencer
  par un essai de 2 semaines.</p>

  <h2>Poulet et chien : les précautions à connaître</h2>
  <h3>Allergies et intolérances au poulet</h3>
  <p>Le poulet convient à la grande majorité des chiens, y compris aux estomacs sensibles. Il fait pourtant partie,
  avec le bœuf et les produits laitiers, des sources de protéines le plus souvent impliquées dans les allergies
  alimentaires du chien.</p>
  <p>Démangeaisons, rougeurs de la peau, otites à répétition, pelage terne ou troubles digestifs peuvent signaler
  une allergie ou une intolérance. Dans ce cas, parlez-en à votre vétérinaire : lui seul peut poser un diagnostic,
  généralement grâce à un régime d'éviction. Si le poulet doit sortir de la gamelle, nos recettes au
  <a href="https://elmut.fr/produits-chien/frais/boeuf">bœuf</a>, au
  <a href="https://elmut.fr/produits-chien/frais/porc">porc</a> ou au
  <a href="https://elmut.fr/produits-chien/frais/poisson">poisson</a> prennent le relais avec une autre source de
  protéines.</p>
  <h3>Blanc de poulet : un complément, pas un repas</h3>
  <p>Vous pouvez donner du blanc de poulet à votre chien, à condition qu'il soit cuit, nature, sans peau, sans os et
  sans assaisonnement (ni sel, ni ail, ni oignon). Il reste un complément : servi seul, il ne couvre pas les
  besoins de votre chien en calcium, en vitamines et en minéraux. C'est tout l'intérêt d'une recette complète comme
  la nôtre.</p>
  <h3>Os de poulet cuits : un vrai danger</h3>
  <p>Cuits, les os de poulet se brisent en éclats pointus qui peuvent blesser la bouche, l'œsophage ou l'intestin.
  Ne laissez pas votre chien accéder aux carcasses. S'il en a avalé, surveillez-le et contactez votre vétérinaire
  au moindre signe inhabituel (vomissements, abattement, sang dans les selles). Notre recette ne contient aucun
  os : uniquement de la viande, du foie et du cœur de poulet.</p>
 </div>
</section>
"""


if __name__ == "__main__":
    cached = CACHE / "rendered.html"
    source = cached.read_text(encoding="utf-8") if cached.exists() else asyncio.run(render())
    (ROOT / "index.html").write_text(build(source), encoding="utf-8")
    print("index.html écrit")
