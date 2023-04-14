if '_base_':
    from ..common.ms_3x_coco import *
    from .._base_.models.faster_rcnn_r50_fpn import *
from mmdet.models.backbones.regnet import RegNet
from mmdet.models.necks.fpn import FPN

model.merge(
    dict(
        data_preprocessor=dict(
            # The mean and std are used in PyCls when training RegNets
            mean=[103.53, 116.28, 123.675],
            std=[57.375, 57.12, 58.395],
            bgr_to_rgb=False),
        backbone=dict(
            _delete_=True,
            type=RegNet,
            arch='regnetx_3.2gf',
            out_indices=(0, 1, 2, 3),
            frozen_stages=1,
            norm_cfg=dict(type='BN', requires_grad=True),
            norm_eval=True,
            style='pytorch',
            init_cfg=dict(
                type='Pretrained', checkpoint='open-mmlab://regnetx_3.2gf')),
        neck=dict(
            type=FPN,
            in_channels=[96, 192, 432, 1008],
            out_channels=256,
            num_outs=5)))

optim_wrapper.merge(dict(optimizer=dict(weight_decay=0.00005)))
