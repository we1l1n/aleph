import os
import logging
import requests
from tempfile import NamedTemporaryFile

from aleph.core import archive, celery
from aleph.model import clear_session
from aleph.model.metadata import Metadata
from aleph.ingest.ingestor import Ingestor

log = logging.getLogger(__name__)

# https://bugzilla.redhat.com/show_bug.cgi?id=191060#c1
# https://github.com/deanmalmgren/textract/blob/master/textract/parsers/pptx_parser.py
# https://github.com/chardet/chardet
# http://poppler.freedesktop.org/
# http://www.unixuser.org/~euske/python/pdfminer/index.html
# https://mstamy2.github.io/PyPDF2/#documentation
# http://pybrary.net/pyPdf/pythondoc-pyPdf.pdf.html
# https://svn.apache.org/viewvc/httpd/httpd/branches/2.2.x/docs/conf/mime.types?view=annotate


@celery.task()
def ingest_url(source_id, metadata, url):
    clear_session()
    meta = Metadata(data=metadata)
    with NamedTemporaryFile() as fh:
        log.info("Ingesting URL: %r", url)
        res = requests.get(url, stream=True)
        meta.source_url = res.url
        for chunk in res.iter_content(chunk_size=1024):
            if chunk:
                fh.write(chunk)
        fh.flush()

        if not meta.has('file_name'):
            meta.file_name = meta.file_name
        meta.headers = res.headers
        ingest_file(source_id, meta, fh.name)


def ingest_file(source_id, meta, file_name, move=False):
    if not os.path.isfile(file_name):
        raise ValueError("No such file: %r", file_name)
    if not meta.has('source_path'):
        meta.source_path = file_name
    meta = archive.archive_file(file_name, meta, move=move)
    ingest.delay(source_id, meta.data)


@celery.task()
def ingest(source_id, metadata):
    clear_session()
    meta = Metadata(data=metadata)
    Ingestor.dispatch(source_id, meta)
