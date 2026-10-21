import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))

from Scripts import recovery_fetcher


def main():
    parser = argparse.ArgumentParser(description="Download and verify a macOS recovery image.")
    parser.add_argument("--macos", required=True, help="macOS major version, for example 26")
    parser.add_argument("--dest", help="destination folder")
    parser.add_argument("--print-board", action="store_true", help="print the board id and exit")
    args = parser.parse_args()

    major = int(args.macos.split(".")[0])
    darwin = major + 9 if major <= 15 else major - 1
    fetcher = recovery_fetcher.RecoveryFetcher()
    board = fetcher.get_board(str(darwin))
    if not board:
        print("No board known for macOS {}".format(args.macos), file=sys.stderr)
        return 1

    if args.print_board:
        print(board["board_id"])
        return 0
    if not args.dest:
        parser.error("--dest is required")

    os.makedirs(args.dest, exist_ok=True)
    result = fetcher.download(str(darwin), args.dest)
    if not result:
        print("Recovery download or chunklist verification failed.", file=sys.stderr)
        return 1

    for name in ("BaseSystem.dmg", "BaseSystem.chunklist"):
        path = os.path.join(result, name)
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            print("Missing or empty: {}".format(path), file=sys.stderr)
            return 1
        print("{}: {} bytes".format(name, os.path.getsize(path)))
    print("Recovery image downloaded and verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
