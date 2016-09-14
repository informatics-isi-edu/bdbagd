import web
import ioboxd

"""
This will run the web.py local server. It is intended for use as a debugging tool only.
"""
if __name__ == "__main__":
    app = web.application(ioboxd.web_urls(), globals())
    app.run()
