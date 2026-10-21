import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

LOG_NAME = "MacBootsmith.log"


def redirect_missing_streams():
    if sys.stdout is not None and sys.stderr is not None:
        return None
    from Scripts import app_paths
    try:
        handle = open(os.path.join(app_paths.app_dir(), LOG_NAME), "w", encoding="utf-8", buffering=1)
    except OSError:
        handle = open(os.devnull, "w", encoding="utf-8")
    if sys.stdout is None:
        sys.stdout = handle
    if sys.stderr is None:
        sys.stderr = handle
    return handle


def option_value(argv, flag):
    index = argv.index(flag)
    return argv[index + 1] if index + 1 < len(argv) else None


def main(argv):
    redirect_missing_streams()
    from Scripts import utils
    utils.Utils.install_output_proxy()

    if "--headless" in argv or "--analyze-log" in argv:
        from Scripts.gui import session
        module = session.load_main_module()
        if "--headless" in argv:
            answers = option_value(argv, "--headless")
            if not answers:
                print("Usage: MacBootsmith --headless <answers.json>")
                return 1
            return module.run_headless(answers)
        location = option_value(argv, "--analyze-log")
        if not location:
            print("Usage: MacBootsmith --analyze-log <log file, folder or drive>")
            return 1
        return module.analyze_log(location)

    from Scripts.gui import app
    return app.main(argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
