"""Erros específicos da fundação de consulta v0.2."""


class InvalidWorkflowState(RuntimeError):
    """Indica ausência ou incompatibilidade de dados exigidos por um nó."""
