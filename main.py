"""Interactive command-line entry point for the ingestion pipeline."""

import psycopg

from thelibrary.config import DATABASE_URL
from thelibrary.mounting import DRIVE_ID, resolve_corpus_root
from thelibrary.pipeline import (
    discover_incremental,
    ingest_files,
    run_chunking,
    run_embedding,
    run_extraction,
    run_metadata_backfill,
)


def main():
    """Run the interactive ingest/update menu."""
    main_root = resolve_corpus_root(DRIVE_ID) / "Files"
    print("Welcome to TheLibrary. What would you like to do?")
    print("-------------------------------------------------")
    print("Current root: " + str(main_root))
    print("(1) Load an entire new folder")
    print("(2) Check for changed/new files")
    choice = input("Input: ")

    if choice == "1":
        print("What is your desired directory?")
        folder = input("Desired Directory: ")
        with psycopg.connect(DATABASE_URL) as conn:
            root = main_root
            print("Begin ingesting files...")
            print("-" * 20)
            ingest_files(conn, root, folder, DRIVE_ID)
            print("-" * 20)
            print("...End ingesting files")
            print()
            print("Begin extraction...")
            print("-" * 20)
            run_extraction(conn, root=root)
            print("-" * 20)
            print("...End extraction")
            print()
            print("Begin backfill...")
            print("-" * 20)
            run_metadata_backfill(conn, root=root)
            print("-" * 20)
            print("...End backfill")
            print()
            print("Begin chunking...")
            print("-" * 20)
            run_chunking(conn)
            print("-" * 20)
            print("...End chunking")
            print()
            print("Begin embedding...")
            print("-" * 20)
            run_embedding(conn)
            print("-" * 20)
            print("...End embedding")
    elif choice == "2":
        print("What is your desired directory?")
        folder = input("Desired Directory: ")
        with psycopg.connect(DATABASE_URL) as conn:
            root = main_root / folder
            discover_incremental(conn, root, DRIVE_ID)
    else:
        print("Choice not understood. Exiting...")


if __name__ == "__main__":
    main()
