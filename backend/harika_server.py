"""Entry point for the bundled HARIKA backend (the program the desktop app starts).

Development still uses `python -m uvicorn app.main:app`. The packaged app runs
this file's frozen build; the desktop shell passes --port and HARIKA_DATA_DIR.
"""
import argparse
import multiprocessing


def main() -> None:
    parser = argparse.ArgumentParser(description="HARIKA backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=47801)
    args = parser.parse_args()

    import uvicorn
    from app.main import app

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    multiprocessing.freeze_support()  # required for frozen Windows builds
    main()
