"""API HTTP local (127.0.0.1 + token) sobre os mesmos serviços da interface."""

from .servidor import VERSAO_API, ConfiguracaoAPI, ErroAPI, ServicoWeb, ServidorAPI

__all__ = ["VERSAO_API", "ConfiguracaoAPI", "ErroAPI", "ServicoWeb", "ServidorAPI"]
