# /usr/bin/env python3.5
# -*- mode: python -*-
# =============================================================================
#  @@-COPYRIGHT-START-@@
#
#  Copyright (c) 2017-2018, Qualcomm Innovation Center, Inc. All rights reserved.
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

import unittest.mock

import torch
import torchvision

from aimet_common.utils import round_up_to_multiplicity, round_down_to_multiplicity
from aimet_torch.utils import replace_modules_of_type1_with_type2, replace_modules_with_instances_of_new_type, \
    get_ordered_list_of_modules, get_ordered_list_of_conv_modules, get_reused_modules
from aimet_torch.defs import PassThroughOp
from aimet_torch.examples.test_models import ModelWithReusedNodes


class TestTrainingExtensionsUtils(unittest.TestCase):

    def test_round_up_to_higher_multiplicity(self):
        self.assertEqual(round_up_to_multiplicity(8, 3, 32), 8)
        self.assertEqual(round_up_to_multiplicity(8, 13, 32), 16)
        self.assertEqual(round_up_to_multiplicity(8, 17, 32), 24)
        self.assertEqual(round_up_to_multiplicity(8, 29, 32), 32)

    def test_round_down_to_lower_multiplicity(self):
        self.assertEqual(round_down_to_multiplicity(8, 3), 3)
        self.assertEqual(round_down_to_multiplicity(8, 13), 8)
        self.assertEqual(round_down_to_multiplicity(8, 17), 16)
        self.assertEqual(round_down_to_multiplicity(8, 29), 24)
        self.assertEqual(round_down_to_multiplicity(8, 16), 8)
        self.assertEqual(round_down_to_multiplicity(32, 64), 32)

    def test_replace_relu_with_relu6(self):
        model = torchvision.models.resnet18()
        model.eval()

        replace_modules_of_type1_with_type2(model, torch.nn.ReLU, torch.nn.ReLU6)

        # check - no ReLU modules left in the model anymore
        for module in model.modules():
            self.assertTrue(not isinstance(module, torch.nn.ReLU))

        # sanity-check: forward pass continues to work
        with torch.no_grad():
            x = torch.rand(1, 3, 224, 224)
            output = model(x)

    def test_replace_some_bns_with_passthrough(self):
        model = torchvision.models.resnet18()
        model.eval()

        replace_modules_with_instances_of_new_type(model, [model.layer1[0].bn1, model.layer1[1].bn1],
                                                   PassThroughOp)

        # check - given modules have been replaced
        self.assertTrue(isinstance(model.layer1[0].bn1, PassThroughOp))
        self.assertTrue(isinstance(model.layer1[1].bn1, PassThroughOp))

        # check - other bn layers have not been modified
        self.assertFalse(isinstance(model.layer1[0].bn2, PassThroughOp))
        self.assertFalse(isinstance(model.layer1[1].bn2, PassThroughOp))

        # sanity-check: forward pass continues to work
        with torch.no_grad():
            x = torch.rand(1, 3, 224, 224)
            output = model(x)

    def test_get_ordered_ops(self):
        model = torchvision.models.resnet18(pretrained=False)
        model.eval()

        all_ops = get_ordered_list_of_modules(model, (1, 3, 224, 224))
        conv_ops = get_ordered_list_of_conv_modules(model, (1, 3, 224, 224))

        self.assertEqual(60, len(all_ops))
        self.assertEqual(20, len(conv_ops))
        for _, module in conv_ops:
            self.assertTrue(isinstance(module, torch.nn.Conv2d))

    def test_get_reused_modules(self):
        """ Test get_reused_modules utility """
        model = ModelWithReusedNodes()
        inp_shape = (1, 3, 32, 32)
        reused_modules = get_reused_modules(model, inp_shape)
        self.assertEqual(1, len(reused_modules))
        self.assertEqual(reused_modules[0][1], model.relu1)
