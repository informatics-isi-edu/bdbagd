import os.path
import logging
import time
import simplejson as json
from ioboxd.core import BadRequest, Unauthorized
from ioboxd.providers.export.api import configure_logging, create_access_descriptor, open_session, get_file
import bdbag
from bdbag import bdbag_api as bdb

logger = logging.getLogger('')
logger.propagate = False


def export_bag(config=None, cookies=None, base_dir=None, identity=None, quiet=False):

    log_handler = configure_logging(logging.WARN if quiet else logging.INFO,
                                    log_path=os.path.abspath(os.path.join(base_dir, '.log')))
    try:
        try:
            if not config:
                raise BadRequest("No configuration specified.")

            catalog_config = config['catalog']
            host = catalog_config['host']
            path = catalog_config['path']
            username = catalog_config.get('username', None)
            password = catalog_config.get('password', None)

            bag_config = config.get('bag', {})
            bag_name = bag_config.get('bag_name', ''.join(["bdbag", '_', time.strftime("%Y-%m-%d_%H.%M.%S")]))
            bag_path = os.path.abspath(os.path.join(base_dir if base_dir else ".", bag_name))
            bag_archiver = bag_config.get('bag_archiver', "zip")
            bag_metadata = bag_config.get('bag_metadata', {"Internal-Sender-Identifier":
                                                           "ioboxd:%s" % (os.path.basename(base_dir))})
        except Exception as e:
            raise BadRequest('Error parsing configuration: %s' % bdbag.get_named_exception(e))

        if username and password:
            session = open_session(host, login_params={'username': username, 'password': password})
        elif cookies:
            session = open_session(host, cookies=cookies)
        else:
            raise Unauthorized("The requested service requires authentication.")

        create_access_descriptor(base_dir, identity=username if not identity else identity)

        if not os.path.exists(bag_path):
            os.makedirs(bag_path)
        bag = bdb.make_bag(bag_path, algs=['sha256'], metadata=bag_metadata)
        remote_file_manifest = None

        for query in catalog_config['queries']:
            url = ''.join([host, path, query['query_path']])
            output_name = query.get('output_name', None)
            output_path = query['output_path']
            output_format = query['output_format']
            schema_path = query.get('schema_path', None)
            schema_output_path = os.path.abspath(os.path.join(bag_path, 'data', ''.join([output_path, '-schema.json'])))

            try:
                if output_format == 'csv':
                    headers = {'accept': 'text/csv'}
                    output_path = \
                        ''.join([os.path.join(output_path, output_name) if output_name else output_path, '.csv'])
                    output_file = os.path.abspath(os.path.join(bag_path, 'data', output_path))
                elif output_format == 'json':
                    headers = {'accept': 'application/json'}
                    output_path = \
                        ''.join([os.path.join(output_path, output_name) if output_name else output_path, '.json'])
                    output_file = os.path.abspath(os.path.join(bag_path, 'data', output_path))
                elif output_format == 'prefetch':
                    headers = {'accept': 'application/x-json-stream'}
                    output_file = os.path.abspath(
                        ''.join([os.path.join(bag_path, output_name) if output_name else 'prefetch-manifest', '.json']))
                elif output_format == 'fetch':
                    headers = {'accept': 'application/x-json-stream'}
                    remote_file_manifest = os.path.abspath(
                        ''.join([os.path.join(base_dir, 'remote-file-manifest'), '.json']))
                    output_file = os.path.abspath(
                        ''.join([os.path.join(bag_path, output_name) if output_name else 'fetch-manifest', '.json']))
                else:
                    raise BadRequest("Unsupported output type: %s" % output_format)

                get_file(url, output_file, headers, session)

                if schema_path:
                    schema_url = ''.join([host, path, schema_path])
                    get_file(schema_url, schema_output_path, {'accept': 'application/json'}, session)

                if output_format == 'prefetch':
                    logger.info("Prefetching file(s)...")
                    try:
                        with open(output_file, "r") as in_file:
                            for line in in_file:
                                prefetch_entry = json.loads(line)
                                prefetch_url = prefetch_entry['url']
                                prefetch_length = int(prefetch_entry['length'])
                                prefetch_filename = \
                                    os.path.abspath(os.path.join(
                                        bag_path, 'data', output_path, prefetch_entry['filename']))
                                logger.debug("Prefetching %s as %s" % (prefetch_url, prefetch_filename))
                                get_file(prefetch_url, prefetch_filename, headers, session)
                                file_bytes = os.path.getsize(prefetch_filename)
                                if prefetch_length != file_bytes:
                                    raise RuntimeError(
                                        "File size of %s does not match expected size of %s for file %s" %
                                        (prefetch_length, file_bytes, prefetch_filename))
                    finally:
                        os.remove(output_file)

                elif output_format == 'fetch':
                    with open(output_file, "r") as in_file, open(remote_file_manifest, "w") as remote_file:
                        for line in in_file:
                            remote_file.write(line)
                    os.remove(output_file)

            except RuntimeError as e:
                logger.error(bdbag.get_named_exception(e))
                bdb.cleanup_bag(bag_path)
                raise e

        try:
            bag = bdb.make_bag(bag_path, remote_file_manifest=remote_file_manifest, update=True)
        except Exception as e:
            logger.fatal("Exception while updating bag manifests: %s", bdbag.get_named_exception(e))
            bdb.cleanup_bag(bag_path)
            raise e
        finally:
            if remote_file_manifest and os.path.exists(remote_file_manifest):
                os.remove(remote_file_manifest)

        logger.info('Created bag: %s' % bag_path)

        if bag_archiver is not None:
            try:
                archive = bdb.archive_bag(bag_path, bag_archiver.lower())
                bdb.cleanup_bag(bag_path)
                return archive
            except Exception as e:
                logger.error("Exception while creating data bag archive:", bdbag.get_named_exception(e))
                raise e
        else:
            return bag_path
    finally:
        logger.removeHandler(log_handler)
