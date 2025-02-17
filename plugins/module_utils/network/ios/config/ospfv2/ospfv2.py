# -*- coding: utf-8 -*-
# Copyright 2020 Red Hat
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""
The ios_ospfv2 class
It is in this file where the current configuration (as dict)
is compared to the provided configuration (as dict) and the command set
necessary to bring the current configuration to it's desired end-state is
created
"""
from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.module_utils.six import iteritems
from ansible_collections.community.ciscosmb.plugins.module_utils.network.ios.facts.facts import (
    Facts,
)

from ansible_collections.community.ciscosmb.plugins.module_utils.network.ios.rm_templates.ospfv2 import (
    Ospfv2Template,
)
from ansible_collections.ansible.netcommon.plugins.module_utils.network.common.utils import (
    dict_merge,
)
from ansible_collections.ansible.netcommon.plugins.module_utils.network.common.resource_module import (
    ResourceModule,
)


class Ospfv2(ResourceModule):
    """
    The ios_ospfv2 class
    """

    gather_subset = ["!all", "!min"]

    gather_network_resources = ["ospfv2"]

    def __init__(self, module):
        super(Ospfv2, self).__init__(
            empty_fact_val={},
            facts_module=Facts(module),
            module=module,
            resource="ospfv2",
            tmplt=Ospfv2Template(),
        )

    def execute_module(self):
        """ Execute the module

        :rtype: A dictionary
        :returns: The result from module execution
        """
        self.gen_config()
        self.run_commands()
        return self.result

    def gen_config(self):
        """ Select the appropriate function based on the state provided

        :rtype: A list
        :returns: the commands necessary to migrate the current configuration
                  to the desired configuration
        """
        if self.want:
            wantd = {}
            for entry in self.want.get("processes", []):
                wantd.update({(entry["process_id"], entry.get("vrf")): entry})
        else:
            wantd = {}
        if self.have:
            haved = {}
            for entry in self.have.get("processes", []):
                haved.update({(entry["process_id"], entry.get("vrf")): entry})
        else:
            haved = {}

        # turn all lists of dicts into dicts prior to merge
        for each in wantd, haved:
            self.list_to_dict(each)
        # if state is merged, merge want onto have
        if self.state == "merged":
            wantd = dict_merge(haved, wantd)

        # if state is deleted, limit the have to anything in want
        # set want to nothing
        if self.state == "deleted":
            temp = {}
            for k, v in iteritems(haved):
                if k in wantd or not wantd:
                    temp.update({k: v})
            haved = temp
            wantd = {}

        # delete processes first so we do run into "more than one" errors
        if self.state in ["overridden", "deleted"]:
            for k, have in iteritems(haved):
                if k not in wantd:
                    self.addcmd(have, "pid", True)

        for k, want in iteritems(wantd):
            self._compare(want=want, have=haved.pop(k, {}))

    def _compare(self, want, have):
        parsers = [
            "adjacency",
            "address_family",
            "auto_cost",
            "bfd",
            "capability",
            "compatible",
            "default_information",
            "default_metric",
            "discard_route",
            "distance.admin_distance",
            "distance.ospf",
            "distribute_list.acls",
            "distribute_list.prefix",
            "distribute_list.route_map",
            "domain_id",
            "domain_tag",
            "event_log",
            "help",
            "ignore",
            "interface_id",
            "ispf",
            "limit",
            "local_rib_criteria",
            "log_adjacency_changes",
            "max_lsa",
            "max_metric",
            "maximum_paths",
            "mpls.ldp",
            "mpls.traffic_eng",
            "neighbor",
            "network",
            "nsf.cisco",
            "nsf.ietf",
            "passive_interface",
            "prefix_suppression",
            "priority",
            "queue_depth.hello",
            "queue_depth.update",
            "router_id",
            "shutdown",
            "summary_address",
            "timers.throttle.lsa",
            "timers.throttle.spf",
            "traffic_share",
            "ttl_security",
        ]

        if want != have:
            self.addcmd(want or have, "pid", False)
            self.compare(parsers, want, have)
            self._areas_compare(want, have)
            if want.get("passive_interfaces"):
                self._passive_interfaces_compare(want, have)

    def _areas_compare(self, want, have):
        wareas = want.get("areas", {})
        hareas = have.get("areas", {})
        for name, entry in iteritems(wareas):
            self._area_compare(want=entry, have=hareas.pop(name, {}))
        for name, entry in iteritems(hareas):
            self._area_compare(want={}, have=entry)

    def _area_compare(self, want, have):
        parsers = [
            "area.authentication",
            "area.capability",
            "area.default_cost",
            "area.nssa",
            "area.nssa.translate",
            "area.ranges",
            "area.sham_link",
            "area.stub",
        ]
        self.compare(parsers=parsers, want=want, have=have)
        self._area_compare_filters(want, have)

    def _area_compare_filters(self, wantd, haved):
        for name, entry in iteritems(wantd):
            h_item = haved.pop(name, {})
            if entry != h_item and name == "filter_list":
                filter_list_entry = {}
                filter_list_entry["area_id"] = wantd["area_id"]
                if h_item:
                    li_diff = [
                        item
                        for item in entry + h_item
                        if item not in entry or item not in h_item
                    ]
                else:
                    li_diff = entry
                filter_list_entry["filter_list"] = li_diff
                self.addcmd(filter_list_entry, "area.filter_list", False)
        for name, entry in iteritems(haved):
            if name == "filter_list":
                self.addcmd(entry, "area.filter_list", True)

    def _passive_interfaces_compare(self, want, have):
        parsers = ["passive_interfaces"]
        h_pi = None
        for k, v in iteritems(want["passive_interfaces"]):
            h_pi = have.get("passive_interfaces", [])
            if h_pi and h_pi.get(k) and h_pi.get(k) != v:
                for each in v["name"]:
                    h_interface_name = h_pi[k].get("name", [])
                    if each not in h_interface_name:
                        temp = {
                            "interface": {each: each},
                            "set_interface": v["set_interface"],
                        }
                        self.compare(
                            parsers=parsers,
                            want={"passive_interfaces": temp},
                            have=dict(),
                        )
                    else:
                        h_interface_name.pop(each)
            elif not h_pi:
                if k == "interface":
                    for each in v["name"]:
                        temp = {
                            "interface": {each: each},
                            "set_interface": v["set_interface"],
                        }
                        self.compare(
                            parsers=parsers,
                            want={"passive_interfaces": temp},
                            have=dict(),
                        )
                elif k == "default":
                    self.compare(
                        parsers=parsers,
                        want={"passive_interfaces": {"default": True}},
                        have=dict(),
                    )
            else:
                h_pi.pop(k)
        if (self.state == "replaced" or self.state == "overridden") and h_pi:
            if h_pi.get("default") or h_pi.get("interface"):
                for k, v in iteritems(h_pi):
                    if k == "interface":
                        for each in v["name"]:
                            temp = {
                                "interface": {each: each},
                                "set_interface": not (v["set_interface"]),
                            }
                            self.compare(
                                parsers=parsers,
                                want={"passive_interface": temp},
                                have=dict(),
                            )
                    elif k == "default":
                        self.compare(
                            parsers=parsers,
                            want=dict(),
                            have={"passive_interface": {"default": True}},
                        )

    def list_to_dict(self, param):
        if param:
            for _pid, proc in iteritems(param):
                for area in proc.get("areas", []):
                    ranges = {}
                    for entry in area.get("ranges", []):
                        ranges.update({entry["address"]: entry})
                    if bool(ranges):
                        area["ranges"] = ranges
                    filter_list = {}
                    for entry in area.get("filter_list", []):
                        filter_list.update({entry["direction"]: entry})
                    if bool(filter_list):
                        area["filter_list"] = filter_list
                temp = {}
                for entry in proc.get("areas", []):
                    temp.update({entry["area_id"]: entry})
                proc["areas"] = temp
                if proc.get("distribute_list"):
                    if "acls" in proc.get("distribute_list"):
                        temp = {}
                        for entry in proc["distribute_list"].get("acls", []):
                            temp.update({entry["name"]: entry})
                        proc["distribute_list"]["acls"] = temp
                if proc.get("passive_interfaces") and proc[
                    "passive_interfaces"
                ].get("interface"):
                    temp = {}
                    for entry in proc["passive_interfaces"]["interface"].get(
                        "name", []
                    ):
                        temp.update({entry: entry})
                    proc["passive_interfaces"]["interface"]["name"] = temp
