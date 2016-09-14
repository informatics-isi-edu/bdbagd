from ioboxd.core import *
from ioboxd.providers.export.api import check_access


class ExportRetrieve (RestHandler):

    def __init__(self):
        RestHandler.__init__(self)

    def send_log(self, file_path):
        web.ctx.ioboxd_content_type = 'text/plain'
        web.header('Content-Type', web.ctx.ioboxd_content_type)
        return self.get_content(file_path, web.ctx.webauthn2_context)

    def send_content(self, file_path):
        web.ctx.ioboxd_content_type = 'application/octet-stream'  # should eventually try to be more specific here
        web.header('Content-Type', web.ctx.ioboxd_content_type)
        web.header('Content-Disposition', "filename*=UTF-8''%s" % urllib.quote(os.path.basename(file_path)))
        return self.get_content(file_path, web.ctx.webauthn2_context)

    @web_method()
    def GET(self, key, requested_file=None):
        export_dir = os.path.abspath(os.path.join(STORAGE_PATH, key))
        if not os.path.isdir(export_dir):
            raise NotFound()
        if not check_access(export_dir):
            return Forbidden("The currently authenticated user is not permitted to access the specified resource.")

        file_path = None
        for dirname, dirnames, filenames in os.walk(export_dir):
            filenames.remove(".access")
            if filenames.__len__() > 1:
                for filename in filenames:
                    file_path = os.path.join(dirname, filename)
                    if filename == ".log":
                        if requested_file and requested_file == 'log':
                            return self.send_log(file_path)
                        else:
                            continue
                    if requested_file:
                        if requested_file == filename:
                            return self.send_content(file_path)
                        else:
                            continue
                    else:
                        return self.send_content(file_path)

            else:
                log_text = 'No additional diagnostic information available.\n'
                if filenames[0] == ".log":
                    file_path = os.path.join(dirname, filenames[0])
                    with open(file_path) as log:
                        log_text = log.read()
                raise NotFound(log_text)

        if not file_path:
            raise NotFound()
