"""Erros fechados da etapa de decoding documental."""


class SourceDocumentIntegrityError(ValueError):
    """Indica divergência entre os bytes persistidos e seu SHA-256 declarado."""


class SourceDocumentDecodingError(ValueError):
    """Indica que os bytes íntegros não puderam ser decodificados estritamente."""


class DocumentSegmentationError(ValueError):
    """Base para documentos incompatíveis com as sentinelas esperadas."""


class MissingDocumentSentinelError(DocumentSegmentationError):
    """Indica ausência de uma sentinela documental obrigatória."""


class AmbiguousDocumentSentinelError(DocumentSegmentationError):
    """Indica múltiplas sentinelas documentais igualmente válidas."""


class InvalidDocumentOrderError(DocumentSegmentationError):
    """Indica sentinelas presentes em ordem documental impossível."""


class LegalStructureParsingError(ValueError):
    """Base para falhas da interpretação estrutural em memória."""


class LegalElementClassificationError(LegalStructureParsingError):
    """Indica bloco reconhecível que não pôde ser classificado com segurança."""


class LegalHierarchyError(LegalStructureParsingError):
    """Indica ausência ou incompatibilidade de ancestral estrutural."""


class LegalStructureValidationError(LegalStructureParsingError):
    """Indica violação das invariantes da árvore produzida."""


class DocumentCoverageError(LegalStructureParsingError):
    """Indica bloco sem destino explícito na auditoria de cobertura."""
