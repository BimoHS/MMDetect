if '_base_':
    from .mask_rcnn_r50_fpn_gn_ws_all_2x_coco import *
from mmdet.models.backbones.resnext import ResNeXt
# model settings
conv_cfg.merge(dict(type='ConvWS'))
norm_cfg.merge(dict(type='GN', num_groups=32, requires_grad=True))
model.merge(
    dict(
        backbone=dict(
            type=ResNeXt,
            depth=50,
            groups=32,
            base_width=4,
            num_stages=4,
            out_indices=(0, 1, 2, 3),
            frozen_stages=1,
            style='pytorch',
            conv_cfg=conv_cfg,
            norm_cfg=norm_cfg,
            init_cfg=dict(
                type='Pretrained',
                checkpoint='open-mmlab://jhu/resnext50_32x4d_gn_ws'))))
