if '_base_':
    from ..dcn.cascade_mask_rcnn_x101_32x4d_dconv_c3_c5_fpn_1x_coco import *

model.merge(
    dict(
        backbone=dict(
            norm_cfg=dict(type='SyncBN', requires_grad=True),
            norm_eval=False,
            plugins=[
                dict(
                    cfg=dict(type='ContextBlock', ratio=1. / 16),
                    stages=(False, True, True, True),
                    position='after_conv3')
            ])))
