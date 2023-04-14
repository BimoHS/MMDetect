if '_base_':
    from .._base_.models.retinanet_r50_fpn import *
    from .._base_.datasets.coco_detection import *
    from .._base_.schedules.schedule_1x import *
    from .._base_.default_runtime import *
from torch.optim.adamw import AdamW

checkpoint = 'https://download.openmmlab.com/mmclassification/v0/resnet/resnet50_8xb256-rsb-a1-600e_in1k_20211228-20e21305.pth'  # noqa
model.merge(
    dict(
        backbone=dict(
            init_cfg=dict(
                type='Pretrained', prefix='backbone.',
                checkpoint=checkpoint))))

optim_wrapper.merge(
    dict(
        optimizer=dict(
            _delete_=True, type=AdamW, lr=0.0001, weight_decay=0.05),
        paramwise_cfg=dict(norm_decay_mult=0., bypass_duplicate=True)))
