# Copyright 2022 Guillaume Belanger
# See LICENSE file for licensing details.

"""Interface used by provider and requirer of the 5G N2."""

import logging
from typing import Optional

from ops.charm import CharmBase, CharmEvents, RelationChangedEvent
from ops.framework import EventBase, EventSource, Handle, Object

# The unique Charmhub library identifier, never change it
LIBID = "9cffc4bd8216447a9463a14ac8ecae0b"

# Increment this major API version when introducing breaking changes
LIBAPI = 0

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 1


logger = logging.getLogger(__name__)


class N2AvailableEvent(EventBase):
    """Charm event emitted when an N2 is available."""

    def __init__(
        self,
        handle: Handle,
        amf_address: str,
    ):
        """Init."""
        super().__init__(handle)
        self.amf_address = amf_address

    def snapshot(self) -> dict:
        """Returns snapshot."""
        return {
            "amf_address": self.amf_address,
        }

    def restore(self, snapshot: dict) -> None:
        """Restores snapshot."""
        self.amf_address = snapshot["amf_address"]


class FiveGN2RequirerCharmEvents(CharmEvents):
    """List of events that the 5G N2 requirer charm can leverage."""

    amf_available = EventSource(N2AvailableEvent)


class FiveGN2Requires(Object):
    """Class to be instantiated by the charm requiring the 5G N2 Interface."""

    on = FiveGN2RequirerCharmEvents()

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
        if "amf_address" not in remote_app_relation_data:
            logger.info("No amf_address in relation data - Not triggering amf_available event")
            return
        self.on.amf_available.emit(
            amf_address=remote_app_relation_data["amf_address"],
        )

    @property
    def amf_address_available(self) -> bool:
        """Returns whether amf address is available in relation data."""
        if self.amf_address:
            return True
        else:
            return False

    @property
    def amf_address(self) -> Optional[str]:
        """Returns amf_address from relation data."""
        relation = self.model.get_relation(relation_name=self.relationship_name)
        remote_app_relation_data = relation.data.get(relation.app)
        if not remote_app_relation_data:
            return None
        return remote_app_relation_data.get("amf_address", None)


class FiveGN2Provides(Object):
    """Class to be instantiated by the AMF charm providing the 5G N2 Interface."""

    def __init__(self, charm: CharmBase, relationship_name: str):
        """Init."""
        super().__init__(charm, relationship_name)
        self.relationship_name = relationship_name
        self.charm = charm

    def set_amf_information(
        self,
        amf_address: str,
        relation_id: int,
    ) -> None:
        """Sets N2 information in relation data.

        Args:
            amf_address: N2 address
            relation_id: Relation ID

        Returns:
            None
        """
        relation = self.model.get_relation(self.relationship_name, relation_id=relation_id)
        if not relation:
            raise RuntimeError(f"Relation {self.relationship_name} not created yet.")
        relation.data[self.charm.app].update(
            {
                "amf_address": amf_address,
            }
        )
