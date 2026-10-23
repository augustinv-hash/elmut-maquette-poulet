# Maquette SEO : elmut.fr/produits-chien/frais/poulet

Maquette statique annotée de la page https://elmut.fr/produits-chien/frais/poulet, avec les recommandations SEO datashake pour la requête « nourriture chien poulet ». Démo en `noindex`, non destinée à être indexée.

- Version 2 (22/10/2026), suite au retour d'Elmut du 21/10 : aucun bloc de texte en bas de page.
- Encadrés verts : recommandations (title, meta, petit H1 en surtitre, alt du hero et alt en anglais, H2 « Informations nutritionnelles » doublé et sans espace, FAQ propre au poulet).
- Contours pointillés verts : H1 ajouté et nouvelles questions de la FAQ, réponses dépliées pour la lecture.
- Le texte existant de la page n'est pas modifié.
- Bouton « Masquer les recommandations » : affiche la page optimisée sans les annotations.

Chiffres de la FAQ relevés le 22/10/2026 sur les 5 fiches recettes chien. Brief Corpus « nourriture chien poulet » (dossier Elmut).

## Reconstruire

```bash
cd ~/Documents/CODE/elmut-maquette-poulet
~/Documents/CODE/seo-tools/.venv/bin/python -I scripts/build.py
```

Le script rend la page réelle avec Playwright (cache dans `scripts/cache/`, à supprimer pour forcer un nouveau rendu), retire le JavaScript et les traceurs, puis applique les recommandations. Polices : mêmes règles que la maquette /produits-chien (OFL en local, PP Pangaia et Maison Neue remplacées par Playfair Display et Archivo).
