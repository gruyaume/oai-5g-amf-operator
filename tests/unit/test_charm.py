# Copyright 2022 Guillaume Belanger
# See LICENSE file for licensing details.

import unittest
from unittest.mock import patch

import ops.testing
from ops.model import ActiveStatus
from ops.testing import Harness

from charm import Oai5GAMFOperatorCharm


class TestCharm(unittest.TestCase):
    @patch(
        "charm.KubernetesServicePatch",
        lambda charm, ports: None,
    )
    def setUp(self):
        ops.testing.SIMULATE_CAN_CONNECT = True
        self.model_name = "whatever"
        self.addCleanup(setattr, ops.testing, "SIMULATE_CAN_CONNECT", False)
        self.harness = Harness(Oai5GAMFOperatorCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.set_model_name(name=self.model_name)
        self.harness.begin()

    def _create_nrf_relation_with_valid_data(self):
        relation_id = self.harness.add_relation("fiveg-nrf", "nrf")
        self.harness.add_relation_unit(relation_id=relation_id, remote_unit_name="nrf/0")

        nrf_ipv4_address = "1.2.3.4"
        nrf_port = "81"
        nrf_api_version = "v1"
        nrf_fqdn = "nrf.example.com"
        key_values = {
            "nrf_ipv4_address": nrf_ipv4_address,
            "nrf_port": nrf_port,
            "nrf_fqdn": nrf_fqdn,
            "nrf_api_version": nrf_api_version,
        }
        self.harness.update_relation_data(
            relation_id=relation_id, app_or_unit="nrf", key_values=key_values
        )
        return nrf_ipv4_address, nrf_port, nrf_api_version, nrf_fqdn

    def _create_udm_relation_with_valid_data(self):
        relation_id = self.harness.add_relation("fiveg-udm", "udm")
        self.harness.add_relation_unit(relation_id=relation_id, remote_unit_name="udm/0")

        udm_ipv4_address = "1.2.3.4"
        udm_port = "81"
        udm_api_version = "v1"
        udm_fqdn = "udm.example.com"
        key_values = {
            "udm_ipv4_address": udm_ipv4_address,
            "udm_port": udm_port,
            "udm_fqdn": udm_fqdn,
            "udm_api_version": udm_api_version,
        }
        self.harness.update_relation_data(
            relation_id=relation_id, app_or_unit="udm", key_values=key_values
        )
        return udm_ipv4_address, udm_port, udm_api_version, udm_fqdn

    def _create_ausf_relation_with_valid_data(self):
        relation_id = self.harness.add_relation("fiveg-ausf", "ausf")
        self.harness.add_relation_unit(relation_id=relation_id, remote_unit_name="ausf/0")

        ausf_ipv4_address = "1.2.3.4"
        ausf_port = "81"
        ausf_api_version = "v1"
        ausf_fqdn = "ausf.example.com"
        key_values = {
            "ausf_ipv4_address": ausf_ipv4_address,
            "ausf_port": ausf_port,
            "ausf_fqdn": ausf_fqdn,
            "ausf_api_version": ausf_api_version,
        }
        self.harness.update_relation_data(
            relation_id=relation_id, app_or_unit="ausf", key_values=key_values
        )
        return ausf_ipv4_address, ausf_port, ausf_api_version, ausf_fqdn

    def _create_database_relation_with_valid_data(self):
        relation_id = self.harness.add_relation(relation_name="database", remote_app="mysql")
        self.harness.add_relation_unit(relation_id=relation_id, remote_unit_name="mysql/0")
        username = "whatever username"
        password = "whatever password"
        endpoints = "whatever endpoint 1,whatever endpoint 2"
        key_values = {
            "username": username,
            "password": password,
            "endpoints": endpoints,
        }
        self.harness.update_relation_data(
            relation_id=relation_id, app_or_unit="mysql", key_values=key_values
        )
        return username, password, endpoints

    @patch("ops.model.Container.push")
    def test_given_nrf_relation_contains_nrf_info_when_nrf_relation_joined_then_config_file_is_pushed(  # noqa: E501
        self, mock_push
    ):
        self.harness.set_can_connect(container="amf", val=True)
        (
            nrf_ipv4_address,
            nrf_port,
            nrf_api_version,
            nrf_fqdn,
        ) = self._create_nrf_relation_with_valid_data()

        (
            udm_ipv4_address,
            udm_port,
            udm_api_version,
            udm_fqdn,
        ) = self._create_udm_relation_with_valid_data()

        (
            ausf_ipv4_address,
            ausf_port,
            ausf_api_version,
            ausf_fqdn,
        ) = self._create_ausf_relation_with_valid_data()
        (username, password, endpoints) = self._create_database_relation_with_valid_data()

        mock_push.assert_called_with(
            path="/openair-amf/etc/amf.conf",
            source="################################################################################\n"  # noqa: E501, W505
            "# Licensed to the OpenAirInterface (OAI) Software Alliance under one or more\n"
            "# contributor license agreements.  See the NOTICE file distributed with\n"
            "# this work for additional information regarding copyright ownership.\n"
            "# The OpenAirInterface Software Alliance licenses this file to You under\n"
            '# the OAI Public License, Version 1.1  (the "License"); you may not use this file\n'  # noqa: E501, W505
            "# except in compliance with the License.\n"
            "# You may obtain a copy of the License at\n"
            "#\n#      http://www.openairinterface.org/?page_id=698\n"
            "#\n"
            "# Unless required by applicable law or agreed to in writing, software\n"
            '# distributed under the License is distributed on an "AS IS" BASIS,\n'
            "# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.\n"
            "# See the License for the specific language governing permissions and\n"
            "# limitations under the License.\n"
            "#-------------------------------------------------------------------------------\n"  # noqa: E501, W505
            "# For more information about the OpenAirInterface (OAI) Software Alliance:\n"
            "#      contact@openairinterface.org\n"
            "################################################################################\n\n"  # noqa: E501, W505
            "AMF =\n"
            "{\n"
            "  INSTANCE_ID = 0;            # 0 is the default\n"
            '  PID_DIRECTORY = "/var/run";   # /var/run is the default\n\n'
            '  AMF_NAME = "OAI_AMF";\n\n'
            "  RELATIVE_CAPACITY = 30;\n"
            "  # Display statistics about whole system (in seconds)\n"
            "  STATISTICS_TIMER_INTERVAL = 20;\n\n"
            "  CORE_CONFIGURATION:\n"
            "  {\n"
            '    EMERGENCY_SUPPORT = "false";\n'
            "  };\n\n"
            "  GUAMI:\n"
            "  {\n"
            '    MCC = "208"; MNC = "99"; RegionID = "128"; AMFSetID = "1"; AMFPointer = "1"\n'  # noqa: E501, W505
            "  }\n\n"
            "  SERVED_GUAMI_LIST = (\n"
            '    {MCC = "208"; MNC = "99"; RegionID = "128"; AMFSetID = "1"; AMFPointer = "0"}, #48bits <MCC><MNC><RegionID><AMFSetID><AMFPointer>\n'  # noqa: E501, W505
            '    {MCC = "460"; MNC = "11"; RegionID = "10"; AMFSetID = "1"; AMFPointer = "1"}  #48bits <MCC><MNC><RegionID><AMFSetID><AMFPointer>\n'  # noqa: E501, W505
            "  );\n\n"
            "  PLMN_SUPPORT_LIST = (\n"
            "  {\n"
            '    MCC = "208"; MNC = "99"; TAC = 0x0001;\n'
            "    SLICE_SUPPORT_LIST = (\n"
            '      {SST = "1"; SD = "1"},\n'
            '      {SST = "111"; SD = "124"},\n'
            '      {SST = "2"; SD = "2"}\n'
            "     )\n"
            "  }\n"
            "  );\n\n"
            "  INTERFACES:\n"
            "  {\n"
            "    # AMF binded interface for N1/N2 interface (NGAP)\n"
            "    NGAP_AMF:\n"
            "    {\n"
            '      INTERFACE_NAME = "eth0";\n'
            '      IPV4_ADDRESS   = "read";\n'
            "      PORT           = 38412;\n"
            "      PPID           = 60;\n"
            "    };\n\n"
            "    # AMF binded interface for SBI (N11 (SMF)/N12 (AUSF), etc.)\n"
            "    N11:\n"
            "    {\n"
            '      INTERFACE_NAME = "eth0";\n'
            '      IPV4_ADDRESS   = "read";\n'
            "      PORT           = 80;\n"
            '      API_VERSION    = "v1";\n'
            "      HTTP2_PORT     = 9090;\n\n"
            "      SMF_INSTANCES_POOL = (\n"
            '        {SMF_INSTANCE_ID = 1; IPV4_ADDRESS = "0.0.0.0"; PORT = "80"; HTTP2_PORT = 8080, VERSION = "v1"; FQDN = "oai-smf-svc", SELECTED = "true"},\n'  # noqa: E501, W505
            '        {SMF_INSTANCE_ID = 2; IPV4_ADDRESS = "0.0.0.0"; PORT = "80"; HTTP2_PORT = 8080, VERSION = "v1"; FQDN = "localhost", SELECTED = "false"}\n'  # noqa: E501, W505
            "      );\n"
            "    };\n\n"
            "    NRF :\n"
            "    {\n"
            f'      IPV4_ADDRESS = "{nrf_ipv4_address}";\n'
            f"      PORT         = {nrf_port};            # Default: 80\n"
            f'      API_VERSION  = "{nrf_api_version}";\n'
            f'      FQDN         = "{nrf_fqdn}"\n'
            "    };\n\n"
            "    AUSF :\n"
            "    {\n"
            f'      IPV4_ADDRESS = "{ ausf_ipv4_address }";\n'
            f"      PORT         = { ausf_port };            # Default: 80\n"
            f'      API_VERSION  = "{ ausf_api_version }";\n'
            f'      FQDN         = "{ ausf_fqdn }"\n'
            "    };\n\n"
            "    UDM :\n"
            "    {\n"
            f'      IPV4_ADDRESS = "{ udm_ipv4_address }";\n'
            f"      PORT         = { udm_port };             # Default: 80\n"
            f'      API_VERSION  = "{ udm_api_version }";\n'
            f'      FQDN         = "{ udm_fqdn }";\n'
            "    };\n\n"
            "    NSSF :\n"
            "    {\n"
            '      IPV4_ADDRESS = "127.0.0.1";\n'
            "      PORT         = 80;            # Default: 80\n"
            '      API_VERSION  = "v1";\n'
            '      FQDN         = "oai-nssf-svc"\n'
            "    };\n  };\n\n  SUPPORT_FEATURES:\n"
            '  {\n     # STRING, {"yes", "no"},\n'
            '     NF_REGISTRATION = "yes";  # Set to yes if AMF resgisters to an NRF\n'
            '     NRF_SELECTION   = "no";    # Set to yes to enable NRF discovery and selection\n'  # noqa: E501, W505
            '     EXTERNAL_NRF    = "no";     # Set to yes if AMF works with an external NRF\n'  # noqa: E501, W505
            '     SMF_SELECTION   = "yes";    # Set to yes to enable SMF discovery and selection\n'  # noqa: E501, W505
            '     EXTERNAL_AUSF   = "yes";    # Set to yes if AMF works with an external AUSF\n'  # noqa: E501, W505
            '     EXTERNAL_UDM    = "no";     # Set to yes if AMF works with an external UDM\n'  # noqa: E501, W505
            '     EXTERNAL_NSSF   = "no";    # Set to yes if AMF works with an external NSSF\n'  # noqa: E501, W505
            '     USE_FQDN_DNS    = "yes";     # Set to yes if AMF relies on a DNS to resolve NRF/SMF/UDM/AUSF\'s FQDN\n'  # noqa: E501, W505
            '     USE_HTTP2       = "no";        # Set to yes to enable HTTP2 for AMF server\n'  # noqa: E501, W505
            "}\n\n"
            "  AUTHENTICATION:\n"
            "  {\n"
            "    ## MySQL mandatory options\n"
            f'    MYSQL_server = "{ endpoints.split(",")[0] }"; # MySQL Server address\n'
            f'    MYSQL_user   = "{ username }";   # Database server login\n'
            f'    MYSQL_pass   = "{ password }";   # Database server password\n'
            f'    MYSQL_db     = "oai_db";     # Your database name\n'
            '    RANDOM = "true";\n'
            "  };\n\n"
            "  NAS:\n"
            "  {\n"
            '    ORDERED_SUPPORTED_INTEGRITY_ALGORITHM_LIST = [ "NIA0" , "NIA1" , "NIA2" ];  #Default [ "NIA0" , "NIA1" , "NIA2" ];\n'  # noqa: E501, W505
            '    ORDERED_SUPPORTED_CIPHERING_ALGORITHM_LIST = [ "NEA0" , "NEA1" , "NEA2" ]; #Default [ "NEA0" , "NEA1" , "NEA2" ];\n'  # noqa: E501, W505
            "  };\n"
            "};\n\n"
            "MODULES =\n"
            "{\n"
            "  NGAP_MESSAGE = (\n"
            '    {MSG_NAME = "NGSetupRequest"; ProcedureCode = 21; TypeOfMessage = "initialMessage"}\n'  # noqa: E501, W505
            "  );\n"
            "};",
        )

    @patch("ops.model.Container.push")
    def test_given_nrf_and_db_relation_are_set_when_config_changed_then_pebble_plan_is_created(  # noqa: E501
        self, _
    ):
        self.harness.set_can_connect(container="amf", val=True)
        self._create_nrf_relation_with_valid_data()
        self._create_udm_relation_with_valid_data()
        self._create_ausf_relation_with_valid_data()
        self._create_database_relation_with_valid_data()

        expected_plan = {
            "services": {
                "amf": {
                    "override": "replace",
                    "summary": "amf",
                    "command": "/openair-amf/bin/oai_amf -c /openair-amf/etc/amf.conf -o",
                    "startup": "enabled",
                }
            },
        }
        self.harness.container_pebble_ready("amf")
        updated_plan = self.harness.get_container_pebble_plan("amf").to_dict()
        self.assertEqual(expected_plan, updated_plan)
        service = self.harness.model.unit.get_container("amf").get_service("amf")
        self.assertTrue(service.is_running())
        self.assertEqual(self.harness.model.unit.status, ActiveStatus())

    def test_given_unit_is_leader_when_amf_relation_joined_then_amf_relation_data_is_set(self):
        self.harness.set_leader(True)

        relation_id = self.harness.add_relation(relation_name="fiveg-amf", remote_app="amf")
        self.harness.add_relation_unit(relation_id=relation_id, remote_unit_name="amf/0")

        relation_data = self.harness.get_relation_data(
            relation_id=relation_id, app_or_unit=self.harness.model.app.name
        )

        assert relation_data["amf_ipv4_address"] == "127.0.0.1"
        assert relation_data["amf_fqdn"] == f"oai-5g-amf.{self.model_name}.svc.cluster.local"
        assert relation_data["amf_port"] == "80"
        assert relation_data["amf_api_version"] == "v1"
