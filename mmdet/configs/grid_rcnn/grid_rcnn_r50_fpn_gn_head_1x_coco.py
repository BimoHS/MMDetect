if '_base_':
    from .grid_rcnn_r50_fpn_gn_head_2x_coco import *
from mmengine.optim.scheduler.lr_scheduler import LinearLR, MultiStepLR

# training schedule
max_epochs = 12
train_cfg.merge(dict(max_epochs=max_epochs))

# learning rate
param_scheduler = [
    dict(type=LinearLR, start_factor=0.0001, by_epoch=False, begin=0, end=500),
    dict(
        type=MultiStepLR,
        begin=0,
        end=max_epochs,
        by_epoch=True,
        milestones=[8, 11],
        gamma=0.1)
]
