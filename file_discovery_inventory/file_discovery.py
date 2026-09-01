from pathlib import Path

def find_pdfs(root: Path):
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() == ".pdf":
            yield p

pdfs = find_pdfs(Path("test_corpus"))
count = 0
for pdf in pdfs:
    print(pdf)
    count +=1

print(count)