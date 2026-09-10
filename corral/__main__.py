"""Entry point: python -m corral [--web-only]"""

import sys

from . import config, webserver


def main():
    cfg = config.load_config()
    web_url = webserver.start_in_thread(cfg)

    if "--web-only" in sys.argv:
        if web_url is None:
            sys.exit(1)
        print(f"corral dashboard: {web_url}")
        import threading
        threading.Event().wait()
        return

    from .menubar import CorralApp
    CorralApp(cfg, web_url=web_url).run()


if __name__ == "__main__":
    main()
