# Solver du captcha image de MyBB

Exercice : résoudre automatiquement le captcha généré par `captcha.php`, en
s'appuyant sur la façon dont il est construit plutôt que sur un OCR générique.

Tout tourne hors-ligne : `generate.php` reproduit le rendu de `captcha.php`
(mêmes fonctions de dessin, mêmes polices de `inc/captcha_fonts/`), ce qui
permet de fabriquer autant d'images étiquetées qu'on veut pour entraîner et
mesurer le solver.

## Ce que la construction révèle

En lisant `captcha.php` et `inc/class_captcha.php` :

| Élément | Valeur dans le code | Conséquence pour le solver |
| --- | --- | --- |
| Taille | 200×60, fond blanc, bordure noire 1 px | Géométrie fixe, bordure facile à ignorer |
| Bruit (lignes, arcs, carrés) | `rand(150, 255)` sur chaque canal | Toujours clair |
| Points | `rand(200, 255)` sur chaque canal | Toujours très clairs |
| Texte | `rand(0, 200)` sur chaque canal, ombre à +20 | Au moins un canal < 150 dans ~98 % des cas |
| Longueur | `random_str(5)` | Toujours 5 caractères |
| Position | `pos_x = spacing/4 + i*spacing` = 10 + 40·i | Segmentation sur une grille fixe de 40 px |
| Polices | 2 fichiers TTF, taille 20–32, rotation ±30° | Espace de variation petit et fini |
| Validation | `my_strtolower()` des deux côtés | 36 classes au lieu de 62 |

Le point clé : le bruit et le texte vivent dans des plages de couleurs
presque disjointes. Un seuil `min(R, G, B) < 150` efface le bruit et garde le
texte, sans aucun filtrage morphologique.

## Pipeline (`solver.py`)

1. **Masque d'encre** : `min(R,G,B) < 150`, bordure mise à zéro.
   Repli à 215 pour une cellule vide (caractère tiré avec une couleur claire).
2. **Segmentation** : composantes connexes 8-voisinage, chaque composante est
   attribuée à la cellule de 40 px qui contient le plus de ses pixels ; une
   composante à cheval (glyphes qui se touchent) est coupée pixel par pixel.
3. **Normalisation** : recadrage sur l'encre, remplissage en carré,
   rééchantillonnage 24×24, vecteur unitaire, plus hauteur et largeur absolues
   (pour distinguer un « o » minuscule d'un grand « O »).
4. **Classification** : k plus proches voisins (k = 3, distance euclidienne)
   sur des glyphes extraits de captchas produits par `generate.php`.

## Utilisation

```sh
# Tout en une commande (génération, entraînement, évaluation, démo)
sh captcha_solver/run_demo.sh

# Ou étape par étape
php captcha_solver/generate.php --out data/train --count 8000
php captcha_solver/generate.php --out data/test  --count 500
python3 captcha_solver/solver.py train --data data/train --model model.npz
python3 captcha_solver/solver.py eval  --data data/test  --model model.npz
python3 captcha_solver/solver.py solve --model model.npz image.png
```

`solve` affiche le fichier, le texte prédit et une confiance par caractère.
Une image récupérée sur un forum réel (`captcha.php?imagehash=…`) se traite
de la même façon, c'est le même PNG 200×60.

Dépendances : PHP avec GD + FreeType, Python 3 avec `numpy` et `Pillow`.
L'entraînement sur 8 000 captchas prend moins d'une minute.

## Résultats

Modèle entraîné sur 12 000 captchas (60 000 glyphes), évalué sur 500 captchas
jamais vus :

| Mesure | Résultat |
| --- | --- |
| Caractères corrects | 96,0 % |
| Captchas entiers corrects | 81,4 % |

41 des 99 erreurs de caractère sont des confusions `0` ↔ `o`. Elles sont
intrinsèques au captcha : la police MINYN dessine le chiffre 0 comme un
« o » minuscule, la police edmunds dessine 0 et O quasi identiques, et la
validation ignore la casse. Un humain ne peut pas faire mieux sur ces cas.
Sans elles, le solver est à ~97,7 % par caractère.

Comme `validate_captcha()` supprime la ligne et propose une nouvelle image
après un échec, un taux de 81 % par tentative suffit largement pour passer
un formulaire automatiquement : l'espérance est d'environ 1,2 essai.

## Pourquoi ça marche, et comment durcir le captcha

Les faiblesses exploitées, par ordre d'importance :

1. **Couleurs de bruit et de texte séparables par un seuil.** Faire chevaucher
   complètement les plages (bruit sombre aussi) ou dessiner le bruit *après*
   le texte avec la même couleur.
2. **Grille de positions fixe.** Décaler aléatoirement chaque caractère,
   faire varier l'espacement, laisser les glyphes se chevaucher.
3. **Validation insensible à la casse** avec des polices où `0`/`O`/`o` et
   `1`/`l`/`I` sont confondus : cela n'aide que l'attaquant, qui gagne des
   classes, et nuit aux humains. Retirer les caractères ambigus de l'alphabet.
4. **Rendu entièrement reproductible** (code et polices publics) : un
   attaquant génère son jeu d'entraînement gratuitement. C'est inhérent à un
   logiciel libre ; la vraie réponse est de proposer un captcha externe
   (reCAPTCHA, hCaptcha, Turnstile, déjà supportés par `class_captcha.php`).

## Fichiers

- `generate.php` : copie autonome du rendu de `captcha.php` (à resynchroniser
  si `captcha.php` change).
- `solver.py` : prétraitement, segmentation, k-NN, commandes `train` /
  `eval` / `solve`.
- `run_demo.sh` : enchaîne tout.
- `data/` et `*.npz` sont ignorés par git.
