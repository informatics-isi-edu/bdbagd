# ioboxd
REST Web Service Interface DERIVA I/O.

The `ioboxd` webservice provides a set of REST APIs for exporting and importing data to and from ERMrest.
 The service supports both export and import of data to/from individual files, or filesets contained within 
 [BagIt](https://datatracker.ietf.org/doc/draft-kunze-bagit/) serialized archive files.


### Prerequisites
1. Python 2.7 or higher
2. ERMrest installed.
3. Webauthn installed.

### Installation
1. Clone source from GitHub:
    * `git clone https://github.com/informatics-isi-edu/ioboxd.git`


2. From the source distribution base directory, run:
    * `make deploy`

### Configuration

See the [Configuration guide](./doc/config.md) for further details.

### Usage

See the [API guide](./doc/api.md) for further details.

### Integration with Chaise

See the [Integration guide](./doc/integration.md) for further details.
