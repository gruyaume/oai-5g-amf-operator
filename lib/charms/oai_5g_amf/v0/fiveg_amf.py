# Copyright 2022 Guillaume Belanger
# See LICENSE file for licensing details.

"""Interface used by provider and requirer of the 5G AMF."""

import logging
from typing import Optional

from ops.charm import CharmBase, CharmEvents, RelationChangedEvent
from ops.framework import EventBase, EventSource, Handle, Object

# The unique Charmhub library identifier, never change it
LIBID = "ff1717f64ab7465e8a725ec1cd6f5095"

# Increment this major API version when introducing breaking changes
LIBAPI = 0

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 1


logger = logging.getLogger(__name__)


class AMFAvailableEvent(EventBase):
    """Charm event emitted when an AMF is available."""

    def __init__(
        self,
        handle: Handle,
        amf_ipv4_address: str,
        amf_fqdn: str,
        amf_port: str,
        amf_api_version: str,
    ):
        """Init."""
        super().__init__(handle)
        self.amf_ipv4_address = amf_ipv4_address
        self.amf_fqdn = amf_fqdn
        self.amf_port = amf_port
        self.amf_api_version = amf_api_version

    def snapshot(self) -> dict:
        """Returns snapshot."""
        return {
            "amf_ipv4_address": self.amf_ipv4_address,
            "amf_fqdn": self.amf_fqdn,
            "amf_port": self.amf_port,
            "amf_api_version": self.amf_api_version,
        }

    def restore(self, snapshot: dict) -> None:
        """Restores snapshot."""
        self.amf_ipv4_address = snapshot["amf_ipv4_address"]
        self.amf_fqdn = snapshot["amf_fqdn"]
        self.amf_port = snapshot["amf_port"]
        self.amf_api_version = snapshot["amf_api_version"]


class FiveGAMFRequirerCharmEvents(CharmEvents):
    """List of events that the 5G AMF requirer charm can leverage."""

    amf_available = EventSource(AMFAvailableEvent)


class FiveGAMFRequires(Object):
    """Class to be instantiated by the charm requiring the 5G AMF Interface."""

    on = FiveGAMFRequirerCharmEvents()

    def __init__(self, charm: CharmBase, relationship_name: str):
        """Init."""
        super().__init__(charm, relationship_name)
        self.charm = charm
        self.relationship_name = relationship_name
        self.framework.observe(
            charm.on[relationship_name].relation_changed, self._on_relation_changed
        )

    def _on_relation_changed(self, event: RelationChangedEvent) -> None:
        """Handler triggered on relation changed event.

        Args:
            event: Juju event (RelationChangedEvent)

        Returns:
            None
        """
        relation = event.relation
        if not relation.app:
            logger.warning("No remote application in relation: %s", self.relationship_name)
            return
        remote_app_relation_data = relation.data[relation.app]
        if "amf_ipv4_address" not in remote_app_relation_data:
            logger.info(
                "No amf_ipv4_address in relation data - Not triggering amf_available event"
            )
            return
        if "amf_fqdn" not in remote_app_relation_data:
            logger.info("No amf_fqdn in relation data - Not triggering amf_available event")
            return
        if "amf_port" not in remote_app_relation_data:
            logger.info("No amf_port in relation data - Not triggering amf_available event")
            return
        if "amf_api_version" not in remote_app_relation_data:
            logger.info("No amf_api_version in relation data - Not triggering amf_available event")
            return
        self.on.amf_available.emit(
            amf_ipv4_address=remote_app_relation_data["amf_ipv4_address"],
            amf_fqdn=remote_app_relation_data["amf_fqdn"],
            amf_port=remote_app_relation_data["amf_port"],
            amf_api_version=remote_app_relation_data["amf_api_version"],
        )

    @property
    def amf_ipv4_address_available(self) -> bool:
        """Returns whether amf address is available in relation data."""
        if self.amf_ipv4_address:
            return True
        else:
            return False

    @property
    def amf_ipv4_address(self) -> Optional[str]:
        """Returns amf_ipv4_address from relation data."""
        relation = self.model.get_relation(relation_name=self.relationship_name)
        remote_app_relation_data = relation.data.get(relation.app)
        if not remote_app_relation_data:
            return None
        return remote_app_relation_data.get("amf_ipv4_address", None)

    @property
    def amf_fqdn_available(self) -> bool:
        """Returns whether amf fqdn is available in relation data."""
        if self.amf_fqdn:
            return True
        else:
            return False

    @property
    def amf_fqdn(self) -> Optional[str]:
        """Returns amf_fqdn from relation data."""
        relation = self.model.get_relation(relation_name=self.relationship_name)
        remote_app_relation_data = relation.data.get(relation.app)
        if not remote_app_relation_data:
            return None
        return remote_app_relation_data.get("amf_fqdn", None)

    @property
    def amf_port_available(self) -> bool:
        """Returns whether amf port is available in relation data."""
        if self.amf_port:
            return True
        else:
            return False

    @property
    def amf_port(self) -> Optional[str]:
        """Returns amf_port from relation data."""
        relation = self.model.get_relation(relation_name=self.relationship_name)
        remote_app_relation_data = relation.data.get(relation.app)
        if not remote_app_relation_data:
            return None
        return remote_app_relation_data.get("amf_port", None)

    @property
    def amf_api_version_available(self) -> bool:
        """Returns whether amf api version is available in relation data."""
        if self.amf_api_version:
            return True
        else:
            return False

    @property
    def amf_api_version(self) -> Optional[str]:
        """Returns amf_api_version from relation data."""
        relation = self.model.get_relation(relation_name=self.relationship_name)
        remote_app_relation_data = relation.data.get(relation.app)
        if not remote_app_relation_data:
            return None
        return remote_app_relation_data.get("amf_api_version", None)


class FiveGAMFProvides(Object):
    """Class to be instantiated by the AMF charm providing the 5G AMF Interface."""

    def __init__(self, charm: CharmBase, relationship_name: str):
        """Init."""
        super().__init__(charm, relationship_name)
        self.relationship_name = relationship_name
        self.charm = charm

    def set_amf_information(
        self,
        amf_ipv4_address: str,
        amf_fqdn: str,
        amf_port: str,
        amf_api_version: str,
        relation_id: int,
    ) -> None:
        """Sets AMF information in relation data.

        Args:
            amf_ipv4_address: AMF address
            amf_fqdn: AMF FQDN
            amf_port: AMF port
            amf_api_version: AMF API version
            relation_id: Relation ID

        Returns:
            None
        """
        relation = self.model.get_relation(self.relationship_name, relation_id=relation_id)
        if not relation:
            raise RuntimeError(f"Relation {self.relationship_name} not created yet.")
        relation.data[self.charm.app].update(
            {
                "amf_ipv4_address": amf_ipv4_address,
                "amf_fqdn": amf_fqdn,
                "amf_port": amf_port,
                "amf_api_version": amf_api_version,
            }
        )
