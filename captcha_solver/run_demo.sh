#!/bin/sh
# End-to-end demo: generate a training set and a test set with the exact
# captcha.php drawing code, build the k-NN model, measure accuracy, and solve
# a handful of fresh images.
#
#   sh captcha_solver/run_demo.sh [WORKDIR] [TRAIN_COUNT] [TEST_COUNT]
set -e

HERE=$(cd "$(dirname "$0")" && pwd)
WORK=${1:-"$HERE/data"}
TRAIN=${2:-8000}
TEST=${3:-500}

rm -rf "$WORK/train" "$WORK/test" "$WORK/demo"
echo "== generating $TRAIN training captchas"
php "$HERE/generate.php" --out "$WORK/train" --count "$TRAIN"
echo "== generating $TEST test captchas"
php "$HERE/generate.php" --out "$WORK/test" --count "$TEST"

echo "== training"
python3 "$HERE/solver.py" train --data "$WORK/train" --model "$WORK/model.npz"

echo "== evaluating"
python3 "$HERE/solver.py" eval --data "$WORK/test" --model "$WORK/model.npz"

echo "== solving 5 fresh captchas (file, prediction, per-character confidence)"
php "$HERE/generate.php" --out "$WORK/demo" --count 5 >/dev/null
python3 "$HERE/solver.py" solve --model "$WORK/model.npz" "$WORK"/demo/*.png
