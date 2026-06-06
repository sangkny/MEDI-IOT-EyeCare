# MEDI 회귀 · Git 운영

SSOT: idea-collection `book/appendix/medi-regression-guide.md` · `projects/docs/medi-regression-guide.md`

```bash
cd ../..   # projects/
bash MEDI-IOT-EyeCare/scripts/medi-regression.sh quick   # ~30s
bash MEDI-IOT-EyeCare/scripts/medi-regression.sh unit    # ~15min
bash MEDI-IOT-EyeCare/scripts/medi-regression.sh core    # ~70min
```

안전 커밋:

```bash
MSG="feat: ..." PUSH=1 bash scripts/git_commit_safe.sh path/to/file.py
```
