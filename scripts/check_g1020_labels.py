#!/usr/bin/env python3
"""G1020 json 라벨 구조 확인 (GPU Docker 1회용)."""
import json
import glob

files = glob.glob("/dataset/Glaucoma_extra2/G1020/G1020/Images/*.json")
print(f"총 json 라벨: {len(files)}")
sample = json.load(open(files[0]))
labels = {s["label"] for s in sample["shapes"]}
print(f"라벨 종류: {labels}")
print(f"shapes 개수: {len(sample['shapes'])}")
