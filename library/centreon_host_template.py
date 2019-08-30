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
module: centreon_host_template
version_added: "2.2"
short_description: add host template to centreon

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
      - Host Template list for this host template
    type: list
  alias:
    description:
      - Host template alias
  ipaddr:
    description:
      - IP address
  params:
    description:
      - Config specific parameter (dict)
  macros:
    description:
      - Set Host Macros (dict)
  state:
    description:
      - Create / Delete host template on Centreon
    default: present
    choices: ['present', 'absent']
  status:
    description:
      - Enable / Disable host template on Centreon
    default: enabled
    choices: c
requirements:
  - Python Centreon API
author:
    - Guillaume Watteeux
'''

EXAMPLES = '''
# Add host template
 - centreon_host_template:
     url: 'https://centreon.company.net/centreon'
     username: 'ansible_api'
     password: 'strong_pass_from_vault'
     name: "{{ ansible_fqdn }}"
     alias: "{{ ansible_hostname }}"
     ipaddr: "{{ ansible_default_ipv4.address }}"
     hosttemplates:
       - OS-Linux-SNMP-custom
       - OS-Linux-SNMP-disk
     status: enabled
     state: present
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
            params=dict(type='list', default=[]),
            macros=dict(type='list', default=[]),
            state=dict(default='present', choices=['present', 'absent']),
            status=dict(default='enabled', choices=['enabled', 'disabled'])
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
    params = module.params["params"]
    macros = module.params["macros"]
    state = module.params["state"]
    status = module.params["status"]

    has_changed = False

    try:
        centreon = Centreon(url, username, password)
    except Exception as e:
        module.fail_json(
            msg="Unable to connect to Centreon API: %s" % e.message
        )

    data = list()

    ht = None
    try:
        ht = centreon.host_template.get(name)
    except requests.exceptions.HTTPError as e:
        data.append("Host template %s not found" % name)

    if ht is None and state == "present":
        try:
            data.append("Add %s %s %s %s" %
                        (name, alias, ipaddr, hosttemplates))
            centreon.host_template.add(
                name,
                alias,
                ipaddr,
                hosttemplates
            )
            has_changed = True
            data.append("Add host template: %s" % name)
        except Exception as e:
            module.fail_json(msg='Create: %s - %s' % (e.message, data), changed=has_changed)

        try:
            ht = centreon.host_template.get(name)
        except requests.exceptions.HTTPError as e:
            module.fail_json(msg='Failed to retrieve host template %s after creation: %s' % (name, e.message), changed=has_changed)

    if not ht:
        module.fail_json(msg="Unable to find host template %s " % name, changed=has_changed)

    if state == "absent":
        try:
            centreon.host_template.delete(name)
            has_changed = True
            module.exit_json(
                changed=has_changed, result="Host %s deleted" % name
            )
        except requests.exceptions.HTTPError as e:
            module.fail_json(msg='Failed to delete host template: %s' % e.message, changed=has_changed)

    if status == "disabled" and int(ht.state) == 1:
        try:
            centreon.host_template.disable(name)
            has_changed = True
            data.append("Host disabled")
        except requests.exceptions.HTTPError as e:
            module.fail_json(msg='Unable to disable host template: %s' % e.message, changed=has_changed)

    if status == "enabled" and int(ht.state) == 0:
        try:
            centreon.host_template.enable(name)
            has_changed = True
            data.append("Host enabled")
        except requests.exceptions.HTTPError as e:
            module.fail_json(msg='Unable to enable host template: %s' % e.message, changed=has_changed)

    if not ht.address == ipaddr and ipaddr:
        try:
            centreon.host_template.setparam(name, 'address', ipaddr)
            has_changed = True
            data.append(
                "Change ip addr: %s -> %s" % (ht.address, ipaddr)
            )
        except requests.exceptions.HTTPError as e:
            module.fail_json(msg='Unable to change ip addr: %s' % e.message, changed=has_changed)

    if not ht.alias == alias and alias:
        try:
            centreon.host_template.setparam(name, 'alias', alias)
            has_changed = True
            data.append("Change alias: %s -> %s" % (ht.alias, alias))
        except requests.exceptions.HTTPError as e:
            module.fail_json(msg='Unable to change alias: %s' % e.message, changed=has_changed)

    #### HostTemplates
    if hosttemplates:
        try:
            gettemplate_result = centreon.host_template.gettemplate(name)
        except requests.exceptions.HTTPError as e:
            module.fail_json(
                msg="Unable to retrieve list of parent templates: %s" % e.message,
                changed=has_changed
            )

        parent_template_list = list()
        for parent_ht in gettemplate_result['result']:
            parent_template_list.append(parent_ht['name'])

        new_template_list = list(set(hosttemplates) - set(parent_template_list))
        data.append(new_template_list)
        if new_template_list:
            try:
                centreon.host_template.addtemplate(new_template_list)
                has_changed = True
                data.append("Add parent HostTemplate: %s" % new_template_list)
            except requests.exceptions.HTTPError as e:
                module.fail_json(
                    msg="Unable to add templates: %s" % e.message,
                    changed=has_changed
                )

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
                centreon.host_template.setmacro(name, k.get('name').upper(), k.get('value'))
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
                centreon.host_template.setparam(k.get('name'), k.get('value'))
                has_changed = True
            except requests.exceptions.HTTPError as e:
                module.fail_json(
                    msg='Unable to set param %s: %s' % (k.get('name'), e.message),
                    changed=has_changed
                )

    module.exit_json(changed=has_changed, msg=data)


if __name__ == '__main__':
    main()
