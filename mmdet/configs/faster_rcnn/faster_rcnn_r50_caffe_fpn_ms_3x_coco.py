if '_base_':
    from .faster_rcnn_r50_fpn_ms_3x_coco import *
from mmdet.models.data_preprocessors.data_preprocessor import DetDataPreprocessor

model.merge(
    dict(
        data_preprocessor=dict(
            type=DetDataPreprocessor,
            mean=[103.530, 116.280, 123.675],
            std=[1.0, 1.0, 1.0],
            bgr_to_rgb=False,
            pad_size_divisor=32),
        backbone=dict(
            norm_cfg=dict(requires_grad=False),
            norm_eval=True,
            style='caffe',
            init_cfg=dict(
                type='Pretrained',
                checkpoint='open-mmlab://detectron2/resnet50_caffe'))))
