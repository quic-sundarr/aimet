# /usr/bin/env python3.5
# -*- mode: python -*-
# =============================================================================
#  @@-COPYRIGHT-START-@@
#
#  Copyright (c) 2019, Qualcomm Innovation Center, Inc. All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#
#  1. Redistributions of source code must retain the above copyright notice,
#     this list of conditions and the following disclaimer.
#
#  2. Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions and the following disclaimer in the documentation
#     and/or other materials provided with the distribution.
#
#  3. Neither the name of the copyright holder nor the names of its contributors
#     may be used to endorse or promote products derived from this software
#     without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
#  ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
#  LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
#  CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
#  SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
#  INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
#  CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
#  ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
#  POSSIBILITY OF SUCH DAMAGE.
#
#  SPDX-License-Identifier: BSD-3-Clause
#
#  @@-COPYRIGHT-END-@@
# =============================================================================
""" This file contains unit tests for testing ConnectedGraph module for PyTorch. """

import unittest
import torch
from aimet_common.connected_graph.connectedgraph_utils import get_all_input_ops, get_all_output_ops
from aimet_torch.examples.test_models import SingleResidual, MultiInput, ConcatModel, ModuleListModel, ModelWithDropouts
from aimet_torch.meta.connectedgraph import _split_inputs, ConnectedGraph
from aimet_torch.utils import create_rand_tensors_given_shapes


class TestConnectedGraph(unittest.TestCase):
    """ Unit tests for testing ConnectedGraph module"""

    def test_split_inputs(self):
        """ Test split_inputs() utility"""
        named_groups = {}
        inputs = 'input2, weight0, _3, [1, 1], False, [0,0], 1'
        split = _split_inputs(inputs, named_groups)
        self.assertEqual(9, len(split))

        inputs = 'x1, [annotate(List[_3, _4], int), -1]'
        split = _split_inputs(inputs, named_groups)
        self.assertEqual('annotate(List[_3, _4], int)', split[1])
        self.assertEqual(3, len(split))

        with self.assertRaises(AssertionError):
            inputs = 'input2, weight0, _3)'
            _ = _split_inputs(inputs, named_groups)

        with self.assertRaises(AssertionError):
            inputs = 'input2, weight0, _3]'
            _ = _split_inputs(inputs, named_groups)

    def test_single_residual(self):
        """ Test building ConnectedGraph on single residual model """
        # pylint: disable=protected-access
        model = SingleResidual()
        model.eval()
        inp_shape = (1, 3, 32, 32)
        inp_tensor_list = create_rand_tensors_given_shapes(inp_shape)
        conn_graph = ConnectedGraph(model, inp_tensor_list)
        self.assertEqual(17, len(conn_graph.ordered_ops))
        # Split count of 2 due to residual as well as reshape having a split
        self.assertEqual(2, conn_graph._split_count)
        # All ops will include 2 inserted split ops
        self.assertEqual(19, len(conn_graph.get_all_ops().keys()))
        input_ops = get_all_input_ops(conn_graph)
        self.assertEqual(1, len(input_ops))
        self.assertEqual(model.conv1, input_ops[0].get_module())
        output_ops = get_all_output_ops(conn_graph)
        self.assertEqual(1, len(output_ops))
        self.assertEqual(model.fc, output_ops[0].get_module())

    def test_multi_input(self):
        """ Test building ConnectedGraph on a model with multiple inputs """
        # pylint: disable=protected-access
        model = MultiInput()
        model.eval()
        inp_shape_1 = (1, 3, 32, 32)
        inp_shape_2 = (1, 3, 20, 20)
        inp_tensor_list = create_rand_tensors_given_shapes([inp_shape_1, inp_shape_2])
        conn_graph = ConnectedGraph(model, inp_tensor_list)
        self.assertEqual(11, len(conn_graph.ordered_ops))
        # Split count of 2 due to residual as well as reshape having a split
        self.assertEqual(1, conn_graph._split_count)
        conv1 = conn_graph.get_op_from_module_name('MultiInput.conv1')
        self.assertEqual(model.conv1, conv1.get_module())
        self.assertEqual(2, len(conv1.inputs))
        conv2 = conn_graph.get_op_from_module_name('MultiInput.conv2')
        self.assertEqual(model.conv2, conv2.get_module())
        self.assertEqual(3, len(conv2.inputs))
        conv3 = conn_graph.get_op_from_module_name('MultiInput.conv3')
        self.assertEqual(model.conv3, conv3.get_module())
        self.assertEqual(3, len(conv3.inputs))

        input_ops = get_all_input_ops(conn_graph)
        input_modules = [op.get_module() for op in input_ops]
        self.assertEqual(2, len(input_ops))
        self.assertTrue(model.conv1 in input_modules)
        self.assertTrue(model.conv3 in input_modules)
        output_ops = get_all_output_ops(conn_graph)
        self.assertEqual(1, len(output_ops))
        self.assertEqual(model.fc, output_ops[0].get_module())

    def test_module_list(self):
        """ Test building ConnectedGraph on a model with module list """
        model = ModuleListModel()
        model.eval()
        inp_data_1 = torch.rand(1, 3, 8, 8)
        conn_graph = ConnectedGraph(model, (inp_data_1,))
        self.assertEqual(10, len(conn_graph.ordered_ops))
        self.assertEqual(conn_graph.get_op_from_module_name('ModuleListModel.mod_list.4'), conn_graph.ordered_ops[0])
        self.assertEqual(conn_graph.get_op_from_module_name('ModuleListModel.seq_list.2'), conn_graph.ordered_ops[1])
        self.assertEqual(conn_graph.get_op_from_module_name('ModuleListModel.mod_list.1'), conn_graph.ordered_ops[2])
        self.assertEqual(conn_graph.get_op_from_module_name('ModuleListModel.mod_list.0'), conn_graph.ordered_ops[3])
        self.assertEqual(conn_graph.get_op_from_module_name('ModuleListModel.mod_list.2'), conn_graph.ordered_ops[4])
        self.assertEqual(conn_graph.get_op_from_module_name('ModuleListModel.seq_list.0'), conn_graph.ordered_ops[5])

    def test_concat(self):
        """ Test building ConnectedGraph on a model with concat """
        model = ConcatModel()
        model.eval()
        inp_shape_1 = (1, 3, 8, 8)
        inp_shape_2 = (1, 3, 8, 8)
        inp_shape_3 = (1, 3, 8, 8)
        inp_tensor_list = create_rand_tensors_given_shapes([inp_shape_1, inp_shape_2, inp_shape_3])
        conn_graph = ConnectedGraph(model, inp_tensor_list)
        concat_op = conn_graph.get_all_ops()['cat_3']
        self.assertEqual(3, len(concat_op.inputs))
        self.assertEqual(14, concat_op.output_shape[1])

    def test_dropouts(self):
        """ Test building ConnectedGraph on a model with dropouts """
        # pylint: disable=protected-access
        model = ModelWithDropouts()
        model.eval()
        inp_shape = (1, 3, 32, 32)
        inp_tensor_list = create_rand_tensors_given_shapes(inp_shape)
        conn_graph = ConnectedGraph(model, inp_tensor_list)
        self.assertEqual(9, len(conn_graph.ordered_ops))
        # Split count of 2 due to residual as well as reshape having a split
        self.assertEqual(1, conn_graph._split_count)
        # All ops will include 2 inserted split ops
        self.assertEqual(10, len(conn_graph.get_all_ops().keys()))
        dropout_1_op = conn_graph.get_all_ops()['dropout_3']
        dropout_2_op = conn_graph.get_all_ops()['feature_dropout_4']
        self.assertEqual(model.dropout1, dropout_1_op.get_module())
        self.assertEqual(model.dropout2, dropout_2_op.get_module())

    def test_model_and_input_on_cpu_and_gpu(self):
        """ Test building the ConnectedGraph  for all possible combinations of the Model and the Input Tensor
        on CPU and GPU """

        # pylint: disable=protected-access
        model = SingleResidual()
        model.eval()

        inp_shape = (1, 3, 32, 32)
        inp_tensor_tuple_cpu = tuple(create_rand_tensors_given_shapes(inp_shape))

        # 1. Model and Input on CPU
        conn_graph = ConnectedGraph(model, inp_tensor_tuple_cpu)
        self.assertEqual(17, len(conn_graph.ordered_ops))

        # 2. Model on GPU, Input on CPU
        model.cuda()
        conn_graph = ConnectedGraph(model, inp_tensor_tuple_cpu)
        self.assertEqual(17, len(conn_graph.ordered_ops))

        # 3. Model on CPU, Input on GPU.
        model.cpu()
        inp_tensor_tuple_gpu = tuple([inp.cuda() for inp in inp_tensor_tuple_cpu])
        conn_graph = ConnectedGraph(model, inp_tensor_tuple_gpu)
        self.assertEqual(17, len(conn_graph.ordered_ops))

        # 4. Model and Input on GPU.
        model.cuda()
        conn_graph = ConnectedGraph(model, inp_tensor_tuple_gpu)
        self.assertEqual(17, len(conn_graph.ordered_ops))
