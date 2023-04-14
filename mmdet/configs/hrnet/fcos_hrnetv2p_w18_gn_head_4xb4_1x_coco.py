if '_base_':
    from .fcos_hrnetv2p_w32_gn_head_4xb4_1x_coco import *
from mmdet.models.necks.hrfpn import HRFPN

model.merge(
    dict(
        backbone=dict(
            extra=dict(
                stage2=dict(num_channels=(18, 36)),
                stage3=dict(num_channels=(18, 36, 72)),
                stage4=dict(num_channels=(18, 36, 72, 144))),
            init_cfg=dict(
                type='Pretrained',
                checkpoint='open-mmlab://msra/hrnetv2_w18')),
        neck=dict(type=HRFPN, in_channels=[18, 36, 72, 144],
                  out_channels=256)))
