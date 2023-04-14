if '_base_':
    from ..faster_rcnn.faster_rcnn_r50_fpn_1x_coco import *
from mmdet.models.roi_heads.bbox_heads.convfc_bbox_head import Shared4Conv1FCBBoxHead

conv_cfg = dict(type='ConvWS')
norm_cfg = dict(type='GN', num_groups=32, requires_grad=True)
model.merge(
    dict(
        backbone=dict(
            conv_cfg=conv_cfg,
            norm_cfg=norm_cfg,
            init_cfg=dict(
                type='Pretrained',
                checkpoint='open-mmlab://jhu/resnet50_gn_ws')),
        neck=dict(conv_cfg=conv_cfg, norm_cfg=norm_cfg),
        roi_head=dict(
            bbox_head=dict(
                type=Shared4Conv1FCBBoxHead,
                conv_out_channels=256,
                conv_cfg=conv_cfg,
                norm_cfg=norm_cfg))))
