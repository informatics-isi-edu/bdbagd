import copy
import time
import simplejson as json
import bdbag
from bdbag import bdbag_api as bdb
from bdbag import bdbag_ro as ro
from ioboxd.core import BadRequest
from ioboxd.export.api import *
from ioboxd.export.transforms import *
from ioboxd.globals import FILETYPE_ONTOLOGY_MAP, MIMETYPE_EXTENSION_MAP

logger = logging.getLogger('')
logger.propagate = False


def export_bag(config=None, cookies=None, base_dir=None, identity=None, quiet=False, create_ro_metadata=True):

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
            remote_file_manifest = None
            ro_manifest = None
        except Exception as e:
            raise BadRequest('Error parsing configuration: %s' % bdbag.get_named_exception(e))

        session = authenticate(host, cookies, username, password)
        create_access_descriptor(base_dir, identity=username if not identity else identity['id'])

        if create_ro_metadata:
            ro_creator_name = username if not identity else identity.get(
                'full_name', identity.get('display_name', identity.get('id', None)))
            ro_manifest = init_ro_manifest(creator_name=ro_creator_name)
            bag_metadata.update({bdbag.BAG_PROFILE_TAG: bdbag.BDBAG_RO_PROFILE_ID})

        if not os.path.exists(bag_path):
            os.makedirs(bag_path)
        bag = bdb.make_bag(bag_path, algs=['sha256'], metadata=bag_metadata)

        for query in catalog_config['queries']:
            url = ''.join([host, path, query['query_path']])
            output_name = query.get('output_name', None)
            output_path = query['output_path']
            output_format = query['output_format']
            output_format_params = query.get('output_format_params', None)
            schema_path = query.get('schema_path', None)
            schema_name = ''.join([output_path, '-schema.json'])
            schema_output_path = os.path.abspath(os.path.join(bag_path, 'data', schema_name))

            try:
                if output_format == 'csv':
                    ext = '.csv'
                    headers = {'accept': 'text/csv'}
                    final_output_path = get_final_output_path(output_path, output_name, ext)
                    output_file = os.path.abspath(os.path.join(bag_path, 'data', final_output_path))
                    ro.add_provenance(
                        ro.add_aggregate(ro_manifest,
                                         uri=''.join(["../data/", final_output_path]),
                                         mediatype="text/csv",
                                         conforms_to=FILETYPE_ONTOLOGY_MAP.get(ext, None)),
                        retrieved_from=dict(retrievedFrom=url))

                elif output_format == 'json':
                    ext = '.json'
                    headers = {'accept': 'application/json'}
                    final_output_path = get_final_output_path(output_path, output_name, ext)
                    output_file = os.path.abspath(os.path.join(bag_path, 'data', final_output_path))
                    ro.add_provenance(
                        ro.add_aggregate(ro_manifest,
                                         uri=''.join(["../data/", final_output_path]),
                                         mediatype="application/json",
                                         conforms_to=FILETYPE_ONTOLOGY_MAP.get(ext, None)),
                        retrieved_from=dict(retrievedFrom=url))

                elif output_format == 'fasta':
                    ext = '.json'
                    headers = {'accept': 'application/x-json-stream'}
                    final_output_path = get_final_output_path(output_path, output_name, ext)
                    output_file = os.path.abspath(os.path.join(bag_path, 'data', final_output_path))

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
                    get_schema_for_output(schema_name,
                                          ''.join([host, path, schema_path]),
                                          schema_output_path,
                                          session,
                                          final_output_path,
                                          ro_manifest)

                if output_format == 'prefetch':
                    prefetch_files(output_file,
                                   base_path=os.path.join(bag_path, 'data'),
                                   subdir_path=final_output_path,
                                   session=session,
                                   ro_manifest=ro_manifest)

                elif output_format == 'fetch':
                    create_remote_file_manifest(remote_file_manifest, output_file, ro_manifest)

                elif output_format == 'fasta':
                    convert_to_fasta(output_file, output_path, output_format_params, url, ro_manifest)

            except (RuntimeError, Exception) as e:
                logger.error(bdbag.get_named_exception(e))
                bdb.cleanup_bag(bag_path)
                raise e

        try:
            bag_metadata_dir = os.path.abspath(os.path.join(bag_path, "metadata"))
            if not os.path.exists(bag_metadata_dir):
                os.mkdir(bag_metadata_dir)
            if ro_manifest:
                ro_manifest_path = os.path.join(bag_metadata_dir, "manifest.json")
                ro.write_ro_manifest(ro_manifest, ro_manifest_path)
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


def get_schema_for_output(schema_name, schema_url, schema_output_path, session, output_path=None, ro_manifest=None):
    get_file(schema_url, schema_output_path, {'accept': 'application/json'}, session)
    if ro_manifest:
        ro.add_provenance(
            ro.add_aggregate(ro_manifest,
                             uri=''.join(["../data/", schema_name]),
                             mediatype="application/json",
                             conforms_to=FILETYPE_ONTOLOGY_MAP.get('.json', None)),
            retrieved_from=dict(retrievedFrom=schema_url))
        if output_path:
            ro.add_annotation(ro_manifest,
                              uri=str("urn:uuid:%s" % str(uuid.uuid4())),
                              about=''.join(["../data/", output_path]),
                              content=''.join(["../data/", schema_name]))


def prefetch_files(input_manifest, base_path, subdir_path, session, ro_manifest=None):
    logger.info("Retrieving file(s)...")
    try:
        with open(input_manifest, "r") as in_file:
            for line in in_file:
                entry = json.loads(line)
                if not (has_attr(entry, 'url') and has_attr(entry, 'length') and has_attr(entry, 'filename')):
                    logger.warn("Unable to locate required attribute(s) in prefetch line %s" % line)
                url = entry['url']
                length = int(entry['length'])
                filename = \
                    os.path.abspath(os.path.join(
                        base_path, subdir_path, entry['filename']))
                logger.debug("Retrieving %s as %s" % (url, filename))
                get_file(url, filename, None, session)
                file_bytes = os.path.getsize(filename)
                if length != file_bytes:
                    raise RuntimeError(
                        "File size of %s does not match expected size of %s for file %s" %
                        (length, file_bytes, filename))
                file_ext = os.path.splitext(entry['filename'])[1][1:]
                mimetype = guess_mimetype(entry['url'])
                if ro_manifest:
                    ro.add_provenance(
                        ro.add_aggregate(ro_manifest,
                                         uri=''.join(["../data/", subdir_path, "/", entry['filename']]),
                                         mediatype=mimetype if mimetype
                                         else MIMETYPE_EXTENSION_MAP.get(file_ext, None),
                                         conforms_to=FILETYPE_ONTOLOGY_MAP.get(file_ext, None)),
                        retrieved_from=dict(retrievedFrom=entry['url']))
    finally:
        os.remove(input_manifest)


def create_remote_file_manifest(remote_file_manifest, input_file, ro_manifest=None):
    with open(input_file, "r") as in_file, open(remote_file_manifest, "w") as remote_file:
        for line in in_file:
            remote_file.write(line)
            entry = json.loads(line)
            file_ext = os.path.splitext(entry['filename'])[1][1:]
            mimetype = guess_mimetype(entry['url'])
            if ro_manifest:
                ro.add_provenance(
                    ro.add_aggregate(ro_manifest,
                                     uri=''.join(["../data/", entry['filename']]),
                                     mediatype=mimetype if mimetype
                                     else MIMETYPE_EXTENSION_MAP.get(file_ext, None),
                                     conforms_to=FILETYPE_ONTOLOGY_MAP.get(file_ext, None)),
                    retrieved_from=dict(retrievedFrom=entry['url']))
    os.remove(input_file)


def convert_to_fasta(output_file, output_path, output_format_params, url=None, ro_manifest=None):
    ext = '.fasta'
    result_file = ''.join([os.path.splitext(output_file)[0], ext])
    fasta.convert_json_file_to_fasta(output_file, result_file, output_format_params)
    os.remove(output_file)
    file_ext = os.path.splitext(result_file)[1][1:]
    mimetype = guess_mimetype(result_file)
    if ro_manifest:
        ro.add_provenance(
            ro.add_aggregate(ro_manifest,
                             uri=''.join(["../data/", output_path, ext]),
                             mediatype=mimetype if mimetype
                             else MIMETYPE_EXTENSION_MAP.get(file_ext, None),
                             conforms_to=FILETYPE_ONTOLOGY_MAP.get(file_ext, None)),
            retrieved_from=dict(retrievedFrom=url))

