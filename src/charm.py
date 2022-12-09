#!/usr/bin/env python3
# Copyright 2022 Guillaume Belanger
# See LICENSE file for licensing details.

"""Charmed Operator for the OpenAirInterface 5G Core AMF component."""


import logging

from charms.data_platform_libs.v0.database_requires import (  # type: ignore[import]
    DatabaseRequires,
)
from charms.oai_5g_ausf.v0.fiveg_ausf import FiveGAUSFRequires  # type: ignore[import]
from charms.oai_5g_nrf.v0.fiveg_nrf import FiveGNRFRequires  # type: ignore[import]
from charms.oai_5g_udm.v0.oai_5g_udm import FiveGUDMRequires  # type: ignore[import]
from charms.observability_libs.v1.kubernetes_service_patch import (  # type: ignore[import]
    KubernetesServicePatch,
    ServicePort,
)
from jinja2 import Environment, FileSystemLoader
from ops.charm import CharmBase, ConfigChangedEvent
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus

logger = logging.getLogger(__name__)

BASE_CONFIG_PATH = "/openair-amf/etc"
CONFIG_FILE_NAME = "amf.conf"
DATABASE_NAME = "oai_db"


class Oai5GAMFOperatorCharm(CharmBase):
    """Charm the service."""

    def __init__(self, *args):
        """Observes juju events."""
        super().__init__(*args)
        self._container_name = "amf"
        self._container = self.unit.get_container(self._container_name)
        self.service_patcher = KubernetesServicePatch(
            charm=self,
            ports=[
                ServicePort(
                    name="oai-amf",
                    port=int(self._config_ngap_amf_interface_port),
                    protocol="SCTP",
                    targetPort=int(self._config_ngap_amf_interface_port),
                ),
                ServicePort(
                    name="http1",
                    port=int(self._config_n11_amf_interface_port),
                    protocol="TCP",
                    targetPort=int(self._config_n11_amf_interface_port),
                ),
                ServicePort(
                    name="http2",
                    port=int(self._config_n11_amf_interface_http2_port),
                    protocol="TCP",
                    targetPort=int(self._config_n11_amf_interface_http2_port),
                ),
            ],
        )
        self.nrf_requires = FiveGNRFRequires(self, "fiveg-nrf")
        self.udm_requires = FiveGUDMRequires(self, "fiveg-udm")
        self.ausf_requires = FiveGAUSFRequires(self, "fiveg-ausf")
        self.database = DatabaseRequires(
            self, relation_name="database", database_name=DATABASE_NAME
        )
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.fiveg_nrf_relation_changed, self._on_config_changed)
        self.framework.observe(self.on.fiveg_udm_relation_changed, self._on_config_changed)
        self.framework.observe(self.on.fiveg_ausf_relation_changed, self._on_config_changed)
        self.framework.observe(self.database.on.database_created, self._on_config_changed)

    def _on_config_changed(self, event: ConfigChangedEvent) -> None:
        """Triggered on any change in configuration.

        Args:
            event: Config Changed Event

        Returns:
            None
        """
        if not self._container.can_connect():
            self.unit.status = WaitingStatus("Waiting for Pebble in workload container")
            event.defer()
            return
        if not self._database_relation_created:
            self.unit.status = BlockedStatus("Waiting for relation to database to be created")
            return
        if not self._nrf_relation_created:
            self.unit.status = BlockedStatus("Waiting for relation to NRF to be created")
            return
        if not self._udm_relation_created:
            self.unit.status = BlockedStatus("Waiting for relation to UDM to be created")
            return
        if not self._ausf_relation_created:
            self.unit.status = BlockedStatus("Waiting for relation to AUSF to be created")
            return
        if not self._database_relation_data_is_available:
            self.unit.status = WaitingStatus("Waiting for database relation data to be available")
            return
        if not self.nrf_requires.nrf_ipv4_address_available:
            self.unit.status = WaitingStatus(
                "Waiting for NRF IPv4 address to be available in relation data"
            )
            return
        if not self.udm_requires.udm_ipv4_address_available:
            self.unit.status = WaitingStatus(
                "Waiting for UDM IPv4 address to be available in relation data"
            )
            return
        if not self.ausf_requires.ausf_ipv4_address_available:
            self.unit.status = WaitingStatus(
                "Waiting for AUSF IPv4 address to be available in relation data"
            )
            return
        self._push_config()
        self._update_pebble_layer()
        self.unit.status = ActiveStatus()

    def _update_pebble_layer(self) -> None:
        """Updates pebble layer with new configuration.

        Returns:
            None
        """
        self._container.add_layer("amf", self._pebble_layer, combine=True)
        self._container.replan()
        self.unit.status = ActiveStatus()

    @property
    def _database_relation_created(self) -> bool:
        return self._relation_created("database")

    @property
    def _nrf_relation_created(self) -> bool:
        return self._relation_created("fiveg-nrf")

    @property
    def _udm_relation_created(self) -> bool:
        return self._relation_created("fiveg-udm")

    @property
    def _ausf_relation_created(self) -> bool:
        return self._relation_created("fiveg-ausf")

    def _relation_created(self, relation_name: str) -> bool:
        if not self.model.get_relation(relation_name):
            return False
        return True

    @property
    def _database_relation_data_is_available(self) -> bool:
        relation_data = self.database.fetch_relation_data()
        if not relation_data:
            return False
        relation = self.model.get_relation(relation_name="database")
        if not relation:
            return False
        if "username" not in relation_data[relation.id]:
            return False
        if "password" not in relation_data[relation.id]:
            return False
        if "endpoints" not in relation_data[relation.id]:
            return False
        return True

    def _push_config(self) -> None:
        jinja2_environment = Environment(loader=FileSystemLoader("src/templates/"))
        template = jinja2_environment.get_template(f"{CONFIG_FILE_NAME}.j2")
        content = template.render(
            instance=self._config_instance,
            pid_directory=self._config_pid_directory,
            amf_name=self._config_amf_name,
            mcc=self._config_mcc,
            mnc=self._config_mnc,
            region_id=self._config_region_id,
            amf_set_id=self._config_amf_set_id,
            served_guami_mcc_0=self._config_served_guami_mcc_0,
            served_guami_mnc_0=self._config_served_guami_mnc_0,
            served_guami_region_id_0=self._config_served_guami_region_id_0,
            served_guami_amf_set_id_0=self._config_served_guami_amf_set_id_0,
            served_guami_mcc_1=self._config_served_guami_mcc_1,
            served_guami_mnc_1=self._config_served_guami_mnc_1,
            served_guami_region_id_1=self._config_served_guami_region_id_1,
            served_guami_amf_set_id_1=self._config_served_guami_amf_set_id_1,
            plmn_support_mcc=self._config_plmn_support_mcc,
            plmn_support_mnc=self._config_plmn_support_mnc,
            plmn_support_tac=self._config_plmn_support_tac,
            sd_0=self._config_sd_0,
            sd_1=self._config_sd_1,
            sd_2=self._config_sd_2,
            sst_0=self._config_sst_0,
            sst_1=self._config_sst_1,
            sst_2=self._config_sst_2,
            ngap_amf_interface_name=self._config_ngap_amf_interface_name,
            ngap_amf_interface_port=self._config_ngap_amf_interface_port,
            n11_amf_interface_name=self._config_n11_amf_interface_name,
            n11_amf_interface_port=self._config_n11_amf_interface_port,
            n11_amf_api_version=self._config_n11_amf_api_version,
            n11_amf_interface_http2_port=self._config_n11_amf_interface_http2_port,
            smf_instance_id_0=self._config_smf_instance_id_0,
            smf_ipv4_address_0=self._config_smf_ipv4_address_0,
            smf_port_0=self._config_smf_port_0,
            smf_http2_port_0=self._config_smf_http2_port_0,
            smf_api_version_0=self._config_smf_api_version_0,
            smf_fqdn_0=self._config_smf_fqdn_0,
            smf_instance_id_1=self._config_smf_instance_id_1,
            smf_ipv4_address_1=self._config_smf_ipv4_address_1,
            smf_port_1=self._config_smf_port_1,
            smf_http2_port_1=self._config_smf_http2_port_1,
            smf_api_version_1=self._config_smf_api_version_1,
            smf_fqdn_1=self._config_smf_fqdn_1,
            nrf_ipv4_address=self.nrf_requires.nrf_ipv4_address,
            nrf_port=self.nrf_requires.nrf_port,
            nrf_api_version=self.nrf_requires.nrf_api_version,
            nrf_fqdn=self.nrf_requires.nrf_fqdn,
            udm_ipv4_address=self.udm_requires.udm_ipv4_address,
            udm_port=self.udm_requires.udm_port,
            udm_api_version=self.udm_requires.udm_api_version,
            udm_fqdn=self.udm_requires.udm_fqdn,
            ausf_ipv4_address=self.ausf_requires.ausf_ipv4_address,
            ausf_port=self.ausf_requires.ausf_port,
            ausf_api_version=self.ausf_requires.ausf_api_version,
            ausf_fqdn=self.ausf_requires.ausf_fqdn,
            nssf_ipv4_address=self._config_nssf_ipv4_address,
            nssf_port=self._config_nssf_port,
            nssf_api_version=self._config_nssf_api_version,
            nssf_fqdn=self._config_nssf_fqdn,
            nf_registration=self._config_nf_registration,
            nrf_selection=self._config_nrf_selection,
            external_nrf=self._config_external_nrf,
            smf_selection=self._config_smf_selection,
            external_ausf=self._config_external_ausf,
            external_udm=self._config_external_udm,
            external_nssf=self._config_external_nssf,
            use_fqdn_dns=self._config_use_fqdn_dns,
            use_http2=self._config_use_http2,
            mysql_server=self._database_relation_server,
            mysql_user=self._database_relation_user,
            mysql_password=self._database_relation_password,
            mysql_database=DATABASE_NAME,
            integrity_algorithm_list=self._config_integrity_algorithm_list,
            cyphering_algorithm_list=self._config_cyphering_algorithm_list,
        )

        self._container.push(path=f"{BASE_CONFIG_PATH}/{CONFIG_FILE_NAME}", source=content)
        logger.info(f"Wrote file to container: {CONFIG_FILE_NAME}")

    @property
    def _config_file_is_pushed(self) -> bool:
        """Check if config file is pushed to the container."""
        if not self._container.exists(f"{BASE_CONFIG_PATH}/{CONFIG_FILE_NAME}"):
            logger.info(f"Config file is not written: {CONFIG_FILE_NAME}")
            return False
        logger.info("Config file is pushed")
        return True

    @property
    def _config_instance(self) -> str:
        return "0"

    @property
    def _config_pid_directory(self) -> str:
        return "/var/run"

    @property
    def _config_mcc(self) -> str:
        return self.model.config["mcc"]

    @property
    def _config_mnc(self) -> str:
        return self.model.config["mnc"]

    @property
    def _config_region_id(self) -> str:
        return self.model.config["region_id"]

    @property
    def _config_amf_set_id(self) -> str:
        return self.model.config["amf_set_id"]

    @property
    def _config_served_guami_mcc_0(self) -> str:
        return self.model.config["served_guami_mcc_0"]

    @property
    def _config_served_guami_mnc_0(self) -> str:
        return self.model.config["served_guami_mnc_0"]

    @property
    def _config_served_guami_region_id_0(self) -> str:
        return self.model.config["served_guami_region_id_0"]

    @property
    def _config_served_guami_amf_set_id_0(self) -> str:
        return self.model.config["served_guami_amf_set_id_0"]

    @property
    def _config_served_guami_mcc_1(self) -> str:
        return self.model.config["served_guami_mcc_1"]

    @property
    def _config_served_guami_mnc_1(self) -> str:
        return self.model.config["served_guami_mnc_1"]

    @property
    def _config_served_guami_region_id_1(self) -> str:
        return self.model.config["served_guami_region_id_1"]

    @property
    def _config_served_guami_amf_set_id_1(self) -> str:
        return self.model.config["served_guami_amf_set_id_1"]

    @property
    def _config_plmn_support_mcc(self) -> str:
        return self.model.config["plmn_support_mcc"]

    @property
    def _config_plmn_support_mnc(self) -> str:
        return self.model.config["plmn_support_mnc"]

    @property
    def _config_plmn_support_tac(self) -> str:
        return self.model.config["plmn_support_tac"]

    @property
    def _config_sd_0(self) -> str:
        return self.model.config["sd_0"]

    @property
    def _config_sst_0(self) -> str:
        return self.model.config["sst_0"]

    @property
    def _config_sd_1(self) -> str:
        return self.model.config["sd_1"]

    @property
    def _config_sst_1(self) -> str:
        return self.model.config["sst_1"]

    @property
    def _config_sd_2(self) -> str:
        return self.model.config["sd_2"]

    @property
    def _config_sst_2(self) -> str:
        return self.model.config["sst_2"]

    @property
    def _config_amf_name(self) -> str:
        return "OAI_AMF"

    @property
    def _config_use_fqdn_dns(self) -> str:
        return "yes"

    @property
    def _config_register_nrf(self) -> str:
        return "no"

    @property
    def _config_use_http2(self) -> str:
        return "no"

    @property
    def _config_n11_amf_interface_name(self) -> str:
        return self.model.config["amfInterfaceNameForN11"]

    @property
    def _config_ngap_amf_interface_name(self) -> str:
        return self.model.config["amfInterfaceNameForNGAP"]

    @property
    def _config_ngap_amf_interface_port(self) -> str:
        return "38412"

    @property
    def _config_n11_amf_interface_port(self) -> str:
        return "80"

    @property
    def _config_n11_amf_api_version(self) -> str:
        return "v1"

    @property
    def _config_n11_amf_interface_http2_port(self) -> str:
        return "9090"

    @property
    def _config_smf_instance_id_0(self) -> str:
        return "1"

    @property
    def _config_smf_ipv4_address_0(self) -> str:
        return "0.0.0.0"

    @property
    def _config_smf_port_0(self) -> str:
        return "80"

    @property
    def _config_smf_http2_port_0(self) -> str:
        return "8080"

    @property
    def _config_smf_api_version_0(self) -> str:
        return "v1"

    @property
    def _config_smf_fqdn_0(self) -> str:
        return "oai-smf-svc"

    @property
    def _config_smf_instance_id_1(self) -> str:
        return "2"

    @property
    def _config_smf_ipv4_address_1(self) -> str:
        return "0.0.0.0"

    @property
    def _config_smf_port_1(self) -> str:
        return "80"

    @property
    def _config_smf_http2_port_1(self) -> str:
        return "8080"

    @property
    def _config_smf_api_version_1(self) -> str:
        return "v1"

    @property
    def _config_smf_fqdn_1(self) -> str:
        return "localhost"

    @property
    def _config_nssf_ipv4_address(self) -> str:
        return "127.0.0.1"

    @property
    def _config_nssf_port(self) -> str:
        return "80"

    @property
    def _config_nssf_api_version(self) -> str:
        return "v1"

    @property
    def _config_nssf_fqdn(self) -> str:
        return "oai-nssf-svc"

    @property
    def _config_nf_registration(self) -> str:
        return "yes"

    @property
    def _config_nrf_selection(self) -> str:
        return "no"

    @property
    def _config_external_nrf(self) -> str:
        return "no"

    @property
    def _config_smf_selection(self) -> str:
        return "yes"

    @property
    def _config_external_ausf(self) -> str:
        return "yes"

    @property
    def _config_external_udm(self) -> str:
        return "no"

    @property
    def _config_external_nssf(self) -> str:
        return "no"

    @property
    def _config_integrity_algorithm_list(self) -> str:
        return '[ "NIA0" , "NIA1" , "NIA2" ]'

    @property
    def _config_cyphering_algorithm_list(self) -> str:
        return '[ "NEA0" , "NEA1" , "NEA2" ]'

    @property
    def _database_relation_server(self) -> str:
        relation_data = self.database.fetch_relation_data()
        relation = self.model.get_relation(relation_name="database")
        if not relation:
            raise ValueError("Database relation is not created")
        return relation_data[relation.id]["endpoints"].split(",")[0]

    @property
    def _database_relation_user(self) -> str:
        relation_data = self.database.fetch_relation_data()
        relation = self.model.get_relation(relation_name="database")
        if not relation:
            raise ValueError("Database relation is not created")
        return relation_data[relation.id]["username"]

    @property
    def _database_relation_password(self) -> str:
        relation_data = self.database.fetch_relation_data()
        relation = self.model.get_relation(relation_name="database")
        if not relation:
            raise ValueError("Database relation is not created")
        return relation_data[relation.id]["password"]

    @property
    def _pebble_layer(self) -> dict:
        """Return a dictionary representing a Pebble layer."""
        return {
            "summary": "amf layer",
            "description": "pebble config layer for amf",
            "services": {
                "amf": {
                    "override": "replace",
                    "summary": "amf",
                    "command": f"/openair-amf/bin/oai_amf -c {BASE_CONFIG_PATH}/{CONFIG_FILE_NAME} -o",  # noqa: E501
                    "startup": "enabled",
                }
            },
        }


if __name__ == "__main__":
    main(Oai5GAMFOperatorCharm)
