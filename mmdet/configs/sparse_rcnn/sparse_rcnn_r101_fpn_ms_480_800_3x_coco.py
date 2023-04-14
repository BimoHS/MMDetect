if '_base_':
    from .sparse_rcnn_r50_fpn_ms_480_800_3x_coco import *

model.merge(
    dict(
        backbone=dict(
            depth=101,
            init_cfg=dict(
                type='Pretrained', checkpoint='torchvision://resnet101'))))
