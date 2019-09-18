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
module: centreon_service_template
version_added: "2.2"
short_description: add service template to centreon

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
      - Servicename
    required: True
  parenttemplate:
    description:
      - Parent Service Template for this service template
    type: list
  alias:
    description:
      - Service template alias
  params:
    description:
      - Config specific parameter (dict)
  macros:
    description:
      - Set Service Macros (dict)
  state:
    description:
      - Create / Delete service template on Centreon
    default: present
    choices: ['present', 'absent']
requirements:
  - Python Centreon API
author:
    - Guillaume Watteeux
'''

EXAMPLES = '''
# Add service template
 - centreon_service_template:
     url: 'https://centreon.company.net/centreon'
     username: 'ansible_api'
     password: 'strong_pass_from_vault'
     name: "{{ ansible_fqdn }}"
     alias: "{{ ansible_servicename }}"
     parenttemplate: OS-Linux-SNMP-custom
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
            alias=dict(default=None),
            parenttemplate=dict(default=None),
            hosttemplates=dict(type='list', default=[]),
            hosttemplates_action=dict(default='add', choices=['add', 'set']),
            params=dict(type='list', default=[]),
            macros=dict(type='list', default=[]),
            state=dict(default='present', choices=['present', 'absent']),
            # NB: clapi does not support it, even though this operation is supported by the GUI
            # status=dict(default='enabled', choices=['enabled', 'disabled'])
        )
    )

    if not centreonapi_found:
        module.fail_json(msg="Python centreonapi module is required (>0.1.0)")

    url = module.params["url"]
    username = module.params["username"]
    password = module.params["password"]
    name = module.params["name"]
    alias = module.params["alias"]
    parenttemplate = module.params["parenttemplate"]
    hosttemplates = module.params["hosttemplates"]
    hosttemplates_action = module.params["hosttemplates_action"]
    params = module.params["params"]
    macros = module.params["macros"]
    state = module.params["state"]
    # status = module.params["status"]

    has_changed = False

    try:
        centreon = Centreon(url, username, password)
    except Exception as e:
        module.fail_json(
            msg="Unable to connect to Centreon API: %s" % e.message
        )

    data = list()

    st = None
    try:
        st = centreon.service_template.get(name)
    except requests.exceptions.HTTPError as e:
        data.append("Service template %s not found" % name)

    is_creation = False

    if st is None and state == "present":
        is_creation = True
        try:
            data.append("Add %s %s %s" %
                        (name, alias, parenttemplate))
            centreon.service_template.add(
                name,
                alias,
                parenttemplate
            )
            has_changed = True
            data.append("Add service template: %s" % name)
        except Exception as e:
            module.fail_json(msg='Create: %s - %s' % (e.message, data), changed=has_changed)

        try:
            st = centreon.service_template.get(name)
        except requests.exceptions.HTTPError as e:
            module.fail_json(msg='Failed to retrieve service template %s after creation: %s' % (name, e.message), changed=has_changed)

    if not st:
        module.fail_json(msg="Unable to find service template %s " % name, changed=has_changed)

    if state == "absent":
        try:
            centreon.service_template.delete(name)
            has_changed = True
            module.exit_json(
                changed=has_changed, result="Service %s deleted" % name
            )
        except requests.exceptions.HTTPError as e:
            module.fail_json(msg='Failed to delete service template: %s' % e.message, changed=has_changed)

    # if status == "disabled" and int(st.state) == 1:
    #     try:
    #         centreon.service_template.disable(name)
    #         has_changed = True
    #         data.append("Service disabled")
    #     except requests.exceptions.HTTPError as e:
    #         module.fail_json(msg='Unable to disable service template: %s' % e.message, changed=has_changed)

    # if status == "enabled" and int(st.state) == 0:
    #     try:
    #         centreon.service_template.enable(name)
    #         has_changed = True
    #         data.append("Service enabled")
    #     except requests.exceptions.HTTPError as e:
    #         module.fail_json(msg='Unable to enable service template: %s' % e.message, changed=has_changed)

    if not st.alias == alias and alias:
        try:
            centreon.service_template.setparam(name, 'alias', alias)
            has_changed = True
            data.append("Change alias: %s -> %s" % (st.alias, alias))
        except requests.exceptions.HTTPError as e:
            module.fail_json(msg='Unable to change alias: %s' % e.message, changed=has_changed)

    #### HostTemplates
    if hosttemplates:
        try:
            if hosttemplates_action == 'add':
                centreon.service_template.addhosttemplate(name, hosttemplates)
            else:
                centreon.service_template.sethosttemplate(name, hosttemplates)
            has_changed = True
            data.append("Add HostTemplate: %s" % hosttemplates)
        except requests.exceptions.HTTPError as e:
            module.fail_json(
                msg="Unable to add templates: %s" % e.message,
                changed=has_changed
            )

    #### Macros
    if macros:
        # try:
        #     getmacro_result = centreon.service_template.getmacro(name)
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
                centreon.service_template.setmacro(name, k.get('name').upper(), k.get('value'), k.get('description'))
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
                centreon.service_template.setparam(name, k.get('name'), k.get('value'))
                has_changed = True
            except requests.exceptions.HTTPError as e:
                module.fail_json(
                    msg='Unable to set param %s: %s' % (k.get('name'), e.message),
                    changed=has_changed
                )

    module.exit_json(changed=has_changed, msg=data)


if __name__ == '__main__':
    main()
