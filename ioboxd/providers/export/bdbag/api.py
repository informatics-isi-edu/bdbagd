import os
import copy
import logging
import mimetypes
import time
import simplejson as json
import uuid
from ioboxd.globals import FILETYPE_ONTOLOGY_MAP, MIMETYPE_EXTENSION_MAP
from ioboxd.core import BadRequest, Unauthorized
from ioboxd.providers.export.api import configure_logging, create_access_descriptor, open_session, get_file
import bdbag
from bdbag import bdbag_api as bdb
from bdbag import bdbag_ro as ro

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

        create_access_descriptor(base_dir, identity=username if not identity else identity['id'])

        if not os.path.exists(bag_path):
            os.makedirs(bag_path)
        bag = bdb.make_bag(bag_path, algs=['sha256'], metadata=bag_metadata)

        remote_file_manifest = None
        ro_creator_name = username if not identity else identity.get(
            'full_name', identity.get('display_name', identity.get('id', None)))
        ro_manifest = init_ro_manifest(creator_name=ro_creator_name)

        for query in catalog_config['queries']:
            url = ''.join([host, path, query['query_path']])
            output_name = query.get('output_name', None)
            output_path = query['output_path']
            output_format = query['output_format']
            schema_path = query.get('schema_path', None)
            schema_name = ''.join([output_path, '-schema.json'])
            schema_output_path = os.path.abspath(os.path.join(bag_path, 'data', schema_name))

            try:
                if output_format == 'csv':
                    headers = {'accept': 'text/csv'}
                    output_path = \
                        ''.join([os.path.join(output_path, output_name) if output_name else output_path, '.csv'])
                    output_file = os.path.abspath(os.path.join(bag_path, 'data', output_path))
                    ro.add_provenance(
                        ro.add_aggregate(ro_manifest,
                                         uri=''.join(["../data/", output_path]),
                                         mediatype="text/csv",
                                         conforms_to=FILETYPE_ONTOLOGY_MAP.get('.csv', None)),
                        retrieved_from=dict(retrievedFrom=url))
                elif output_format == 'json':
                    headers = {'accept': 'application/json'}
                    output_path = \
                        ''.join([os.path.join(output_path, output_name) if output_name else output_path, '.json'])
                    output_file = os.path.abspath(os.path.join(bag_path, 'data', output_path))
                    ro.add_provenance(
                        ro.add_aggregate(ro_manifest,
                                         uri=''.join(["../data/", output_path]),
                                         mediatype="application/json",
                                         conforms_to=FILETYPE_ONTOLOGY_MAP.get('.json', None)),
                        retrieved_from=dict(retrievedFrom=url))
                elif output_format == 'prefetch':
                    headers = {'accept': 'application/x-json-stream'}
                    output_file = os.path.abspath(
                        ''.join([os.path.join(bag_path, output_name if output_name else 'prefetch-manifest'), '.json']))
                elif output_format == 'fetch':
                    headers = {'accept': 'application/x-json-stream'}
                    remote_file_manifest = os.path.abspath(
                        ''.join([os.path.join(base_dir, 'remote-file-manifest'), '.json']))
                    output_file = os.path.abspath(
                        ''.join([os.path.join(bag_path, output_name if output_name else 'fetch-manifest'), '.json']))
                else:
                    raise BadRequest("Unsupported output type: %s" % output_format)

                get_file(url, output_file, headers, session)

                if schema_path:
                    schema_url = ''.join([host, path, schema_path])
                    get_file(schema_url, schema_output_path, {'accept': 'application/json'}, session)
                    ro.add_provenance(
                        ro.add_aggregate(ro_manifest,
                                         uri=''.join(["../data/", schema_name]),
                                         mediatype="application/json",
                                         conforms_to=FILETYPE_ONTOLOGY_MAP.get('.json', None)),
                        retrieved_from=dict(retrievedFrom=schema_url))
                    ro.add_annotation(ro_manifest,
                                      uri=str("urn:uuid:%s" % str(uuid.uuid4())),
                                      about=''.join(["../data/", output_path]),
                                      content=''.join(["../data/", schema_name]))

                if output_format == 'prefetch':
                    logger.info("Prefetching file(s)...")
                    try:
                        with open(output_file, "r") as in_file:
                            for line in in_file:
                                entry = json.loads(line)
                                url = entry['url']
                                length = int(entry['length'])
                                filename = \
                                    os.path.abspath(os.path.join(
                                        bag_path, 'data', output_path, entry['filename']))
                                logger.debug("Prefetching %s as %s" % (url, filename))
                                get_file(url, filename, headers, session)
                                file_bytes = os.path.getsize(filename)
                                if length != file_bytes:
                                    raise RuntimeError(
                                        "File size of %s does not match expected size of %s for file %s" %
                                        (length, file_bytes, filename))
                                file_ext = os.path.splitext(entry['filename'])[1][1:]
                                mimetype = guess_mimetype(entry['url'])
                                ro.add_provenance(
                                    ro.add_aggregate(ro_manifest,
                                                     uri=''.join(["../data/", output_path, "/", entry['filename']]),
                                                     mediatype=mimetype if mimetype
                                                     else MIMETYPE_EXTENSION_MAP.get(file_ext, None),
                                                     conforms_to=FILETYPE_ONTOLOGY_MAP.get(file_ext, None)),
                                    retrieved_from=dict(retrievedFrom=entry['url']))
                    finally:
                        os.remove(output_file)

                elif output_format == 'fetch':
                    with open(output_file, "r") as in_file, open(remote_file_manifest, "w") as remote_file:
                        for line in in_file:
                            remote_file.write(line)
                            entry = json.loads(line)
                            file_ext = os.path.splitext(entry['filename'])[1][1:]
                            mimetype = guess_mimetype(entry['url'])
                            ro.add_provenance(
                                ro.add_aggregate(ro_manifest,
                                                 uri=''.join(["../data/", entry['filename']]),
                                                 mediatype=mimetype if mimetype
                                                 else MIMETYPE_EXTENSION_MAP.get(file_ext, None),
                                                 conforms_to=FILETYPE_ONTOLOGY_MAP.get(file_ext, None)),
                                retrieved_from=dict(retrievedFrom=entry['url']))
                    os.remove(output_file)

            except RuntimeError as e:
                logger.error(bdbag.get_named_exception(e))
                bdb.cleanup_bag(bag_path)
                raise e

        try:
            bag_metadata_dir = os.path.abspath(os.path.join(bag_path, "metadata"))
            if not os.path.exists(bag_metadata_dir):
                os.mkdir(bag_metadata_dir)
            ro_manifest_path = os.path.join(bag_metadata_dir, "manifest.json")
            ro.write_ro_manifest(ro_manifest, ro_manifest_path)
            bag_metadata.update({bdbag.BAG_PROFILE_TAG: bdbag.BDBAG_RO_PROFILE_ID})
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


def init_ro_manifest(creator_name=None, creator_uri=None, creator_orcid=None):
    manifest = copy.deepcopy(ro.DEFAULT_RO_MANIFEST)
    created_on = ro.make_created_on()
    created_by = None
    if creator_name:
        if creator_orcid and not creator_orcid.startswith("http"):
            creator_orcid = "/".join(["http://orcid.org", creator_orcid])
        created_by = ro.make_created_by(creator_name, uri=creator_uri, orcid=creator_orcid)
    ro.add_provenance(manifest, created_on=created_on, created_by=created_by)

    return manifest


def guess_mimetype(file_path):
    mtype = mimetypes.guess_type(file_path, False)
    mimetype = "+".join([mtype[0], mtype[1]]) if (mtype[0] is not None and mtype[1] is not None) \
        else (mtype[0] if mtype[0] is not None else mtype[1])
    return mimetype
