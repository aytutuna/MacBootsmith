import logging
import subprocess


def run(args, capture=True, merge=True):
    args = [str(arg) for arg in args]
    logging.debug("$ %s", " ".join(args))
    if not capture:
        return subprocess.run(args)
    # callers that parse stdout pass merge=False so warnings on stderr cannot corrupt it
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT if merge else subprocess.PIPE)
    result.stdout = result.stdout.decode("utf-8", "replace")
    if result.stdout.strip():
        logging.debug(result.stdout.rstrip())
    if not merge:
        result.stderr = result.stderr.decode("utf-8", "replace")
        if result.stderr.strip():
            logging.debug("stderr: %s", result.stderr.rstrip())
    return result


def check(args, capture=True):
    result = run(args, capture=capture)
    if result.returncode != 0:
        if capture and result.stdout.strip():
            logging.error(result.stdout.rstrip())
        raise RuntimeError("{} failed with exit code {}".format(args[0], result.returncode))
    return result
