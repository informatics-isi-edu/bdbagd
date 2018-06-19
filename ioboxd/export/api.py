import os
import sys
import errno
import logging
import uuid
import web
from deriva.core import urlparse, format_credential, format_exception
from deriva.transfer import GenericDownloader
from ioboxd.core import STORAGE_PATH, AUTHENTICATION, client_has_identity, get_client_identity, BadRequest, \
    Unauthorized, logger as sys_logger

logger = logging.getLogger('')
logger.propagate = False


def configure_logging(level=logging.INFO, log_path=None):

    logger.setLevel(level)
    if log_path:
        handler = logging.FileHandler(log_path)
    else:
        handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)

    return handler


def create_output_dir():

    key = str(uuid.uuid4())
    output_dir = os.path.abspath(os.path.join(STORAGE_PATH, key))
    if not os.path.isdir(output_dir):
        try:
            os.makedirs(output_dir)
        except OSError as error:
            if error.errno != errno.EEXIST:
                raise
    return key, output_dir


def get_final_output_path(output_path, output_name=None, ext=''):
    return ''.join([os.path.join(output_path, output_name) if output_name else output_path, ext])


def create_access_descriptor(directory, identity):
    with open(os.path.abspath(os.path.join(directory, ".access")), 'w') as access:
        access.writelines(''.join([identity if identity else "*", '\n']))


def check_access(directory):
    if not AUTHENTICATION:
        return True

    with open(os.path.abspath(os.path.join(directory, ".access")), 'r') as access:
        for identity in access.readlines():
            if client_has_identity(identity.strip()):
                return True
    return False


def export(config=None, base_dir=None, quiet=False, files_only=False):

    log_handler = configure_logging(logging.WARN if quiet else logging.INFO,
                                    log_path=os.path.abspath(os.path.join(base_dir, '.log')))
    try:
        if not config:
            raise BadRequest("No configuration specified.")
        server = dict()
        try:
            # parse host/catalog params
            catalog_config = config["catalog"]
            host = catalog_config["host"]
            if host.startswith("http"):
                url = urlparse(host)
                server["protocol"] = url.scheme
                server["host"] = url.netloc
            else:
                server["protocol"] = "https"
                server["host"] = host
            server["catalog_id"] = catalog_config.get('catalog_id', "1")

            # parse credential params
            token = catalog_config.get("token", None)
            username = catalog_config.get("username", "Anonymous")
            password = catalog_config.get("password", None)

            # sanity-check some bag params
            if "bag" in config:
                if files_only:
                    del config["bag"]
                else:
                    if not config["bag"].get("bag_archiver"):
                        config["bag"]["bag_archiver"] = "zip"

        except (KeyError, AttributeError) as e:
            raise BadRequest('Error parsing configuration: %s' % format_exception(e))

        try:
            auth_token = token if token else web.cookies().get("webauthn")
            credentials = format_credential(token=auth_token,
                                            username=username,
                                            password=password)
        except ValueError as e:
            raise Unauthorized(format_exception(e))

        try:
            downloader = GenericDownloader(server, output_dir=base_dir, config=config, credentials=credentials)
            identity = get_client_identity()
            user_id = username if not identity else identity.get('display_name', identity.get('id'))
            create_access_descriptor(base_dir, identity=username if not identity else identity.get('id'))
            sys_logger.info("Creating export at [%s] on behalf of user: %s" % (base_dir, user_id))
            return downloader.download(identity)
        except (KeyError, AttributeError) as e:
            raise BadRequest(format_exception(e))
        except:
            et, ev, tb = sys.exc_info()
            raise RuntimeError(format_exception(ev))
    finally:
        logger.removeHandler(log_handler)
