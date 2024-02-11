# Copyright (c) OpenMMLab. All rights reserved.
from mmengine.config import read_base
from mmengine.optim import AmpOptimWrapper
from torch.optim.sgd import SGD

from mmdet.models import BatchFixedSizePad

with read_base():
    from .._base_.models.faster_rcnn_r50_fpn import *
    from ..common.lsj_200e_coco_detection import *

image_size = (1024, 1024)
batch_augments = [dict(type=BatchFixedSizePad, size=image_size)]

model.update(dict(data_preprocessor=dict(batch_augments=batch_augments)))

train_dataloader.update(dict(batch_size=8, num_workers=4))
# Enable automatic-mixed-precision training with AmpOptimWrapper.
optim_wrapper.update(
    dict(
        type=AmpOptimWrapper,
        optimizer=dict(
            type=SGD, lr=0.02 * 4, momentum=0.9, weight_decay=0.00004)))

# NOTE: `auto_scale_lr` is for automatically scaling LR,
# USER SHOULD NOT CHANGE ITS VALUES.
# base_batch_size = (8 GPUs) x (8 samples per GPU)
auto_scale_lr.update(dict(base_batch_size=64))
