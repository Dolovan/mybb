#!/usr/bin/env python3
"""
Solver for MyBB's built-in image captcha (captcha.php).

The solver is built on what the generator leaks:

  * The image is always 200x60 with a white background and a 1px black border.
  * Every noise primitive (lines, arcs, squares, dots) uses colours whose
    three channels are >= 150, while the text colour has every channel <= 200
    (shadow: <= 220). Thresholding min(R, G, B) < 150 therefore erases the
    noise almost entirely and keeps the glyphs.
  * The string always has 5 characters and character i is drawn at
    x = 10 + 40 * i, so segmentation is a fixed 40px grid, refined with
    connected components so that a rotated glyph spilling into the
    neighbouring cell is attributed to the right character.
  * Validation is case-insensitive, so only 36 classes have to be told apart.
  * There are only two fonts, 13 font sizes and 61 rotation angles. A k-NN
    classifier on glyphs rendered by the same code (generate.php) covers that
    space densely with a few thousand training captchas.

Usage:
  python3 solver.py train --data DIR --model model.npz
  python3 solver.py eval  --data DIR --model model.npz
  python3 solver.py solve --model model.npz IMAGE [IMAGE ...]
  python3 solver.py show  --model model.npz --out stages.png IMAGE

DIR is a directory produced by generate.php (PNG files + labels.txt).
"""

import argparse
import os
import sys
from collections import Counter

import numpy as np
from PIL import Image

IMG_W, IMG_H = 200, 60
NCHARS = 5
CELL_W = IMG_W // NCHARS          # 40 px per character
INK_THRESHOLD = 150               # noise channels are always >= 150
FALLBACK_THRESHOLD = 215          # used only when a cell looks empty
MIN_COMPONENT = 4                 # drop anti-aliasing specks smaller than this
GLYPH_SIZE = 24                   # normalised glyph is GLYPH_SIZE x GLYPH_SIZE
SIZE_WEIGHT = 0.6                 # weight of the (height, width) features vs the pixels
CLASSES = "0123456789abcdefghijklmnopqrstuvwxyz"


# --------------------------------------------------------------------------
# Pre-processing
# --------------------------------------------------------------------------

def load_rgb(path):
    img = Image.open(path).convert("RGB")
    if img.size != (IMG_W, IMG_H):
        img = img.resize((IMG_W, IMG_H), Image.BILINEAR)
    return np.asarray(img, dtype=np.uint8)


def ink_mask(rgb, threshold=INK_THRESHOLD):
    """Pixels that cannot be noise: at least one channel below the threshold."""
    mask = rgb.min(axis=2) < threshold
    # The 1px border is pure black; it is not part of any glyph.
    mask[0, :] = mask[-1, :] = False
    mask[:, 0] = mask[:, -1] = False
    return mask


def connected_components(mask):
    """8-connected labelling. Returns (labels, n) with labels in 1..n."""
    h, w = mask.shape
    labels = np.zeros((h, w), dtype=np.int32)
    current = 0
    ys, xs = np.nonzero(mask)
    for y0, x0 in zip(ys, xs):
        if labels[y0, x0]:
            continue
        current += 1
        stack = [(y0, x0)]
        labels[y0, x0] = current
        while stack:
            y, x = stack.pop()
            for dy in (-1, 0, 1):
                ny = y + dy
                if ny < 0 or ny >= h:
                    continue
                for dx in (-1, 0, 1):
                    nx = x + dx
                    if nx < 0 or nx >= w or labels[ny, nx] or not mask[ny, nx]:
                        continue
                    labels[ny, nx] = current
                    stack.append((ny, nx))
    return labels, current


def segment(rgb):
    """Split the captcha into NCHARS binary cells, one glyph each.

    Each connected component of the ink mask is attributed to the 40px cell
    that holds most of its pixels. Components that straddle two cells
    (touching glyphs) are split pixel by pixel along the cell boundary.
    """
    mask = ink_mask(rgb)
    cells = np.zeros((NCHARS, IMG_H, IMG_W), dtype=bool)
    labels, n = connected_components(mask)
    for k in range(1, n + 1):
        ys, xs = np.nonzero(labels == k)
        if len(ys) < MIN_COMPONENT:
            continue
        cols = np.clip(xs // CELL_W, 0, NCHARS - 1)
        counts = np.bincount(cols, minlength=NCHARS)
        best = int(counts.argmax())
        if counts[best] >= 0.8 * len(ys):
            cells[best, ys, xs] = True
        else:
            cells[cols, ys, xs] = True

    # A character whose colour happens to be light (all channels >= 150)
    # vanishes at the strict threshold. Retry that cell alone with a looser
    # threshold: the noise comes back, but the k-NN still has a chance.
    for i in range(NCHARS):
        if cells[i].sum() < 2 * MIN_COMPONENT:
            loose = ink_mask(rgb, FALLBACK_THRESHOLD)
            x0, x1 = i * CELL_W, (i + 1) * CELL_W
            cell = np.zeros_like(loose)
            cell[:, x0:x1] = loose[:, x0:x1]
            cells[i] = cell
    return cells


def normalise_glyph(cell):
    """Crop the cell to its ink, pad to a square and resample to GLYPH_SIZE.

    The square resampling makes the shape scale-invariant, which is what we
    want for the random font size, but it also hides the one thing that tells
    '0' from 'o' (validation is case-insensitive, so 'o' and 'O' are one
    class). The absolute height and width of the glyph are therefore appended
    as two extra features.
    """
    ys, xs = np.nonzero(cell)
    if len(ys) == 0:
        return np.zeros(GLYPH_SIZE * GLYPH_SIZE + 2, dtype=np.float32)
    crop = cell[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = crop.shape
    side = max(h, w)
    square = np.zeros((side, side), dtype=np.uint8)
    oy, ox = (side - h) // 2, (side - w) // 2
    square[oy:oy + h, ox:ox + w] = crop * 255
    small = Image.fromarray(square).resize((GLYPH_SIZE, GLYPH_SIZE), Image.BOX)
    vec = np.asarray(small, dtype=np.float32).ravel() / 255.0
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    size = np.array([h / IMG_H, w / CELL_W], dtype=np.float32) * SIZE_WEIGHT
    return np.concatenate([vec, size])


def features(path):
    rgb = load_rgb(path)
    return np.stack([normalise_glyph(c) for c in segment(rgb)])


# --------------------------------------------------------------------------
# k-NN model
# --------------------------------------------------------------------------

def read_labels(data_dir):
    with open(os.path.join(data_dir, "labels.txt")) as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line:
                continue
            name, text = line.split("\t")
            yield os.path.join(data_dir, name), text.lower()


def train(data_dir, model_path):
    feats, labels = [], []
    for n, (path, text) in enumerate(read_labels(data_dir), 1):
        if len(text) != NCHARS:
            continue
        feats.append(features(path))
        labels.extend(CLASSES.index(ch) for ch in text)
        if n % 500 == 0:
            print(f"  {n} captchas processed", file=sys.stderr)
    X = np.concatenate(feats).astype(np.float16)
    y = np.asarray(labels, dtype=np.int16)
    np.savez_compressed(model_path, X=X, y=y)
    print(f"model: {len(y)} glyphs from {len(feats)} captchas -> {model_path}")


class Model:
    def __init__(self, path, k=5):
        data = np.load(path)
        self.X = data["X"].astype(np.float32)
        self.y = data["y"].astype(np.int64)
        self.k = k
        self.sq = (self.X ** 2).sum(axis=1)

    def classify(self, glyphs):
        """glyphs: (n, D) feature vectors -> list of (char, confidence)."""
        # Squared euclidean distance: |a|^2 + |b|^2 - 2 a.b
        d2 = (glyphs ** 2).sum(axis=1)[:, None] + self.sq[None, :] - 2.0 * (glyphs @ self.X.T)
        idx = np.argpartition(d2, self.k, axis=1)[:, :self.k]
        out = []
        for row, near in zip(d2, idx):
            votes = np.zeros(len(CLASSES))
            for j in near:
                votes[self.y[j]] += 1.0 / (1e-3 + max(row[j], 0.0))
            best = int(votes.argmax())
            out.append((CLASSES[best], float(votes[best] / max(votes.sum(), 1e-9))))
        return out

    def solve(self, path):
        preds = self.classify(features(path))
        return "".join(ch for ch, _ in preds), [c for _, c in preds]


def visualise(model, path, out_path, scale=3):
    """Write a PNG showing every stage of the pipeline for one captcha."""
    from PIL import ImageDraw

    rgb = load_rgb(path)
    mask = ink_mask(rgb)
    cells = segment(rgb)
    glyphs = np.stack([normalise_glyph(c) for c in cells])
    preds = model.classify(glyphs)
    text = "".join(ch for ch, _ in preds)

    # Stage images, all 200x60 so they stack nicely.
    original = Image.fromarray(rgb)
    mask_img = Image.fromarray(np.where(mask, 0, 255).astype(np.uint8)).convert("RGB")
    palette = [(220, 40, 40), (40, 150, 40), (40, 80, 220), (200, 120, 0), (140, 40, 180)]
    seg = np.full((IMG_H, IMG_W, 3), 255, dtype=np.uint8)
    for i, cell in enumerate(cells):
        seg[cell] = palette[i]
    seg_img = Image.fromarray(seg)
    draw = ImageDraw.Draw(seg_img)
    for i in range(1, NCHARS):
        draw.line([(i * CELL_W, 0), (i * CELL_W, IMG_H - 1)], fill=(200, 200, 200))

    # Normalised glyphs, one per cell, drawn 48x48 under their prediction.
    glyph_row = Image.new("RGB", (IMG_W, IMG_H), "white")
    for i, (vec, (ch, conf)) in enumerate(zip(glyphs, preds)):
        pix = vec[:GLYPH_SIZE * GLYPH_SIZE]
        pix = pix / (pix.max() or 1.0) * 255
        g = Image.fromarray(pix.reshape(GLYPH_SIZE, GLYPH_SIZE).astype(np.uint8)).convert("RGB")
        g = Image.eval(g, lambda v: 255 - v).resize((36, 36), Image.NEAREST)
        glyph_row.paste(g, (i * CELL_W + 2, 2))
        ImageDraw.Draw(glyph_row).text((i * CELL_W + 2, 42), f"{ch} {conf:.2f}", fill=palette[i])

    stages = [
        ("1. captcha", original),
        ("2. masque min(R,G,B) < %d" % INK_THRESHOLD, mask_img),
        ("3. segmentation en %d cellules de %d px" % (NCHARS, CELL_W), seg_img),
        ("4. glyphes normalises %dx%d + k-NN" % (GLYPH_SIZE, GLYPH_SIZE), glyph_row),
    ]
    label_h = 14
    sheet = Image.new("RGB", (IMG_W * scale, len(stages) * (IMG_H * scale + label_h) + 2 * label_h), "white")
    d = ImageDraw.Draw(sheet)
    y = 0
    for title, img in stages:
        d.text((4, y), title, fill=(0, 0, 0))
        y += label_h
        sheet.paste(img.resize((IMG_W * scale, IMG_H * scale), Image.NEAREST), (0, y))
        y += IMG_H * scale
    d.text((4, y + 2), f"solution : {text}", fill=(0, 0, 0))
    sheet.save(out_path)
    return text


def evaluate(data_dir, model_path, k):
    model = Model(model_path, k)
    n_captcha = n_captcha_ok = n_char = n_char_ok = 0
    confusions = Counter()
    for path, text in read_labels(data_dir):
        if len(text) != NCHARS:
            continue
        pred, _ = model.solve(path)
        n_captcha += 1
        n_captcha_ok += pred == text
        for p, t in zip(pred, text):
            n_char += 1
            n_char_ok += p == t
            if p != t:
                confusions[(t, p)] += 1
    print(f"captchas: {n_captcha_ok}/{n_captcha} = {100.0 * n_captcha_ok / max(n_captcha, 1):.1f}%")
    print(f"chars:    {n_char_ok}/{n_char} = {100.0 * n_char_ok / max(n_char, 1):.2f}%")
    if confusions:
        print("most common confusions (truth -> prediction):")
        for (t, p), c in confusions.most_common(10):
            print(f"  {t} -> {p}: {c}")


# --------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("train", help="build the k-NN model from a generate.php directory")
    p.add_argument("--data", required=True)
    p.add_argument("--model", default="model.npz")

    p = sub.add_parser("eval", help="measure accuracy on a labelled directory")
    p.add_argument("--data", required=True)
    p.add_argument("--model", default="model.npz")
    p.add_argument("-k", type=int, default=5)

    p = sub.add_parser("solve", help="print the text of one or more captcha images")
    p.add_argument("--model", default="model.npz")
    p.add_argument("-k", type=int, default=5)
    p.add_argument("images", nargs="+")

    p = sub.add_parser("show", help="write a PNG with every intermediate stage and the solution")
    p.add_argument("--model", default="model.npz")
    p.add_argument("-k", type=int, default=3)
    p.add_argument("--out", required=True)
    p.add_argument("image")

    args = ap.parse_args(argv)
    if args.cmd == "train":
        train(args.data, args.model)
    elif args.cmd == "eval":
        evaluate(args.data, args.model, args.k)
    elif args.cmd == "show":
        text = visualise(Model(args.model, args.k), args.image, args.out)
        print(f"{args.image}\t{text}\t-> {args.out}")
    else:
        model = Model(args.model, args.k)
        for image in args.images:
            text, conf = model.solve(image)
            print(f"{image}\t{text}\t{' '.join(f'{c:.2f}' for c in conf)}")


if __name__ == "__main__":
    main()
