# Copyright 2022 Guillaume Belanger
# See LICENSE file for licensing details.

"""Interface used by provider and requirer of the 5G UDM."""

import logging
from typing import Optional

from ops.charm import CharmBase, CharmEvents, RelationChangedEvent
from ops.framework import EventBase, EventSource, Handle, Object

# The unique Charmhub library identifier, never change it
LIBID = "431fe7c4892f4fce82303e14cc40764f"

# Increment this major API version when introducing breaking changes
LIBAPI = 0

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 1


logger = logging.getLogger(__name__)


class UDMAvailableEvent(EventBase):
    """Charm event emitted when an UDM is available."""

    def __init__(
        self,
        handle: Handle,
        udm_ipv4_address: str,
        udm_fqdn: str,
        udm_port: str,
        udm_api_version: str,
    ):
        """Init."""
        super().__init__(handle)
        self.udm_ipv4_address = udm_ipv4_address
        self.udm_fqdn = udm_fqdn
        self.udm_port = udm_port
        self.udm_api_version = udm_api_version

    def snapshot(self) -> dict:
        """Returns snapshot."""
        return {
            "udm_ipv4_address": self.udm_ipv4_address,
            "udm_fqdn": self.udm_fqdn,
            "udm_port": self.udm_port,
            "udm_api_version": self.udm_api_version,
        }

    def restore(self, snapshot: dict) -> None:
        """Restores snapshot."""
        self.udm_ipv4_address = snapshot["udm_ipv4_address"]
        self.udm_fqdn = snapshot["udm_fqdn"]
        self.udm_port = snapshot["udm_port"]
        self.udm_api_version = snapshot["udm_api_version"]


class FiveGUDMRequirerCharmEvents(CharmEvents):
    """List of events that the 5G UDM requirer charm can leverage."""

    udm_available = EventSource(UDMAvailableEvent)


class FiveGUDMRequires(Object):
    """Class to be instantiated by the charm requiring the 5G UDM Interface."""

    on = FiveGUDMRequirerCharmEvents()

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
        if "udm_ipv4_address" not in remote_app_relation_data:
            logger.info(
                "No udm_ipv4_address in relation data - Not triggering udm_available event"
            )
            return
        if "udm_fqdn" not in remote_app_relation_data:
            logger.info("No udm_fqdn in relation data - Not triggering udm_available event")
            return
        if "udm_port" not in remote_app_relation_data:
            logger.info("No udm_port in relation data - Not triggering udm_available event")
            return
        if "udm_api_version" not in remote_app_relation_data:
            logger.info("No udm_api_version in relation data - Not triggering udm_available event")
            return
        self.on.udm_available.emit(
            udm_ipv4_address=remote_app_relation_data["udm_ipv4_address"],
            udm_fqdn=remote_app_relation_data["udm_fqdn"],
            udm_port=remote_app_relation_data["udm_port"],
            udm_api_version=remote_app_relation_data["udm_api_version"],
        )

    @property
    def udm_ipv4_address_available(self) -> bool:
        """Returns whether udm address is available in relation data."""
        if self.udm_ipv4_address:
            return True
        else:
            return False

    @property
    def udm_ipv4_address(self) -> Optional[str]:
        """Returns udm_ipv4_address from relation data."""
        relation = self.model.get_relation(relation_name=self.relationship_name)
        remote_app_relation_data = relation.data.get(relation.app)
        if not remote_app_relation_data:
            return None
        return remote_app_relation_data.get("udm_ipv4_address", None)

    @property
    def udm_fqdn_available(self) -> bool:
        """Returns whether udm fqdn is available in relation data."""
        if self.udm_fqdn:
            return True
        else:
            return False

    @property
    def udm_fqdn(self) -> Optional[str]:
        """Returns udm_fqdn from relation data."""
        relation = self.model.get_relation(relation_name=self.relationship_name)
        remote_app_relation_data = relation.data.get(relation.app)
        if not remote_app_relation_data:
            return None
        return remote_app_relation_data.get("udm_fqdn", None)

    @property
    def udm_port_available(self) -> bool:
        """Returns whether udm port is available in relation data."""
        if self.udm_port:
            return True
        else:
            return False

    @property
    def udm_port(self) -> Optional[str]:
        """Returns udm_port from relation data."""
        relation = self.model.get_relation(relation_name=self.relationship_name)
        remote_app_relation_data = relation.data.get(relation.app)
        if not remote_app_relation_data:
            return None
        return remote_app_relation_data.get("udm_port", None)

    @property
    def udm_api_version_available(self) -> bool:
        """Returns whether udm api version is available in relation data."""
        if self.udm_api_version:
            return True
        else:
            return False

    @property
    def udm_api_version(self) -> Optional[str]:
        """Returns udm_api_version from relation data."""
        relation = self.model.get_relation(relation_name=self.relationship_name)
        remote_app_relation_data = relation.data.get(relation.app)
        if not remote_app_relation_data:
            return None
        return remote_app_relation_data.get("udm_api_version", None)


class FiveGUDMProvides(Object):
    """Class to be instantiated by the UDM charm providing the 5G UDM Interface."""

    def __init__(self, charm: CharmBase, relationship_name: str):
        """Init."""
        super().__init__(charm, relationship_name)
        self.relationship_name = relationship_name
        self.charm = charm

    def set_udm_information(
        self,
        udm_ipv4_address: str,
        udm_fqdn: str,
        udm_port: str,
        udm_api_version: str,
        relation_id: int,
    ) -> None:
        """Sets UDM information in relation data.

        Args:
            udm_ipv4_address: UDM address
            udm_fqdn: UDM FQDN
            udm_port: UDM port
            udm_api_version: UDM API version
            relation_id: Relation ID

        Returns:
            None
        """
        relation = self.model.get_relation(self.relationship_name, relation_id=relation_id)
        if not relation:
            raise RuntimeError(f"Relation {self.relationship_name} not created yet.")
        relation.data[self.charm.app].update(
            {
                "udm_ipv4_address": udm_ipv4_address,
                "udm_fqdn": udm_fqdn,
                "udm_port": udm_port,
                "udm_api_version": udm_api_version,
            }
        )
