import pdfplumber
from cv_management.ports.text_extractor import ITextExtractor


class PDFExtractionError(Exception):
    """Base exception for PDF extraction errors."""
    pass


class PDFMalformedError(PDFExtractionError):
    """Raised when PDF is malformed or corrupted."""
    pass


class PDFEncryptedError(PDFExtractionError):
    """Raised when PDF is encrypted and password-protected."""
    pass


class PDFScannedError(PDFExtractionError):
    """Raised when PDF appears to be scanned (no extractable text)."""
    pass


class PdfTextExtractor(ITextExtractor):
    def extract_text(self, file_path: str) -> str:
        """
        Extract text from PDF with robust error handling.
        
        Raises:
            PDFMalformedError: If PDF is malformed or corrupted
            PDFEncryptedError: If PDF is password-protected
            PDFScannedError: If PDF has no extractable text (scanned/image-based)
            PDFExtractionError: For other extraction errors
        """
        text = ""
        
        try:
            # pdfplumber handles encryption automatically - if PDF is encrypted and no password provided,
            # it will raise an exception. We catch that and convert to our custom exception.
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                
                # Check if we extracted any text (scanned PDF detection)
                if not text or len(text.strip()) < 50:
                    # Very little or no text extracted - likely scanned
                    raise PDFScannedError(
                        "PDF appears to be scanned or image-based with no extractable text. "
                        "OCR processing is not supported."
                    )
                
                return text
                
        except Exception as e:
            # Check if it's one of our custom exceptions (already raised above)
            if isinstance(e, (PDFEncryptedError, PDFScannedError)):
                raise
            
            # Handle pdfplumber-specific errors
            error_msg = str(e).lower()
            if "syntax" in error_msg or "malformed" in error_msg or "corrupted" in error_msg:
                raise PDFMalformedError(f"PDF is malformed or corrupted: {str(e)}")
            elif "encrypted" in error_msg or "password" in error_msg:
                raise PDFEncryptedError(f"PDF is password-protected: {str(e)}")
            elif "file not found" in error_msg:
                raise PDFExtractionError(f"PDF file not found: {file_path}")
            else:
                # Generic error
                raise PDFExtractionError(f"Failed to extract text from PDF: {str(e)}")
