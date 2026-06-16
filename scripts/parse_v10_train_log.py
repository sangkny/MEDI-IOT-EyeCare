#!/usr/bin/env python3
"""Parse train_v10.py log lines — best composite / GL AUC / epoch."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

EPOCH_RE = re.compile(
    r"epoch (\d+)/\d+ .* GL=([\d.]+) .* composite=([\d.]+)"
)


def parse_log(path: Path) -> dict:
    best_comp = {"epoch": 0, "gl": 0.0, "composite": -1.0}
    best_gl = {"epoch": 0, "gl": -1.0, "composite": 0.0}
    last_epoch = 0
    early_stop = False
    ok_line = ""

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "early_stop" in line:
            early_stop = True
        if line.startswith("OK ") and "composite=" in line:
            ok_line = line.strip()
        m = EPOCH_RE.search(line)
        if not m:
            continue
        ep, gl, comp = int(m.group(1)), float(m.group(2)), float(m.group(3))
        last_epoch = ep
        if comp > best_comp["composite"]:
            best_comp = {"epoch": ep, "gl": gl, "composite": comp}
        if gl > best_gl["gl"]:
            best_gl = {"epoch": ep, "gl": gl, "composite": comp}

    return {
        "last_epoch": last_epoch,
        "best_composite": best_comp,
        "best_gl_auc": best_gl,
        "early_stop": early_stop,
        "ok_line": ok_line,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("log", type=Path)
    args = p.parse_args()
    r = parse_log(args.log)
    bc = r["best_composite"]
    bg = r["best_gl_auc"]
    print(f"last_epoch={r['last_epoch']}")
    print(f"best_composite={bc['composite']:.4f} (ep{bc['epoch']} GL={bc['gl']:.4f})")
    print(f"best_gl_auc={bg['gl']:.4f} (ep{bg['epoch']} composite={bg['composite']:.4f})")
    if r["early_stop"]:
        print("early_stop=yes")
    if r["ok_line"]:
        print(r["ok_line"])


if __name__ == "__main__":
    main()
