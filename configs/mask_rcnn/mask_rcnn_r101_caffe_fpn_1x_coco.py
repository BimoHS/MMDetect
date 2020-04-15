_base_ = './mask_rcnn_r50_caffe_fpn_1x_coco.py'
model = dict(
    pretrained='open-mmlab://resnet101_caffe', backbone=dict(depth=101))
