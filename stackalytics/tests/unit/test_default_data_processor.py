# Copyright (c) 2013 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import copy

import mock
import testtools

from stackalytics.processor import default_data_processor
from stackalytics.processor import normalizer
from stackalytics.tests.unit import test_data


class TestDefaultDataProcessor(testtools.TestCase):
    def setUp(self):
        super(TestDefaultDataProcessor, self).setUp()

        self.get_users = mock.Mock(return_value=[
            test_data.USERS,
        ])

        normalized_data = copy.deepcopy(test_data.DEFAULT_DATA)
        normalizer.normalize_default_data(normalized_data)

    def tearDown(self):
        super(TestDefaultDataProcessor, self).tearDown()

    def test_normalizer(self):
        data = copy.deepcopy(test_data.DEFAULT_DATA)

        normalizer.normalize_default_data(data)

        self.assertIn('releases', data['repos'][0])
        self.assertEqual([], data['repos'][0]['releases'],
                         message='Empty list of releases expected')
        self.assertEqual(0, data['users'][0]['companies'][-1]['end_date'],
                         message='The last company end date should be 0')
        self.assertIn('user_id', data['users'][0])
        self.assertEqual(test_data.USERS[0]['launchpad_id'],
                         data['users'][0]['user_id'],
                         message='User id should be set')

        # verify that *independent company is added automatically
        self.assertEqual(3, len(data['users'][1]['companies']))
        self.assertEqual(0, data['users'][1]['companies'][-1]['end_date'],
                         message='The last company end date should be 0')

    def test_update_project_list(self):
        with mock.patch('stackalytics.processor.default_data_processor.'
                        '_retrieve_project_list_from_gerrit') as retriever:
            retriever.return_value = [
                {'module': 'nova',
                 'uri': 'git://git.openstack.org/openstack/nova',
                 'organization': 'openstack'},
                {'module': 'qa', 'uri': 'git://git.openstack.org/openstack/qa',
                 'has_gerrit': True,
                 'organization': 'openstack'},
            ]
            dd = {
                'repos': [
                    {'module': 'qa',
                     'uri': 'git://git.openstack.org/openstack/qa',
                     'organization': 'openstack'},
                    {'module': 'tux',
                     'uri': 'git://git.openstack.org/stackforge/tux',
                     'organization': 'stackforge'},
                ],
                'project_sources': [{'organization': 'openstack',
                                     'uri': 'gerrit://'}],
                'module_groups': [],
            }

            default_data_processor._update_project_list(dd)

            self.assertEqual(3, len(dd['repos']))
            self.assertIn('qa', set([r['module'] for r in dd['repos']]))
            self.assertIn('nova', set([r['module'] for r in dd['repos']]))
            self.assertIn('tux', set([r['module'] for r in dd['repos']]))

            self.assertIn('has_gerrit', dd['repos'][0])
            self.assertNotIn('has_gerrit', dd['repos'][1])
            self.assertNotIn('has_gerrit', dd['repos'][2])

            self.assertEqual(2, len(dd['module_groups']))
            self.assertIn({'id': 'openstack',
                           'module_group_name': 'openstack',
                           'modules': ['qa', 'nova'],
                           'tag': 'organization'}, dd['module_groups'])
            self.assertIn({'id': 'stackforge',
                           'module_group_name': 'stackforge',
                           'modules': ['tux'],
                           'tag': 'organization'}, dd['module_groups'])

    def test_update_project_list_ext_project_source(self):
        with mock.patch('stackalytics.processor.default_data_processor.'
                        '_retrieve_project_list_from_github') as retriever:
            retriever.return_value = [
                {'module': 'kubernetes',
                 'uri': 'git://github.com/kubernetes/kubernetes',
                 'organization': 'kubernetes'},
            ]
            dd = {
                'repos': [],
                'project_sources': [
                    {'organization': 'kubernetes',
                     'uri': 'github://',
                     'module_group_id': 'kubernetes-group'},
                ],
                'module_groups': [],
            }

            default_data_processor._update_project_list(dd)

            self.assertEqual(1, len(dd['repos']))
            self.assertIn('kubernetes',
                          set([r['module'] for r in dd['repos']]))

            self.assertEqual(1, len(dd['module_groups']))
            self.assertIn({'id': 'kubernetes-group',
                           'module_group_name': 'kubernetes',
                           'modules': ['kubernetes'],
                           'tag': 'organization'}, dd['module_groups'])

    @mock.patch('stackalytics.processor.utils.read_json_from_uri')
    def test_update_with_driverlog(self, mock_read_from_json):
        default_data = {'repos': [{'module': 'cinder', }], 'users': []}
        driverlog_dd = {'drivers': [{
            'project_id': 'openstack/cinder',
            'vendor': 'VMware',
            'name': 'VMware VMDK Driver',
            'ci': {
                'id': 'vmwareminesweeper',
                'success_pattern': 'Build successful',
                'failure_pattern': 'Build failed'
            }
        }]}
        mock_read_from_json.return_value = driverlog_dd

        default_data_processor._update_with_driverlog_data(default_data, 'uri')

        expected_user = {
            'user_id': 'ci:vmware_vmdk_driver',
            'user_name': 'VMware VMDK Driver',
            'static': True,
            'companies': [
                {'company_name': 'VMware', 'end_date': None}],
        }
        self.assertIn(expected_user, default_data['users'])
        self.assertIn(driverlog_dd['drivers'][0],
                      default_data['repos'][0]['drivers'])

    @mock.patch('stackalytics.processor.utils.read_json_from_uri')
    def test_update_with_driverlog_specific_repo(self, mock_read_from_json):
        default_data = {'repos': [{'module': 'fuel-plugin-mellanox', }],
                        'users': []}
        driverlog_dd = {'drivers': [{
            'project_id': 'openstack/fuel',
            'repo': 'stackforge/fuel-plugin-mellanox',
            'vendor': 'Mellanox',
            'name': 'ConnectX-3 Pro Network Adapter Support plugin',
            'ci': {
                'id': 'mellanox',
                'success_pattern': 'SUCCESS',
                'failure_pattern': 'FAILURE'
            }
        }]}
        mock_read_from_json.return_value = driverlog_dd

        default_data_processor._update_with_driverlog_data(default_data, 'uri')

        expected_user = {
            'user_id': 'ci:connectx_3_pro_network_adapter_support_plugin',
            'user_name': 'ConnectX-3 Pro Network Adapter Support plugin',
            'static': True,
            'companies': [
                {'company_name': 'Mellanox', 'end_date': None}],
        }
        self.assertIn(expected_user, default_data['users'])
        self.assertIn(driverlog_dd['drivers'][0],
                      default_data['repos'][0]['drivers'])
