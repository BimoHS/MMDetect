if '_base_':
    from ..mask_rcnn.mask_rcnn_r50_fpn_1x_coco import *
from mmdet.models.roi_heads.bbox_heads.convfc_bbox_head import Shared4Conv1FCBBoxHead
from mmengine.optim.scheduler.lr_scheduler import LinearLR, MultiStepLR

norm_cfg = dict(type='GN', num_groups=32, requires_grad=True)
model.merge(
    dict(
        data_preprocessor=dict(
            mean=[103.530, 116.280, 123.675],
            std=[1.0, 1.0, 1.0],
            bgr_to_rgb=False),
        backbone=dict(
            norm_cfg=norm_cfg,
            init_cfg=dict(
                type='Pretrained',
                checkpoint='open-mmlab://detectron/resnet50_gn')),
        neck=dict(norm_cfg=norm_cfg),
        roi_head=dict(
            bbox_head=dict(
                type=Shared4Conv1FCBBoxHead,
                conv_out_channels=256,
                norm_cfg=norm_cfg),
            mask_head=dict(norm_cfg=norm_cfg))))

# learning policy
max_epochs = 24
train_cfg.merge(dict(max_epochs=max_epochs))

# learning rate
param_scheduler = [
    dict(type=LinearLR, start_factor=0.001, by_epoch=False, begin=0, end=500),
    dict(
        type=MultiStepLR,
        begin=0,
        end=max_epochs,
        by_epoch=True,
        milestones=[16, 22],
        gamma=0.1)
]
