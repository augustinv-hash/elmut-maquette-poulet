# Maquette SEO : elmut.fr/produits-chien/frais/poulet

Maquette statique annotée de la page https://elmut.fr/produits-chien/frais/poulet, avec les recommandations SEO datashake pour la requête « nourriture chien poulet ». Démo en `noindex`, non destinée à être indexée.

- Encadrés verts : recommandations (title, meta, H1, alt des visuels du hero, H2 de la FAQ).
- Contours pointillés verts : titres modifiés et contenu ajouté en bas de page.
- Le texte existant de la page n'est pas modifié.
- Bouton « Masquer les recommandations » : affiche la page optimisée sans les annotations.

Source du contenu de bas de page : v2 du draft Surfer « nourriture chien poulet » (octobre 2026).

## Reconstruire

```bash
cd ~/Documents/CODE/elmut-maquette-poulet
~/Documents/CODE/seo-tools/.venv/bin/python -I scripts/build.py
```

Le script rend la page réelle avec Playwright (cache dans `scripts/cache/`, à supprimer pour forcer un nouveau rendu), retire le JavaScript et les traceurs, puis applique les recommandations. Polices : mêmes règles que la maquette /produits-chien (OFL en local, PP Pangaia et Maison Neue remplacées par Playfair Display et Archivo).
