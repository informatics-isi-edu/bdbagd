import simplejson as json
import web

from ioboxd.core import get_client_identity, web_method, RestHandler
from ioboxd.export.api import create_output_dir
from ioboxd.export.providers.bdbag import api as export


class ExportBag(RestHandler):
    def __init__(self):
        RestHandler.__init__(self)

    @web_method()
    def POST(self):

        key, output_dir = create_output_dir()

        export.export_bag(config=json.loads(web.data()),
                          base_dir=output_dir,
                          cookies=web.cookies(),
                          identity=get_client_identity())

        url = ''.join([web.ctx.home, web.ctx.path, '/', key])

        return self.create_response(url)
