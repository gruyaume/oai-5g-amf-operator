#!/usr/bin/env python3
# Copyright 2022 Guillaume Belanger
# See LICENSE file for licensing details.

"""Charmed Operator for the OpenAirInterface 5G Core AMF component."""


import logging

from charms.data_platform_libs.v0.database_requires import (  # type: ignore[import]
    DatabaseRequires,
)
from charms.oai_5g_amf.v0.fiveg_amf import FiveGAMFProvides  # type: ignore[import]
from charms.oai_5g_amf.v0.fiveg_n2 import FiveGN2Provides  # type: ignore[import]
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
from ops.model import ActiveStatus, BlockedStatus, ModelError, WaitingStatus

from kubernetes import Kubernetes

logger = logging.getLogger(__name__)

BASE_CONFIG_PATH = "/openair-amf/etc"
CONFIG_FILE_NAME = "amf.conf"
DATABASE_NAME = "oai_db"


class Oai5GAMFOperatorCharm(CharmBase):
    """Charm the service."""

    def __init__(self, *args):
        """Observes juju events."""
        super().__init__(*args)
        self._container_name = self._service_name = "amf"
        self._container = self.unit.get_container(self._container_name)
        self.service_patcher = KubernetesServicePatch(
            charm=self,
            service_type="LoadBalancer",
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
        self.kubernetes = Kubernetes(namespace=self.model.name)
        self.amf_provides = FiveGAMFProvides(self, "fiveg-amf")
        self.n2_provides = FiveGN2Provides(self, "fiveg-n2")
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
        self.framework.observe(
            self.on.fiveg_amf_relation_joined, self._on_fiveg_amf_relation_joined
        )
        self.framework.observe(self.on.fiveg_n2_relation_joined, self._on_fiveg_n2_relation_joined)

    def _on_fiveg_amf_relation_joined(self, event) -> None:
        """Triggered when a relation is joined.

        Args:
            event: Relation Joined Event
        """
        if not self.unit.is_leader():
            return
        if not self._amf_service_started:
            logger.info("AMF service not started yet, deferring event")
            event.defer()
            return
        amf_hostname, amf_ipv4_address = self.kubernetes.get_service_load_balancer_address(
            name=self.app.name
        )
        if not amf_ipv4_address:
            raise Exception("Loadbalancer doesn't have an IP address")
        self.amf_provides.set_amf_information(
            amf_ipv4_address=amf_ipv4_address,
            amf_fqdn=f"{self.model.app.name}.{self.model.name}.svc.cluster.local",
            amf_port=self._config_n11_amf_interface_port,
            amf_api_version=self._config_n11_amf_api_version,
            relation_id=event.relation.id,
        )

    def _on_fiveg_n2_relation_joined(self, event) -> None:
        if not self.unit.is_leader():
            return
        if not self._amf_service_started:
            logger.info("AMF service not started yet, deferring event")
            event.defer()
            return
        amf_hostname, amf_ipv4_address = self.kubernetes.get_service_load_balancer_address(
            name=self.app.name
        )
        if not amf_ipv4_address:
            raise Exception("Loadbalancer doesn't have an IP address")
        self.n2_provides.set_amf_information(
            amf_address=amf_ipv4_address, relation_id=event.relation.id
        )

    @property
    def _amf_service_started(self) -> bool:
        if not self._container.can_connect():
            return False
        try:
            service = self._container.get_service(self._service_name)
        except ModelError:
            return False
        if not service.is_running():
            return False
        return True

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
        self._container.restart(self._service_name)

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
            guami_mcc=self._config_guami_mcc,
            guami_mnc=self._config_guami_mnc,
            guami_region_id=self._config_guami_region_id,
            guami_amf_set_id=self._config_guami_amf_set_id,
            served_guami_0_mcc=self._config_served_guami_0_mcc,
            served_guami_0_mnc=self._config_served_guami_0_mnc,
            served_guami_0_region_id=self._config_served_guami_0_region_id,
            served_guami_0_amf_set_id=self._config_served_guami_0_amf_set_id,
            served_guami_1_mcc=self._config_served_guami_1_mcc,
            served_guami_1_mnc=self._config_served_guami_1_mnc,
            served_guami_1_region_id=self._config_served_guami_1_region_id,
            served_guami_1_amf_set_id=self._config_served_guami_1_amf_set_id,
            plmn_0_support_mcc=self._config_plmn_0_support_mcc,
            plmn_0_support_mnc=self._config_plmn_0_support_mnc,
            plmn_0_support_tac=self._config_plmn_0_support_tac,
            plmn_0_slice_0_sd=self._config_plmn_0_slice_0_sd,
            plmn_0_slice_1_sd=self._config_plmn_0_slice_1_sd,
            plmn_0_slice_2_sd=self._config_plmn_0_slice_2_sd,
            plmn_0_slice_0_sst=self._config_plmn_0_slice_0_sst,
            plmn_0_slice_1_sst=self._config_plmn_0_slice_1_sst,
            plmn_0_slice_2_sst=self._config_plmn_0_slice_2_sst,
            ngap_amf_interface_name=self._config_ngap_amf_interface_name,
            ngap_amf_interface_port=self._config_ngap_amf_interface_port,
            n11_amf_interface_name=self._config_n11_amf_interface_name,
            n11_amf_interface_port=self._config_n11_amf_interface_port,
            n11_amf_api_version=self._config_n11_amf_api_version,
            n11_amf_interface_http2_port=self._config_n11_amf_interface_http2_port,
            smf_0_instance_id=self._config_smf_0_instance_id,
            smf_0_ipv4_address=self._config_smf_0_ipv4_address,
            smf_0_port=self._config_smf_0_port,
            smf_0_http2_port=self._config_smf_0_http2_port,
            smf_0_api_version=self._config_smf_0_api_version,
            smf_0_fqdn=self._config_smf_0_fqdn,
            smf_1_instance_id=self._config_smf_1_instance_id,
            smf_1_ipv4_address=self._config_smf_1_ipv4_address,
            smf_1_port=self._config_smf_1_port,
            smf_1_http2_port=self._config_smf_1_http2_port,
            smf_1_api_version=self._config_smf_1_api_version,
            smf_1_fqdn=self._config_smf_1_fqdn,
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
    def _config_guami_mcc(self) -> str:
        return self.model.config["guami-mcc"]

    @property
    def _config_guami_mnc(self) -> str:
        return self.model.config["guami-mnc"]

    @property
    def _config_guami_region_id(self) -> str:
        return self.model.config["guami-region-id"]

    @property
    def _config_guami_amf_set_id(self) -> str:
        return self.model.config["guami-amf-set-id"]

    @property
    def _config_served_guami_0_mcc(self) -> str:
        return self.model.config["served-guami-0-mcc"]

    @property
    def _config_served_guami_0_mnc(self) -> str:
        return self.model.config["served-guami-0-mnc"]

    @property
    def _config_served_guami_0_region_id(self) -> str:
        return self.model.config["served-guami-0-region-id"]

    @property
    def _config_served_guami_0_amf_set_id(self) -> str:
        return self.model.config["served-guami-0-amf-set-id"]

    @property
    def _config_served_guami_1_mcc(self) -> str:
        return self.model.config["served-guami-1-mcc"]

    @property
    def _config_served_guami_1_mnc(self) -> str:
        return self.model.config["served-guami-1-mnc"]

    @property
    def _config_served_guami_1_region_id(self) -> str:
        return self.model.config["served-guami-1-region-id"]

    @property
    def _config_served_guami_1_amf_set_id(self) -> str:
        return self.model.config["served-guami-1-amf-set-id"]

    @property
    def _config_plmn_0_support_mcc(self) -> str:
        return self.model.config["plmn-0-support-mcc"]

    @property
    def _config_plmn_0_support_mnc(self) -> str:
        return self.model.config["plmn-0-support-mnc"]

    @property
    def _config_plmn_0_support_tac(self) -> str:
        return self.model.config["plmn-0-support-tac"]

    @property
    def _config_plmn_0_slice_0_sd(self) -> str:
        return self.model.config["plmn-0-slice-0-sd"]

    @property
    def _config_plmn_0_slice_0_sst(self) -> str:
        return self.model.config["plmn-0-slice-0-sst"]

    @property
    def _config_plmn_0_slice_1_sd(self) -> str:
        return self.model.config["plmn-0-slice-1-sd"]

    @property
    def _config_plmn_0_slice_1_sst(self) -> str:
        return self.model.config["plmn-0-slice-1-sst"]

    @property
    def _config_plmn_0_slice_2_sd(self) -> str:
        return self.model.config["plmn-0-slice-2-sd"]

    @property
    def _config_plmn_0_slice_2_sst(self) -> str:
        return self.model.config["plmn-0-slice-2-sst"]

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
        return "eth0"

    @property
    def _config_ngap_amf_interface_name(self) -> str:
        return "eth0"

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
    def _config_smf_0_instance_id(self) -> str:
        return "1"

    @property
    def _config_smf_0_ipv4_address(self) -> str:
        return "0.0.0.0"

    @property
    def _config_smf_0_port(self) -> str:
        return "80"

    @property
    def _config_smf_0_http2_port(self) -> str:
        return "8080"

    @property
    def _config_smf_0_api_version(self) -> str:
        return "v1"

    @property
    def _config_smf_0_fqdn(self) -> str:
        return "oai-smf-svc"

    @property
    def _config_smf_1_instance_id(self) -> str:
        return "2"

    @property
    def _config_smf_1_ipv4_address(self) -> str:
        return "0.0.0.0"

    @property
    def _config_smf_1_port(self) -> str:
        return "80"

    @property
    def _config_smf_1_http2_port(self) -> str:
        return "8080"

    @property
    def _config_smf_1_api_version(self) -> str:
        return "v1"

    @property
    def _config_smf_1_fqdn(self) -> str:
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
        return relation_data[relation.id]["endpoints"].split(",")[0].split(":")[0]

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
                self._service_name: {
                    "override": "replace",
                    "summary": "amf",
                    "command": f"/openair-amf/bin/oai_amf -c {BASE_CONFIG_PATH}/{CONFIG_FILE_NAME} -o",  # noqa: E501
                    "startup": "enabled",
                }
            },
        }


if __name__ == "__main__":
    main(Oai5GAMFOperatorCharm)
