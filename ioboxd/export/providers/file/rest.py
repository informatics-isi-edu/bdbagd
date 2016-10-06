import os

import simplejson as json
import web

from ioboxd.core import get_client_identity, web_method, RestHandler
from ioboxd.export.api import create_output_dir
from ioboxd.export.providers.file import api as export


class ExportFiles(RestHandler):
    def __init__(self):
        RestHandler.__init__(self)

    @web_method()
    def POST(self):

        key, output_dir = create_output_dir()

        file_list = export.export_files(config=json.loads(web.data()),
                                        base_dir=output_dir,
                                        cookies=web.cookies(),
                                        identity=get_client_identity())

        url_list = list()
        for file_path in file_list:
            url_list.append(''.join([web.ctx.home, web.ctx.path, str('/%s/%s' % (key, os.path.basename(file_path)))]))

        return self.create_response(url_list)
