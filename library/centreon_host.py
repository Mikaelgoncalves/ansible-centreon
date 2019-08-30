#!/usr/bin/python
# -*- coding: utf-8 -*-

# import module snippets
from ansible.module_utils.basic import AnsibleModule
import requests

ANSIBLE_METADATA = {
    'status': ['preview'],
    'supported_by': 'community',
    'metadata_version': '0.2',
    'version': '0.2'
}

DOCUMENTATION = '''
---
module: centreon_host
version_added: "2.2"
short_description: add host to centreon

options:
  url:
    description:
      - Centreon URL
    required: True

  username:
    description:
      - Centreon API username
    required: True
  password:
    description:
      - Centreon API username's password
    required: True
  name:
    description:
      - Hostname
    required: True
  hosttemplates:
    description:
      - Host Template list for this host
    type: list
  alias:
    description:
      - Host alias
  ipaddr:
    description:
      - IP address
  instance:
    description:
      - Poller instance to check host
    default: Central
  hostgroups:
    description:
      - Hostgroups list
    type: list
  hostgroups_action:
    description:
      - Define hostgroups setting method (add/set)
    default: add
    choices: ['add','set']
  params:
    description:
      - Config specific parameter (dict)
  macros:
    description:
      - Set Host Macros (dict)
  state:
    description:
      - Create / Delete host on Centreon
    default: present
    choices: ['present', 'absent']
  status:
    description:
      - Enable / Disable host on Centreon
    default: enabled
    choices: c
requirements:
  - Python Centreon API
author:
    - Guillaume Watteeux
'''

EXAMPLES = '''
# Add host
 - centreon_host:
     url: 'https://centreon.company.net/centreon'
     username: 'ansible_api'
     password: 'strong_pass_from_vault'
     name: "{{ ansible_fqdn }}"
     alias: "{{ ansible_hostname }}"
     ipaddr: "{{ ansible_default_ipv4.address }}"
     hosttemplates:
       - OS-Linux-SNMP-custom
       - OS-Linux-SNMP-disk
     hostgroups:
       - Linux-Servers
       - Production-Servers
       - App1
     hostgroups_action: set
     instance: Central
     status: enabled
     state: present:
     params:
       notes_url: "https://wiki.company.org/servers/{{ ansible_fqdn }}"
       notes: "My Best server"
     macros:
       - name: MACRO1
         value: value1
         ispassword: 1
       - name: MACRO2
         value: value2
         desc: my macro
'''

# =============================================
# Centreon module API Rest
#

try:
    from centreonapi.centreon import Centreon
except ImportError:
    centreonapi_found = False
else:
    centreonapi_found = True


def main():

    module = AnsibleModule(
        argument_spec=dict(
            url=dict(required=True),
            username=dict(default='admin', no_log=True),
            password=dict(default='centreon', no_log=True),
            name=dict(required=True),
            hosttemplates=dict(type='list', default=[]),
            alias=dict(default=None),
            ipaddr=dict(default=None),
            instance=dict(default='Central'),
            hostgroups=dict(type='list', default=[]),
            hostgroups_action=dict(default='add', choices=['add', 'set']),
            params=dict(type='list', default=[]),
            macros=dict(type='list', default=[]),
            state=dict(default='present', choices=['present', 'absent']),
            status=dict(default='enabled', choices=['enabled', 'disabled']),
            applycfg=dict(default=True, type='bool')
        )
    )

    if not centreonapi_found:
        module.fail_json(msg="Python centreonapi module is required (>0.1.0)")

    url = module.params["url"]
    username = module.params["username"]
    password = module.params["password"]
    name = module.params["name"]
    alias = module.params["alias"]
    ipaddr = module.params["ipaddr"]
    hosttemplates = module.params["hosttemplates"]
    instance = module.params["instance"]
    hostgroups = module.params["hostgroups"]
    hostgroups_action = module.params["hostgroups_action"]
    params = module.params["params"]
    macros = module.params["macros"]
    state = module.params["state"]
    status = module.params["status"]
    applycfg = module.params["applycfg"]

    has_changed = False

    try:
        centreon = Centreon(url, username, password)
    except Exception as e:
        module.fail_json(
            msg="Unable to connect to Centreon API: %s" % e.message
        )

    try:
        poller = centreon.poller.get(instance)
    except requests.exceptions.HTTPError as e:
        module.fail_json(msg="Unable to get poller list %s " % e.message)

    data = list()

    host = None
    try:
        host = centreon.host.get(name)
    except requests.exceptions.HTTPError as e:
        data.append("Host %s not found" % name)


    if host is None and state == "present":
        try:
            data.append("Add %s %s %s %s %s %s" %
                        (name, alias, ipaddr, hosttemplates, instance, hostgroups))
            centreon.host.add(
                name,
                alias,
                ipaddr,
                hosttemplates,
                instance,
                hostgroups
            )
            host = centreon.host.get(name)
            has_changed = True
            data.append("Add host: %s" % name)
        except Exception as e:
            module.fail_json(msg='Create: %s - %s' % (e.message, data), changed=has_changed)

        try:
            host = centreon.host.get(name)
        except requests.exceptions.HTTPError as e:
            module.fail_json(msg='Failed to retrieve host %s after creation: %s' % (name, e.message), changed=has_changed)

        # Apply the host templates for create associate services
        try:
            centreon.host.applytemplate(name)
            has_changed = True
        except requests.exceptions.HTTPError as e:
            module.fail_json(msg='Failed while applying templates on host %s - %s' % (name, e.message), changed=has_changed)


    if not host:
        module.fail_json(msg="Unable to find host %s " % name, changed=has_changed)

    if state == "absent":
        try:
            centreon.host.delete(host)
            has_changed = True
        except requests.exceptions.HTTPError as e:
            module.fail_json(msg='Failed to delete host: %s' % e.message, changed=has_changed)
        if applycfg:
            try:
                centreon.poller.applycfg(instance)
                has_changed = True
            except requests.exceptions.HTTPError as e:
                module.fail_json(msg='Failed while reloading poller: %s' % e.message, changed=has_changed)
        module.exit_json(changed=has_changed, result="Host %s deleted" % name)

    if status == "disabled" and int(host.state) == 1:
        try:
            centreon.host.disable(name)
            has_changed = True
            data.append("Host disabled")
        except requests.exceptions.HTTPError as e:
            module.fail_json(msg='Unable to disable host: %s' % e.message, changed=has_changed)

    if status == "enabled" and int(host.state) == 0:
        try:
            centreon.host.enable(name)
            has_changed = True
            data.append("Host enabled")
        except requests.exceptions.HTTPError as e:
            module.fail_json(msg='Unable to enable host: %s' % e.message, changed=has_changed)

    if not host.address == ipaddr and ipaddr:
        try:
            centreon.host.setparam(name, 'address', ipaddr)
            has_changed = True
            data.append(
                "Change ip addr: %s -> %s" % (host.address, ipaddr)
            )
        except requests.exceptions.HTTPError as e:
            module.fail_json(msg='Unable to change ip addr: %s' % e.message, changed=has_changed)

    if not host.alias == alias and alias:
        try:
            centreon.host_template.setparam(name, 'alias', alias)
            has_changed = True
            data.append("Change alias: %s -> %s" % (host.alias, alias))
        except requests.exceptions.HTTPError as e:
            module.fail_json(msg='Unable to change alias: %s' % e.message, changed=has_changed)

    #### HostGroup
    if hostgroups:
        try:
            gethostgroup_result = centreon.host.gethostgroup(name)
        except requests.exceptions.HTTPError as e:
            module.fail_json(
                msg="Unable to retrieve list of host groups: %s" % e.message,
                changed=has_changed
            )
        current_hg_list = [hg['name'] for hg in gethostgroup_result["result"]]
        if hostgroups_action == "add":
            for hg in hostgroups:
                if hg not in current_hg_list:
                    try:
                        centreon.host.addhostgroup(name, hg)
                        has_changed = True
                    except requests.exceptions.HTTPError as e:
                         module.fail_json(
                             msg="Unable to add hostgroups %s: %s" % (hg, e.message),
                             changed=has_changed
                         )
        else:
            if set(current_hg_list) > set(hostgroups):
                try:
                    centreon.host.sethostgroup(name, hostgroups)
                    has_changed = True
                    data.append("Set hostgroups: %s" % hostgroups)
                except requests.exceptions.HTTPError as e:
                    module.fail_json(
                        msg="Unable to set hostgroups: %s" % (e.message),
                        changed=has_changed
                    )

    #### HostTemplates
    if hosttemplates:
        try:
            gettemplate_result = centreon.host.gettemplate(name)
        except requests.exceptions.HTTPError as e:
            module.fail_json(
                msg="Unable to retrieve list of parent templates: %s" % e.message,
                changed=has_changed
            )

        parent_template_list = list()
        for parent_ht in gettemplate_result['result']:
            parent_template_list.append(parent_ht['name'])

        new_template_list = list(set(hosttemplates) - set(template_list))
        data.append(new_template_list)
        if new_template_list:
            try:
                centreon.host.addtemplate(new_template)
                has_changed = True
                data.append("Add parent HostTemplate: %s" % new_template_list)
            except requests.exceptions.HTTPError as e:
                module.fail_json(
                    msg="Unable to add templates: %s" % e.message,
                    changed=has_changed
                )
            try:
                centreon.host.applytemplate(host)
                has_changed = True
            except requests.exceptions.HTTPError as e:
                module.fail_json(msg='Failed while applying templates on host %s - %s' % (name, e.message), changed=has_changed)


    #### Macros
    if macros:
        # try:
        #     getmacro_result = centreon.host_template.getmacro(name)
        # except requests.exceptions.HTTPError as e:
        #     module.fail_json(
        #         msg="Unable to retrieve list of macros: %s" % e.message,
        #         changed=has_changed
        #     )
        # current_macro_dict = {}
        # for current_macro in getmacro_result['result']:
        #     k = current_macro['macro name']
        #     v = current_macro['macro value']
        #     macro_dict[k] = v

        # NB: cannot seem to set `description` and `is_password` w/ current clapi version

        for k in macros:
            try:
                centreon.host.setmacro(name, k.get('name').upper(), k.get('value'))
                has_changed = True
                data.append("Add macros %s" % k.get('name').upper())
            except requests.exceptions.HTTPError as e:
                module.fail_json(
                    msg="Unable to set macro %s: %s" % (k.get('name'), e.message),
                    changed=has_changed
                )

    #### Params
    if params:
        for k in params:
            try:
                centreon.host.setparam(k.get('name'), k.get('value'))
                has_changed = True
            except requests.exceptions.HTTPError as e:
                module.fail_json(
                    msg='Unable to set param %s: %s' % (k.get('name'), e.message),
                    changed=has_changed
                )

    # TODO: fix this
    if applycfg and has_changed:
        try:
            centreon.poller.applycfg(instance)
            has_changed = True
        except requests.exceptions.HTTPError as e:
            module.fail_json(msg='Failed while reloading poller: %s' % e.message, changed=has_changed)
    module.exit_json(changed=has_changed, msg=data)


if __name__ == '__main__':
    main()
