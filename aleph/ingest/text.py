import os
import logging
from tempfile import mkstemp

from lxml import html, etree
from lxml.html.clean import Cleaner
from extractors import extract_pdf
from extractors import document_to_pdf, image_to_pdf, html_to_pdf

from aleph.core import get_archive, get_config
from aleph.model import db, Document, DocumentPage
from aleph.ingest.ingestor import Ingestor

log = logging.getLogger(__name__)


class TextIngestor(Ingestor):
    DOCUMENT_TYPE = Document.TYPE_TEXT

    def create_document(self, meta, type=None):
        document = super(TextIngestor, self).create_document(meta, type=type)
        document.delete_pages()
        return document

    def create_page(self, document, text, number=1):
        page = DocumentPage()
        page.document_id = document.id
        page.text = text
        page.number = number
        db.session.add(page)
        return page

    def get_languages(self, meta):
        default_languages = get_config('OCR_DEFAULTS', ['en'])
        languages = meta.languages + default_languages
        return list(set(languages))

    def extract_pdf(self, meta, pdf_path):
        data = extract_pdf(pdf_path, languages=self.get_languages(meta))
        if data is None:
            self.log_error(meta, error_type='PDFSyntaxError',
                           error_message="Could not parse PDF: %r" % meta)
            return

        if not meta.has('author') and data.get('author'):
            meta['author'] = data.get('author')

        if not meta.has('title') and data.get('title'):
            meta.title = data.get('title')

        document = self.create_document(meta)
        for i, page in enumerate(data['pages']):
            self.create_page(document, page, number=i + 1)
        self.emit(document)

    def store_pdf(self, meta, pdf_path):
        get_archive().archive_file(pdf_path, meta.pdf, move=False)


class PDFIngestor(TextIngestor):
    MIME_TYPES = ['application/pdf']
    EXTENSIONS = ['pdf']

    def ingest(self, meta, local_path):
        try:
            self.extract_pdf(meta, local_path)
        except Exception as exception:
            self.log_exception(meta, exception)

    @classmethod
    def match(cls, meta, local_path):
        with open(local_path, 'r') as fh:
            if fh.read(10).startswith('%PDF-1.'):
                return 15
        return -1


class DocumentIngestor(TextIngestor):
    MIME_TYPES = ['application/msword', 'application/rtf', 'application/x-rtf',
                  'application/vnd.oasis.opendocument.text',
                  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # noqa
                  'text/richtext', 'application/wordperfect', 'application/vnd.wordperfect']  # noqa
    EXTENSIONS = ['doc', 'docx', 'rtf', 'odt', 'sxw', 'dot', 'docm', 'hqx',
                  'pdb', 'txt', 'wpd']
    BASE_SCORE = 5

    def extract_pdf_alternative(self, meta, pdf_path):
        try:
            self.store_pdf(meta, pdf_path)
            self.extract_pdf(meta, pdf_path)
        except Exception as exception:
            self.log_exception(meta, exception)
        finally:
            if pdf_path is not None and os.path.isfile(pdf_path):
                os.unlink(pdf_path)

    def ingest(self, meta, local_path):
        pdf_path = document_to_pdf(local_path)
        if pdf_path is None or not os.path.isfile(pdf_path):
            self.log_error(meta, error_type='DocumentConvertError',
                           error_message="Could not convert doc: %r" % meta)
            return
        self.extract_pdf_alternative(meta, pdf_path)


class PresentationIngestor(DocumentIngestor):
    MIME_TYPES = ['application/vnd.ms-powerpoint.presentation',
                  'application/vnd.ms-powerpoint',
                  'application/vnd.openxmlformats-officedocument.presentationml.presentation',  # noqa
                  'application/vnd.openxmlformats-officedocument.presentationml.slideshow',  # noqa
                  'application/vnd.oasis.opendocument.presentation',
                  'application/vnd.sun.xml.impress']
    EXTENSIONS = ['ppt', 'pptx', 'odp', 'pot', 'pps', 'ppa']
    BASE_SCORE = 5


class HtmlIngestor(DocumentIngestor):
    MIME_TYPES = ['text/html']
    EXTENSIONS = ['html', 'htm', 'asp', 'aspx', 'jsp']

    cleaner = Cleaner(scripts=True, javascript=True, style=True, links=True,
                      embedded=True, forms=True, annoying_tags=True,
                      meta=False)

    def ingest(self, meta, local_path):
        fh, out_path = mkstemp(suffix='.htm')
        os.close(fh)
        with open(local_path, 'rb') as fh:
            doc = html.fromstring(fh.read())
            if not meta.has('title'):
                title = doc.findtext('.//title')
                if title is not None:
                    meta.title = title.strip()

            if not meta.has('summary'):
                summary = doc.find('.//meta[@name="description"]')
                if summary is not None and summary.get('content'):
                    meta.summary = summary.get('content')

            self.cleaner(doc)
        try:
            with open(out_path, 'w') as fh:
                fh.write(etree.tostring(doc))

            pdf_path = html_to_pdf(out_path)
            if pdf_path is None or not os.path.isfile(pdf_path):
                self.log_error(meta, error_type='HTMLConvertError',
                               error_message="Could not convert HTML: %r" % meta)  # noqa
                return
            self.extract_pdf_alternative(meta, pdf_path)
        finally:
            if os.path.isfile(out_path):
                os.unlink(out_path)


class ImageIngestor(TextIngestor):
    MIME_TYPES = ['image/png', 'image/tiff', 'image/x-tiff',
                  'image/jpeg', 'image/bmp', 'image/x-windows-bmp',
                  'image/x-portable-bitmap', 'application/postscript',
                  'image/vnd.dxf', 'image/svg+xml']
    EXTENSIONS = ['gif', 'png', 'jpg', 'jpeg', 'tif', 'tiff', 'bmp',
                  'jpe', 'pbm']
    BASE_SCORE = 5

    def ingest(self, meta, local_path):
        try:
            pdf_path = image_to_pdf(local_path)
            if pdf_path is None or not os.path.isfile(pdf_path):
                self.log_error(meta, error_type='ImageConvertError', error_message="Could not convert image: %r" % meta)  # noqa
                return
            self.store_pdf(meta, pdf_path)
            self.extract_pdf(meta, pdf_path)
        finally:
            if os.path.isfile(pdf_path):
                os.unlink(pdf_path)
