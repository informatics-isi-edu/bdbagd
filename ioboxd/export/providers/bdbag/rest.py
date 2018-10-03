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
        url = ''.join([web.ctx.home, web.ctx.path, '/' if not web.ctx.path.endswith("/") else "", key])

        # perform the export
        output = export(config=json.loads(web.data()), base_dir=output_dir)
        output_metadata = output.values()[0] or {}

        return_uri_list = False
        identifier_landing_page = output_metadata.get("identifier_landing_page")
        if identifier_landing_page:
            url = [identifier_landing_page, url]
            # return_uri_list = True
        else:
            identifier = output_metadata.get("identifier")
            if identifier:
                url = ["https://n2t.net/" + identifier, "https://identifiers.org/" + identifier, url]
                # return_uri_list = True

        return self.create_response(url, return_uri_list)
