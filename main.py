from pathlib import Path

from file_discovery_inventory import find_pdfs, hash_file, file_stats

pdfs = find_pdfs(Path("test_corpus"))
for pdf in pdfs:
    print(hash_file(pdf), pdf.name)
    stat = file_stats(pdf)
    print("size: ", stat["size"])
    print("mtime: ", stat["mtime"])
    