_base_ = './htc_r50_fpn_1x.py'
model = dict(pretrained='torchvision://resnet101', backbone=dict(depth=101))
# learning policy
lr_config = dict(step=[16, 19])
total_epochs = 20
work_dir = './work_dirs/htc_r101_fpn_20e'
