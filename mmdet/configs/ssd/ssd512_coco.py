if '_base_':
    from .ssd300_coco import *
from mmdet.models.task_modules.prior_generators.anchor_generator import SSDAnchorGenerator
from mmcv.transforms.loading import LoadImageFromFile, LoadImageFromFile
from mmdet.datasets.transforms.loading import LoadAnnotations, LoadAnnotations
from mmdet.datasets.transforms.transforms import Expand, MinIoURandomCrop, Resize, RandomFlip, PhotoMetricDistortion, Resize
from mmdet.datasets.transforms.formatting import PackDetInputs, PackDetInputs

# model settings
input_size = 512
model.merge(
    dict(
        neck=dict(
            out_channels=(512, 1024, 512, 256, 256, 256, 256),
            level_strides=(2, 2, 2, 2, 1),
            level_paddings=(1, 1, 1, 1, 1),
            last_kernel_size=4),
        bbox_head=dict(
            in_channels=(512, 1024, 512, 256, 256, 256, 256),
            anchor_generator=dict(
                type=SSDAnchorGenerator,
                scale_major=False,
                input_size=input_size,
                basesize_ratio_range=(0.1, 0.9),
                strides=[8, 16, 32, 64, 128, 256, 512],
                ratios=[[2], [2, 3], [2, 3], [2, 3], [2, 3], [2], [2]]))))

# dataset settings
train_pipeline = [
    dict(type=LoadImageFromFile, backend_args=backend_args),
    dict(type=LoadAnnotations, with_bbox=True),
    dict(
        type=Expand,
        mean=model.data_preprocessor.mean,
        to_rgb=model.data_preprocessor.bgr_to_rgb,
        ratio_range=(1, 4)),
    dict(
        type=MinIoURandomCrop,
        min_ious=(0.1, 0.3, 0.5, 0.7, 0.9),
        min_crop_size=0.3),
    dict(type=Resize, scale=(input_size, input_size), keep_ratio=False),
    dict(type=RandomFlip, prob=0.5),
    dict(
        type=PhotoMetricDistortion,
        brightness_delta=32,
        contrast_range=(0.5, 1.5),
        saturation_range=(0.5, 1.5),
        hue_delta=18),
    dict(type=PackDetInputs)
]
test_pipeline = [
    dict(type=LoadImageFromFile, backend_args=backend_args),
    dict(type=Resize, scale=(input_size, input_size), keep_ratio=False),
    dict(type=LoadAnnotations, with_bbox=True),
    dict(
        type=PackDetInputs,
        meta_keys=('img_id', 'img_path', 'ori_shape', 'img_shape',
                   'scale_factor'))
]
train_dataloader.merge(
    dict(dataset=dict(dataset=dict(pipeline=train_pipeline))))
val_dataloader.merge(dict(dataset=dict(pipeline=test_pipeline)))
test_dataloader = val_dataloader

# NOTE: `auto_scale_lr` is for automatically scaling LR,
# USER SHOULD NOT CHANGE ITS VALUES.
# base_batch_size = (8 GPUs) x (8 samples per GPU)
auto_scale_lr.merge(dict(base_batch_size=64))
