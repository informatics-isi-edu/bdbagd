import json
import web
from ioboxd.core import web_method, RestHandler
from ioboxd.export.api import create_output_dir, export


class ExportBag(RestHandler):
    def __init__(self):
        RestHandler.__init__(self)

    @web_method()
    def POST(self):
        key, output_dir = create_output_dir()
        file_list = export(config=json.loads(web.data()), base_dir=output_dir)
        url = ''.join([web.ctx.home, web.ctx.path, '/', key])

        return self.create_response(url)
