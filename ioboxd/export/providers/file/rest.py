import os
import json
import web
from ioboxd.core import web_method, RestHandler
from ioboxd.export.api import create_output_dir, export


class ExportFiles(RestHandler):
    def __init__(self):
        RestHandler.__init__(self)

    @web_method()
    def POST(self):
        key, output_dir = create_output_dir()
        file_list = export(config=json.loads(web.data()), base_dir=output_dir, files_only=True)
        url_list = list()
        for file_path in file_list.keys():
            url_list.append(''.join([web.ctx.home, web.ctx.path, '/' if not web.ctx.path.endswith("/") else "",
                                     str('%s/%s' % (key, os.path.basename(file_path)))]))

        return self.create_response(url_list)
