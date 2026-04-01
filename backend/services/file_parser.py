"""File Parser - PDF/TXT/MD extraction"""
import os
import logging
from pathlib import Path
from config import Config

logger = logging.getLogger(__name__)


class FileParser:
    @staticmethod
    def extract_text(filepath):
        """Extract text from a file based on extension."""
        ext = Path(filepath).suffix.lower()
        if ext == '.pdf':
            return FileParser._extract_pdf(filepath)
        elif ext in ('.md', '.markdown'):
            return FileParser._extract_text(filepath)
        elif ext == '.txt':
            return FileParser._extract_text(filepath)
        else:
            raise ValueError(f'Unsupported file type: {ext}')

    @staticmethod
    def _extract_pdf(filepath):
        """Extract text from PDF using PyMuPDF."""
        import fitz
        doc = fitz.open(filepath)
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text())
        doc.close()
        return '\n\n'.join(text_parts)

    @staticmethod
    def _extract_text(filepath):
        """Extract text from TXT/MD with encoding detection."""
        # Try UTF-8 first
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            pass

        # Fallback: charset_normalizer
        try:
            from charset_normalizer import from_path
            result = from_path(filepath).best()
            if result:
                return str(result)
        except ImportError:
            pass

        # Last resort
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()

    @staticmethod
    def extract_multiple(filepaths):
        """Extract and merge text from multiple files."""
        results = []
        for fp in filepaths:
            try:
                text = FileParser.extract_text(fp)
                filename = Path(fp).name
                results.append({
                    'filename': filename,
                    'path': fp,
                    'text': text,
                })
                logger.info(f'Parsed {filename}: {len(text)} chars')
            except Exception as e:
                logger.error(f'Failed to parse {fp}: {e}')
        return results

    @staticmethod
    def split_into_chunks(text, chunk_size=500, overlap=50):
        """Split text into overlapping chunks at sentence boundaries."""
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            if end >= len(text):
                chunks.append(text[start:])
                break

            # Try to split at sentence boundary
            split_pos = end
            for offset in range(min(50, chunk_size // 4)):
                pos = end - offset
                if pos > start and text[pos] in '.。!！?？\n':
                    split_pos = pos + 1
                    break

            chunks.append(text[start:split_pos])
            start = split_pos - overlap
            if start <= chunks[-1].__len__() - chunk_size // 2:
                start = split_pos

        return chunks
