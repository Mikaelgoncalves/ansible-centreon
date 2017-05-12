#!/usr/bin/python
# -*- coding: utf-8 -*-

ANSIBLE_METADATA = { 'status': ['preview'],
                     'supported_by': 'community',
                     'metadata_version': '0.1',
                     'version': '0.1'}

DOCUMENTATION = '''
---
module: centreon_hostgroup
version_added: "2.2"
short_description: Create or delete hostgroup

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
      - Hostgroup name (/ alias)
  state:
    description:
      - Create / Delete hostgroup
    default: present
    choices: ['present', 'absent']
requirements:
  - Python Centreon API
author:
    - Guillaume Watteeux
'''

EXAMPLES = '''
# Add host
- centreon_hostgroup:
    url: 'https://centreon.company.net/centreon'
    username: 'ansible_api'
    password: 'strong_pass_from_vault'
    name:
      Linux-Servers: Linux Server
    state: present
     
# Delete host
- centreon_hostgroup:
    url: 'https://centreon.company.net/centreon'
    username: 'ansible_api'
    password: 'strong_pass_from_vault'
    name:
      Linux-Serveur:
    state: absent
'''

# =============================================
# Centreon module API Rest
#

# import module snippets
from ansible.module_utils.basic import *

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
            name=dict(required=True, type='dict'),
            state=dict(default='present', choices=['present','absent']),
        )
    )

    if not centreonapi_found:
        module.fail_json(msg="Python centreonapi module is required")

    url = module.params["url"]
    username = module.params["username"]
    password = module.params["password"]
    name = module.params["name"]
    state = module.params["state"]

    has_changed = False

    try:
        centreon = Centreon(url, username, password)
    except Exception as exc:
        module.fail_json(msg="Unable to connect to Centreon API: %s" % exc.message)

    try:
        for hg in name.keys():
            if centreon.exists_hostgroups(hg):
                if state == "absent":
                    centreon.hostgroups.delete(hg)
                    has_changed = True
            else:
                if state == "present":
                    if name.get(hg) is None:
                        alias = hg
                    else:
                        alias = name.get(hg)
                    centreon.hostgroups.add(hg, alias)
                    has_changed = True

    except Exception as exc:
        module.fail_json(msg='%s' % exc.message)

    module.exit_json(changed=has_changed)


if __name__ == '__main__':
    main()


