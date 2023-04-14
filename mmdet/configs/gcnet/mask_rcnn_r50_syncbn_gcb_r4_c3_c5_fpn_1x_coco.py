if '_base_':
    from ..mask_rcnn.mask_rcnn_r50_fpn_1x_coco import *

model.merge(
    dict(
        backbone=dict(
            norm_cfg=dict(type='SyncBN', requires_grad=True),
            norm_eval=False,
            plugins=[
                dict(
                    cfg=dict(type='ContextBlock', ratio=1. / 4),
                    stages=(False, True, True, True),
                    position='after_conv3')
            ])))
