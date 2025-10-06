# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from abc import ABC, abstractmethod
from typing import List

from wayflowcore.tracing.span import Span


class SpanExporter(ABC):
    """Interface for exporting spans.

    Interface to be implemented by services that want to export in their own format
    the spans being recorded.
    """

    @abstractmethod
    def export(self, spans: List[Span], mask_sensitive_information: bool = True) -> None:
        """
        Exports a batch of telemetry data.

        Parameters
        ----------
        spans:
            The spans to be exported
        mask_sensitive_information
            Whether to mask potentially sensitive information from the span and its events
        """

    @abstractmethod
    def startup(self) -> None:
        """Start the exporter."""

    @abstractmethod
    def shutdown(self) -> None:
        """Shut down the exporter."""

    @abstractmethod
    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """
        Ensure that all the pending exports are completed as soon as possible.

        Parameters
        ----------
        timeout_millis:
            The time conceded to perform the flush

        Returns
        -------
            False if the timeout is exceeded, True otherwise
        """
