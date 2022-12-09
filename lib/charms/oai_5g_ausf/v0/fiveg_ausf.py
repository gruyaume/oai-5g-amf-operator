# Copyright 2022 Guillaume Belanger
# See LICENSE file for licensing details.

"""Interface used by provider and requirer of the 5G AUSF."""

import logging
from typing import Optional

from ops.charm import CharmBase, CharmEvents, RelationChangedEvent
from ops.framework import EventBase, EventSource, Handle, Object

# The unique Charmhub library identifier, never change it
LIBID = "369e9887896d4002960fd0621ea9db2c"

# Increment this major API version when introducing breaking changes
LIBAPI = 0

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 1


logger = logging.getLogger(__name__)


class AUSFAvailableEvent(EventBase):
    """Charm event emitted when an AUSF is available."""

    def __init__(
        self,
        handle: Handle,
        ausf_ipv4_address: str,
        ausf_fqdn: str,
        ausf_port: str,
        ausf_api_version: str,
    ):
        """Init."""
        super().__init__(handle)
        self.ausf_ipv4_address = ausf_ipv4_address
        self.ausf_fqdn = ausf_fqdn
        self.ausf_port = ausf_port
        self.ausf_api_version = ausf_api_version

    def snapshot(self) -> dict:
        """Returns snapshot."""
        return {
            "ausf_ipv4_address": self.ausf_ipv4_address,
            "ausf_fqdn": self.ausf_fqdn,
            "ausf_port": self.ausf_port,
            "ausf_api_version": self.ausf_api_version,
        }

    def restore(self, snapshot: dict) -> None:
        """Restores snapshot."""
        self.ausf_ipv4_address = snapshot["ausf_ipv4_address"]
        self.ausf_fqdn = snapshot["ausf_fqdn"]
        self.ausf_port = snapshot["ausf_port"]
        self.ausf_api_version = snapshot["ausf_api_version"]


class FiveGAUSFRequirerCharmEvents(CharmEvents):
    """List of events that the 5G AUSF requirer charm can leverage."""

    ausf_available = EventSource(AUSFAvailableEvent)


class FiveGAUSFRequires(Object):
    """Class to be instantiated by the charm requiring the 5G AUSF Interface."""

    on = FiveGAUSFRequirerCharmEvents()

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
        if "ausf_ipv4_address" not in remote_app_relation_data:
            logger.info(
                "No ausf_ipv4_address in relation data - Not triggering ausf_available event"
            )
            return
        if "ausf_fqdn" not in remote_app_relation_data:
            logger.info("No ausf_fqdn in relation data - Not triggering ausf_available event")
            return
        if "ausf_port" not in remote_app_relation_data:
            logger.info("No ausf_port in relation data - Not triggering ausf_available event")
            return
        if "ausf_api_version" not in remote_app_relation_data:
            logger.info(
                "No ausf_api_version in relation data - Not triggering ausf_available event"
            )
            return
        self.on.ausf_available.emit(
            ausf_ipv4_address=remote_app_relation_data["ausf_ipv4_address"],
            ausf_fqdn=remote_app_relation_data["ausf_fqdn"],
            ausf_port=remote_app_relation_data["ausf_port"],
            ausf_api_version=remote_app_relation_data["ausf_api_version"],
        )

    @property
    def ausf_ipv4_address_available(self) -> bool:
        """Returns whether ausf address is available in relation data."""
        if self.ausf_ipv4_address:
            return True
        else:
            return False

    @property
    def ausf_ipv4_address(self) -> Optional[str]:
        """Returns ausf_ipv4_address from relation data."""
        relation = self.model.get_relation(relation_name=self.relationship_name)
        remote_app_relation_data = relation.data.get(relation.app)
        if not remote_app_relation_data:
            return None
        return remote_app_relation_data.get("ausf_ipv4_address", None)

    @property
    def ausf_fqdn_available(self) -> bool:
        """Returns whether ausf fqdn is available in relation data."""
        if self.ausf_fqdn:
            return True
        else:
            return False

    @property
    def ausf_fqdn(self) -> Optional[str]:
        """Returns ausf_fqdn from relation data."""
        relation = self.model.get_relation(relation_name=self.relationship_name)
        remote_app_relation_data = relation.data.get(relation.app)
        if not remote_app_relation_data:
            return None
        return remote_app_relation_data.get("ausf_fqdn", None)

    @property
    def ausf_port_available(self) -> bool:
        """Returns whether ausf port is available in relation data."""
        if self.ausf_port:
            return True
        else:
            return False

    @property
    def ausf_port(self) -> Optional[str]:
        """Returns ausf_port from relation data."""
        relation = self.model.get_relation(relation_name=self.relationship_name)
        remote_app_relation_data = relation.data.get(relation.app)
        if not remote_app_relation_data:
            return None
        return remote_app_relation_data.get("ausf_port", None)

    @property
    def ausf_api_version_available(self) -> bool:
        """Returns whether ausf api version is available in relation data."""
        if self.ausf_api_version:
            return True
        else:
            return False

    @property
    def ausf_api_version(self) -> Optional[str]:
        """Returns ausf_api_version from relation data."""
        relation = self.model.get_relation(relation_name=self.relationship_name)
        remote_app_relation_data = relation.data.get(relation.app)
        if not remote_app_relation_data:
            return None
        return remote_app_relation_data.get("ausf_api_version", None)


class FiveGAUSFProvides(Object):
    """Class to be instantiated by the AUSF charm providing the 5G AUSF Interface."""

    def __init__(self, charm: CharmBase, relationship_name: str):
        """Init."""
        super().__init__(charm, relationship_name)
        self.relationship_name = relationship_name
        self.charm = charm

    def set_ausf_information(
        self,
        ausf_ipv4_address: str,
        ausf_fqdn: str,
        ausf_port: str,
        ausf_api_version: str,
        relation_id: int,
    ) -> None:
        """Sets AUSF information in relation data.

        Args:
            ausf_ipv4_address: AUSF address
            ausf_fqdn: AUSF FQDN
            ausf_port: AUSF port
            ausf_api_version: AUSF API version
            relation_id: Relation ID

        Returns:
            None
        """
        relation = self.model.get_relation(self.relationship_name, relation_id=relation_id)
        if not relation:
            raise RuntimeError(f"Relation {self.relationship_name} not created yet.")
        relation.data[self.charm.app].update(
            {
                "ausf_ipv4_address": ausf_ipv4_address,
                "ausf_fqdn": ausf_fqdn,
                "ausf_port": ausf_port,
                "ausf_api_version": ausf_api_version,
            }
        )
