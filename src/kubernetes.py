# Copyright 2022 Guillaume Belanger
# See LICENSE file for licensing details.

"""Kubernetes specific utilities."""

import logging
from typing import Optional, Tuple

from lightkube import Client
from lightkube.resources.core_v1 import Service

logger = logging.getLogger(__name__)


class Kubernetes:
    """Kubernetes main class."""

    def __init__(self, namespace: str):
        """Initializes K8s client."""
        self.client = Client()
        self.namespace = namespace

    def get_service(self, name: str) -> Service:
        """Gets service based on name."""
        return self.client.get(Service, name, namespace=self.namespace)  # type: ignore[return-value]  # noqa: E501

    def get_service_load_balancer_address(self, name: str) -> Tuple[Optional[str], Optional[str]]:
        """Retrieves LoadBalancer address based on service name."""
        service = self.get_service(name)
        if service.spec.type != "LoadBalancer":
            raise RuntimeError("Service is not of type LoadBalancer.")
        ingress = service.status.loadBalancer.ingress
        if not ingress:
            raise RuntimeError("The service has no ingress address.")
        return ingress[0].hostname, ingress[0].ip
