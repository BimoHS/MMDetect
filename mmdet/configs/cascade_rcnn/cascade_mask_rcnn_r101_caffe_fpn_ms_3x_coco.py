if '_base_':
    from .cascade_mask_rcnn_r50_caffe_fpn_ms_3x_coco import *

model.merge(
    dict(
        backbone=dict(
            depth=101,
            init_cfg=dict(
                type='Pretrained',
                checkpoint='open-mmlab://detectron2/resnet101_caffe'))))
