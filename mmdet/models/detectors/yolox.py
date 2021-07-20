#!/usr/bin/env python
# Copyright (c) 2014-2021 Megvii Inc. All rights reserved.

from ..builder import DETECTORS
from .single_stage import SingleStageDetector


@DETECTORS.register_module()
class YOLOX(SingleStageDetector):
    """Implementation of `YOLOX <https://arxiv.org/abs/2107.08430>`_."""

    def __init__(self,
                 backbone,
                 neck,
                 bbox_head,
                 train_cfg=None,
                 test_cfg=None,
                 pretrained=None,
                 init_cfg=None):
        super(YOLOX, self).__init__(backbone, neck, bbox_head, train_cfg,
                                    test_cfg, pretrained, init_cfg)


# TODO
# def init_yolo(M):
#     for m in M.modules():
#         if isinstance(m, nn.BatchNorm2d):
#             m.eps = 1e-3
#             m.momentum = 0.03
# self.model.apply(init_yolo)
